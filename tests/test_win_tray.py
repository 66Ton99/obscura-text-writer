"""DESKTOP-001-S04: the own Win32 tray icon. The logic runs against a fake API; no test shows a real icon in the tray."""
import io
import logging
import os
import queue
import threading

import pytest

from storygen import win_tray
from storygen.win_tray import CALLBACK, NIN_KEYSELECT, NIN_SELECT, WM_CONTEXTMENU, NotifyIcon, TrayUnavailable, icon_xy

HWND, HICON, TASKBAR = 7, 99, 0xC0DE


class FakeApi:
    def __init__(self, add=True, version=True, choice=0):
        self.calls, self.add, self.version, self.choice = [], add, version, choice
        self.procedure, self.messages, self.quit = None, queue.Queue(), False
        self.on_menu = None

    def register_message(self, name):
        self.calls.append(('register_message', name))
        return TASKBAR

    def register_class(self, name, procedure):
        self.calls.append(('register_class', name))
        self.procedure = procedure

    def unregister_class(self, name):
        self.calls.append(('unregister_class', name))

    def create_window(self, class_name):
        self.calls.append(('create_window', class_name))
        return HWND

    def destroy_window(self, hwnd):
        self.calls.append(('destroy_window', hwnd))
        self.procedure(hwnd, win_tray.WM_DESTROY, 0, 0)

    def small_icon_size(self):
        return 20

    def icon_from_png(self, data, size):
        self.calls.append(('icon_from_png', data, size))
        return HICON

    def destroy_icon(self, hicon):
        self.calls.append(('destroy_icon', hicon))

    def add_icon(self, hwnd, hicon, tip):
        self.calls.append(('add_icon', hwnd, hicon, tip))
        return self.add

    def set_version(self, hwnd):
        self.calls.append(('set_version', hwnd))
        return self.version

    def delete_icon(self, hwnd):
        self.calls.append(('delete_icon', hwnd))

    def popup_menu(self, hwnd, labels, default, x, y):
        self.calls.append(('popup_menu', hwnd, labels, default, x, y))
        if self.on_menu:
            self.on_menu()
        return self.choice

    def post(self, hwnd, message):
        self.calls.append(('post', hwnd, message))
        self.messages.put((hwnd, message, 0, 0))

    def run_loop(self):
        while not self.quit:
            hwnd, message, wparam, lparam = self.messages.get(timeout=5)
            self.procedure(hwnd, message, wparam, lparam)

    def post_quit(self):
        self.calls.append(('post_quit',))
        self.quit = True

    def names(self):
        return [call[0] for call in self.calls]


def make(api, actions=None):
    actions = actions if actions is not None else []
    items = [(label, (lambda name: lambda: actions.append(name))(label)) for label in ('A', 'B', 'C')]
    return NotifyIcon(api, 'Obscura', lambda size: b'png%d' % size, items), actions


def started(icon, api):
    """Run the icon in a thread until its window exists; the caller ends it with close()."""
    thread = threading.Thread(target=icon.run, daemon=True)
    thread.start()
    for _ in range(500):
        if 'set_version' in api.names():
            break
        threading.Event().wait(0.01)
    return thread


@pytest.mark.req('DESKTOP-001')
def test_start_adds_the_icon_with_version_4():
    api = FakeApi()
    icon, _ = make(api)
    thread = started(icon, api)
    assert ('icon_from_png', b'png20', 20) in api.calls
    assert api.calls.index(('add_icon', HWND, HICON, 'Obscura')) < api.calls.index(('set_version', HWND))
    icon.close()
    thread.join(5)
    assert not thread.is_alive()


@pytest.mark.req('DESKTOP-001')
def test_select_and_enter_run_the_default_action():
    icon, actions = make(FakeApi())
    assert icon.handle(HWND, CALLBACK, 0, NIN_SELECT) == 0
    icon.handle(HWND, CALLBACK, 0, NIN_KEYSELECT)
    icon.handle(HWND, CALLBACK, 0, 0x0200)
    assert actions == ['A', 'A']


@pytest.mark.req('DESKTOP-001')
def test_context_menu_opens_at_the_icon_and_runs_the_choice():
    api = FakeApi(choice=2)
    icon, actions = make(api)
    wparam = (0xFFFF & -1200) | (300 << 16)
    icon.handle(HWND, CALLBACK, wparam, WM_CONTEXTMENU)
    assert ('popup_menu', HWND, ['A', 'B', 'C'], 0, -1200, 300) in api.calls
    assert actions == ['B']


