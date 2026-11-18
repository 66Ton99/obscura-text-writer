"""STORE-MCP-001 S08–S11: connecting Claude Desktop and Claude Code, the .mcpb fallback and restarting Claude Desktop."""
import json
import os
import subprocess
import zipfile
from pathlib import Path

import pytest

from storygen import claude_connect as cc


@pytest.fixture
def roots(tmp_path):
    made = cc.Roots(local_appdata=tmp_path / 'Local', appdata=tmp_path / 'Roaming', userprofile=tmp_path / 'home')
    for folder in (made.local_appdata, made.appdata, made.userprofile):
        folder.mkdir()
    return made


def store_claude(roots, content='{}'):
    (roots.local_appdata / 'Packages' / 'Claude_abc123').mkdir(parents=True)
    config = roots.local_appdata / 'Claude-Data' / 'claude_abc123' / 'claude_desktop_config.json'
    config.parent.mkdir(parents=True)
    config.write_text(content, encoding='utf-8')
    return config


def installer_claude(roots, content='{}'):
    (roots.local_appdata / 'AnthropicClaude').mkdir()
    config = roots.appdata / 'Claude' / 'claude_desktop_config.json'
    config.parent.mkdir(parents=True)
    config.write_text(content, encoding='utf-8')
    return config


def command_for(roots, tmp_path, **changes):
    values = dict(frozen=True, executable=tmp_path / 'app' / 'Obscura.exe', data_dir=tmp_path / 'Obscura',
                  default_data_dir=tmp_path / 'Obscura', desktop_launched=True, base_url='http://127.0.0.1:8765')
    values.update(changes)
    return cc.bridge_command(roots, **values)


# --- the bridge command -------------------------------------------------------------------------------------------

@pytest.mark.req('STORE-MCP-001')
def test_command_for_package_is_the_alias(roots, tmp_path):
    alias = roots.local_appdata / 'Microsoft' / 'WindowsApps' / 'obscura-mcp.exe'
    alias.parent.mkdir(parents=True)
    alias.write_bytes(b'')
    assert command_for(roots, tmp_path) == [str(alias)]
    alias.unlink()
    assert command_for(roots, tmp_path) == [str(tmp_path / 'app' / 'obscura-mcp.exe')]
    assert command_for(roots, tmp_path, data_dir=tmp_path / 'Other')[1:] == ['--data-dir', str(tmp_path / 'Other')]


@pytest.mark.req('STORE-MCP-001')
def test_command_for_checkout_server_is_the_url(roots, tmp_path):
    scripts = tmp_path / 'venv' / 'Scripts'
    command = command_for(roots, tmp_path, frozen=False, executable=scripts / 'python.exe', desktop_launched=False,
                          base_url='http://127.0.0.1:8771')
    assert command == [str(scripts / 'storygen-mcp.exe'), '--url', 'http://127.0.0.1:8771']


@pytest.mark.req('STORE-MCP-001')
def test_command_for_desktop_launcher_passes_the_folder(roots, tmp_path):
    scripts = tmp_path / 'venv' / 'Scripts'
    command = command_for(roots, tmp_path, frozen=False, executable=scripts / 'python.exe')
    assert command == [str(scripts / 'storygen-mcp.exe'), '--data-dir', str(tmp_path / 'Obscura')]


@pytest.mark.req('STORE-MCP-001')
def test_claude_code_gets_the_alias_by_name(roots):
    alias = str(roots.local_appdata / 'Microsoft' / 'WindowsApps' / 'obscura-mcp.exe')
    assert cc.claude_code_command(roots, [alias]) == ['obscura-mcp.exe']
    assert cc.claude_code_command(roots, ['C:/x/storygen-mcp.exe', '--url', 'u']) == ['C:/x/storygen-mcp.exe', '--url', 'u']


# --- finding the Claude Desktop configuration -----------------------------------------------------------------------

@pytest.mark.req('STORE-MCP-001')
def test_store_config_is_found_by_package(roots):
    config = store_claude(roots)
    found = cc.find_desktop_config(roots)
    assert found == cc.DesktopConfig(config, 'store', 'Claude_abc123')


@pytest.mark.req('STORE-MCP-001')
def test_store_and_installer_prefer_the_existing_newer_file(roots):
    store, installer = store_claude(roots), installer_claude(roots)
    os.utime(store, (1_000_000, 1_000_000))
    assert cc.find_desktop_config(roots).path == installer
    os.utime(installer, (500_000, 500_000))
    assert cc.find_desktop_config(roots).path == store
    store.unlink()
    assert cc.find_desktop_config(roots).path == installer


