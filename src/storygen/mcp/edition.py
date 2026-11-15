"""STORE-MCP-001 S05: an edition refusal from Obscura reaches the chat as a hint about the paid version.

The texts come from the guards themselves (no copies), so a changed guard text never silently stops matching. The hint is in
Ukrainian and English together: the refusal arrives on any request, where the bridge does not know the story's language.
"""
import re

from ..book.guard import NO_LONG_PROSE, READ_ONLY, READ_ONLY_SERIES
from ..rating.guard import EDITION_LIMIT

PAID_TEXT = ('Це можливість платної версії Obscura: довга проза (книги, частини, арки), серії й сцени без обмеження рейтингу.\n'
             'This is a feature of the paid version of Obscura: long prose (books, parts, arcs), series and scenes without '
             'the rating limit.')
WAITLIST_TEXT = 'Записатися / Join the waitlist: {url}'
INVALID_PREFIX = 'Некоректні дані: '
_EXACT = frozenset({NO_LONG_PROSE, READ_ONLY, READ_ONLY_SERIES})


def _template(text: str) -> re.Pattern:
    # Every `{name}` becomes a lazy wildcard, the rest is literal: the regex is built from the constant itself.
    return re.compile('^' + '.+?'.join(re.escape(part) for part in re.split(r'\{[^{}]*\}', text)) + '$', re.S)


_LIMIT = _template(EDITION_LIMIT)


def edition_refusal(detail: str, waitlist_url: str) -> str | None:
    """The chat text for an edition refusal, or `None` when `detail` is any other refusal (it is left as it is)."""
    # Obscura's ValueError handler and the long-prose middleware send «Некоректні дані: <refusal>».
    detail = detail.removeprefix(INVALID_PREFIX)
    if detail not in _EXACT and not _LIMIT.match(detail):
        return None
    lines = [detail, '', PAID_TEXT]
    if waitlist_url:
        lines.append(WAITLIST_TEXT.format(url=waitlist_url))
    return '\n'.join(lines)
