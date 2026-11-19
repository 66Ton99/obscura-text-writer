"""DESKTOP-001-S07/S08: Obscura in its own window — Microsoft Edge in app mode with a profile of its own.

The window belongs to the Edge process started with `--user-data-dir=<data folder>/.window`. It is found by that
argument in the process command line rather than by the process Obscura started: a second launch with the same
profile only hands the address to the first Edge process and exits, and an Edge window may outlive a crashed Obscura.
Without Edge, or when anything here fails, the page opens in the default browser as before.
"""
import logging
import ntpath
import os
import re
import subprocess
import webbrowser
from pathlib import Path
from typing import Callable

from .storage.integrity import WINDOW_PROFILE as PROFILE_NAME  # one name for the window and for backups

logger = logging.getLogger(__name__)

_ARGUMENT = re.compile(r'(")?--user-data-dir=')


def profile_dir(data_dir: Path) -> Path:
    return Path(data_dir) / PROFILE_NAME


def launch_args(edge: Path, profile: Path, url: str) -> list[str]:
    return [str(edge), f'--user-data-dir={profile}', f'--app={url}', '--no-first-run', '--no-default-browser-check']


def _profile_values(command_line: str):
    for match in _ARGUMENT.finditer(command_line):
        rest = command_line[match.end():]
        if match.group(1):  # "--user-data-dir=C:\a b\.window": the whole argument is quoted
            yield rest.split('"', 1)[0]
        elif rest.startswith('"'):  # --user-data-dir="C:\a b\.window"
            yield rest[1:].split('"', 1)[0]
        else:
            yield re.match(r'\S*', rest).group(0)


def _same_path(a: str, b: str) -> bool:
    def canonical(value):
        return ntpath.normcase(ntpath.normpath(value.rstrip('\\/')))
    return bool(a) and canonical(a) == canonical(b)


def matches_profile(command_line: str, profile: Path) -> bool:
    """True when an Edge command line runs exactly this profile (case-insensitive, quoted or not)."""
    return any(_same_path(value, str(profile)) for value in _profile_values(command_line or ''))


def edge_path() -> Path | None:
    """msedge.exe from the App Paths registration (machine first, then user); None outside Windows or without Edge."""
    if os.name != 'nt':
        return None
    import winreg
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            with winreg.OpenKey(hive, r'SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe') as key:
                value = Path(winreg.QueryValueEx(key, '')[0].strip('"'))
        except OSError:
            continue
        if value.is_file():
            return value
    return None


class AppWindow:
    """show() brings the Obscura window forward or opens it; close() closes it; open_external() uses the browser."""

    def __init__(self, url: str, data_dir: Path, *, api=None, edge: Callable[[], Path | None] = edge_path,
                 fallback: Callable[[str], object] = webbrowser.open):
        self.url, self.profile = url, profile_dir(data_dir)
        self._api, self._edge, self._fallback = api, edge, fallback

    @property
    def api(self):
        if self._api is None:
            self._api = Win32Windows()
        return self._api

    def _windows(self) -> list[int]:
        return [hwnd for pid in self.api.profile_pids(self.profile) for hwnd in self.api.visible_windows(pid)]

    def show(self) -> None:
        try:
            edge = self._edge()
            if edge is None:
                self._fallback(self.url)
                return
            windows = self._windows()
            if windows:
                hwnd = windows[0]
                if self.api.is_minimized(hwnd):
                    self.api.restore(hwnd)
                self.api.focus(hwnd)
                return
            self.profile.mkdir(parents=True, exist_ok=True)
            self.api.hide_folder(self.profile)
            self.api.launch(launch_args(edge, self.profile, self.url))
        except Exception as error:  # noqa: BLE001 - the browser is the fallback for any failure of the window
            logger.warning('Вікно Obscura не відкрилося (%s); сторінка відкривається у браузері', type(error).__name__)
            self._fallback(self.url)

    def close(self) -> None:
        try:
            if self._edge() is None:
                return
            for hwnd in self._windows():
                self.api.close_window(hwnd)
        except Exception as error:  # noqa: BLE001 - "Quit" must finish even if the window cannot be closed
            logger.warning('Вікно Obscura не закрилося: %s', type(error).__name__)

    def open_external(self, url: str) -> None:
        self._fallback(url)