@pytest.mark.req('STORE-MCP-001')
def test_several_store_profiles_pick_the_newest(roots):
    newest = store_claude(roots)
    older = roots.local_appdata / 'Claude-Data' / 'claude_000old' / 'claude_desktop_config.json'
    older.parent.mkdir(parents=True)
    older.write_text('{}', encoding='utf-8')
    os.utime(older, (1_000_000, 1_000_000))
    assert cc.find_desktop_config(roots).path == newest


@pytest.mark.req('STORE-MCP-001')
def test_missing_config_is_none(roots):
    (roots.local_appdata / 'Packages' / 'Claude_abc123').mkdir(parents=True)
    assert cc.find_desktop_config(roots) is None


# --- writing the entry ----------------------------------------------------------------------------------------------

@pytest.mark.req('STORE-MCP-001')
def test_entry_is_added_beside_other_keys_in_order(roots):
    before = '{"preferences": {"a": 1}, "mcpServers": {"other": {"command": "x.exe"}}, "z": "ї"}'
    config = store_claude(roots, before)
    assert cc.write_desktop_entry(config, ['C:/a/obscura-mcp.exe']) == 'added'
    data = json.loads(config.read_text(encoding='utf-8'))
    assert list(data) == ['preferences', 'mcpServers', 'z'] and data['z'] == 'ї'
    assert data['mcpServers'] == {'other': {'command': 'x.exe'}, 'obscura': {'command': 'C:/a/obscura-mcp.exe'}}
    assert config.with_name('claude_desktop_config.json.obscura-backup').read_text(encoding='utf-8') == before


@pytest.mark.req('STORE-MCP-001')
def test_existing_entry_is_updated_or_left_unchanged(roots):
    config = store_claude(roots, '{"mcpServers": {"obscura": {"command": "old.exe"}}}')
    assert cc.write_desktop_entry(config, ['new.exe', '--data-dir', 'D:/s']) == 'updated'
    assert json.loads(config.read_text(encoding='utf-8'))['mcpServers']['obscura'] == {'command': 'new.exe', 'args': ['--data-dir', 'D:/s']}
    backup = config.with_name('claude_desktop_config.json.obscura-backup')
    backup.unlink()
    stamp = config.stat().st_mtime_ns
    assert cc.write_desktop_entry(config, ['new.exe', '--data-dir', 'D:/s']) == 'unchanged'
    assert config.stat().st_mtime_ns == stamp and not backup.exists()


@pytest.mark.req('STORE-MCP-001')
@pytest.mark.parametrize('content', ['{"mcpServers": ', '\ufeff{}', '{"mcpServers": []}', '[]', '', '{"a": 1} // note'])
def test_unusable_config_is_left_untouched(roots, content):
    config = store_claude(roots, content)
    before, stamp = config.read_bytes(), config.stat().st_mtime_ns
    with pytest.raises(cc.UnusableConfig) as raised:
        cc.write_desktop_entry(config, ['obscura-mcp.exe'])
    assert raised.value.path == config and config.read_bytes() == before and config.stat().st_mtime_ns == stamp
    assert not config.with_name('claude_desktop_config.json.obscura-backup').exists()


# --- the .mcpb fallback ---------------------------------------------------------------------------------------------

@pytest.mark.req('STORE-MCP-001')
def test_mcpb_manifest_and_files(tmp_path):
    launcher = tmp_path / 'obscura-mcp.exe'
    launcher.write_bytes(b'MZ launcher')
    target = cc.build_mcpb(tmp_path / 'claude' / 'obscura.mcpb', ['C:/a/obscura-mcp.exe'], launcher, '1.0.0')
    with zipfile.ZipFile(target) as bundle:
        manifest = json.loads(bundle.read('manifest.json'))
        assert bundle.read('server/obscura-mcp.exe') == b'MZ launcher'
    assert manifest['manifest_version'] == '0.3' and manifest['name'] == 'obscura' and manifest['version'] == '1.0.0'
    assert manifest['server'] == {'type': 'binary', 'entry_point': 'server/obscura-mcp.exe',
                                  'mcp_config': {'command': 'C:/a/obscura-mcp.exe', 'args': []}}
    assert manifest['compatibility'] == {'platforms': ['win32']}


