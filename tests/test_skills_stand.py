"""CLAUDE-SKILLS: the stand for `claude -p` runs talks only to its own test server."""
import json

import pytest

from scripts.skills_stand import claude_command, obscura_call, parse_result, tool_calls, tool_errors, write_mcp_config


@pytest.mark.req('CLAUDE-SKILLS')
def test_claude_command_is_isolated(tmp_path):
    cfg = write_mcp_config(tmp_path/'mcp.json', 9123)
    data = json.loads(cfg.read_text(encoding='utf-8'))
    assert list(data['mcpServers']) == ['obscura']
    assert data['mcpServers']['obscura']['args'][-2:] == ['--url', 'http://127.0.0.1:9123']
    cmd = claude_command('hi', mcp_config=cfg, plugin_dir=tmp_path, model='sonnet', budget_usd=1.0)
    # Without --strict-mcp-config the author's own `obscura` from ~/.claude.json would load too.
    assert '--strict-mcp-config' in cmd and cmd[cmd.index('--mcp-config')+1] == str(cfg)
    assert cmd[cmd.index('--max-budget-usd')+1] == '1.0' and cmd[cmd.index('--model')+1] == 'sonnet'
    assert cmd[cmd.index('--plugin-dir')+1] == str(tmp_path)


@pytest.mark.req('CLAUDE-SKILLS')
def test_tool_calls_and_cost_from_stream_json():
    lines = [json.dumps({'type': 'assistant', 'message': {'content': [
                 {'type': 'text', 'text': 'Reading.'},
                 {'type': 'tool_use', 'name': 'mcp__obscura__get_story', 'input': {'story_id': 's'}}]}}),
             'not json',
             json.dumps({'type': 'assistant', 'message': {'content': [{'type': 'tool_use', 'name': 'AskUserQuestion', 'input': {}}]}}),
             json.dumps({'type': 'result', 'total_cost_usd': 0.12, 'usage': {'input_tokens': 10, 'output_tokens': 5}, 'result': 'ok'})]
    assert tool_calls(lines) == [('get_story', {'story_id': 's'}), ('AskUserQuestion', {})]
    result = parse_result(lines)
    assert result.cost_usd == 0.12 and result.usage == {'input_tokens': 10, 'output_tokens': 5}
    assert result.text == 'Reading.\nok'


@pytest.mark.req('CLAUDE-SKILLS')
def test_tool_errors_name_the_refused_tool():
    lines = [json.dumps({'type': 'assistant', 'message': {'content': [
                 {'type': 'tool_use', 'id': 't1', 'name': 'mcp__obscura__save_stage_result', 'input': {}},
                 {'type': 'tool_use', 'id': 't2', 'name': 'mcp__obscura__get_story', 'input': {}}]}}),
             json.dumps({'type': 'user', 'message': {'content': [
                 {'type': 'tool_result', 'tool_use_id': 't1', 'is_error': True, 'content': 'schema: beats missing'},
                 {'type': 'tool_result', 'tool_use_id': 't2', 'content': '{}'}]}})]
    assert tool_errors(lines) == [('save_stage_result', 'schema: beats missing')]
    assert parse_result(lines).errors == [('save_stage_result', 'schema: beats missing')]


@pytest.mark.req('CLAUDE-SKILLS')
def test_obscura_call_reaches_the_given_server(tmp_path):
    pytest.importorskip('mcp')
    from fastapi.testclient import TestClient
    from storygen.application.settings import AppSettings
    from storygen.web.app import create_app
    http = TestClient(create_app(AppSettings(data_dir=tmp_path/'data')), base_url='http://127.0.0.1:8765')
    story = obscura_call(http, 'create_story', {'title': 'Стенд', 'language': 'uk'})
    assert story['title'] == 'Стенд'
    assert [s['id'] for s in obscura_call(http, 'list_stories', {})] == [story['id']]
