"""SCENE-NARRATOR-S03, S05: the narrator over HTTP and in the story view (#214)."""
import json

import pytest
from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.domain import SceneCreate, StoryCreate
from storygen.storage.repository import Repository
from storygen.web.app import create_app


def client_for(tmp_path):
    return TestClient(create_app(AppSettings(data_dir=tmp_path)), base_url='http://127.0.0.1:8765')


def setup(tmp_path, beats='Хто бере участь: Юлія'):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Пристань'))
    cards = [{'schema_version': 2, 'id': id, 'name': name, 'entries': []} for id, name in (('j', 'Юлія'), ('o', 'Олег'))]
    ref = repo.save_version(story.id, None, 'character_cards', json.dumps(cards, ensure_ascii=False), [])
    repo.publish_story_material(story.id, 'characters_version_id', ref.id, repo.get_story(story.id).revision)
    scene = repo.create_scene(story.id, SceneCreate(title='Пристань', beats=beats, character_ids=['j']))
    return repo, story, scene


def patch(client, story, scene, narrator):
    return client.patch(f'/api/scenes/{scene.id}', json={'story_id': story.id, 'expected_revision': scene.revision, 'narrator': narrator})


def listed(client, story, scene):
    return next(s for s in client.get(f'/api/stories/{story.id}').json()['scenes'] if s['id'] == scene.id)


@pytest.mark.req('SCENE-NARRATOR')
def test_patch_sets_and_resets_the_narrator(tmp_path):
    repo, story, scene = setup(tmp_path)
    with client_for(tmp_path) as client:
        response = patch(client, story, scene, {'person': 'third_limited', 'character_id': 'o'})
        assert response.status_code == 200, response.text
        card = listed(client, story, scene)
        assert card['narrator'] == {'person': 'third_limited', 'character_id': 'o'} and card['narrator_source'] == 'scene'
        assert card['narrator_problems'] == ['Оповідача немає серед учасників сцени: Олег.']
        response = patch(client, story, repo.get_scene(scene.id), None)
        assert response.status_code == 200 and response.json()['narrator'] is None
        # A patch without the field leaves the narrator alone.
        patch(client, story, repo.get_scene(scene.id), {'person': 'third_omniscient', 'character_id': None})
        current = repo.get_scene(scene.id)
        client.patch(f'/api/scenes/{scene.id}', json={'story_id': story.id, 'expected_revision': current.revision, 'title': 'Берег'})
        assert repo.get_scene(scene.id).narrator.person == 'third_omniscient'


@pytest.mark.req('SCENE-NARRATOR')
def test_invalid_narrator_is_rejected(tmp_path):
    repo, story, scene = setup(tmp_path)
    with client_for(tmp_path) as client:
        for value in ({'person': 'first', 'character_id': None}, {'person': 'third_omniscient', 'character_id': 'j'}, {'person': 'second', 'character_id': 'j'}):
            assert patch(client, story, scene, value).status_code == 422, value
    assert repo.get_scene(scene.id).narrator is None


@pytest.mark.req('SCENE-NARRATOR')
def test_story_view_reports_the_plan_line(tmp_path):
    repo, story, scene = setup(tmp_path, beats='Хто бере участь: Юлія\nОповідач: Юлія, перша особа')
    with client_for(tmp_path) as client:
        card = listed(client, story, scene)
    assert card['narrator'] is None and card['narrator_source'] == 'plan'
    assert card['narrator_effective'] == {'person': 'first', 'character_id': 'j'} and card['narrator_problems'] == []


@pytest.mark.req('SCENE-NARRATOR')
def test_narrator_messages_are_translated():
    from storygen.web.localization import diagnostic
    assert diagnostic('Оповідача немає серед учасників сцени: Олег.', 'en') == 'The narrator is not among the scene participants: Олег.'
    assert diagnostic('Оповідач: вкажіть одного героя: Юлія, Олег, перша особа', 'en').startswith('Narrator: name one character')