@pytest.mark.req('DESKTOP-001')
def test_menu_is_not_reopened_while_shown():
    api = FakeApi()
    icon, _ = make(api)
    api.on_menu = lambda: icon.handle(HWND, CALLBACK, 0, WM_CONTEXTMENU)
    icon.handle(HWND, CALLBACK, 0, WM_CONTEXTMENU)
    assert api.names().count('popup_menu') == 1


@pytest.mark.req('DESKTOP-001')
def test_taskbar_restart_adds_the_same_icon_again():
    api = FakeApi()
    icon, _ = make(api)
    thread = started(icon, api)
    icon.handle(HWND, TASKBAR, 0, 0)
    assert api.names().count('add_icon') == 2 and api.names().count('set_version') == 2
    assert all(call[2] == HICON for call in api.calls if call[0] == 'add_icon')
    assert api.names().count('icon_from_png') == 1
    icon.close()
    thread.join(5)


@pytest.mark.req('DESKTOP-001')
def test_close_from_another_thread_ends_the_loop_and_frees_everything():
    api = FakeApi()
    icon, _ = make(api)
    thread = started(icon, api)
    icon.close()
    thread.join(5)
    assert not thread.is_alive()
    names = api.names()
    for name in ('delete_icon', 'destroy_window', 'destroy_icon', 'unregister_class'):
        assert name in names
    assert names.count('destroy_window') == 1 and names.count('delete_icon') == 1 and ('destroy_icon', HICON) in api.calls


@pytest.mark.req('DESKTOP-001')
def test_close_before_start_after_end_and_twice_is_harmless():
    api = FakeApi()
    icon, _ = make(api)
    icon.close()
    icon.close()
    assert 'post' not in api.names()
    thread = threading.Thread(target=icon.run, daemon=True)
    thread.start()
    thread.join(5)
    assert not thread.is_alive(), 'run() after close() must end on its own'
    assert api.names().count('post') == 1 and api.names().count('delete_icon') == 1
    other = FakeApi()
    icon, _ = make(other)
    thread = started(icon, other)
    icon.close()
    thread.join(5)
    posts = other.names().count('post')
    icon.close()
    assert other.names().count('post') == posts


@pytest.mark.req('DESKTOP-001')
@pytest.mark.parametrize('failing,deletes', [('add', 0), ('version', 1)])
def test_failed_add_or_version_is_unavailable_and_cleans_up(failing, deletes):
    api = FakeApi(add=failing != 'add', version=failing != 'version')
    icon, _ = make(api)
    with pytest.raises(TrayUnavailable):
        icon.run()
    names = api.names()
    assert ('destroy_icon', HICON) in api.calls and 'destroy_window' in names and 'unregister_class' in names
    assert names.count('delete_icon') == deletes  # an icon that was never added is not deleted


@pytest.mark.req('DESKTOP-001')
def test_action_error_is_logged_and_the_icon_keeps_running(caplog):
    calls = []

    def broken():
        calls.append(1)
        raise OSError('no browser')
    icon = NotifyIcon(FakeApi(), 'Obscura', lambda size: b'', [('Open', broken)])
    with caplog.at_level(logging.ERROR, logger='storygen.win_tray'):
        icon.handle(HWND, CALLBACK, 0, NIN_SELECT)
        icon.handle(HWND, CALLBACK, 0, NIN_SELECT)
    assert calls == [1, 1] and caplog.records


@pytest.mark.req('DESKTOP-001')
def test_icon_xy_is_signed():
    assert icon_xy((0xFFFF & -5) | ((0xFFFF & -7) << 16)) == (-5, -7)
    assert icon_xy(100 | (200 << 16)) == (100, 200)


@pytest.mark.req('DESKTOP-001')
@pytest.mark.skipif(os.name != 'nt', reason='Windows API')
def test_real_api_builds_and_frees_an_icon():
    from PIL import Image
    buffer = io.BytesIO()
    Image.new('RGBA', (16, 16), (92, 26, 43, 255)).save(buffer, format='PNG')
    api = win_tray.Win32Api()
    hicon = api.icon_from_png(buffer.getvalue(), 16)
    assert hicon
    api.destroy_icon(hicon)


@pytest.mark.req('DESKTOP-001')
@pytest.mark.skipif(os.name != 'nt', reason='Windows API')
def test_icon_asks_for_the_standard_tooltip():
    """Version 4 hides the standard tooltip unless NIF_SHOWTIP is set: the hover showed an empty box."""
    data = win_tray.Win32Api()._data(0, None, 'Obscura')
    assert data.uFlags & win_tray.NIF_SHOWTIP and data.szTip == 'Obscura'