class Win32Windows:
    """The only place with ctypes for the window: processes of the profile, their windows, launch."""

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    PROCESS_COMMAND_LINE_INFORMATION = 60
    TH32CS_SNAPPROCESS = 0x2
    SW_RESTORE = 9
    WM_CLOSE = 0x0010
    FILE_ATTRIBUTE_HIDDEN = 0x2

    def __init__(self):
        import ctypes
        from ctypes import wintypes
        self.ctypes, self.wintypes = ctypes, wintypes
        self.user32 = ctypes.WinDLL('user32', use_last_error=True)
        self.kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
        self.ntdll = ctypes.WinDLL('ntdll')

        class PROCESSENTRY32W(ctypes.Structure):
            _fields_ = [('dwSize', wintypes.DWORD), ('cntUsage', wintypes.DWORD), ('th32ProcessID', wintypes.DWORD),
                        ('th32DefaultHeapID', ctypes.c_size_t), ('th32ModuleID', wintypes.DWORD),
                        ('cntThreads', wintypes.DWORD), ('th32ParentProcessID', wintypes.DWORD),
                        ('pcPriClassBase', ctypes.c_long), ('dwFlags', wintypes.DWORD),
                        ('szExeFile', wintypes.WCHAR * 260)]

        class UNICODE_STRING(ctypes.Structure):
            _fields_ = [('Length', wintypes.USHORT), ('MaximumLength', wintypes.USHORT), ('Buffer', wintypes.LPWSTR)]
        self.PROCESSENTRY32W, self.UNICODE_STRING = PROCESSENTRY32W, UNICODE_STRING
        k = self.kernel32
        k.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
        k.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
        k.Process32FirstW.argtypes = k.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
        k.OpenProcess.restype = wintypes.HANDLE
        k.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        k.CloseHandle.argtypes = [wintypes.HANDLE]
        k.GetFileAttributesW.argtypes = [wintypes.LPCWSTR]
        k.GetFileAttributesW.restype = wintypes.DWORD
        k.SetFileAttributesW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD]
        self.ntdll.NtQueryInformationProcess.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.ULONG,
                                                         ctypes.POINTER(wintypes.ULONG)]
        self.ntdll.NtQueryInformationProcess.restype = ctypes.c_long
        u = self.user32
        self.ENUM = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        u.EnumWindows.argtypes = [self.ENUM, wintypes.LPARAM]
        u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        for name in ('IsWindowVisible', 'IsIconic', 'SetForegroundWindow'):
            getattr(u, name).argtypes = [wintypes.HWND]
        u.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
        u.GetWindow.restype = wintypes.HWND
        u.GetClassNameW.argtypes = u.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        u.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        u.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]

    def _edge_pids(self) -> list[int]:
        snapshot = self.kernel32.CreateToolhelp32Snapshot(self.TH32CS_SNAPPROCESS, 0)
        if not snapshot or snapshot == self.wintypes.HANDLE(-1).value:
            raise OSError('CreateToolhelp32Snapshot')
        pids = []
        try:
            entry = self.PROCESSENTRY32W(dwSize=self.ctypes.sizeof(self.PROCESSENTRY32W))
            ok = self.kernel32.Process32FirstW(snapshot, self.ctypes.byref(entry))
            while ok:
                if entry.szExeFile.lower() == 'msedge.exe':
                    pids.append(entry.th32ProcessID)
                ok = self.kernel32.Process32NextW(snapshot, self.ctypes.byref(entry))
        finally:
            self.kernel32.CloseHandle(snapshot)
        return pids

    def command_line(self, pid: int) -> str:
        handle = self.kernel32.OpenProcess(self.PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return ''
        try:
            size = self.wintypes.ULONG(0)
            self.ntdll.NtQueryInformationProcess(handle, self.PROCESS_COMMAND_LINE_INFORMATION, None, 0,
                                                 self.ctypes.byref(size))
            if not size.value:
                return ''
            buffer = self.ctypes.create_string_buffer(size.value)
            if self.ntdll.NtQueryInformationProcess(handle, self.PROCESS_COMMAND_LINE_INFORMATION, buffer, size.value,
                                                    self.ctypes.byref(size)) != 0:
                return ''
            text = self.UNICODE_STRING.from_buffer(buffer)
            return self.ctypes.wstring_at(text.Buffer, text.Length // 2) if text.Buffer else ''
        finally:
            self.kernel32.CloseHandle(handle)

    def profile_pids(self, profile: Path) -> list[int]:
        return [pid for pid in self._edge_pids() if matches_profile(self.command_line(pid), profile)]

    def visible_windows(self, pid: int) -> list[int]:
        found = []
        u, buffer = self.user32, self.ctypes.create_unicode_buffer(256)

        def visit(hwnd, _):
            owner = self.wintypes.DWORD()
            u.GetWindowThreadProcessId(hwnd, self.ctypes.byref(owner))
            if owner.value == pid and u.IsWindowVisible(hwnd) and not u.GetWindow(hwnd, 4):  # GW_OWNER: top level only
                u.GetClassNameW(hwnd, buffer, 256)
                if buffer.value == 'Chrome_WidgetWin_1' and u.GetWindowTextW(hwnd, buffer, 256):
                    found.append(hwnd)
            return True
        u.EnumWindows(self.ENUM(visit), 0)
        return found

    def is_minimized(self, hwnd) -> bool:
        return bool(self.user32.IsIconic(hwnd))

    def restore(self, hwnd) -> None:
        self.user32.ShowWindow(hwnd, self.SW_RESTORE)

    def focus(self, hwnd) -> None:
        self.user32.SetForegroundWindow(hwnd)

    def close_window(self, hwnd) -> None:
        self.user32.PostMessageW(hwnd, self.WM_CLOSE, 0, 0)

    def launch(self, args: list[str]) -> None:
        subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         close_fds=True)

    def hide_folder(self, path: Path) -> None:
        attributes = self.kernel32.GetFileAttributesW(str(path))
        if attributes != 0xFFFFFFFF:
            self.kernel32.SetFileAttributesW(str(path), attributes | self.FILE_ATTRIBUTE_HIDDEN)
