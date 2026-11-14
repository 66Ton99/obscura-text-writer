"""SERIES-BIBLE-S02–S04, S07: the world bible is a direct source of every book's start snapshot (neutral examples)."""
import pytest

from storygen.book.series import series_status, start_memory
from storygen.domain import SceneCreate, StoryCreate
from storygen.memory.journal import MemoryJournal, _add_event, _change_event, replay_memory
from storygen.memory.series_start import read_series_start
from storygen.series_models import SeriesStart
from storygen.storage import series as store
from storygen.storage.repository import Repository
from tests.series.helpers import book, finished_book, into_series, memory, prose



def snapshot(repo, story):
    story = repo.get_story(story.id)
    return read_series_start(repo.read_text(story.series_start_version_id), story.series_start_version_id)


def texts(journal):
    return sorted(e.text for e in replay_memory(journal).values())


def by_key(journal):
    from storygen.memory.merge import _key
    return {_key(e): e.text for e in replay_memory(journal).values()}


def write_bible(repo, item, facts=('Магія коштує крові',), finished=True):
    story = repo.create_story(StoryCreate(title='Біблія'))
    story = store.set_story_series(repo, story.id, item.id, None, None, story.revision, bible=True)
    scene = repo.create_scene(story.id, SceneCreate(title='Світ'))
    if finished:
        rewrite_bible(repo, scene, facts)
    return repo.get_story(story.id), repo.get_scene(scene.id)


def rewrite_bible(repo, scene, facts):
    """New prose and a new memory of the bible's only scene (the bible changed)."""
    p = prose(repo, scene, ' '.join(f'{f}.' for f in facts))
    memory(repo, scene, MemoryJournal(schema_version=3), [_add_event('facts', f, p.id, f'{f}.', 0) for f in facts])


def write_book_one(repo, item, cast=('A',)):
    """Book 1 in the series over its snapshot: Anna's clothing and a fact of its own."""
    story, scene = book(repo, 'Книга 1', written=False, cast=list(cast))
    story = into_series(repo, story, item.id, 1)
    base = snapshot(repo, story).journal if story.series_start_version_id else MemoryJournal(schema_version=3)
    p = prose(repo, scene, 'Анна в халаті. Сусід пішов додому.')
    cloth = _add_event('character_states', 'Халат', p.id, 'Анна в халаті.', 0, ['A'], slot='clothing')
    memory(repo, scene, base, [cloth, _add_event('facts', 'Сусід пішов', p.id, 'Сусід пішов додому.', 0)])
    return repo.get_story(story.id), cloth


@pytest.mark.req('SERIES-BIBLE-001')
def test_book_one_takes_its_snapshot_from_the_bible(tmp_path):
    repo = Repository(tmp_path)
    item = store.create_series(repo, 'Сага')
    bible, _ = write_bible(repo, item)
    first, _ = book(repo, 'Книга 1')
    first = into_series(repo, first, item.id, 1)
    data = snapshot(repo, first)
    assert texts(data.journal) == ['Магія коштує крові']
    assert [s['story_id'] for s in data.source['sources']] == [bible.id]
    assert data.source['bible_keys'] == [f'claim:{e.claim_id}' for e in replay_memory(data.journal).values()]
    assert series_status(repo, first).state == 'fresh'


@pytest.mark.req('SERIES-BIBLE-001')
def test_without_a_bible_book_one_has_no_snapshot(tmp_path):
    repo = Repository(tmp_path)
    item = store.create_series(repo, 'Сага')
    first, _ = book(repo, 'Книга 1')
    first = into_series(repo, first, item.id, 1)
    assert first.series_start_version_id is None and series_status(repo, first).state == 'first'


@pytest.mark.req('SERIES-BIBLE-001')
def test_a_bible_without_a_summary_blocks_the_snapshot_and_a_trashed_one_is_no_source(tmp_path):
    repo = Repository(tmp_path)
    item = store.create_series(repo, 'Сага')
    bible, _ = write_bible(repo, item, finished=False)
    first, _ = book(repo, 'Книга 1')
    first = into_series(repo, first, item.id, 1)
    status = series_status(repo, first)
    assert first.series_start_version_id is None and (status.state, status.source_story_id) == ('no_summary', bible.id)
    bible = repo.get_story(bible.id)
    repo.set_story_trashed(bible.id, bible.revision, False)
    assert series_status(repo, repo.get_story(first.id)).state == 'first'


@pytest.mark.req('SERIES-BIBLE-001')
def test_book_two_takes_the_current_bible_not_the_copy_from_book_one(tmp_path):
    repo = Repository(tmp_path)
    item = store.create_series(repo, 'Сага')
    bible, bible_scene = write_bible(repo, item, facts=('Магія коштує крові', 'Столиця на трьох річках'))
    first, cloth = write_book_one(repo, item)
    second, _ = book(repo, 'Книга 2', cast=['A'])
    second = into_series(repo, second, item.id, 2)
    data = snapshot(repo, second)
    assert texts(data.journal) == ['Магія коштує крові', 'Столиця на трьох річках', 'Сусід пішов', 'Халат']
    assert [s['story_id'] for s in data.source['sources']] == [bible.id, first.id]
    assert sorted(by_key(data.journal)[k] for k in data.source['bible_keys']) == ['Магія коштує крові', 'Столиця на трьох річках']
    rewrite_bible(repo, bible_scene, ('Магія коштує сну',))
    assert series_status(repo, repo.get_story(second.id)).state == 'source_changed'
    assert series_status(repo, repo.get_story(first.id)).state == 'source_changed'
    store.refresh_snapshot(repo, second.id, repo.get_story(second.id).revision)
    data = snapshot(repo, second)
    assert texts(data.journal) == ['Магія коштує сну', 'Сусід пішов', 'Халат']
    assert [by_key(data.journal)[k] for k in data.source['bible_keys']] == ['Магія коштує сну']


