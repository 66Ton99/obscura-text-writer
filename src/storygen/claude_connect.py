"""STORE-MCP-001 S08–S11, S14–S16: connect Obscura's MCP bridge and skills to Claude Desktop and Claude Code, and
restart Claude Desktop.

Every function takes its folders and process operations as arguments, so tests never touch the real Claude. Only the entry
`mcpServers.obscura` of Claude Desktop's configuration is written; everything else in that file is kept as it was. Processes
run with fixed argv, never through a shell and never with text from a request.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal

from .skill_bundles import desktop_zip, skill_names, user_files

ALIAS = 'obscura-mcp.exe'
CHECKOUT_BRIDGE = 'storygen-mcp.exe'
ENTRY = 'obscura'
BACKUP_SUFFIX = '.obscura-backup'
CONFIG_NAME = 'claude_desktop_config.json'
TIMEOUT = 30
NO_WINDOW = 0x08000000 if sys.platform == 'win32' else 0
VERSION_MARKER = 'obscura-version.txt'
TEMP_MARK = '.obscura-temp'
MARKETPLACE = 'obscura'
PLUGIN = 'obscura@obscura'
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Roots:
    local_appdata: Path
    appdata: Path
    userprofile: Path

    @classmethod
    def current(cls) -> 'Roots':
        home = Path(os.environ.get('USERPROFILE') or Path.home())
        return cls(Path(os.environ.get('LOCALAPPDATA') or home / 'AppData' / 'Local'),
                   Path(os.environ.get('APPDATA') or home / 'AppData' / 'Roaming'), home)


@dataclass(frozen=True)
class DesktopConfig:
    path: Path
    variant: Literal['store', 'installer']
    package_family: str | None = None


class UnusableConfig(Exception):
    """Claude Desktop's configuration is not a JSON object with an object `mcpServers`: it is never rewritten."""

    def __init__(self, path: Path):
        super().__init__(str(path))
        self.path = path


def alias_path(roots: Roots) -> Path:
    return roots.local_appdata / 'Microsoft' / 'WindowsApps' / ALIAS


def bridge_command(roots: Roots, *, frozen: bool, executable: Path, data_dir: Path, default_data_dir: Path,
                   desktop_launched: bool, base_url: str) -> list[str]:
    """The command a chat client starts. The package alias never changes with updates; a checkout names its own bridge."""
    if frozen:
        alias = alias_path(roots)
        command = str(alias) if os.path.lexists(alias) else str(Path(executable).with_name(ALIAS))
        same = Path(data_dir).resolve() == Path(default_data_dir).resolve()
        return [command] if same else [command, '--data-dir', str(data_dir)]
    command = str(Path(executable).with_name(CHECKOUT_BRIDGE))
    return [command, '--data-dir', str(data_dir)] if desktop_launched else [command, '--url', base_url]


def claude_code_command(roots: Roots, command: list[str]) -> list[str]:
    # Claude Code starts the process without a shell; the alias folder is on PATH, so the bare name survives updates.
    return [ALIAS, *command[1:]] if command and Path(command[0]) == alias_path(roots) else list(command)


def find_desktop_config(roots: Roots) -> DesktopConfig | None:
    """Store Claude first, then the installer; both installed — the newer existing file; a missing file is `None`."""
    packages = sorted((roots.local_appdata / 'Packages').glob('Claude_*'))
    family = packages[0].name if packages else None
    store = sorted(path for path in (roots.local_appdata / 'Claude-Data').glob(f'claude_*/{CONFIG_NAME}') if path.is_file())
    installer = roots.appdata / 'Claude' / CONFIG_NAME
    candidates = []
    if family and store:
        candidates += [DesktopConfig(path, 'store', family) for path in store]
    if (roots.local_appdata / 'AnthropicClaude').is_dir() and installer.is_file():
        candidates.append(DesktopConfig(installer, 'installer'))
    if not candidates:
        # Neither variant is recognisably installed: an existing file still says where Claude reads its servers.
        candidates = [DesktopConfig(path, 'store', family) for path in store]
        if installer.is_file():
            candidates.append(DesktopConfig(installer, 'installer'))
    return max(candidates, key=lambda found: found.path.stat().st_mtime_ns) if candidates else None


