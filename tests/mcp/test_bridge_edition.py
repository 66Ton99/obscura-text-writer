"""STORE-MCP-001 S05: edition refusals reach the chat as a hint about the paid version with the waitlist link."""
import anyio
import httpx
import pytest

pytest.importorskip('mcp')
from mcp import Client  # noqa: E402

from storygen.book.guard import NO_LONG_PROSE, READ_ONLY, READ_ONLY_SERIES  # noqa: E402
from storygen.domain import ContentRating  # noqa: E402
from storygen.mcp.bridge import build_server  # noqa: E402
from storygen.mcp.edition import edition_refusal  # noqa: E402
from storygen.rating.guard import enforce_rating_limit  # noqa: E402

WAITLIST = 'https://example.com/waitlist'


def limit_text(store_edition) -> str:
    with pytest.raises(ValueError) as raised:
        enforce_rating_limit(ContentRating(sexual=2, violence=0, themes=0))
    return str(raised.value)


@pytest.mark.req('STORE-MCP-001')
@pytest.mark.parametrize('kind', ['no_long_prose', 'read_only', 'read_only_series', 'edition_limit'])
def test_edition_texts_become_a_paid_version_hint(kind, store_edition):
    detail = {'no_long_prose': NO_LONG_PROSE, 'read_only': READ_ONLY, 'read_only_series': READ_ONLY_SERIES,
              'edition_limit': limit_text(store_edition) if kind == 'edition_limit' else ''}[kind]
    hint = edition_refusal(detail, WAITLIST)
    assert hint is not None and detail in hint
    assert 'платної версії' in hint and 'paid version' in hint and WAITLIST in hint


@pytest.mark.req('STORE-MCP-001')
def test_empty_waitlist_has_no_link():
    hint = edition_refusal(NO_LONG_PROSE, '')
    assert hint is not None and 'https://' not in hint


@pytest.mark.req('STORE-MCP-001')
def test_other_refusals_stay_as_they_are(store_edition):
    assert edition_refusal('Сцену не знайдено', WAITLIST) is None
    assert edition_refusal(limit_text(store_edition)[:-10], WAITLIST) is None
    assert edition_refusal(NO_LONG_PROSE + ' і ще щось', WAITLIST) is None


@pytest.mark.req('STORE-MCP-001')
def test_bridge_tool_error_carries_the_hint(store_edition):
    limit, info = limit_text(store_edition), []

    def handler(request):
        if request.url.path == '/api/app-info':
            info.append(1)
            return httpx.Response(200, json={'waitlist_url': WAITLIST})
        return httpx.Response(403, json={'detail': 'Generation is blocked…', 'detail_original': limit})
    http = httpx.Client(base_url='http://127.0.0.1:8765', transport=httpx.MockTransport(handler))

    async def run():
        async with Client(build_server(http)) as client:
            return [await client.call_tool('get_scene_text', {'scene_id': 'scene-1', 'material': 'draft'}) for _ in range(2)]
    results = anyio.run(run)
    for result in results:
        text = ''.join(getattr(item, 'text', '') for item in result.content)
        assert result.is_error and WAITLIST in text and 'платної версії' in text
    assert info == [1]
