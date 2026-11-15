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
