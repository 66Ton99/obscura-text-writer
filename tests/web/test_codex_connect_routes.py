"""STORE-MCP-001: owner-only Codex settings; no client or model processes."""
import json
import os

import pytest
from fastapi.testclient import TestClient

from storygen import claude_connect as cc
from storygen.application.settings import AppSettings
from storygen.codex_skill_install import InstallReport
from storygen.web import routes_codex_connect as routes
from storygen.web.app import create_app

BASE = 'http://127.0.0.1:8765'
PREFIX = '/api/connect/codex'


@pytest.fixture
def roots(tmp_path, monkeypatch):
    made = cc.Roots(tmp_path/'Local', tmp_path/'Roaming', tmp_path/'home')
    monkeypatch.setattr(routes, '_roots', lambda: made)
    monkeypatch.setenv('CODEX_HOME', str(tmp_path/'codex'))
    return made


@pytest.fixture
def client(tmp_path, roots):
    with TestClient(create_app(AppSettings(data_dir=tmp_path/'data', port=8765)), base_url=BASE) as made:
        yield made


@pytest.mark.req('STORE-MCP-001')
def test_mcp_save_and_repeat(client):
    answer = client.post(PREFIX)
    assert answer.status_code == 200
    assert answer.json()['result'] == 'configured' and answer.json()['created']
    assert client.post(PREFIX).json()['result'] == 'unchanged'
    assert client.get(PREFIX+'/status').json()['mcp']['state'] == 'configured'
    assert 'connected' not in json.dumps(answer.json())


@pytest.mark.req('STORE-MCP-001')
def test_status_is_read_only(client, roots):
    config = routes.config_path(roots.userprofile, os.environ['CODEX_HOME'])
    assert not config.parent.exists() and not roots.userprofile.exists()
    answer = client.get(PREFIX+'/status')
    assert answer.status_code == 200
    assert answer.json()['mcp']['state'] == 'missing'
    assert answer.json()['skills']['state'] == 'missing'
    assert not config.parent.exists() and not roots.userprofile.exists()
    config.parent.mkdir()
    config.write_text('private = [', encoding='utf-8')
    assert client.get(PREFIX+'/status').json()['mcp']['state'] == 'invalid'
    assert config.read_text() == 'private = ['


@pytest.mark.req('CODEX-SKILLS')
def test_skills_install_and_repeat(client, roots):
    answer = client.post(PREFIX+'/skills')
    assert answer.status_code == 200 and answer.json()['result'] == 'installed'
    assert len(answer.json()['names']) == 5
    assert client.post(PREFIX+'/skills').json()['result'] == 'unchanged'
    assert client.get(PREFIX+'/status').json()['skills']['state'] == 'current'
    assert not (roots.userprofile/'.codex').exists()


@pytest.mark.req('STORE-MCP-001')
def test_corrupt_config_is_untouched(client, roots):
    config = routes.config_path(roots.userprofile, os.environ['CODEX_HOME'])
    config.parent.mkdir()
    config.write_text('private = [', encoding='utf-8')
    answer = client.post(PREFIX)
    assert answer.status_code == 422 and answer.json()['reason'] == 'invalid_config'
    assert 'private' not in answer.text and config.read_text() == 'private = ['
    assert list(config.parent.iterdir()) == [config]


@pytest.mark.req('CODEX-SKILLS')
def test_partial_report_keeps_backups(client, roots, monkeypatch):
    backup = roots.userprofile/'.agents/obscura-backups/op/obscura-start-story'
    monkeypatch.setattr(routes, 'install_skills', lambda *args: InstallReport(
        'partial', installed=('obscura-draft-scene',), conflicts=('obscura-start-story',),
        restored=('obscura-publish',), backups=(backup,), errors=('install_io_failed',)))
    answer = client.post(PREFIX+'/skills')
    assert answer.status_code == 500
    assert answer.json()['result'] == 'partial'
    assert answer.json()['backups'] == [str(backup)]
    assert answer.json()['restored'] == ['obscura-publish']