# --- Claude Code ----------------------------------------------------------------------------------------------------

class Runner:
    def __init__(self, get_output='obscura: obscura-mcp.exe', add_code=0):
        self.calls, self.get_output, self.add_code = [], get_output, add_code

    def __call__(self, argv, **kwargs):
        assert not kwargs.get('shell') and kwargs.get('timeout')
        self.calls.append(argv)
        code = self.add_code if argv[2] == 'add' else 0
        return subprocess.CompletedProcess(argv, code, self.get_output.encode() if argv[2] == 'get' else b'', b'')


@pytest.mark.req('STORE-MCP-001')
def test_claude_code_sequence_and_check(tmp_path):
    claude, run = tmp_path / 'claude.exe', Runner()
    assert cc.connect_claude_code(claude, ['obscura-mcp.exe'], run=run) is True
    base = [str(claude), 'mcp']
    assert run.calls == [base + ['remove', '--scope', 'user', 'obscura'],
                         base + ['add', '--scope', 'user', 'obscura', '--', 'obscura-mcp.exe'], base + ['get', 'obscura']]
    assert cc.connect_claude_code(claude, ['obscura-mcp.exe'], run=Runner(get_output='obscura: other.exe')) is False
    assert cc.connect_claude_code(claude, ['obscura-mcp.exe'], run=Runner(add_code=1)) is False


@pytest.mark.req('STORE-MCP-001')
def test_claude_code_is_found_or_none(roots):
    assert cc.find_claude_code(roots, which=lambda name: None) is None
    local = roots.userprofile / '.local' / 'bin' / 'claude.exe'
    local.parent.mkdir(parents=True)
    local.write_bytes(b'')
    assert cc.find_claude_code(roots, which=lambda name: None) == local
    assert cc.find_claude_code(roots, which=lambda name: 'C:/tools/claude.exe') == Path('C:/tools/claude.exe')


# --- restarting Claude Desktop --------------------------------------------------------------------------------------

@pytest.mark.req('STORE-MCP-001')
def test_restart_never_touches_claude_code(roots):
    code = roots.userprofile / '.local' / 'bin' / 'claude.exe'
    desktop = Path('C:/Program Files/WindowsApps/Claude_1.2.3.0_x64__abc123/app/claude.exe')
    alias = roots.local_appdata / 'Microsoft' / 'WindowsApps' / 'claude-desktop.exe'
    alias.parent.mkdir(parents=True)
    alias.write_bytes(b'')
    running = [(11, code), (12, desktop), (13, desktop)]
    stopped, started = [], []

    def listing():
        return [item for item in running if item[0] not in stopped]
    config = cc.DesktopConfig(Path('c.json'), 'store', 'Claude_abc123')
    assert cc.restart_desktop(config, roots, list_processes=listing, stop=stopped.append, start=started.append,
                              sleep=lambda seconds: None) is True
    assert stopped == [12, 13] and started == [[str(alias)]]


@pytest.mark.req('STORE-MCP-001')
def test_restart_store_falls_back_to_apps_folder(roots):
    config = cc.DesktopConfig(Path('c.json'), 'store', 'Claude_abc123')
    started = []
    assert cc.restart_desktop(config, roots, list_processes=lambda: [], stop=lambda pid: None, start=started.append,
                              sleep=lambda seconds: None, app_id=lambda family: 'ClaudeApp') is True
    assert started == [['explorer.exe', 'shell:AppsFolder\\Claude_abc123!ClaudeApp']]
    assert cc.restart_desktop(config, roots, list_processes=lambda: [], stop=lambda pid: None, start=started.append,
                              sleep=lambda seconds: None, app_id=lambda family: None) is False


@pytest.mark.req('STORE-MCP-001')
def test_restart_installer_runs_its_exe(roots):
    exe = roots.local_appdata / 'AnthropicClaude' / 'claude.exe'
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b'')
    stopped, started = [], []
    config = cc.DesktopConfig(Path('c.json'), 'installer', None)
    cc.restart_desktop(config, roots, list_processes=lambda: [(21, exe)] if not stopped else [], stop=stopped.append,
                       start=started.append, sleep=lambda seconds: None)
    assert stopped == [21] and started == [[str(exe)]]


# --- the stable marketplace copy and the plugin in Claude Code --------------------------------------------------------

