"""SERIES-BIBLE-S06: a new scene takes the author's prose at once, without a plan (neutral examples)."""
import pytest

from storygen.domain import ContentRating, SceneCreate, StoryCreate
from storygen.generation.dependencies import save_manual_prose
from storygen.storage import series as store
from storygen.storage.repository import Repository
from storygen.storage.snapshots import compare_snapshot

pytestmark = pytest.mark.req('SERIES-BIBLE-001')


@pytest.mark.parametrize('bible', [False, True])
@pytest.mark.parametrize('flashback', [False, True])
def test_new_scene_takes_manual_prose_at_once(tmp_path, bible, flashback):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Світ', content_rating=ContentRating(sexual=0, violence=0, themes=0)))
    if bible:
        item = store.create_series(repo, 'Серія')
        story = store.set_story_series(repo, story.id, item.id, None, None, story.revision, bible=True)
    scene = repo.create_scene(story.id, SceneCreate(title='Магія', flashback=flashback))
    ref = save_manual_prose(repo, scene.id, 'Магія коштує крові.', repo.get_scene(scene.id).revision)
    assert repo.get_scene(scene.id).heads['prose'] == ref.id and repo.get_version(ref.id).stale is False
    assert not compare_snapshot(repo.context_view(story.id), ref.dependency_snapshot)
