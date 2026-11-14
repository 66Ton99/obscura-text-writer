"""SERIES-BIBLE-S08 (server part): the world bible through HTTP, the series screen, MCP and the plan preamble."""
import pytest
from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.book.series import SUMMARY_NO_MEMORY, series_status
from storygen.domain import StoryCreate
from storygen.mcp.bridge import story_series
from storygen.plan_sections import cut_series_lines
from storygen.series_models import SeriesStart
from storygen.storage import series as store
from storygen.storage.repository import Repository
from storygen.web.app import create_app
from tests.series.test_series_bible_snapshot import write_bible, write_book_one
from tests.series.test_series_import import SCENES, run
from tests.series.helpers import book


def client_for(tmp_path):
    return TestClient(create_app(AppSettings(data_dir=tmp_path)), base_url='http://127.0.0.1:8765')


@pytest.mark.req('SERIES-BIBLE-001')
def test_patch_makes_a_bible_and_back_a_book(tmp_path):
    repo = Repository(tmp_path)
    item = store.create_series(repo, 'Сага')
    story = repo.create_story(StoryCreate(title='Світ'))
    with client_for(tmp_path) as client:
        bad = client.patch(f'/api/stories/{story.id}/series', json={'series_id': item.id, 'number': 1, 'bible': True,
                                                                   'expected_revision': story.revision})
        assert bad.status_code == 400 and store.SERIES_BIBLE_FIELDS in bad.text  # a domain refusal, as a taken number
        started = client.patch(f'/api/stories/{story.id}/series', json={'series_id': item.id, 'bible': True,
                                                                       'start_text': 'Рік 1, опора 1',
                                                                       'expected_revision': story.revision})
        assert started.status_code == 400 and store.SERIES_BIBLE_FIELDS in started.text
        made = client.patch(f'/api/stories/{story.id}/series', json={'series_id': item.id, 'bible': True,
                                                                    'expected_revision': story.revision})
        assert made.status_code == 200 and made.json()['series_bible'] is True
        view = client.get(f'/api/stories/{story.id}').json()
        assert view['series']['bible'] is True and view['series']['number'] is None
        assert view['series']['status']['state'] == 'bible'
        back = client.patch(f'/api/stories/{story.id}/series', json={'series_id': item.id, 'number': 1, 'bible': False,
                                                                    'expected_revision': made.json()['revision']})
        assert back.status_code == 200 and back.json()['series_bible'] is False and back.json()['series_number'] == 1


@pytest.mark.req('SERIES-BIBLE-001')
def test_new_bible_endpoint_refuses_a_second_one(tmp_path):
    repo = Repository(tmp_path)
    item = store.create_series(repo, 'Сага')
    with client_for(tmp_path) as client:
        made = client.post(f'/api/series/{item.id}/bible', json={'title': 'Біблія світу: Сага'})
        assert made.status_code == 200 and made.json()['series_bible'] is True
        second = client.post(f'/api/series/{item.id}/bible', json={'title': 'Ще одна'})
        assert second.status_code == 400 and store.SERIES_BIBLE_TAKEN in second.text


@pytest.mark.req('SERIES-BIBLE-001')
def test_new_bible_needs_long_prose(tmp_path, store_edition):
    repo = Repository(tmp_path)
    item = store.create_series(repo, 'Сага')
    with client_for(tmp_path) as client:
        refused = client.post(f'/api/series/{item.id}/bible', json={'title': 'Біблія'})
    assert refused.status_code == 400 and 'довгою прозою' in refused.text
    assert not any(b.series_bible for b in store.series_books(repo, item.id))


@pytest.mark.req('SERIES-BIBLE-001')
def test_bible_status_names_its_summary(tmp_path):
    repo = Repository(tmp_path)
    item = store.create_series(repo, 'Сага')
    bible, _ = write_bible(repo, item, finished=False)
    status = series_status(repo, bible)
    assert status.state == 'bible' and status.summary == SUMMARY_NO_MEMORY
    other = store.create_series(repo, 'Інша')
    done, _ = write_bible(repo, other)
    assert series_status(repo, done).state == 'bible' and series_status(repo, done).summary is None


