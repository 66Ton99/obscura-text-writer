"""DESKTOP-001-S08: external links from the Obscura window open in the default browser."""
import pytest
from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.web.app import create_app
from storygen.web.bridge_marker import BRIDGE_HEADER

BASE = 'http://127.0.0.1:8765'


class Window:
    def __init__(self):
        self.external = []

    def open_external(self, url):
        self.external.append(url)


def client(tmp_path, window=None):
    app = create_app(AppSettings(data_dir=tmp_path))
    if window is not None:
        app.state.app_window = window
    return TestClient(app, base_url=BASE)


@pytest.mark.req('DESKTOP-001')
def test_external_link_goes_to_the_window(tmp_path):
    window = Window()
    with client(tmp_path, window) as c:
        response = c.post('/api/app-window/open-external', json={'url': 'https://obscurawriter.com/report.html'})
    assert response.status_code == 204 and window.external == ['https://obscurawriter.com/report.html']


@pytest.mark.req('DESKTOP-001')
def test_without_the_desktop_window_the_route_does_not_exist(tmp_path):
    with client(tmp_path) as c:
        assert c.post('/api/app-window/open-external', json={'url': 'https://example.org'}).status_code == 404


@pytest.mark.req('DESKTOP-001')
@pytest.mark.parametrize('url', ['ftp://example.org/x', '/stories', 'javascript:alert(1)', 'file:///C:/Windows',
                                 'https://', 'mailto:a@b.c', ''])
def test_only_absolute_web_addresses_are_opened(tmp_path, url):
    window = Window()
    with client(tmp_path, window) as c:
        assert c.post('/api/app-window/open-external', json={'url': url}).status_code == 422
    assert window.external == []


@pytest.mark.req('DESKTOP-001')
def test_another_site_cannot_open_links(tmp_path):
    window = Window()
    with client(tmp_path, window) as c:
        response = c.post('/api/app-window/open-external', json={'url': 'https://example.org'},
                          headers={'Origin': 'https://evil.example'})
    assert response.status_code == 403 and window.external == []


@pytest.mark.req('DESKTOP-001')
def test_the_chat_cannot_open_links_on_the_authors_desktop(tmp_path):
    window = Window()
    with client(tmp_path, window) as c:
        response = c.post('/api/app-window/open-external', json={'url': 'https://example.org'}, headers={BRIDGE_HEADER: 'mcp'})
    assert response.status_code == 403 and window.external == []


@pytest.mark.req('DESKTOP-001')
def test_pages_load_the_link_script_only_in_the_window(tmp_path):
    with client(tmp_path, Window()) as c:
        assert '/static/app-window.js' in c.get('/').text
    with client(tmp_path / 'plain') as c:
        assert '/static/app-window.js' not in c.get('/').text