def desktop_entry(command: list[str]) -> dict:
    return {'command': command[0], 'args': list(command[1:])} if len(command) > 1 else {'command': command[0]}


def _read_config(path: Path) -> dict:
    raw = path.read_bytes()
    if raw.startswith(b'\xef\xbb\xbf'):
        raise UnusableConfig(path)
    try:
        data = json.loads(raw.decode('utf-8'))
    except (UnicodeDecodeError, ValueError):
        raise UnusableConfig(path) from None
    if not isinstance(data, dict) or not isinstance(data.get('mcpServers', {}), dict):
        raise UnusableConfig(path)
    return data


def write_desktop_entry(config: Path, command: list[str]) -> Literal['added', 'updated', 'unchanged']:
    """Add or update `mcpServers.obscura`, keeping every other key and its order; copy the file first."""
    data = _read_config(config)
    servers = data.get('mcpServers', {})
    entry = desktop_entry(command)
    if servers.get(ENTRY) == entry:
        return 'unchanged'
    result = 'updated' if ENTRY in servers else 'added'
    servers[ENTRY] = entry
    data['mcpServers'] = servers
    shutil.copyfile(config, config.with_name(config.name + BACKUP_SUFFIX))
    temporary = config.with_name(config.name + '.obscura-tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    os.replace(temporary, config)
    if _read_config(config).get('mcpServers', {}).get(ENTRY) != entry:
        raise UnusableConfig(config)
    return result


def build_mcpb(target: Path, command: list[str], launcher: Path, version: str) -> Path:
    """The fallback extension (manifest 0.3, probe 5): Claude starts `command`; the bundled launcher is only its entry point."""
    manifest = {
        'manifest_version': '0.3', 'name': ENTRY, 'display_name': 'Obscura', 'version': version,
        'description': 'Obscura — local story editor / локальний редактор історій.', 'author': {'name': 'Obscura'},
        'server': {'type': 'binary', 'entry_point': f'server/{ALIAS}',
                   'mcp_config': {'command': command[0], 'args': list(command[1:])}},
        'compatibility': {'platforms': ['win32']},
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + '.tmp')
    with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2))
        bundle.write(launcher, f'server/{ALIAS}')
    os.replace(temporary, target)
    return target


def find_claude_code(roots: Roots, which: Callable[[str], str | None] = shutil.which) -> Path | None:
    found = which('claude')
    if found:
        return Path(found)
    local = roots.userprofile / '.local' / 'bin' / 'claude.exe'
    return local if local.is_file() else None


def _run(run, argv: list[str]):
    try:
        return run(argv, capture_output=True, timeout=TIMEOUT, creationflags=NO_WINDOW)
    except (OSError, subprocess.TimeoutExpired):
        return None


def claude_code_registered(claude: Path, command: list[str], run=subprocess.run) -> bool:
    got = _run(run, [str(claude), 'mcp', 'get', ENTRY])
    return got is not None and got.returncode == 0 and command[0] in (got.stdout or b'').decode('utf-8', 'replace')


def connect_claude_code(claude: Path, command: list[str], run=subprocess.run) -> bool:
    """`claude mcp add` for the user scope (an old entry is removed first) and `claude mcp get` as the proof."""
    _run(run, [str(claude), 'mcp', 'remove', '--scope', 'user', ENTRY])
    added = _run(run, [str(claude), 'mcp', 'add', '--scope', 'user', ENTRY, '--', *command])
    if added is None or added.returncode:
        return False
    return claude_code_registered(claude, command, run)


def _is_desktop(path: Path, roots: Roots) -> bool:
    # Claude Code ships the same image name, so only paths inside a Claude Desktop install count.
    parts = [part.lower() for part in Path(path).parts]
    if 'windowsapps' in parts and any(part.startswith('claude_') and '__' in part for part in parts):
        return True
    try:
        Path(path).resolve().relative_to((roots.local_appdata / 'AnthropicClaude').resolve())
        return True
    except ValueError:
        return False


