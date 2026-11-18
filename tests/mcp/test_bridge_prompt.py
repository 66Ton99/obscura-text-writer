"""STORE-MCP-001 S06: the chat is led from an idea to the story in the Obscura window."""
import anyio
import httpx
import pytest

pytest.importorskip('mcp')
from mcp import Client  # noqa: E402

from pathlib import Path  # noqa: E402

from storygen.mcp.bridge import INSTRUCTIONS, START_STORY_IDEA, build_server  # noqa: E402
from storygen.skill_bundles import guide_text  # noqa: E402

PLUGIN = Path(__file__).resolve().parents[2]/'integrations/claude/obscura'


def server(plugin=None):
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={}))
    return build_server(httpx.Client(base_url='http://127.0.0.1:8765', transport=transport), plugin=plugin)


def prompt_text(plugin, arguments):
    async def run():
        async with Client(server(plugin)) as client:
            answer = await client.get_prompt('start_story', arguments)
            return ' '.join(getattr(message.content, 'text', '') for message in answer.messages)
    return anyio.run(run)


@pytest.mark.req('STORE-MCP-001')
def test_start_story_prompt_walks_from_idea_to_the_obscura_window():
    async def run():
        async with Client(server()) as client:
            names = [prompt.name for prompt in (await client.list_prompts()).prompts]
            answer = await client.get_prompt('start_story', {'idea': 'маяк на острові'})
            return names, ' '.join(getattr(message.content, 'text', '') for message in answer.messages)
    names, text = anyio.run(run)
    assert 'start_story' in names and 'маяк на острові' in text
    steps = ['create_story', 'get_templates', 'import_plan_and_characters', 'get_scene_context', 'save_draft', 'next_steps']
    positions = [text.index(step) for step in steps]
    assert positions == sorted(positions)


@pytest.mark.req('STORE-MCP-001')
@pytest.mark.parametrize('idea', [None, '   '])
def test_start_story_without_idea_asks_the_person(idea):
    async def run():
        async with Client(server()) as client:
            answer = await client.get_prompt('start_story', {} if idea is None else {'idea': idea})
            return ' '.join(getattr(message.content, 'text', '') for message in answer.messages)
    assert 'спитайте людину' in anyio.run(run)


@pytest.mark.req('STORE-MCP-001')
def test_start_story_prompt_keeps_the_idea_and_follows_the_skill():
    text = prompt_text(PLUGIN, {'idea': 'маяк на острові'})
    assert text == START_STORY_IDEA.format(idea='маяк на острові') + guide_text(PLUGIN, 'start-story')


@pytest.mark.req('STORE-MCP-001')
def test_instructions_offer_the_obscura_link():
    assert 'next_steps' in INSTRUCTIONS and 'вікні Obscura' in INSTRUCTIONS