@pytest.mark.req('CODEX-SKILLS')
@pytest.mark.parametrize('mode', ['store', 'frozen'])
def test_store_skills_are_unsupported_without_touching_sources(client, roots, monkeypatch, mode):
    from types import SimpleNamespace
    if mode == 'store':
        monkeypatch.setattr(routes.build_edition, 'current', lambda: SimpleNamespace(edition='store', long_prose=False))
    else:
        monkeypatch.setattr(routes.sys, 'frozen', True, raising=False)
    monkeypatch.setattr(routes, 'generate_skills', lambda *args: pytest.fail('sources accessed'))
    status = client.get(PREFIX+'/status')
    assert status.json()['skills']['available'] is False
    assert client.post(PREFIX+'/skills').status_code == 409
    assert not roots.userprofile.exists()


@pytest.mark.req('STORE-MCP-001')
def test_request_cannot_choose_destinations_or_bridge_url(client, roots, tmp_path):
    target = tmp_path/'attacker'
    body = dict(command=['evil'], source=str(target), destination=str(target), url='https://evil.test')
    one = client.post(PREFIX, json=body, headers={'Host':'localhost:9999'})
    two = client.post(PREFIX, json=body, headers={'Host':'127.0.0.1:1234'})
    assert one.status_code == two.status_code == 200
    assert one.json()['command'] == two.json()['command']
    config = routes.config_path(roots.userprofile, os.environ['CODEX_HOME']).read_text()
    assert '127.0.0.1:8765' in config and 'evil' not in config and '9999' not in config
    assert not target.exists()


@pytest.mark.req('STORE-MCP-001')
@pytest.mark.parametrize('method,path', [('get',PREFIX+'/status'), ('post',PREFIX), ('post',PREFIX+'/skills')])
def test_bridge_cannot_access_codex_routes(client, roots, monkeypatch, method, path):
    monkeypatch.setattr(routes, '_roots', lambda: pytest.fail('action attempted'))
    answer = getattr(client, method)(path, headers={'X-Obscura-Client':'mcp'})
    assert answer.status_code == 403 and 'Codex' in answer.text


@pytest.mark.req('STORE-MCP-001')
@pytest.mark.parametrize('path', [PREFIX, PREFIX+'/skills'])
def test_foreign_origin_cannot_write(client, monkeypatch, path):
    monkeypatch.setattr(routes, '_roots', lambda: pytest.fail('action attempted'))
    assert client.post(path, headers={'Origin':'https://evil.test'}).status_code == 403


@pytest.mark.req('STORE-MCP-001')
def test_invalid_codex_home_does_not_hide_skills(client, roots, monkeypatch):
    monkeypatch.setenv('CODEX_HOME', 'relative-home')
    answer = client.get(PREFIX+'/status')
    assert answer.status_code == 200
    assert answer.json()['mcp']['state'] == 'error'
    assert answer.json()['mcp']['reason'] == 'config_home_must_be_absolute'
    assert answer.json()['skills']['available'] is True
    assert answer.json()['command'].startswith('codex mcp add')
    assert client.post(PREFIX+'/skills').status_code == 200


@pytest.mark.req('STORE-MCP-001')
def test_skill_source_error_does_not_hide_mcp(client, monkeypatch):
    from storygen.codex_skills import GenerationError
    def broken(*args):
        raise GenerationError('source_changed')
    monkeypatch.setattr(routes, 'generate_skills', broken)
    answer = client.get(PREFIX+'/status')
    assert answer.status_code == 200
    assert answer.json()['skills']['state'] == 'error'
    assert answer.json()['mcp']['state'] == 'missing'
    assert answer.json()['command'].startswith('codex mcp add')
    assert client.post(PREFIX).status_code == 200


@pytest.mark.req('CODEX-SKILLS')
def test_busy_lock_report_has_specific_reason(client, roots):
    lock = roots.userprofile/'.agents/.obscura-install.lock'
    lock.mkdir(parents=True)
    answer = client.post(PREFIX+'/skills')
    assert answer.status_code == 409 and answer.json()['errors'] == ['install_busy']
    assert answer.json()['conflicts'] == [] and lock.exists()
