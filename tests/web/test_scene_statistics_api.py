import pytest
from fastapi.testclient import TestClient
from storygen.application.settings import AppSettings
from storygen.web.app import create_app
from tests.memory.test_forwarding import seeded


def test_statistics_get_has_no_writes_or_dispatch(tmp_path):
    repo,story,scenes=seeded(tmp_path)
    def snapshot():
        with repo.db.connection() as db:
            return {t:db.execute(f'SELECT * FROM {t}').fetchall() for t in ['stories','scenes','versions','stage_attempts','runs']}
    before=snapshot();calls=[]
    app=create_app(AppSettings(data_dir=tmp_path),gateway_factory=lambda p:calls.append(p))
    with TestClient(app,base_url='http://127.0.0.1:8765') as client:
        for stage in ['brief','draft','edit','memory']:
            response=client.get(f'/api/scenes/{scenes[1].id}/statistics?stage={stage}')
            assert response.status_code==200,response.text
            assert 'system_text' not in response.text and 'user_text' not in response.text
        assert client.get(f'/api/scenes/{scenes[1].id}/statistics?stage=unknown').status_code==422
        assert client.get(f'/api/scenes/{scenes[1].id}/statistics?stage=draft&details=false').status_code==200
    assert not calls and snapshot()==before


def stats_client(tmp_path):
    from storygen.domain import StoryCreate, SceneCreate
    from storygen.generation.dependencies import save_manual_prose
    app = create_app(AppSettings(data_dir=tmp_path)); repo = app.state.repo
    story = repo.create_story(StoryCreate(title='Підсумок'))
    first = repo.create_scene(story.id, SceneCreate(title='Перша', target_words=10))
    save_manual_prose(repo, first.id, 'Три слова тут.', first.revision)
    repo.create_scene(story.id, SceneCreate(title='Друга', target_words=5))
    third = repo.create_scene(story.id, SceneCreate(title='Третя', target_words=1))
    save_manual_prose(repo, third.id, 'Два слова.', third.revision)
    gone = repo.create_scene(story.id, SceneCreate(title='У кошику', target_words=100))
    save_manual_prose(repo, gone.id, 'Ці слова не рахуються взагалі.', gone.revision)
    gone = repo.get_scene(gone.id)
    repo.set_scene_trashed(story.id, gone.id, gone.revision, restore=False)
    return TestClient(app, base_url='http://127.0.0.1:8765'), first


@pytest.mark.req('R18-STATS')
def test_story_totals_sum_the_active_scenes(tmp_path):
    client, first = stats_client(tmp_path)
    with client:
        body = client.get(f'/api/scenes/{first.id}/statistics?stage=draft').json()
    assert body['story_totals'] == {'prose_words': 5, 'target_words': 16, 'scenes': 3}


@pytest.mark.req('R18-STATS')
def test_details_false_skips_memory_context_and_usage(tmp_path):
    client, first = stats_client(tmp_path)
    with client:
        body = client.get(f'/api/scenes/{first.id}/statistics?stage=draft&details=false').json()
        assert client.get(f'/api/scenes/{first.id}/statistics?stage=unknown&details=false').status_code == 422
    assert 'memory' not in body and 'context' not in body and 'last_usage' not in body
    assert body['materials']['prose']['words'] == 3 and body['story_totals']['scenes'] == 3
