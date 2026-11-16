"""DATA-010-S02: the book check accepts all waiting prose as the author's in one transaction."""
import pytest
from storygen.domain import StoryCreate, SceneCreate, RevisionConflict
from storygen.generation.dependencies import save_manual_prose
from storygen.review.capture import plan_review
from storygen.impact.presentation import scene_status
from storygen.storage.repository import Repository


def book(tmp_path, count=3):
    repo=Repository(tmp_path)
    story=repo.create_story(StoryCreate(title='Перевірка'))
    for n in range(count):
        scene=repo.create_scene(story.id,SceneCreate(title=f'Сцена {n+1}',beats=f'План {n+1}'))
        save_manual_prose(repo,scene.id,f'Проза {n+1}.',scene.revision)
    return repo,story


def swap(repo,story):
    # A move changes the order every text records, so all prose waits for review.
    ids=[s.id for s in repo.list_scenes(story.id)]
    repo.reorder_scenes(story.id,[ids[1],ids[0],*ids[2:]],repo.get_story(story.id).revision)


def waiting(repo,story):
    return [t.material for t in plan_review(repo.context_view(story.id)).targets]


def accept_all(repo,story):
    preview=repo.preview_prose_acceptance(story.id)
    return preview,repo.accept_all_prose(story.id,preview['fingerprint'])


@pytest.mark.req('DATA-010')
def test_all_waiting_prose_is_accepted_and_consecutive_scenes_stay_current(tmp_path):
    repo,story=book(tmp_path)
    swap(repo,story)
    assert waiting(repo,story)==['prose','prose','prose']
    texts={s.id:repo.read_text(s.heads['prose']) for s in repo.list_scenes(story.id)}
    preview,result=accept_all(repo,story)
    assert [s['title'] for s in preview['scenes']]==['Сцена 2','Сцена 1','Сцена 3']
    assert [a['title'] for a in result['accepted']]==['Сцена 2','Сцена 1','Сцена 3']
    # The author baseline of scene 2 and 3 holds the acceptance of the scenes before: nothing is stale afterwards.
    assert waiting(repo,story)==[]
    view=repo.context_view(story.id)
    assert all(v['prose']=='current' for v in scene_status(view).values())
    for scene in repo.list_scenes(story.id):
        assert not repo.get_version(scene.heads['prose']).stale and not scene.needs_review
        assert repo.read_text(scene.heads['prose'])==texts[scene.id]
    records=repo.list_acceptances(story.id)
    assert len(records)==3 and {r.action for r in records}=={'accept_prose'}
    assert repo.preview_prose_acceptance(story.id)['scenes']==[]


@pytest.mark.req('DATA-010')
def test_only_prose_is_accepted_and_fresh_prose_gets_no_record(tmp_path):
    repo,story=book(tmp_path,2)
    first,second=repo.list_scenes(story.id)
    brief=repo.save_version(story.id,first.id,'brief','{}',[first.heads['prose']])
    memory=repo.save_version(story.id,first.id,'memory','{}',[first.heads['prose']])
    save_manual_prose(repo,first.id,'Нова проза 1.',repo.get_scene(first.id).revision)
    assert repo.get_version(brief.id).stale and repo.get_version(memory.id).stale
    waiting_ids=[s['scene_id'] for s in repo.preview_prose_acceptance(story.id)['scenes']]
    assert waiting_ids==[second.id]
    accept_all(repo,story)
    assert repo.get_version(brief.id).stale and repo.get_version(memory.id).stale
    assert [r.scene_id for r in repo.list_acceptances(story.id)]==[second.id]


@pytest.mark.req('DATA-010')
def test_change_after_preview_rejects_everything(tmp_path):
    repo,story=book(tmp_path,2)
    swap(repo,story)
    preview=repo.preview_prose_acceptance(story.id)
    second=repo.list_scenes(story.id)[1]
    save_manual_prose(repo,second.id,'Інша проза.',second.revision)
    heads={s.id:s.heads['prose'] for s in repo.list_scenes(story.id)}
    with pytest.raises(RevisionConflict):
        repo.accept_all_prose(story.id,preview['fingerprint'])
    assert repo.list_acceptances(story.id)==[]
    assert {s.id:s.heads['prose'] for s in repo.list_scenes(story.id)}==heads
    assert repo.get_scene(repo.list_scenes(story.id)[0].id).needs_review


@pytest.mark.req('DATA-010')
def test_open_book_review_blocks_bulk_acceptance(tmp_path):
    from storygen.run_models import Run, RunRequest
    repo,story=book(tmp_path,2)
    swap(repo,story)
    preview=repo.preview_prose_acceptance(story.id)
    assert len(preview['scenes'])==2
    repo.enqueue_run(Run(id='review',story_id=story.id,request_id='review',request=RunRequest(story_id=story.id,mode='impact'),state='needs_review',tasks=[]))
    with pytest.raises(ValueError,match='перевірку книги'):
        repo.accept_all_prose(story.id,preview['fingerprint'])
    assert repo.list_acceptances(story.id)==[]
    # A finished review does not block.
    run=repo.get_run('review');run.state='completed';repo.save_run(run)
    assert len(repo.accept_all_prose(story.id,preview['fingerprint'])['accepted'])==2


@pytest.mark.req('DATA-010')
def test_nothing_waiting_gives_an_empty_preview(tmp_path):
    repo,story=book(tmp_path,2)
    preview,result=accept_all(repo,story)
    assert preview['scenes']==[] and result['accepted']==[]


@pytest.mark.req('DATA-010')
def test_http_preview_accept_and_stale_fingerprint(tmp_path):
    from fastapi.testclient import TestClient
    from storygen.web.app import create_app
    from storygen.application.settings import AppSettings
    app=create_app(AppSettings(data_dir=tmp_path))
    repo=app.state.repo
    story=repo.create_story(StoryCreate(title='HTTP'))
    for n in range(2):
        scene=repo.create_scene(story.id,SceneCreate(title=f'S{n}'))
        save_manual_prose(repo,scene.id,f'P{n}.',scene.revision)
    swap(repo,story)
    client=TestClient(app,base_url='http://127.0.0.1:8765')
    url=f'/api/stories/{story.id}/prose-acceptance'
    data=client.get(url).json()
    assert [s['title'] for s in data['scenes']]==['S1','S0']
    assert [t['material'] for t in client.get(f'/api/stories/{story.id}/impact').json()['pending']]==['prose','prose']
    accepted=client.post(url,json={'fingerprint':data['fingerprint']})
    assert accepted.status_code==200 and len(accepted.json()['accepted'])==2
    assert client.get(f'/api/stories/{story.id}/impact').json()['pending']==[]
    assert client.post(url,json={'fingerprint':data['fingerprint']}).status_code==409
