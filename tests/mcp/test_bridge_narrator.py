"""SCENE-NARRATOR-S06: the narrator over MCP and the external draft dependency (#214)."""
import json

import pytest

pytest.importorskip('mcp')

from storygen.domain import SceneCreate, StoryCreate  # noqa: E402
from storygen.mcp.bridge import build_server  # noqa: E402
from storygen.storage.snapshots import resolve_freshness  # noqa: E402

from tests.mcp.test_bridge import call, fresh_save, obscura, text  # noqa: E402

SECTION = 'ОПОВІДАЧ СЦЕНИ — ДЛЯ ЦІЄЇ СЦЕНИ ЗАМІНЯЄ point_of_view ЗІ СТИЛЮ\nПерша особа: розповідає Юлія.'


def story_with_cards(repo):
    story = repo.create_story(StoryCreate(title='Пристань'))
    cards = [{'schema_version': 2, 'id': id, 'name': name, 'entries': []} for id, name in (('j', 'Юлія'), ('o', 'Олег'))]
    ref = repo.save_version(story.id, None, 'character_cards', json.dumps(cards, ensure_ascii=False), [])
    repo.publish_story_material(story.id, 'characters_version_id', ref.id, repo.get_story(story.id).revision)
    return repo.get_story(story.id)


@pytest.mark.req('SCENE-NARRATOR')
def test_add_and_update_scene_set_the_narrator_and_context_shows_it(tmp_path):
    app, http = obscura(tmp_path)
    repo = app.state.repo
    story = story_with_cards(repo)
    server = build_server(http)
    added = json.loads(text(call(server, 'add_scene', {'story_id': story.id, 'title': 'Пристань', 'plan_markdown': 'Хто бере участь: Юлія',
                                                        'character_ids': ['j'], 'narrator': {'person': 'first', 'character_id': 'j'}})))
    scene = repo.get_scene(added['id'])
    assert scene.narrator.person == 'first' and scene.narrator.character_id == 'j'
    context = http.get(f'/api/scenes/{scene.id}/writing-context').json()
    assert context['narrator'] == SECTION and 'narrator_warnings' not in context
    result = call(server, 'update_scene', {'story_id': story.id, 'scene_id': scene.id, 'expected_revision': scene.revision, 'narrator': None})
    assert not result.is_error, text(result)
    assert repo.get_scene(scene.id).narrator is None
    assert 'narrator' not in http.get(f'/api/scenes/{scene.id}/writing-context').json()


@pytest.mark.req('SCENE-NARRATOR')
def test_external_draft_depends_on_the_narrator_and_own_text_does_not(tmp_path):
    app, http = obscura(tmp_path)
    repo = app.state.repo
    story = story_with_cards(repo)
    scene = repo.create_scene(story.id, SceneCreate(title='Пристань', beats='Хто бере участь: Юлія', character_ids=['j']))
    repo.update_scene_metadata(scene.id, {'narrator': {'person': 'first', 'character_id': 'j'}}, repo.get_scene(scene.id).revision)
    server = build_server(http)
    assert not fresh_save(server, http, scene.id, 'Я чекала на пристані.', None).is_error
    external = repo.get_version(repo.get_scene(scene.id).heads['draft'])
    assert any(s.field == 'narrator' and s.expected == 'first:j' for s in external.dependency_snapshot.selectors)
    from storygen.generation.dependencies import save_manual_draft
    own = save_manual_draft(repo, scene.id, 'Вона чекала.', repo.get_scene(scene.id).revision)
    assert not any(s.field == 'narrator' for s in own.dependency_snapshot.selectors)
    repo.update_scene_metadata(scene.id, {'narrator': {'person': 'third_omniscient', 'character_id': None}}, repo.get_scene(scene.id).revision)
    reasons = [(r.reason, r.selector.field if r.selector else None) for r in resolve_freshness(repo.context_view(story.id), external.id).reasons]
    assert ('selector_changed', 'narrator') in reasons
