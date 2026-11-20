"""CHARACTER-NAMES-S05 (#215): memory finds facts by every available name; a name change stales the scene's memory."""
import json

import pytest

from storygen.characters.service import save_character_material
from storygen.generation.context import build_context, story_match_names
from storygen.memory.journal import MemoryJournal, _add_event
from storygen.memory.projection import MemoryItem
from storygen.memory.selection import SelectionInput, classify, narrow_catalog
from storygen.storage.snapshots import resolve_freshness

from tests.generation.test_character_names_context import entry, remember, role, setup

FACT = 'Хазяїн має єдиний ключ'


def selection(**names):
    item = MemoryItem('c1', 'facts', None, '- ' + FACT, FACT, (), None, 1)
    return SelectionInput((item,), 's', 9, ('j', 'h'), ('j',), {'j': 'Юлія', 'h': 'Джон'}, **names)


@pytest.mark.req('CHARACTER-NAMES')
def test_writer_selection_finds_a_fact_by_an_earlier_name():
    assert [i.claim_id for i in classify(selection())['fts']] == ['c1']
    layers = classify(selection(match_names={'j': 'Юлія', 'h': 'Джон, Хазяїн'}))
    assert [i.claim_id for i in layers['facts']] == ['c1']


@pytest.mark.req('CHARACTER-NAMES')
def test_catalog_narrowing_keeps_a_fact_by_an_earlier_name():
    event = _add_event('facts', FACT, 'p1', 'ключ', 0)
    journal = MemoryJournal(schema_version=3, source_prose_ids=['p1'], events=[event])
    args = (['j', 'h'], ['j'])
    assert event.claim_id not in narrow_catalog(journal, *args, {'j': 'Юлія', 'h': 'Джон'}, '', 9, {'p1': 1}).keep
    assert event.claim_id in narrow_catalog(journal, *args, {'j': 'Юлія', 'h': 'Джон, Хазяїн'}, '', 9, {'p1': 1}).keep


@pytest.mark.req('CHARACTER-NAMES')
def test_an_added_name_keeps_the_inflected_mentions_of_the_card_name():
    event = _add_event('facts', 'Олени ключ лежить у шухляді', 'p1', 'ключ', 0)
    journal = MemoryJournal(schema_version=3, source_prose_ids=['p1'], events=[event])
    for names in ({'h': 'Олена'}, {'h': 'Олена, Бос'}):
        assert event.claim_id in narrow_catalog(journal, ['h'], [], names, '', 9, {'p1': 1}).keep
    item = MemoryItem('c1', 'facts', None, '- Олени ключ', 'Олени ключ', (), None, 1)
    inp = SelectionInput((item,), 's', 9, ('h',), (), {'h': 'Олена'}, match_names={'h': 'Олена, Бос'})
    assert [i.claim_id for i in classify(inp)['facts']] == ['c1']


@pytest.mark.req('CHARACTER-NAMES')
def test_requests_match_every_name_available_in_the_scene(tmp_path):
    repo, scenes = setup(tmp_path)
    story = repo.get_story(scenes[0].story_id)
    assert story_match_names(repo, story, scenes, scenes[0]) == {'j': 'Юлія', 'h': 'Хазяїн, Бос'}
    assert story_match_names(repo, story, scenes, scenes[1]) == {'j': 'Юлія', 'h': 'Джон, Хазяїн, Бос'}


def memory_of(repo, scenes):
    scenes = remember(repo, scenes, 0)
    scene = scenes[1]
    prose = repo.save_version(scene.story_id, scene.id, 'manual', 'Юлія чує: Джон.', [])
    repo.set_head(scene.id, 'prose', prose.id, repo.get_scene(scene.id).revision)
    bundle = build_context(repo, scene.id, 'memory', role())
    journal = MemoryJournal(schema_version=3, source_prose_ids=[*json.loads(repo.read_text(repo.get_scene(scenes[0].id).heads['memory']))['source_prose_ids'], prose.id], events=[])
    return repo.save_version(scene.story_id, scene.id, 'memory', journal.model_dump_json(), bundle.input_refs, dependency_snapshot=bundle.dependency_snapshot)


def recard(repo, story_id, other_name, age='Вік: 40'):
    scenes = repo.list_scenes(story_id)
    cards = [
        {'schema_version': 2, 'id': 'j', 'name': 'Юлія', 'entries': [entry('j1', 'Протагоністка')]},
        {'schema_version': 2, 'id': 'h', 'name': 'Хазяїн', 'entries': [
            entry('h1', age), entry('h2', 'Інше ім\'я: Бос'), entry('h3', f'Інше ім\'я: {other_name}', scenes[1].id)]},
    ]
    # Existing IDs are kept: the server assigns IDs only to new cards and entries.
    save_character_material(repo, story_id, cards, repo.get_story(story_id).revision)


def stale_fields(repo, ref):
    return [r.selector.field for r in resolve_freshness(repo.context_view(ref.story_id), ref.id).reasons if r.selector]


@pytest.mark.req('CHARACTER-NAMES')
def test_memory_snapshot_has_no_names_selector_without_other_names(tmp_path):
    repo, scenes = setup(tmp_path)
    plain = [{'schema_version': 2, 'id': 'j', 'name': 'Юлія', 'entries': [entry('j1', 'Протагоністка')]},
             {'schema_version': 2, 'id': 'h', 'name': 'Хазяїн', 'entries': [entry('h1', 'Вік: 40')]}]
    save_character_material(repo, scenes[0].story_id, plain, repo.get_story(scenes[0].story_id).revision)
    memory = memory_of(repo, [repo.get_scene(s.id) for s in scenes])
    assert 'character_names' not in [s.field for s in memory.dependency_snapshot.selectors]


@pytest.mark.req('CHARACTER-NAMES')
def test_name_change_stales_the_memory_of_the_scene(tmp_path):
    repo, scenes = setup(tmp_path)
    memory = memory_of(repo, scenes)
    assert stale_fields(repo, memory) == []
    recard(repo, memory.story_id, 'Джон', age='Вік: 41')
    assert stale_fields(repo, memory) == []
    recard(repo, memory.story_id, 'Петро', age='Вік: 41')
    assert stale_fields(repo, memory) == ['character_names']
