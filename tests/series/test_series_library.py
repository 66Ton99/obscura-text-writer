"""SERIES-LIBRARY: the library groups the books of a series and labels their cards (neutral examples)."""
import re

from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.book.library import library_entries
from storygen.domain import StoryCreate
from storygen.storage import series as store
from storygen.web.app import create_app


def client_for(tmp_path):
    app = create_app(AppSettings(data_dir=tmp_path / 'data', env_file=tmp_path / 'absent.env'))
    return TestClient(app, base_url='http://127.0.0.1'), app.state.repo


def story(repo, title):
    return repo.create_story(StoryCreate(title=title))


def join(repo, item, created, number=None, bible=False):
    return store.set_story_series(repo, created.id, item.id, number, None, created.revision, bible=bible)


def shape(entries):
    return [e.story.title if e.story else (e.series.title, [b.title for b in e.books]) for e in entries]


def test_a_series_stands_where_its_newest_book_stands(tmp_path):
    # Newest first: the series takes the place of its newest active book; inside it the bible comes first, then the
    # books by number. A trashed book leaves the group, a series without active books is not shown.
    client, repo = client_for(tmp_path)
    item = store.create_series(repo, 'Сага')
    empty = store.create_series(repo, 'Порожня')
    second = story(repo, 'Друга')
    alone = story(repo, 'Окрема')
    first = story(repo, 'Перша')
    bible = story(repo, 'Світ')
    gone = story(repo, 'Викинута')
    newest = story(repo, 'Найновіша окрема')
    join(repo, item, second, 2)
    join(repo, item, first, 1)
    join(repo, item, bible, bible=True)
    gone = join(repo, item, gone, 3)
    repo.set_story_trashed(gone.id, gone.revision, False)
    lonely = join(repo, empty, story(repo, 'Сама'), 1)
    repo.set_story_trashed(lonely.id, lonely.revision, False)
    entries = library_entries(repo.list_stories(), store.list_series(repo))
    assert shape(entries) == ['Найновіша окрема', ('Сага', ['Світ', 'Перша', 'Друга']), 'Окрема']


def cards(page):
    return re.findall(r'<p class="card-series">(.*?)</p>', page)


def test_library_page_groups_and_labels_the_series_books(tmp_path):
    client, repo = client_for(tmp_path)
    item = store.create_series(repo, 'Сага')
    join(repo, item, story(repo, 'Перша'), 1)
    join(repo, item, story(repo, 'Світ'), bible=True)
    story(repo, 'Окрема')
    page = client.get('/', headers={'accept-language': 'uk'}).text
    group = re.search(r'<section class="library-series"[^>]*>(.*?)</section>', page, re.S)
    assert group and f'href="/series/{item.id}"' in group[1]
    assert 'Перша' in group[1] and 'Світ' in group[1] and 'Окрема' not in group[1]
    labels = [re.sub(r'<[^>]+>', '', c) for c in cards(page)]
    assert labels == ['Серія «Сага», біблія світу', 'Серія «Сага», книга 1']
    english = client.get('/', headers={'accept-language': 'en'}).text
    assert [re.sub(r'<[^>]+>', '', c) for c in cards(english)] == ['Series «Сага», world bible', 'Series «Сага», book 1']


def test_store_library_groups_without_a_series_link(tmp_path, store_edition):
    client, repo = client_for(tmp_path)
    item = store.create_series(repo, 'Сага')
    join(repo, item, story(repo, 'Перша'), 1)
    page = client.get('/').text
    assert '<section class="library-series"' in page and '/series/' not in page
    assert [re.sub(r'<[^>]+>', '', c) for c in cards(page)] == ['Серія «Сага», книга 1']
