"""DESKTOP-001-S07: the Obscura window — Edge in app mode with its own profile, shown again instead of a new tab."""
from pathlib import Path

import pytest

from storygen import app_window
from storygen.app_window import AppWindow, launch_args, matches_profile, profile_dir

URL = 'http://127.0.0.1:8765'
EDGE = Path(r'C:\Edge\msedge.exe')


class FakeApi:
    """Processes of the profile and their windows, as the Windows API would report them."""

    def __init__(self, processes=None, minimized=()):
        self.processes = dict(processes or {})  # pid -> [hwnd, ...]
        self.minimized = set(minimized)
        self.calls = []
        self.launch_error = None

    def profile_pids(self, profile):
        self.calls.append(('pids', profile))
        return list(self.processes)

    def visible_windows(self, pid):
        return list(self.processes.get(pid, []))

    def is_minimized(self, hwnd):
        return hwnd in self.minimized

    def restore(self, hwnd):
        self.calls.append(('restore', hwnd))

    def focus(self, hwnd):
        self.calls.append(('focus', hwnd))

    def close_window(self, hwnd):
        self.calls.append(('close', hwnd))

    def launch(self, args):
        if self.launch_error:
            raise self.launch_error
        self.calls.append(('launch', args))

    def hide_folder(self, path):
        self.calls.append(('hide', path))


def make(tmp_path, api, edge=EDGE):
    opened = []
    window = AppWindow(URL, tmp_path / 'data', api=api, edge=lambda: edge, fallback=opened.append)
    return window, opened


def actions(api):
    return [call for call in api.calls if call[0] != 'pids']


@pytest.mark.req('DESKTOP-001')
def test_profile_lives_in_the_data_folder(tmp_path):
    assert profile_dir(tmp_path) == tmp_path / '.window'


@pytest.mark.req('DESKTOP-001')
def test_first_show_launches_edge_in_app_mode_with_the_profile(tmp_path):
    api = FakeApi()
    window, opened = make(tmp_path, api)
    window.show()
    profile = tmp_path / 'data' / '.window'
    assert actions(api) == [('hide', profile), ('launch', [str(EDGE), f'--user-data-dir={profile}', f'--app={URL}',
                                                           '--no-first-run', '--no-default-browser-check'])]
    assert profile.is_dir() and opened == []


@pytest.mark.req('DESKTOP-001')
def test_open_window_is_brought_forward_instead_of_a_second_one(tmp_path):
    api = FakeApi({41: [7]})
    window, opened = make(tmp_path, api)
    window.show()
    assert actions(api) == [('focus', 7)] and opened == []


@pytest.mark.req('DESKTOP-001')
def test_minimized_window_is_restored_then_focused(tmp_path):
    api = FakeApi({41: [7]}, minimized={7})
    window, _ = make(tmp_path, api)
    window.show()
    assert actions(api) == [('restore', 7), ('focus', 7)]


@pytest.mark.req('DESKTOP-001')
def test_profile_process_without_windows_gets_a_new_window(tmp_path):
    api = FakeApi({41: []})
    window, _ = make(tmp_path, api)
    window.show()
    assert [call[0] for call in actions(api)] == ['hide', 'launch']


@pytest.mark.req('DESKTOP-001')
def test_window_of_the_process_that_has_one_is_shown(tmp_path):
    api = FakeApi({40: [], 41: [9, 10]})
    window, _ = make(tmp_path, api)
    window.show()
    assert actions(api) == [('focus', 9)]


@pytest.mark.req('DESKTOP-001')
def test_without_edge_the_page_opens_in_the_browser(tmp_path):
    api = FakeApi()
    window, opened = make(tmp_path, api, edge=None)
    window.show()
    assert opened == [URL] and actions(api) == []


@pytest.mark.req('DESKTOP-001')
def test_failed_launch_falls_back_to_the_browser(tmp_path, caplog):
    api = FakeApi()
    api.launch_error = OSError('blocked')
    window, opened = make(tmp_path, api)
    window.show()
    assert opened == [URL] and 'OSError' in caplog.text


@pytest.mark.req('DESKTOP-001')
def test_failed_window_lookup_falls_back_to_the_browser(tmp_path):
    api = FakeApi()
    api.profile_pids = lambda profile: (_ for _ in ()).throw(OSError('denied'))
    window, opened = make(tmp_path, api)
    window.show()
    assert opened == [URL]


@pytest.mark.req('DESKTOP-001')
def test_close_closes_every_window_of_the_profile(tmp_path):
    api = FakeApi({40: [3], 41: [9, 10]})
    window, _ = make(tmp_path, api)
    window.close()
    assert actions(api) == [('close', 3), ('close', 9), ('close', 10)]


@pytest.mark.req('DESKTOP-001')
def test_close_never_raises(tmp_path):
    api = FakeApi()
    api.profile_pids = lambda profile: (_ for _ in ()).throw(OSError('denied'))
    window, _ = make(tmp_path, api)
    window.close()


@pytest.mark.req('DESKTOP-001')
def test_external_links_go_to_the_default_browser(tmp_path):
    api = FakeApi({41: [7]})
    window, opened = make(tmp_path, api)
    window.open_external('https://obscurawriter.com/report.html')
    assert opened == ['https://obscurawriter.com/report.html'] and actions(api) == []


@pytest.mark.req('DESKTOP-001')
@pytest.mark.parametrize('command_line', [
    r'"C:\Edge\msedge.exe" --user-data-dir=C:\Users\Анна\Obscura\.window --app=http://127.0.0.1:8765',
    r'"C:\Edge\msedge.exe" "--user-data-dir=C:\Users\Анна\Obscura\.window" --no-first-run',
    r'"C:\Edge\msedge.exe" --user-data-dir="c:\users\анна\obscura\.window\" --flag',
])
def test_command_line_of_the_profile_matches(command_line):
    assert matches_profile(command_line, Path(r'C:\Users\Анна\Obscura\.window'))


@pytest.mark.req('DESKTOP-001')
@pytest.mark.parametrize('command_line', [
    r'"C:\Edge\msedge.exe" "--user-data-dir=C:\Users\Anna Smith\Obscura\.window" --app=x',
    r'"C:\Edge\msedge.exe" --user-data-dir="C:\Users\Anna Smith\Obscura\.window" --app=x',
])
def test_profile_path_with_a_space_matches(command_line):
    assert matches_profile(command_line, Path(r'C:\Users\Anna Smith\Obscura\.window'))


@pytest.mark.req('DESKTOP-001')
@pytest.mark.parametrize('command_line', [
    r'"C:\Edge\msedge.exe" --user-data-dir=C:\Users\Анна\Obscura\.window2',
    r'"C:\Edge\msedge.exe" --user-data-dir=C:\Users\Анна\Obscura\.window\sub',
    r'"C:\Edge\msedge.exe" --app=http://127.0.0.1:8765',
    r'"C:\Edge\msedge.exe" --type=renderer --user-data-dir=D:\Other',
    '',
])
def test_other_command_lines_do_not_match(command_line):
    assert not matches_profile(command_line, Path(r'C:\Users\Анна\Obscura\.window'))


def test_launch_args_are_exactly_the_documented_flags(tmp_path):
    assert launch_args(EDGE, tmp_path, URL) == [str(EDGE), f'--user-data-dir={tmp_path}', f'--app={URL}',
                                                '--no-first-run', '--no-default-browser-check']


def test_edge_path_is_none_outside_windows(monkeypatch):
    monkeypatch.setattr(app_window.os, 'name', 'posix')
    assert app_window.edge_path() is None
