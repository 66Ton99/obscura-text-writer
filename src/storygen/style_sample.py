"""STYLE-SAMPLE-001: comparing style versions without the voice sample, for storage and dependency checks.

Plain JSON on purpose: storage must not import generation (where StyleProfile lives). A field that one version lacks
and the other has makes them differ, so such a pair is treated as a full style change — the conservative side."""
import json


def without_sample(text: str) -> dict:
    data = json.loads(text)
    data.pop('tone_sample', None)
    return data


def sample_only_change(read_text, old_id, new_id) -> bool:
    """Two existing style versions that differ only in `tone_sample`."""
    if not old_id or not new_id or old_id == new_id:
        return False
    return without_sample(read_text(old_id)) == without_sample(read_text(new_id))