MARKET = Path(__file__).resolve().parents[1] / 'integrations' / 'claude'


def copied_files(target):
    return sorted(path.relative_to(target).as_posix() for path in target.rglob('*') if path.is_file())


@pytest.mark.req('STORE-MCP-001')
def test_sync_creates_copy_with_marker(tmp_path):
    from storygen.skill_bundles import user_files
    target = tmp_path / 'data' / 'claude' / 'marketplace'
    assert cc.sync_marketplace(MARKET, target, '0.1.0') == 'created'
    assert copied_files(target) == sorted(user_files(MARKET) + [cc.VERSION_MARKER])
    assert (target / cc.VERSION_MARKER).read_text(encoding='utf-8') == '0.1.0'
    assert cc.sync_marketplace(MARKET, target, '0.1.0') == 'unchanged'
    (target / 'obscura' / 'stale.md').write_text('old', encoding='utf-8')
    assert cc.sync_marketplace(MARKET, target, '0.2.0') == 'updated'
    assert not (target / 'obscura' / 'stale.md').exists()
    assert (target / cc.VERSION_MARKER).read_text(encoding='utf-8') == '0.2.0'
    assert [p.name for p in target.parent.iterdir()] == ['marketplace']


@pytest.mark.req('STORE-MCP-001')
def test_sync_refuses_foreign_folder(tmp_path):
    target = tmp_path / 'claude' / 'marketplace'
    target.mkdir(parents=True)
    (target / 'notes.txt').write_text('mine', encoding='utf-8')
    with pytest.raises(cc.MarketplaceConflict) as raised:
        cc.sync_marketplace(MARKET, target, '0.1.0')
    assert raised.value.path == target
    assert copied_files(target) == ['notes.txt']


@pytest.mark.req('STORE-MCP-001')
def test_sync_failure_keeps_old_copy(tmp_path, monkeypatch):
    target = tmp_path / 'claude' / 'marketplace'
    cc.sync_marketplace(MARKET, target, '0.1.0')
    before = {name: (target / name).read_bytes() for name in copied_files(target)}
    real, count = cc.shutil.copy2, []

    def failing(src, dst, *args, **kwargs):
        count.append(src)
        if len(count) == 2:
            raise OSError('disk full')
        return real(src, dst, *args, **kwargs)
    monkeypatch.setattr(cc.shutil, 'copy2', failing)
    with pytest.raises(OSError):
        cc.sync_marketplace(MARKET, target, '0.2.0')
    assert {name: (target / name).read_bytes() for name in copied_files(target)} == before
    assert [p.name for p in target.parent.iterdir()] == ['marketplace']


@pytest.mark.req('STORE-MCP-001')
def test_refresh_only_when_copy_exists(tmp_path, caplog):
    target = tmp_path / 'claude' / 'marketplace'
    cc.refresh_marketplace(MARKET, target, '0.1.0')
    assert not target.exists() and not target.parent.exists()
    cc.sync_marketplace(MARKET, target, '0.1.0')
    cc.refresh_marketplace(MARKET, target, '0.2.0')
    assert (target / cc.VERSION_MARKER).read_text(encoding='utf-8') == '0.2.0'
    cc.refresh_marketplace(None, target, '0.3.0')
    assert (target / cc.VERSION_MARKER).read_text(encoding='utf-8') == '0.2.0'
    (target / cc.VERSION_MARKER).unlink()
    cc.refresh_marketplace(MARKET, target, '0.3.0')
    assert not (target / cc.VERSION_MARKER).exists()
    assert 'marketplace' in caplog.text


class PluginRunner:
    """`claude plugin …`: `listed` is what `marketplace list --json` prints; `codes` maps a subcommand to its exit code."""

    def __init__(self, listed='[]', codes=None, raises=None):
        self.calls, self.listed, self.codes, self.raises = [], listed, codes or {}, raises

    def __call__(self, argv, **kwargs):
        assert not kwargs.get('shell') and kwargs.get('timeout') == cc.TIMEOUT
        self.calls.append(argv[1:])
        if self.raises:
            raise self.raises
        key = argv[3] if argv[2] == 'marketplace' else argv[2]
        out = self.listed.encode() if key == 'list' else b''
        return subprocess.CompletedProcess(argv, self.codes.get(key, 0), out, b'')


def listed(path):
    return json.dumps([{'name': 'obscura', 'source': 'directory', 'path': str(path), 'installLocation': str(path)}])