@pytest.mark.req('SERIES-BIBLE-001')
def test_a_bible_added_later_changes_no_snapshot(tmp_path):
    repo = Repository(tmp_path)
    item = store.create_series(repo, 'Сага')
    first, _, _ = finished_book(repo)
    first = into_series(repo, first, item.id, 1)
    second, _ = book(repo, 'Книга 2', cast=['A'])
    second = into_series(repo, second, item.id, 2)
    before = second.series_start_version_id
    write_bible(repo, item)
    assert repo.get_story(second.id).series_start_version_id == before
    assert series_status(repo, repo.get_story(second.id)).state == 'source_changed'
    assert series_status(repo, repo.get_story(first.id)).state == 'source_finished'


@pytest.mark.req('SERIES-BIBLE-001')
def test_the_main_book_still_wins_over_a_prequel(tmp_path):
    repo = Repository(tmp_path)
    item = store.create_series(repo, 'Сага')
    write_bible(repo, item)
    first, cloth = write_book_one(repo, item)
    prequel, scene = book(repo, 'Приквел 2', written=False, cast=['A'])
    prequel = store.set_story_series(repo, prequel.id, item.id, 2, SeriesStart(offset='Рік -10', anchor=1), prequel.revision)
    keys = [f['key'] for f in store.start_facts(repo, prequel.id)]
    store.save_decisions(repo, prequel.id, {k: 'past' for k in keys}, repo.get_story(prequel.id).revision)
    data = snapshot(repo, prequel)
    p = prose(repo, scene, 'Анна в одязі: Сорочка.')
    memory(repo, scene, data.journal, [_change_event('update', cloth.claim_id, 'Сорочка', 'character_states', ['A'], p.id,
                                                     'Анна в одязі: Сорочка.', slot='clothing')])
    third, _ = book(repo, 'Книга 3', cast=['A'])
    third = store.set_story_series(repo, third.id, item.id, 3, SeriesStart(offset='Рік 2', anchor=1), third.revision)
    result = snapshot(repo, third)
    assert 'Халат' in texts(result.journal) and 'Сорочка' not in texts(result.journal)
    assert texts(result.journal).count('Магія коштує крові') == 1
    assert [r['kept_story_id'] for r in result.source['resolved']] == [first.id]


@pytest.mark.req('SERIES-BIBLE-001')
def test_bible_facts_are_the_past_of_a_prequel(tmp_path):
    repo = Repository(tmp_path)
    item = store.create_series(repo, 'Сага')
    write_bible(repo, item)
    write_book_one(repo, item)
    prequel, _ = book(repo, 'Приквел 2', written=False, cast=['A'])
    prequel = store.set_story_series(repo, prequel.id, item.id, 2, SeriesStart(offset='Рік -10', anchor=1), prequel.revision)
    data = snapshot(repo, prequel)
    assert texts(data.journal) == ['Магія коштує крові']
    assert sorted(f['text'] for f in data.future) == ['Сусід пішов', 'Халат']
    bible_key = data.source['bible_keys'][0]
    with pytest.raises(ValueError, match=store.BIBLE_IS_PAST):
        store.save_decisions(repo, prequel.id, {bible_key: 'future'}, repo.get_story(prequel.id).revision)
    # Saving other decisions keeps the bible keys, so a later «future» is still refused.
    others = [f['key'] for f in store.start_facts(repo, prequel.id) if f['key'] != bible_key]
    store.save_decisions(repo, prequel.id, {k: 'past' for k in others}, repo.get_story(prequel.id).revision)
    assert snapshot(repo, prequel).source['bible_keys'] == [bible_key]
    with pytest.raises(ValueError, match=store.BIBLE_IS_PAST):
        store.save_decisions(repo, prequel.id, {bible_key: 'future'}, repo.get_story(prequel.id).revision)


@pytest.mark.req('SERIES-BIBLE-001')
def test_a_series_without_a_bible_keeps_its_snapshots(tmp_path):
    repo = Repository(tmp_path)
    item = store.create_series(repo, 'Сага')
    first, _, _ = finished_book(repo)
    first = into_series(repo, first, item.id, 1)
    second, _ = book(repo, 'Книга 2', cast=['A'])
    second = into_series(repo, second, item.id, 2)
    data = snapshot(repo, second)
    assert 'bible_keys' not in data.source and [s['story_id'] for s in data.source['sources']] == [first.id]
    assert start_memory(repo, repo.get_story(second.id)).bible_keys == []