def running_claude() -> list[tuple[int, Path]]:
    script = ("Get-CimInstance Win32_Process -Filter \"Name='claude.exe'\" | "
              "ForEach-Object { \"$($_.ProcessId)`t$($_.ExecutablePath)\" }")
    answered = _run(subprocess.run, ['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script])
    found = []
    for line in (answered.stdout.decode('utf-8', 'replace') if answered else '').splitlines():
        pid, _, path = line.partition('\t')
        if pid.strip().isdigit() and path.strip():
            found.append((int(pid), Path(path.strip())))
    return found


def store_app_id(family: str) -> str | None:
    name = family.split('_')[0]
    script = f"(Get-AppxPackage -Name '{name}' | Get-AppxPackageManifest).Package.Applications.Application.Id"
    answered = _run(subprocess.run, ['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script])
    value = answered.stdout.decode('utf-8', 'replace').strip().splitlines() if answered and answered.returncode == 0 else []
    return value[0].strip() if value and value[0].strip().replace('.', '').isalnum() else None


def _stop(pid: int) -> None:
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        pass


def _start(argv: list[str]) -> None:
    subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     close_fds=True, creationflags=NO_WINDOW)


def restart_desktop(config: DesktopConfig, roots: Roots, *, list_processes=running_claude, stop=_stop, start=_start,
                    sleep=time.sleep, app_id=store_app_id) -> bool:
    """Close Claude Desktop (never Claude Code) and start it again; `False` when there is nothing to start it with."""
    for pid, path in list_processes():
        if _is_desktop(path, roots):
            stop(pid)
    for _ in range(20):
        if not any(_is_desktop(path, roots) for _, path in list_processes()):
            break
        sleep(0.5)
    if config.variant == 'installer':
        exe = roots.local_appdata / 'AnthropicClaude' / 'claude.exe'
        argv = [str(exe)] if exe.is_file() else None
    else:
        alias = roots.local_appdata / 'Microsoft' / 'WindowsApps' / 'claude-desktop.exe'
        if os.path.lexists(alias):
            argv = [str(alias)]
        else:
            application = app_id(config.package_family) if config.package_family else None
            argv = ['explorer.exe', f'shell:AppsFolder\\{config.package_family}!{application}'] if application else None
    if argv is None:
        return False
    start(argv)
    return True


# --- skills: the stable marketplace copy and the plugin in Claude Code (S14, S15) ----------------------------------

class MarketplaceConflict(Exception):
    """The marketplace folder exists without Obscura's version marker: it is someone else's and is never replaced."""

    def __init__(self, path: Path):
        super().__init__(str(path))
        self.path = path


def marketplace_target(data_dir: Path) -> Path:
    return Path(data_dir) / 'claude' / 'marketplace'


def _rename(source: Path, target: Path, attempts: int = 10) -> None:
    # Windows: an antivirus, the indexer or a reading Claude Code may hold the files for a moment.
    for attempt in range(attempts):
        try:
            os.replace(source, target)
            return
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(0.2)


_SYNC_LOCK = threading.Lock()


def _recover(target: Path) -> None:
    """Undo a swap that stopped halfway (crash, power loss, failed rollback): put our old copy back, drop temp folders."""
    if not target.parent.is_dir():
        return
    old = target.with_name(target.name + '.old')
    if old.exists() and not (old / VERSION_MARKER).is_file():
        raise MarketplaceConflict(old)  # not our backup: never removed or renamed
    if not target.exists() and old.exists():
        _rename(old, target)
    for stale in target.parent.glob('.marketplace-*'):
        # Only folders this module created: they carry TEMP_MARK until the final rename.
        if (stale / TEMP_MARK).is_file():
            shutil.rmtree(stale, ignore_errors=True)


def sync_marketplace(source: Path, target: Path, version: str) -> Literal['created', 'updated', 'unchanged']:
    """Copy the user files of the marketplace to `target` as a whole; the old copy survives any failure."""
    with _SYNC_LOCK:
        _recover(target)
        return _sync(source, target, version)


def _sync(source: Path, target: Path, version: str) -> Literal['created', 'updated', 'unchanged']:
    marker = target / VERSION_MARKER
    exists = target.exists()
    if exists and not marker.is_file():
        raise MarketplaceConflict(target)
    files = user_files(source)
    if exists and marker.read_text(encoding='utf-8') == version and all((target / name).is_file() for name in files):
        return 'unchanged'
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(dir=target.parent, prefix='.marketplace-'))
    old = target.with_name(target.name + '.old')
    try:
        (temporary / TEMP_MARK).write_text('', encoding='utf-8')
        for name in files:
            (temporary / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source / name, temporary / name)
        (temporary / VERSION_MARKER).write_text(version, encoding='utf-8')
        (temporary / TEMP_MARK).unlink()
        if exists:
            if old.exists():
                shutil.rmtree(old)
            _rename(target, old)
        try:
            _rename(temporary, target)
        except OSError:
            if exists:
                try:
                    _rename(old, target)
                except OSError:
                    # The original error matters more; the next sync puts `old` back (_recover).
                    logger.warning('Скіли Claude: стару копію не повернуто, її відновить наступна синхронізація: %s', old)
            raise
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    if exists:
        shutil.rmtree(old, ignore_errors=True)
    return 'updated' if exists else 'created'


def refresh_marketplace(source: Path | None, target: Path, version: str, log: logging.Logger = logger) -> None:
    """At launch: refresh a copy the author already connected; never create one, never call `claude`."""
    if source is None:
        return
    try:
        with _SYNC_LOCK:
            _recover(target)
            if not target.exists():
                return
            result = _sync(source, target, version)
    except MarketplaceConflict as error:
        log.warning('Скіли Claude: тека marketplace без позначки Obscura, не змінено: %s', error.path)
    except OSError as error:
        log.warning('Скіли Claude: копію marketplace не оновлено (%s): %s', type(error).__name__, error)
    else:
        if result != 'unchanged':
            log.info('Скіли Claude: копію marketplace оновлено до %s', version)


def _same_path(a: str, b: Path) -> bool:
    try:
        return os.path.normcase(str(Path(a).resolve())) == os.path.normcase(str(Path(b).resolve()))
    except (OSError, ValueError):
        return False


def connect_claude_plugin(claude: Path, target: Path, run=subprocess.run) -> bool:
    """Register `target` as the user's `obscura` marketplace and install the plugin; any doubt is `False`."""
    base = [str(claude), 'plugin']
    listed = _run(run, base + ['marketplace', 'list', '--json'])
    if listed is None or listed.returncode:
        return False
    try:
        entries = json.loads((listed.stdout or b'').decode('utf-8', 'replace'))
    except ValueError:
        return False
    if not isinstance(entries, list):
        return False
    ours = next((entry for entry in entries if isinstance(entry, dict) and entry.get('name') == MARKETPLACE), None)
    if ours is None or not _same_path(str(ours.get('path') or ''), target):
        if ours is not None:
            removed = _run(run, base + ['marketplace', 'remove', MARKETPLACE])
            if removed is None or removed.returncode:
                return False
        added = _run(run, base + ['marketplace', 'add', str(target), '--scope', 'user'])
        if added is None or added.returncode:
            return False
    installed = _run(run, base + ['install', PLUGIN, '--scope', 'user'])
    return installed is not None and installed.returncode == 0


def _check_zip(path: Path, skill: str) -> None:
    """Read the written archive back: it must open, pass CRC checks and hold the skill's SKILL.md."""
    try:
        with zipfile.ZipFile(path) as archive:
            if archive.testzip() is not None or f'{skill}/SKILL.md' not in archive.namelist():
                raise OSError(f'ZIP скіла {skill} пошкоджено: {path}')
    except zipfile.BadZipFile as error:
        raise OSError(f'ZIP скіла {skill} пошкоджено: {path}') from error


def write_desktop_skills(plugin: Path, folder: Path) -> list[Path]:
    """S16: one `<skill>.zip` per skill for upload in Claude Desktop; only these files are overwritten."""
    folder.mkdir(parents=True, exist_ok=True)
    written = []
    for skill in skill_names(plugin):
        target = folder / f'{skill}.zip'
        handle, name = tempfile.mkstemp(dir=folder, prefix=f'.{skill}-', suffix='.zip.obscura-tmp')
        temporary = Path(name)
        try:
            with os.fdopen(handle, 'wb') as stream:
                stream.write(desktop_zip(plugin, skill))
            _check_zip(temporary, skill)
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
        written.append(target)
    return written


def plugin_commands(target: Path) -> list[str]:
    return [f'claude plugin marketplace add "{target}" --scope user', f'claude plugin install {PLUGIN} --scope user']