@pytest.mark.req('STORE-MCP-001')
def test_plugin_sequence_new(tmp_path):
    target, run = tmp_path / 'marketplace', PluginRunner()
    assert cc.connect_claude_plugin(tmp_path / 'claude.exe', target, run=run) is True
    assert run.calls == [['plugin', 'marketplace', 'list', '--json'],
                         ['plugin', 'marketplace', 'add', str(target), '--scope', 'user'],
                         ['plugin', 'install', 'obscura@obscura', '--scope', 'user']]


@pytest.mark.req('STORE-MCP-001')
def test_plugin_sequence_other_path(tmp_path):
    target, run = tmp_path / 'marketplace', PluginRunner(listed(tmp_path / 'elsewhere'))
    assert cc.connect_claude_plugin(tmp_path / 'claude.exe', target, run=run) is True
    assert run.calls == [['plugin', 'marketplace', 'list', '--json'],
                         ['plugin', 'marketplace', 'remove', 'obscura'],
                         ['plugin', 'marketplace', 'add', str(target), '--scope', 'user'],
                         ['plugin', 'install', 'obscura@obscura', '--scope', 'user']]


@pytest.mark.req('STORE-MCP-001')
def test_plugin_sequence_same_path(tmp_path):
    target = tmp_path / 'marketplace'
    target.mkdir()
    run = PluginRunner(listed(str(target).upper() if os.name == 'nt' else target))
    assert cc.connect_claude_plugin(tmp_path / 'claude.exe', target, run=run) is True
    assert run.calls == [['plugin', 'marketplace', 'list', '--json'],
                         ['plugin', 'install', 'obscura@obscura', '--scope', 'user']]


@pytest.mark.req('STORE-MCP-001')
@pytest.mark.parametrize('runner', [PluginRunner(listed='not json'), PluginRunner(listed='{"a": 1}'),
                                    PluginRunner(codes={'list': 1}), PluginRunner(codes={'add': 1}),
                                    PluginRunner(codes={'install': 1}),
                                    PluginRunner(raises=subprocess.TimeoutExpired('claude', cc.TIMEOUT))])
def test_plugin_failures(tmp_path, runner):
    assert cc.connect_claude_plugin(tmp_path / 'claude.exe', tmp_path / 'marketplace', run=runner) is False


@pytest.mark.req('STORE-MCP-001')
def test_plugin_commands_to_copy(tmp_path):
    target = tmp_path / 'my folder' / 'marketplace'
    assert cc.plugin_commands(target) == [f'claude plugin marketplace add "{target}" --scope user',
                                          'claude plugin install obscura@obscura --scope user']


@pytest.mark.req('STORE-MCP-001')
def test_desktop_skills_written_and_foreign_kept(tmp_path):
    from storygen.skill_bundles import skill_names
    plugin = MARKET / 'obscura'
    folder = tmp_path / 'claude' / 'skills'
    folder.mkdir(parents=True)
    (folder / 'custom.zip').write_bytes(b'mine')
    written = cc.write_desktop_skills(plugin, folder)
    names = skill_names(plugin)
    assert [path.name for path in written] == [f'{name}.zip' for name in names]
    assert sorted(p.name for p in folder.iterdir()) == sorted([f'{name}.zip' for name in names] + ['custom.zip'])
    assert (folder / 'custom.zip').read_bytes() == b'mine'
    for name in names:
        assert f'{name}/SKILL.md' in zipfile.ZipFile(folder / f'{name}.zip').namelist()


@pytest.mark.req('STORE-MCP-001')
def test_sync_retries_a_briefly_locked_rename(tmp_path, monkeypatch):
    """Windows: an antivirus or the indexer may hold freshly written files for a moment, so the folder rename is retried."""
    real, failures = cc.os.replace, []

    def locked_twice(src, dst):
        if Path(src).name.startswith('.marketplace-') and len(failures) < 2:
            failures.append(src)
            raise PermissionError(5, 'Access is denied')
        return real(src, dst)
    monkeypatch.setattr(cc.os, 'replace', locked_twice)
    monkeypatch.setattr(cc.time, 'sleep', lambda seconds: None)
    target = tmp_path / 'claude' / 'marketplace'
    assert cc.sync_marketplace(MARKET, target, '0.1.0') == 'created'
    assert len(failures) == 2 and (target / cc.VERSION_MARKER).is_file()
