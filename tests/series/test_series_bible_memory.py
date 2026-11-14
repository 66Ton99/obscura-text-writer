"""SERIES-BIBLE-S05: the memory of a world bible — facts only, up to 10 per scene, no core (neutral examples)."""
import json

import pytest

from storygen.domain import ContentRating, SceneCreate, StoryCreate
from storygen.generation.context import build_context
from storygen.generation.dependencies import save_manual_prose
from storygen.memory.wire_v4 import BIBLE_FACT_LIMIT, check_v4, memory_wire_v4_schema
from storygen.providers.models import ProviderSettings, RoleSettings
from storygen.storage import series as store
from storygen.storage.repository import Repository
from storygen.storage.snapshots import compare_snapshot

LABEL = 'БІБЛІЯ СВІТУ: УСЕ НОВЕ — ФАКТИ, ДО 10 ЗІ СЦЕНИ; БЕЗ СТАНІВ, ЛІНІЙ І ХРОНОЛОГІЇ'
PROSE = 'Магія коштує крові. Столиця стоїть на трьох річках. Зима триває пів року.'


def role():
    return RoleSettings(provider=ProviderSettings(model='fake'), context_tokens=262144, max_output_tokens=2048)


def world(tmp_path, bible=True, flashback=False):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Світ', content_rating=ContentRating(sexual=0, violence=0, themes=0)))
    if bible:
        item = store.create_series(repo, 'Серія')
        store.set_story_series(repo, story.id, item.id, None, None, story.revision, bible=True)
    scene = repo.create_scene(story.id, SceneCreate(title='Магія', flashback=flashback))
    save_manual_prose(repo, scene.id, PROSE, repo.get_scene(scene.id).revision)
    return repo, repo.get_story(story.id), repo.get_scene(scene.id)


def wire(facts, **extra):
    empty = {'add': []}
    data = {'schema_version': 4, 'core': {}, 'threads': {}, 'facts': {'add': facts}, 'open_threads': dict(empty),
            'timeline': dict(empty), 'character_states': {'add': [], 'update': [], 'retire': []}}
    data.update(extra)
    return data


def fact(i):
    return {'text': f'Факт {i}', 'evidence_ids': ['f000001']}


@pytest.mark.req('SERIES-BIBLE-001')
def test_bible_memory_request_has_facts_only(tmp_path):
    repo, story, scene = world(tmp_path)
    ctx = build_context(repo, scene.id, 'memory', role())
    assert LABEL in ctx.user_text and 'ЯДРО СТАНУ' not in ctx.user_text and 'АКТИВНІ ЛІНІЇ' not in ctx.user_text
    assert 'ЧИННІ ТВЕРДЖЕННЯ' in ctx.user_text and PROSE in ctx.user_text
    bounds = json.loads(ctx.fragments['memory_schema_bounds'])
    assert bounds['fact_limit'] == BIBLE_FACT_LIMIT == 10 and bounds['flashback'] is True
    schema = memory_wire_v4_schema(bounds)['properties']
    assert schema['facts']['properties']['add']['maxItems'] == 10
    assert schema['timeline']['properties']['add']['maxItems'] == 0


@pytest.mark.req('SERIES-BIBLE-001')
def test_bible_flashback_scene_also_gets_ten(tmp_path):
    repo, story, scene = world(tmp_path, flashback=True)
    bounds = json.loads(build_context(repo, scene.id, 'memory', role()).fragments['memory_schema_bounds'])
    assert bounds['fact_limit'] == 10


@pytest.mark.req('SERIES-BIBLE-001')
def test_check_accepts_ten_facts_and_refuses_eleven_or_a_state(tmp_path):
    repo, story, scene = world(tmp_path)
    ctx = build_context(repo, scene.id, 'memory', role())
    bounds = json.loads(ctx.fragments['memory_schema_bounds'])
    from storygen.memory.journal import MemoryJournal
    previous = MemoryJournal.model_validate(json.loads(ctx.fragments['previous_memory']))
    assert not check_v4(wire([fact(i) for i in range(10)]), previous, bounds)
    assert any(v.code == 'add_limit' for v in check_v4(wire([fact(i) for i in range(11)]), previous, bounds))
    state = {'add': [{'text': 'Стан', 'character_ids': [], 'evidence_ids': ['f000001']}], 'update': [], 'retire': []}
    assert any(v.code == 'flashback_only_facts' for v in check_v4(wire([], character_states=state), previous, bounds))


@pytest.mark.req('SERIES-BIBLE-001')
def test_old_flashback_bounds_keep_the_limit_of_six(tmp_path):
    from storygen.memory.journal import MemoryJournal
    repo, story, scene = world(tmp_path)
    ctx = build_context(repo, scene.id, 'memory', role())
    bounds = json.loads(ctx.fragments['memory_schema_bounds'])
    previous = MemoryJournal.model_validate(json.loads(ctx.fragments['previous_memory']))
    old = {k: v for k, v in bounds.items() if k != 'fact_limit'}
    assert not check_v4(wire([fact(i) for i in range(6)]), previous, old)
    assert any(v.code == 'add_limit' for v in check_v4(wire([fact(i) for i in range(7)]), previous, old))
    assert memory_wire_v4_schema(old)['properties']['facts']['properties']['add']['maxItems'] == 6


@pytest.mark.req('SERIES-BIBLE-001')
def test_an_ordinary_book_memory_request_is_unchanged(tmp_path):
    repo, story, scene = world(tmp_path, bible=False)
    ctx = build_context(repo, scene.id, 'memory', role())
    assert LABEL not in ctx.user_text and 'ЯДРО СТАНУ' in ctx.user_text
    bounds = json.loads(ctx.fragments['memory_schema_bounds'])
    assert 'fact_limit' not in bounds and not bounds.get('flashback')
    assert not any(s.field == 'series_bible' for s in ctx.dependency_snapshot.selectors)


@pytest.mark.req('SERIES-BIBLE-001')
def test_bible_flag_set_later_stales_the_memory(tmp_path):
    repo, story, scene = world(tmp_path, bible=False)
    ctx = build_context(repo, scene.id, 'memory', role())
    item = store.create_series(repo, 'Серія')
    store.set_story_series(repo, story.id, item.id, None, None, repo.get_story(story.id).revision, bible=True)
    changes = compare_snapshot(repo.context_view(story.id), ctx.dependency_snapshot)
    assert any(c.selector and c.selector.field == 'series_bible' for c in changes)
    bible_ctx = build_context(repo, scene.id, 'memory', role())
    assert not compare_snapshot(repo.context_view(story.id), bible_ctx.dependency_snapshot)
