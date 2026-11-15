"""STORE-MCP-001 S06: the chat is led from an idea to the story in the Obscura window."""
import anyio
import httpx
import pytest

pytest.importorskip('mcp')
from mcp import Client  # noqa: E402

from storygen.mcp.bridge import INSTRUCTIONS, build_server  # noqa: E402


def server():
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={}))
    return build_server(httpx.Client(base_url='http://127.0.0.1:8765', transport=transport))


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
def test_instructions_offer_the_obscura_link():
    assert 'next_steps' in INSTRUCTIONS and 'вікні Obscura' in INSTRUCTIONS
