"""STORE-MCP-001 S08–S11: connect Obscura's MCP bridge to Claude Desktop and Claude Code, and restart Claude Desktop.

Every function takes its folders and process operations as arguments, so tests never touch the real Claude. Only the entry
`mcpServers.obscura` of Claude Desktop's configuration is written; everything else in that file is kept as it was. Processes
run with fixed argv, never through a shell and never with text from a request.
"""
from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal

ALIAS = 'obscura-mcp.exe'
CHECKOUT_BRIDGE = 'storygen-mcp.exe'
ENTRY = 'obscura'
BACKUP_SUFFIX = '.obscura-backup'
CONFIG_NAME = 'claude_desktop_config.json'
TIMEOUT = 30
NO_WINDOW = 0x08000000 if sys.platform == 'win32' else 0


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
        candidates.append(DesktopConfig(store[0], 'store', family))
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
