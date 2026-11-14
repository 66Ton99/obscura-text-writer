"""SERIES-BIBLE-S01: the world bible of a series — one per series, without a number or a start (neutral examples)."""
import pytest

from storygen.book.protagonists import scene_tracked
from storygen.domain import SceneCreate, StoryCreate
from storygen.series_models import SeriesStart
from storygen.storage import series as store
from storygen.storage.repository import Repository



def bible_in(repo, series_id, title='Світ'):
    story = repo.create_story(StoryCreate(title=title))
    return store.set_story_series(repo, story.id, series_id, None, None, story.revision, bible=True)


@pytest.mark.req('SERIES-BIBLE-001')
def test_a_bible_has_a_series_without_a_number(tmp_path):
    repo = Repository(tmp_path)
    item = store.create_series(repo, 'Серія')
    bible = bible_in(repo, item.id)
    assert bible.series_bible is True and bible.series_id == item.id
    assert bible.series_number is None and bible.series_start is None and bible.series_start_version_id is None


@pytest.mark.req('SERIES-BIBLE-001')
def test_a_bible_refuses_a_number_or_a_start(tmp_path):
    repo = Repository(tmp_path)
    item = store.create_series(repo, 'Серія')
    story = repo.create_story(StoryCreate(title='Світ'))
    with pytest.raises(ValueError, match=store.SERIES_BIBLE_FIELDS):
        store.set_story_series(repo, story.id, item.id, 1, None, story.revision, bible=True)
    with pytest.raises(ValueError, match=store.SERIES_BIBLE_FIELDS):
        store.set_story_series(repo, story.id, item.id, None, SeriesStart(offset='Рік -1', anchor=1),
                               story.revision, bible=True)
    with pytest.raises(ValueError, match=store.SERIES_BIBLE_FIELDS):
        store.set_story_series(repo, story.id, None, None, None, story.revision, bible=True)


@pytest.mark.req('SERIES-BIBLE-001')
def test_one_bible_per_series_even_in_the_trash(tmp_path):
    repo = Repository(tmp_path)
    item = store.create_series(repo, 'Серія')
    first = bible_in(repo, item.id)
    repo.set_story_trashed(first.id, first.revision, False)
    other = repo.create_story(StoryCreate(title='Ще світ'))
    with pytest.raises(ValueError, match=store.SERIES_BIBLE_TAKEN):
        store.set_story_series(repo, other.id, item.id, None, None, other.revision, bible=True)
    second = store.create_series(repo, 'Інша серія')
    assert bible_in(repo, second.id, 'Інший світ').series_bible is True


@pytest.mark.req('SERIES-BIBLE-001')
def test_a_book_that_becomes_the_bible_loses_its_number_and_snapshot_link(tmp_path):
    repo = Repository(tmp_path)
    item = store.create_series(repo, 'Серія')
    story = repo.create_story(StoryCreate(title='Книга'))
    story = store.set_story_series(repo, story.id, item.id, 2, None, story.revision)
    story = store.set_story_series(repo, story.id, item.id, None, None, story.revision, bible=True)
    assert story.series_bible and story.series_number is None and story.series_start_version_id is None
    story = store.set_story_series(repo, story.id, None, None, None, story.revision)
    assert story.series_bible is False and story.series_id is None


@pytest.mark.req('SERIES-BIBLE-001')
def test_a_series_with_a_bible_cannot_be_deleted(tmp_path):
    repo = Repository(tmp_path)
    item = store.create_series(repo, 'Серія')
    bible_in(repo, item.id)
    with pytest.raises(ValueError, match=store.SERIES_NOT_EMPTY):
        store.delete_series(repo, item.id, item.revision)


@pytest.mark.req('SERIES-BIBLE-001')
def test_create_bible(tmp_path):
    repo = Repository(tmp_path)
    item = store.create_series(repo, 'Серія')
    bible = store.create_bible(repo, item.id, 'Біблія світу: Серія')
    assert bible.series_bible and bible.series_number is None and bible.title == 'Біблія світу: Серія'
    with pytest.raises(ValueError, match=store.SERIES_BIBLE_TAKEN):
        store.create_bible(repo, item.id, 'Друга')


@pytest.mark.req('SERIES-BIBLE-001')
def test_a_bible_tracks_no_protagonists(tmp_path):
    from storygen.characters.models import CharacterRecord
    repo = Repository(tmp_path)
    item = store.create_series(repo, 'Серія')
    bible = bible_in(repo, item.id)
    scene = repo.create_scene(bible.id, SceneCreate(title='Магія', character_ids=['c1']))
    cards = [CharacterRecord(id='c1', name='Анна')]
    bible = repo.get_story(bible.id)
    # The same story and cards outside the bible infer Anna as the protagonist.
    assert scene_tracked(bible.model_copy(update={'series_bible': False}), cards, [scene], scene) == ['c1']
    assert scene_tracked(bible, cards, [scene], scene) == []


@pytest.mark.req('SERIES-BIBLE-001')
def test_the_chronology_axis_ignores_the_bible(tmp_path):
    from storygen.book.series import chronology, chronology_moments, prequel_ids
    repo = Repository(tmp_path)
    item = store.create_series(repo, 'Серія')
    bible = bible_in(repo, item.id)
    first = repo.create_story(StoryCreate(title='Книга 1'))
    first = store.set_story_series(repo, first.id, item.id, 1, None, first.revision)
    prequel = repo.create_story(StoryCreate(title='Приквел 2'))
    prequel = store.set_story_series(repo, prequel.id, item.id, 2, SeriesStart(offset='Рік -10', anchor=1), prequel.revision)
    books = store.series_books(repo, item.id)
    assert bible.id in [b.id for b in books]
    assert set(chronology_moments(books)) == {first.id, prequel.id}
    assert chronology(books) == ([prequel.id, first.id], [])
    assert prequel_ids(books) == {prequel.id}
