"""EDIT-LOOP-REVIEW-S02: the pass limit is saved with the editor settings of the story and survives any reload."""
import pytest
from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.domain import SceneCreate, StoryCreate
from storygen.providers.models import ProviderSettings, RoleSettings
from storygen.web.app import create_app


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(AppSettings(data_dir=tmp_path / 'data', env_file=tmp_path / 'absent.env')), base_url='http://127.0.0.1')


@pytest.mark.req('EDIT-LOOP-REVIEW')
def test_pass_limit_saved_with_editor_settings_drives_readiness(client):
    repo = client.app.state.repo
    story = repo.create_story(StoryCreate(title='Маяк'))
    scene = repo.create_scene(story.id, SceneCreate(title='Сцена', beats='План'))
    url = f'/api/stories/{story.id}/settings'
    editor = RoleSettings(provider=ProviderSettings(model='editor'), edit_mode='patches', edit_pass_limit=3)
    saved = client.put(url, json={'expected_revision': client.get(url).json()['story']['revision'], 'role': 'editor', 'settings': editor.model_dump()})
    assert saved.status_code == 200, saved.text
    assert client.get(url).json()['roles']['editor']['edit_pass_limit'] == 3
    scene_op = client.get(f'/api/stories/{story.id}/readiness?scene_id={scene.id}&operation=scene').json()['operations']['scene']
    assert scene_op['edit_pass_limit'] == 3
    other = repo.create_story(StoryCreate(title='Інший'))
    other_url = f'/api/stories/{other.id}/settings'
    assert client.get(other_url).json()['roles'].get('editor', {}).get('edit_pass_limit', 5) == 5


@pytest.mark.req('EDIT-LOOP-REVIEW')
def test_edit_loop_readiness_names_the_limit_the_author_confirms(client):
    """The confirmation shows this number and the run is sent with it, so a later settings change cannot raise it."""
    repo = client.app.state.repo
    story = repo.create_story(StoryCreate(title='Маяк'))
    scene = repo.create_scene(story.id, SceneCreate(title='Сцена', beats='План'))
    url = f'/api/stories/{story.id}/settings'
    editor = RoleSettings(provider=ProviderSettings(model='editor'), edit_mode='patches', edit_pass_limit=2)
    assert client.put(url, json={'expected_revision': client.get(url).json()['story']['revision'], 'role': 'editor', 'settings': editor.model_dump()}).status_code == 200
    op = client.get(f'/api/stories/{story.id}/readiness?scene_id={scene.id}&operation=edit_loop').json()['operations']['edit_loop']
    assert op['edit_pass_limit'] == 2
