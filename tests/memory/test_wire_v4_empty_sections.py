"""MEMORY-002-S14 (#93): an empty list in `core` or `threads` reads as an empty object; a non-empty list stays a violation."""
import json

import pytest

from storygen.domain import SceneCreate, StoryCreate
from storygen.memory.core_review import captured_wire
from storygen.memory.journal import MemoryJournal, parse_memory_result
from storygen.memory.violations import MemoryViolations
from storygen.memory.wire_v4 import empty_sections, schema_bounds_v4
from storygen.storage.repository import Repository
from tests.memory.test_core_review import run_memory
from tests.memory.test_wire_v4 import BOUNDS, PREV, PROSE
from tests.memory.wire_helpers import v4_response

EMPTY = MemoryJournal(schema_version=3, source_prose_ids=[], events=[])
NO_DECISIONS = schema_bounds_v4(EMPTY, PROSE, [], [], {})


def answer(core, threads):
    data = json.loads(v4_response(facts_add=[{'text': 'Ганна вдягла пальто.', 'evidence_ids': ['f000001']}]))
    data['core'], data['threads'] = core, threads
    return data


def parse(data, prev=EMPTY, bounds=NO_DECISIONS, warnings=None):
    return parse_memory_result(json.dumps(data, ensure_ascii=False), prev, 'p2', PROSE, 'evidence_delta', [],
                               warnings=warnings, wire_version=4, bounds=bounds)


def codes(data, prev=EMPTY, bounds=NO_DECISIONS):
    try:parse(data, prev, bounds)
    except MemoryViolations as error:return [tuple(v) for v in error.violations]
    return []


@pytest.mark.req('MEMORY-002')
def test_empty_lists_read_as_no_decisions():
    assert NO_DECISIONS['tracked'] == {} and NO_DECISIONS['threads'] == []
    for core, threads in (([], []), ({}, []), ([], {})):
        warnings = []
        journal = parse(answer(core, threads), warnings=warnings)
        assert [e.text for e in journal.events] == ['Ганна вдягла пальто.'] and warnings == []


@pytest.mark.req('MEMORY-002')
def test_non_empty_list_and_missing_thread_decisions_stay_violations():
    assert codes(answer([], ['x'])) == [('threads', 'schema')]
    assert codes(answer([{'h': {}}], {})) == [('core', 'schema')]
    # With active threads an empty list is "no decision" for each of them, not silent acceptance.
    expected = [('core.h', 'schema')] + [('threads.' + claim_id, 'schema') for claim_id in BOUNDS['threads']]
    assert len(BOUNDS['threads']) == 2 and codes(answer({}, []), PREV, BOUNDS) == expected


@pytest.mark.req('MEMORY-002')
def test_empty_sections_does_not_mutate_and_keeps_other_values():
    data = {'core': [], 'threads': [], 'facts': {'add': []}}
    assert empty_sections(data) == {'core': {}, 'threads': {}, 'facts': {'add': []}} and data['core'] == []
    assert empty_sections({'core': ['x'], 'threads': None}) == {'core': ['x'], 'threads': None}
    assert empty_sections([]) == []


@pytest.mark.req('MEMORY-002')
def test_stage_publishes_memory_and_captured_wire_reads_it(tmp_path):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Без ліній'))
    scene = repo.create_scene(story.id, SceneCreate(title='С1', beats='Ганна.'))
    prose = repo.save_version(story.id, scene.id, 'manual', 'Ганна вдягла пальто.\nНадворі ніч.', [])
    repo.set_head(scene.id, 'prose', prose.id, repo.get_scene(scene.id).revision)
    raw = json.dumps(answer([], []), ensure_ascii=False)
    run_memory(repo, repo.get_scene(scene.id), raw)
    wire, bounds = captured_wire(repo, repo.get_scene(scene.id).heads['memory'])
    assert (wire['core'], wire['threads'], bounds['threads']) == ({}, {}, [])
