"""PLAN-PREAMBLE-S04: the chat reads and replaces the plan preamble over MCP (neutral examples)."""
import pytest

pytest.importorskip('mcp')

from storygen.mcp.bridge import build_server  # noqa: E402

from tests.mcp.test_bridge import call, obscura, text  # noqa: E402
from tests.mcp.test_bridge_story_start import imported_story, ok  # noqa: E402


@pytest.mark.req('PLAN-PREAMBLE')
def test_chat_reads_and_replaces_the_plan_preamble(tmp_path):
    app, http = obscura(tmp_path)
    story = imported_story(app, http)
    server = build_server(http)
    preamble = ok(call(server, 'get_story', {'story_id': story.id}))['plan_preamble']
    plan = app.state.repo.active_source(story.id, 'source_plan').id
    assert preamble['plan_version_id'] == plan and preamble['editable']
    result = ok(call(server, 'update_plan_preamble', {'story_id': story.id, 'text': 'Тон: похмурий.', 'plan_version_id': plan}))
    assert result['changed'] and result['plan_version_id'] == app.state.repo.active_source(story.id, 'source_plan').id
    assert ok(call(server, 'get_story', {'story_id': story.id}))['plan_preamble']['text'] == 'Тон: похмурий.'
    stale = call(server, 'update_plan_preamble', {'story_id': story.id, 'text': 'Інше', 'plan_version_id': plan})
    assert stale.is_error and '409' in text(stale)
