"""STORY-LANGUAGE-S10 (#93): the default writing profile follows the story language; saved profiles stay as saved."""
import json

import pytest
from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.generation.models import StyleProfile, default_style_profile
from storygen.web.app import create_app

UK_RULES = 'Українська мова. Репліки діалогу починай з довгого тире.'
EN = {'point_of_view': 'third person', 'tense': 'past', 'rules': 'English. Put dialogue in double quotation marks.'}


def styles(app, story_id):
    return [v for v in app.state.repo.context_view(story_id).versions.values() if v.kind == 'style']


@pytest.fixture
def setup(tmp_path):
    app = create_app(AppSettings(data_dir=tmp_path))
    with TestClient(app, base_url='http://127.0.0.1:8765') as client:
        yield app, client


def story(client, language):
    data = client.post('/api/stories', json={'title': 'Twin', 'language': language}).json()
    return data['id'], f"/api/stories/{data['id']}/settings"


@pytest.mark.req('STORY-LANGUAGE')
def test_default_profile_follows_story_language(setup):
    app, client = setup
    assert {k: getattr(default_style_profile('en'), k) for k in EN} == EN
    assert default_style_profile('uk') == StyleProfile()
    en_id, en_url = story(client, 'en')
    uk_id, uk_url = story(client, 'uk')
    assert {k: client.get(en_url).json()['profile'][k] for k in EN} == EN
    assert client.get(uk_url).json()['profile']['rules'] == UK_RULES
    # A story without a saved profile follows a language change.
    revision = app.state.repo.get_story(uk_id).revision
    assert client.put(f'/api/stories/{uk_id}/language', json={'language': 'en', 'expected_revision': revision}).status_code == 200
    assert client.get(uk_url).json()['profile']['rules'] == EN['rules']


@pytest.mark.req('STORY-LANGUAGE')
def test_partial_or_empty_profile_body_uses_story_language_defaults(setup):
    app, client = setup
    en_id, url = story(client, 'en')
    revision = client.get(url).json()['story']['revision']
    empty = client.put(url, json={'expected_revision': revision, 'profile': {}})
    assert empty.status_code == 200, empty.text
    assert empty.json()['style_version_id'] is None and styles(app, en_id) == []
    toned = client.put(url, json={'expected_revision': empty.json()['revision'], 'profile': {'tone': 'restrained'}})
    assert toned.status_code == 200, toned.text
    saved = json.loads(app.state.repo.read_text(toned.json()['style_version_id']))
    assert saved['tone'] == 'restrained' and {k: saved[k] for k in EN} == EN
    # Explicit fields are kept as sent, Ukrainian ones included.
    explicit = client.put(url, json={'expected_revision': toned.json()['revision'], 'profile': {'rules': UK_RULES}})
    assert json.loads(app.state.repo.read_text(explicit.json()['style_version_id']))['rules'] == UK_RULES


@pytest.mark.req('STORY-LANGUAGE')
def test_saved_profile_is_read_as_saved(setup):
    app, client = setup
    en_id, url = story(client, 'en')
    revision = client.get(url).json()['story']['revision']
    full = {**StyleProfile().model_dump(), 'tone': 'old'}
    assert client.put(url, json={'expected_revision': revision, 'profile': full}).status_code == 200
    profile = client.get(url).json()['profile']
    assert profile['rules'] == UK_RULES and profile['point_of_view'] == 'третя особа' and profile['tone'] == 'old'
