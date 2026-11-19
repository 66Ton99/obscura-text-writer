"""STORE-FOOTER: the Store story page renders no run options and no extra actions; the full edition keeps both."""
import pytest
from fastapi.testclient import TestClient

from storygen import build_edition
from storygen.application.settings import AppSettings
from storygen.domain import SceneCreate, StoryCreate
from storygen.web.app import create_app


def story_page(tmp_path):
    client = TestClient(create_app(AppSettings(data_dir=tmp_path / 'data', env_file=tmp_path / 'absent.env')), base_url='http://127.0.0.1')
    repo = client.app.state.repo
    story = repo.create_story(StoryCreate(title='Маяк'))
    repo.create_scene(story.id, SceneCreate(title='Сцена', beats='План'))
    return client.get(f'/stories/{story.id}').text


@pytest.mark.req('STORE-FOOTER')
def test_store_story_page_has_no_run_options_or_extra_actions(tmp_path, monkeypatch):
    edition = build_edition.BuildEdition(edition='store')
    monkeypatch.setattr(build_edition, 'current', lambda: edition)
    page = story_page(tmp_path)
    assert 'id="run-options"' not in page and 'workspace-extra' not in page and 'id="generation-controls"' not in page
    assert 'id="workspace-history"' in page and 'id="scene-statistics"' in page and 'id="workspace-use-draft"' in page
    assert 'id="workspace-scene-actions"' not in page


@pytest.mark.req('STORE-FOOTER')
def test_full_story_page_keeps_run_options_and_extra_actions(tmp_path):
    page = story_page(tmp_path)
    assert 'id="run-options"' in page and 'workspace-extra' in page and 'id="generation-controls"' in page
    assert 'id="workspace-scene-actions"' not in page


@pytest.mark.req('STORE-FOOTER')
def test_restore_saves_the_version_format_and_reuses_an_identical_head(tmp_path):
    """The requests the Store history sends: the version's own format wins over the head's; identical text reuses the head."""
    client = TestClient(create_app(AppSettings(data_dir=tmp_path / 'data', env_file=tmp_path / 'absent.env')), base_url='http://127.0.0.1')
    repo = client.app.state.repo
    story = repo.create_story(StoryCreate(title='Маяк'))
    scene = repo.create_scene(story.id, SceneCreate(title='Сцена', beats='План'))

    def save(text, content_format):
        current = repo.get_scene(scene.id)
        response = client.post(f'/api/scenes/{scene.id}/prose', json={'text': text, 'expected_revision': current.revision, 'content_format': content_format})
        assert response.status_code == 200, response.text
        return response.json()
    old = save('Стара **проза**.', 'markdown')['version']
    save('Нова проза.', 'plain')
    restored = save(client.get(f"/api/versions/{old['id']}").json()['text'], old['content_format'])
    assert restored['version']['id'] != old['id'] and restored['version']['content_format'] == 'markdown'
    assert restored['scene']['heads']['prose'] == restored['version']['id']
    again = save('Стара **проза**.', 'markdown')
    assert again['version']['id'] == restored['version']['id']
