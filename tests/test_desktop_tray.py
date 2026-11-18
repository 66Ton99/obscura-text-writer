"""DESKTOP-001-S04: tray menu of the installed build."""
import io
import threading
import time

import pytest

from storygen import desktop, desktop_tray, win_tray
from storygen.desktop_tray import TrayUnavailable, menu_items, run_tray


def labels(items):
    return [label for label, _ in items]


def test_menu_labels_order_and_actions(tmp_path):
    calls = []
    data, backups = tmp_path / 'Obscura', tmp_path / 'Obscura-backups'
    data.mkdir()
    items = menu_items('http://127.0.0.1:8765', data, backups, lambda: calls.append('stop'),
                       opener=lambda url: calls.append(('open', url)), reveal=lambda path: calls.append(('reveal', path)), locale='uk')
    assert labels(items) == ['Відкрити Obscura', 'Тека творів', 'Вийти']
    for _, action in items:
        action()
    assert calls == [('open', 'http://127.0.0.1:8765'), ('reveal', data), 'stop']
    english = menu_items('u', data, backups, lambda: None, locale='en')
    assert labels(english) == ['Open Obscura', 'Stories folder', 'Quit']


def test_backups_item_appears_once_there_are_backups(tmp_path):
    calls = []
    data, backups = tmp_path / 'Obscura', tmp_path / 'Obscura-backups'
    backups.mkdir()
    items = menu_items('u', data, backups, lambda: None, reveal=calls.append, locale='uk')
    assert labels(items) == ['Відкрити Obscura', 'Тека творів', 'Резервні копії', 'Вийти']
    items[2][1]()
    assert calls == [backups]
    assert labels(menu_items('u', data, backups, lambda: None, locale='en'))[2] == 'Backups'


@pytest.mark.parametrize('name,expected', [('Ukrainian_Ukraine', 'uk'), ('uk_UA', 'uk'), ('English_United States', 'en'),
                                           ('pl_PL', 'en'), (None, 'en')])
def test_menu_language_follows_the_system(monkeypatch, name, expected):
    monkeypatch.setattr(desktop_tray, '_windows_ui_langid', lambda: None)
    monkeypatch.setattr(desktop_tray.locale, 'getlocale', lambda: (name, 'cp1251'))
    assert desktop_tray.system_locale() == expected


class RecordingIcon:
    """Stands in for win_tray.NotifyIcon: records what run_tray builds and presses "Quit" twice from run()."""
    made = []

    def __init__(self, api, title, icon_png, items):
        self.api, self.title, self.icon_png, self.items, self.events = api, title, icon_png, items, []
        RecordingIcon.made.append(self)

    def run(self):
        self.items[-1][1]()
        self.items[-1][1]()

    def close(self):
        self.events.append('close')


def test_run_tray_shows_the_menu_and_quit_stops_then_closes(tmp_path, monkeypatch):
    RecordingIcon.made = []
    monkeypatch.setattr(desktop_tray.os, 'name', 'nt')
    monkeypatch.setattr(desktop_tray, '_api_factory', lambda: 'api')
    monkeypatch.setattr(win_tray, 'NotifyIcon', RecordingIcon)
    monkeypatch.setattr(desktop_tray, 'system_locale', lambda: 'uk')
    run_tray('http://127.0.0.1:1', tmp_path, tmp_path / 'none', lambda: RecordingIcon.made[0].events.append('stop'))
    icon = RecordingIcon.made[0]
    assert icon.api == 'api' and icon.title == 'Obscura'
    assert labels(icon.items) == ['Відкрити Obscura', 'Тека творів', 'Вийти']
    assert icon.events == ['stop', 'close']


def test_no_tray_outside_windows(monkeypatch, tmp_path):
    monkeypatch.setattr(desktop_tray.os, 'name', 'posix')
    with pytest.raises(TrayUnavailable):
        run_tray('u', tmp_path, tmp_path, lambda: None)


def test_icon_png_is_a_png_of_the_requested_size():
    from PIL import Image
    image = Image.open(io.BytesIO(desktop_tray.icon_png(24)))
    assert image.format == 'PNG' and image.size == (24, 24) and image.mode == 'RGBA'


def unavailable():
    raise TrayUnavailable()


@pytest.mark.loopback
def test_launcher_without_a_tray_keeps_running_and_logs_it(monkeypatch, tmp_path):
    monkeypatch.setattr(desktop_tray, '_api_factory', unavailable)
    servers = []

    def serve(app, port):
        servers.append(desktop.uvicorn_server(app, port))
        return servers[0]
    result = {}
    data = tmp_path / 'data'
    thread = threading.Thread(target=lambda: result.update(code=desktop.main(['--data-dir', str(data), '--no-browser'], serve=serve)), daemon=True)
    thread.start()
    deadline = time.time() + 30
    while time.time() < deadline and not (servers and servers[0].started and (data / 'server.json').exists()):
        time.sleep(0.05)
    time.sleep(0.3)
    assert thread.is_alive(), 'the launcher must keep serving without a tray'
    servers[0].should_exit = True
    thread.join(30)
    assert result == {'code': 0}
    assert 'Значок у треї недоступний' in (data / 'logs' / 'obscura.log').read_text(encoding='utf-8')


def test_tray_language_follows_the_windows_ui_language(monkeypatch):
    assert desktop_tray.ui_language(0x0422) == 'uk'
    assert desktop_tray.ui_language(0x0409) == 'en'
    assert desktop_tray.ui_language(0x0415) == 'en'
    # A Ukrainian Windows interface wins over a regional format that says otherwise.
    monkeypatch.setattr(desktop_tray, '_windows_ui_langid', lambda: 0x0422)
    monkeypatch.setattr(desktop_tray.locale, 'getlocale', lambda: ('English_United States', 'cp1252'))
    assert desktop_tray.system_locale() == 'uk'
