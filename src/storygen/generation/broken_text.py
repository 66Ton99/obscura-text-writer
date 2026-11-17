"""Letters a provider lost on the way: U+FFFD in model replies (spec 2026-11-17-broken-letters-guard).

Venice can detokenize the two bytes of a Cyrillic letter separately, and each byte becomes U+FFFD. The letter
cannot be recovered. A reply is judged by whole words: a word with U+FFFD is new when the model did not receive
the same word, so damage copied from older texts never blocks a stage.
"""
import json
import re

from ..model_json import unwrap_model_json

REPLACEMENT = '�'
REJECT = frozenset({'memory', 'classify', 'impact_delta', 'impact_check', 'impact_part', 'review_part'})
DROP = frozenset({'rewrite', 'publication_suggest'})
WARN = frozenset({'draft', 'brief', 'prepare', 'timeline_summary'})


def stage_category(stage, edit_mode):
    """1: reject the reply; 2: drop damaged units; 3: keep and warn; None: not guarded."""
    if stage in REJECT:
        return 1
    if stage in DROP or (stage == 'edit' and edit_mode in {'diff', 'patches'}):
        return 2
    if stage in WARN or stage == 'edit':
        return 3
    return None


def _keep(ch):
    return ch.isalnum() or ch == REPLACEMENT


def _trim(word):
    start, end = 0, len(word)
    while start < end and not _keep(word[start]):
        start += 1
    while end > start and not _keep(word[end-1]):
        end -= 1
    return word[start:end]


def _words(text):
    for match in re.finditer(r'\S+', text):
        word = _trim(match.group())
        if REPLACEMENT in word:
            yield word, match.start(), match.end()


def known_words(source):
    """Damaged words the model received; a word of U+FFFD alone covers nothing."""
    return frozenset(word for word, _, _ in _words(source) if word.strip(REPLACEMENT))


def new_broken_words(output, known):
    found = []
    for word, _, _ in _words(output):
        if word not in known and word not in found:
            found.append(word)
    return found


def count_broken(text):
    return text.count(REPLACEMENT)


def request_source(body):
    parts = []
    for message in (body or {}).get('messages') or []:
        content = message.get('content')
        if isinstance(content, str):
            parts.append(content)
        elif isinstance(content, list):
            parts.extend(item.get('text') or '' for item in content if isinstance(item, dict))
    return '\n'.join(parts)


def json_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from json_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from json_strings(item)


def structured_broken(text, known):
    """New damaged words in decoded JSON strings; an unparsable reply is left to the stage's own JSON error."""
    try:
        value = json.loads(unwrap_model_json(text.strip()))
    except (ValueError, RecursionError):
        return []
    found = []
    for string in json_strings(value):
        for word in new_broken_words(string, known):
            if word not in found:
                found.append(word)
    return found


def broken_diff_edits(original, proposal, known):
    """Indices of diff edits whose resulting words, not the bare replacement, carry a new U+FFFD."""
    bad = set()
    shift = 0
    candidate = proposal.candidate_text
    for index, edit in enumerate(proposal.edits):
        start = edit.start+shift
        end = start+len(edit.replacement)
        shift += len(edit.replacement)-(edit.end-edit.start)
        while start > 0 and not candidate[start-1].isspace():
            start -= 1
        while end < len(candidate) and not candidate[end].isspace():
            end += 1
        if new_broken_words(candidate[start:end], known):
            bad.add(index)
    return bad


def drop_diff_edits(original, proposal, indices):
    """The proposal without `indices`, its candidate rebuilt from the original; None when nothing is left."""
    if not indices:
        return proposal
    kept = [edit for index, edit in enumerate(proposal.edits) if index not in indices]
    if not kept:
        return None
    text = original
    for edit in reversed(kept):
        text = text[:edit.start]+edit.replacement+text[edit.end:]
    return proposal.model_copy(update={'edits': kept, 'candidate_text': text})


def drop_broken_suggestions(suggestions, known):
    """Publication fields without damaged values: a text field goes whole, a list loses only its damaged items."""
    kept, dropped = {}, 0
    for key, value in suggestions.items():
        if isinstance(value, str):
            if new_broken_words(value, known):
                dropped += 1
            else:
                kept[key] = value
            continue
        items = [item for item in value if not new_broken_words(item, known)]
        dropped += len(value)-len(items)
        if items:
            kept[key] = items
    return kept, dropped


def dropped_warning(count):
    return f'Відкинуто правок із пошкодженими літерами «�»: {count}. Решту показано.'


def failure_message(count):
    return (f'Відповідь моделі пошкоджена: слів із символом «�» — {count}. Нічого не збережено; повторіть запуск. '
            'Автоматичного повтору немає.')


def kept_warning(count):
    return f'У тексті слів із символом «�»: {count}. Виправте їх у редакторі.'