@pytest.mark.req('SERIES-BIBLE-001')
def test_series_screen_lists_the_bible_apart_from_the_axis(tmp_path):
    repo = Repository(tmp_path)
    item = store.create_series(repo, 'Сага')
    bible, _ = write_bible(repo, item)
    first, _ = write_book_one(repo, item)
    with client_for(tmp_path) as client:
        view = client.get(f'/api/series/{item.id}').json()
    assert view['bible'] == bible.id
    rows = {row['id']: row for row in view['books']}
    assert rows[bible.id]['bible'] is True and rows[bible.id]['number'] is None and rows[first.id]['bible'] is False
    assert bible.id not in view['placed'] + view['outside'] and view['placed'] == [first.id]
    repo.set_story_trashed(bible.id, repo.get_story(bible.id).revision, False)  # False: into the trash
    with client_for(tmp_path) as client:
        view = client.get(f'/api/series/{item.id}').json()
    assert view['bible'] == bible.id and bible.id not in view['placed'] + view['outside']
    assert {row['id']: row for row in view['books']}[bible.id]['trashed'] is True


@pytest.mark.req('SERIES-BIBLE-001')
def test_prequel_facts_mark_the_bible_records(tmp_path):
    repo = Repository(tmp_path)
    item = store.create_series(repo, 'Сага')
    write_bible(repo, item)
    write_book_one(repo, item)
    prequel, _ = book(repo, 'Приквел 2', written=False, cast=['A'])
    prequel = store.set_story_series(repo, prequel.id, item.id, 2, SeriesStart(offset='Рік -10', anchor=1), prequel.revision)
    with client_for(tmp_path) as client:
        facts = client.get(f'/api/stories/{prequel.id}/series/facts').json()['facts']
    marks = {f['text']: (f['bible'], f['decision']) for f in facts}
    assert marks['Магія коштує крові'] == (True, 'past') and marks['Сусід пішов'] == (False, 'future')


@pytest.mark.req('SERIES-BIBLE-001')
def test_mcp_get_story_shows_the_bible(tmp_path):
    repo = Repository(tmp_path)
    item = store.create_series(repo, 'Сага')
    bible, _ = write_bible(repo, item)
    first, _ = book(repo, 'Книга 1')
    first = store.set_story_series(repo, first.id, item.id, 1, None, first.revision)
    with client_for(tmp_path) as client:
        series = story_series(client.get(f'/api/stories/{bible.id}').json())
        book_series = story_series(client.get(f'/api/stories/{first.id}').json())
    assert (series['bible'], series['number'], series['status']) == (True, None, 'bible')
    assert (book_series['bible'], book_series['number']) == (False, 1)


@pytest.mark.req('SERIES-BIBLE-001')
def test_preamble_bible_line(tmp_path):
    assert cut_series_lines('Серія: Сага\nНомер: біблія\n')[1].bible is True
    lines = cut_series_lines('Series: Saga\nNumber: Bible\n')[1]
    assert (lines.bible, lines.number) == (True, None)
    assert cut_series_lines('Серія: Сага\nНомер: біблія\nПочаток: Рік 1, опора 1\n')[1:] == (None, True)
    assert cut_series_lines('Серія: Сага\nНомер: 2\n')[1].bible is False
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Світ'))
    story, warnings = run(repo, story, 'Серія: Сага\nНомер: біблія\n\n' + SCENES)
    assert story.series_bible is True and story.series_number is None
    assert warnings == [store.SERIES_CREATED.format(title='Сага')]
    other = repo.create_story(StoryCreate(title='Ще світ'))
    other, warnings = run(repo, other, 'Серія: Сага\nНомер: біблія\n\n' + SCENES)
    assert other.series_id is None and warnings == [store.SERIES_BIBLE_PLAN_TAKEN]


@pytest.mark.req('SERIES-BIBLE-001')
def test_bible_turned_book_takes_its_snapshot(tmp_path):
    repo = Repository(tmp_path)
    item = store.create_series(repo, 'Сага')
    write_book_one(repo, item)
    world = repo.create_story(StoryCreate(title='Світ'))
    world = store.set_story_series(repo, world.id, item.id, None, None, world.revision, bible=True)
    world = store.set_story_series(repo, world.id, item.id, 2, None, world.revision)
    assert world.series_bible is False and world.series_start_version_id is not None
