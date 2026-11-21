"""DESKTOP-001-S04: the tray icon on the Windows API through ctypes, without third-party libraries.

`Win32Api` is the only place that touches ctypes; `NotifyIcon` holds the window-procedure logic and is tested with a fake API.
Tray events arrive as one callback message (`CALLBACK`): the event code is in LOWORD(lParam), the icon position (version 4)
in wParam. The hidden window is an ordinary invisible top-level window: a message-only window never receives the broadcast
`TaskbarCreated`, after which the icon must be added again.
"""
import ctypes
import logging
import os
import threading
from typing import Callable

logger = logging.getLogger(__name__)

CLASS_NAME = 'ObscuraTray'
WM_NULL, WM_DESTROY, WM_CLOSE, WM_CONTEXTMENU = 0x0000, 0x0002, 0x0010, 0x007B
CALLBACK = 0x8001  # WM_APP + 1
NIN_SELECT, NIN_KEYSELECT = 0x0400, 0x0401
NIM_ADD, NIM_DELETE, NIM_SETVERSION = 0, 2, 4
NIF_MESSAGE, NIF_ICON, NIF_TIP, NIF_SHOWTIP = 0x1, 0x2, 0x4, 0x80  # version 4 hides the tip without NIF_SHOWTIP
NOTIFYICON_VERSION_4 = 4
ERROR_CLASS_ALREADY_EXISTS = 1410
SM_CXSMICON = 49
TPM_RIGHTBUTTON, TPM_NONOTIFY, TPM_RETURNCMD = 0x0002, 0x0080, 0x0100


class TrayUnavailable(RuntimeError):
    """There is no tray to show the icon in: not Windows, or the Windows API refused."""


def icon_xy(wparam: int) -> tuple[int, int]:
    """Screen coordinates of the icon from a version-4 callback; signed, for monitors left of or above the primary one."""
    def signed(value: int) -> int:
        return value - 0x10000 if value >= 0x8000 else value
    return signed(wparam & 0xFFFF), signed((wparam >> 16) & 0xFFFF)


class NotifyIcon:
    """One tray icon with a menu; `items[0]` is the default action (click, Enter)."""

    def __init__(self, api, title: str, icon_png: Callable[[int], bytes], items: list[tuple[str, Callable[[], None]]]):
        self._api, self._title, self._icon_png, self._items = api, title, icon_png, list(items)
        self._lock = threading.Lock()
        self._hwnd = None
        self._hicon = None
        self._taskbar = None
        self._closing = self._ended = self._destroyed = self._menu_open = self._added = False

    def run(self) -> None:
        """Show the icon and block until the window is closed; TrayUnavailable when the icon cannot be shown."""
        api = self._api
        try:
            self._taskbar = api.register_message('TaskbarCreated')
            api.register_class(CLASS_NAME, self.handle)
            try:
                hwnd = api.create_window(CLASS_NAME)
                with self._lock:
                    self._hwnd = hwnd
                    closing = self._closing
                try:
                    size = api.small_icon_size()
                    self._hicon = api.icon_from_png(self._icon_png(size), size)
                    if not self._show(hwnd):
                        raise TrayUnavailable()
                    if closing:
                        api.post(hwnd, WM_CLOSE)
                    api.run_loop()
                finally:
                    with self._lock:
                        self._ended, self._hwnd = True, None
                    self._hide(hwnd)
                    if not self._destroyed:
                        api.destroy_window(hwnd)
                    if self._hicon:
                        api.destroy_icon(self._hicon)
                        self._hicon = None
            finally:
                api.unregister_class(CLASS_NAME)
        finally:
            with self._lock:
                self._ended = True

    def close(self) -> None:
        """End `run` from any thread; harmless before the start, after the end and when repeated."""
        with self._lock:
            if self._ended or self._closing:
                return
            self._closing = True
            hwnd = self._hwnd
        if hwnd is not None:
            self._api.post(hwnd, WM_CLOSE)

    def handle(self, hwnd: int, message: int, wparam: int, lparam: int) -> int | None:
        """The window procedure; None hands the message to DefWindowProc."""
        if message == CALLBACK:
            code = lparam & 0xFFFF
            if code in (NIN_SELECT, NIN_KEYSELECT):
                self._run(0)
            elif code == WM_CONTEXTMENU:
                self._menu(hwnd, wparam)
            return 0
        if self._taskbar and message == self._taskbar:
            self._show(hwnd)
            return 0
        if message == WM_CLOSE:
            self._hide(hwnd)
            self._api.destroy_window(hwnd)
            return 0
        if message == WM_DESTROY:
            self._destroyed = True
            self._api.post_quit()
            return 0
        return None

    def _show(self, hwnd) -> bool:
        if not self._api.add_icon(hwnd, self._hicon, self._title):
            return False
        self._added = True
        if not self._api.set_version(hwnd):
            self._hide(hwnd)
            return False
        return True

    def _hide(self, hwnd) -> None:
        # NIM_DELETE only for an icon that is in the tray: once on close, never for an icon that was not added.
        if self._added:
            self._added = False
            self._api.delete_icon(hwnd)

    def _menu(self, hwnd, wparam) -> None:
        if self._menu_open:  # TrackPopupMenuEx runs a modal loop: a second right click must not nest menus
            return
        self._menu_open = True
        try:
            choice = self._api.popup_menu(hwnd, [label for label, _ in self._items], 0, *icon_xy(wparam))
        finally:
            self._menu_open = False
        if 1 <= choice <= len(self._items):
            self._run(choice - 1)

    def _run(self, index: int) -> None:
        try:
            self._items[index][1]()
        except Exception:
            logger.exception('Tray menu action "%s" failed', self._items[index][0])


class Win32Api:
    """Thin ctypes layer over user32/shell32/kernel32 for one notify icon."""

    def __init__(self):
        if os.name != 'nt':
            raise TrayUnavailable()
        from ctypes import wintypes as w
        try:
            self._user32 = ctypes.WinDLL('user32', use_last_error=True)
            self._shell32 = ctypes.WinDLL('shell32', use_last_error=True)
            kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
            self._declare(w, kernel32)
            self._hinstance = kernel32.GetModuleHandleW(None)
        except (OSError, AttributeError):
            raise TrayUnavailable() from None
        self._w = w
        self._procedures = {}

    def _declare(self, w, kernel32) -> None:
        u, s = self._user32, self._shell32
        lresult = ctypes.c_ssize_t
        self.WNDPROC = ctypes.WINFUNCTYPE(lresult, w.HWND, w.UINT, w.WPARAM, w.LPARAM)

        class WNDCLASS(ctypes.Structure):
            _fields_ = [('style', w.UINT), ('lpfnWndProc', self.WNDPROC), ('cbClsExtra', ctypes.c_int),
                        ('cbWndExtra', ctypes.c_int), ('hInstance', w.HINSTANCE), ('hIcon', w.HICON), ('hCursor', w.HANDLE),
                        ('hbrBackground', w.HBRUSH), ('lpszMenuName', w.LPCWSTR), ('lpszClassName', w.LPCWSTR)]

        class NOTIFYICONDATA(ctypes.Structure):
            _fields_ = [('cbSize', w.DWORD), ('hWnd', w.HWND), ('uID', w.UINT), ('uFlags', w.UINT),
                        ('uCallbackMessage', w.UINT), ('hIcon', w.HICON), ('szTip', w.WCHAR * 128), ('dwState', w.DWORD),
                        ('dwStateMask', w.DWORD), ('szInfo', w.WCHAR * 256), ('uVersion', w.UINT),
                        ('szInfoTitle', w.WCHAR * 64), ('dwInfoFlags', w.DWORD), ('guidItem', ctypes.c_byte * 16),
                        ('hBalloonIcon', w.HICON)]
        self.WNDCLASS, self.NOTIFYICONDATA = WNDCLASS, NOTIFYICONDATA
        signatures = [
            (kernel32.GetModuleHandleW, [w.LPCWSTR], w.HMODULE),
            (u.DefWindowProcW, [w.HWND, w.UINT, w.WPARAM, w.LPARAM], lresult),
            (u.RegisterClassW, [ctypes.POINTER(WNDCLASS)], w.ATOM),
            (u.UnregisterClassW, [w.LPCWSTR, w.HINSTANCE], w.BOOL),
            (u.CreateWindowExW, [w.DWORD, w.LPCWSTR, w.LPCWSTR, w.DWORD, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                 ctypes.c_int, w.HWND, w.HMENU, w.HINSTANCE, w.LPVOID], w.HWND),
            (u.DestroyWindow, [w.HWND], w.BOOL),
            (u.RegisterWindowMessageW, [w.LPCWSTR], w.UINT),
            (u.GetSystemMetrics, [ctypes.c_int], ctypes.c_int),
            (u.CreateIconFromResourceEx, [ctypes.c_char_p, w.DWORD, w.BOOL, w.DWORD, ctypes.c_int, ctypes.c_int, w.UINT],
             w.HICON),
            (u.DestroyIcon, [w.HICON], w.BOOL),
            (u.CreatePopupMenu, [], w.HMENU),
            (u.AppendMenuW, [w.HMENU, w.UINT, ctypes.c_size_t, w.LPCWSTR], w.BOOL),
            (u.SetMenuDefaultItem, [w.HMENU, w.UINT, w.UINT], w.BOOL),
            (u.SetForegroundWindow, [w.HWND], w.BOOL),
            (u.TrackPopupMenuEx, [w.HMENU, w.UINT, ctypes.c_int, ctypes.c_int, w.HWND, w.LPVOID], ctypes.c_int),
            (u.DestroyMenu, [w.HMENU], w.BOOL),
            (u.PostMessageW, [w.HWND, w.UINT, w.WPARAM, w.LPARAM], w.BOOL),
            (u.GetMessageW, [ctypes.POINTER(w.MSG), w.HWND, w.UINT, w.UINT], w.BOOL),
            (u.TranslateMessage, [ctypes.POINTER(w.MSG)], w.BOOL),
            (u.DispatchMessageW, [ctypes.POINTER(w.MSG)], lresult),
            (u.PostQuitMessage, [ctypes.c_int], None),
            (s.Shell_NotifyIconW, [w.DWORD, ctypes.POINTER(NOTIFYICONDATA)], w.BOOL),
        ]
        for function, argtypes, restype in signatures:
            function.argtypes, function.restype = argtypes, restype

    def register_class(self, name: str, procedure) -> None:
        user32 = self._user32

        def window_procedure(hwnd, message, wparam, lparam):
            try:
                result = procedure(hwnd or 0, message, wparam, lparam)
            except Exception:
                logger.exception('Error handling tray message %#x', message)
                result = None
            return user32.DefWindowProcW(hwnd, message, wparam, lparam) if result is None else result
        callback = self.WNDPROC(window_procedure)
        self._procedures[name] = callback  # ctypes must keep the callback alive while the class exists
        window_class = self.WNDCLASS(lpfnWndProc=callback, hInstance=self._hinstance, lpszClassName=name)
        if user32.RegisterClassW(ctypes.byref(window_class)):
            return
        if ctypes.get_last_error() == ERROR_CLASS_ALREADY_EXISTS:
            # A leftover class would call an older procedure: register ours in its place.
            user32.UnregisterClassW(name, self._hinstance)
            if user32.RegisterClassW(ctypes.byref(window_class)):
                return
        raise TrayUnavailable()

    def unregister_class(self, name: str) -> None:
        self._user32.UnregisterClassW(name, self._hinstance)
        self._procedures.pop(name, None)

    def create_window(self, class_name: str) -> int:
        hwnd = self._user32.CreateWindowExW(0, class_name, class_name, 0, 0, 0, 0, 0, None, None, self._hinstance, None)
        if not hwnd:
            raise TrayUnavailable()
        return hwnd

    def destroy_window(self, hwnd) -> None:
        self._user32.DestroyWindow(hwnd)

    def register_message(self, name: str) -> int:
        return self._user32.RegisterWindowMessageW(name)

    def small_icon_size(self) -> int:
        return self._user32.GetSystemMetrics(SM_CXSMICON) or 16

    def icon_from_png(self, data: bytes, size: int) -> int:
        hicon = self._user32.CreateIconFromResourceEx(data, len(data), True, 0x00030000, size, size, 0)
        if not hicon:
            raise TrayUnavailable()
        return hicon

    def destroy_icon(self, hicon) -> None:
        self._user32.DestroyIcon(hicon)

    def _data(self, hwnd, hicon=None, tip=''):
        return self.NOTIFYICONDATA(cbSize=ctypes.sizeof(self.NOTIFYICONDATA), hWnd=hwnd, uID=1,
                                   uFlags=NIF_MESSAGE | NIF_ICON | NIF_TIP | NIF_SHOWTIP, uCallbackMessage=CALLBACK, hIcon=hicon,
                                   szTip=tip[:127])

    def add_icon(self, hwnd, hicon, tip: str) -> bool:
        return bool(self._shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(self._data(hwnd, hicon, tip))))

    def set_version(self, hwnd) -> bool:
        data = self._data(hwnd)
        data.uVersion = NOTIFYICON_VERSION_4
        return bool(self._shell32.Shell_NotifyIconW(NIM_SETVERSION, ctypes.byref(data)))

    def delete_icon(self, hwnd) -> None:
        self._shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(self._data(hwnd)))

    def popup_menu(self, hwnd, labels: list[str], default: int, x: int, y: int) -> int:
        user32 = self._user32
        menu = user32.CreatePopupMenu()
        if not menu:
            return 0
        try:
            for index, label in enumerate(labels):
                user32.AppendMenuW(menu, 0, index + 1, label)
            user32.SetMenuDefaultItem(menu, default + 1, False)
            user32.SetForegroundWindow(hwnd)
            choice = user32.TrackPopupMenuEx(menu, TPM_RETURNCMD | TPM_NONOTIFY | TPM_RIGHTBUTTON, x, y, hwnd, None)
            user32.PostMessageW(hwnd, WM_NULL, 0, 0)  # documented: lets the menu close properly next time
            return choice
        finally:
            user32.DestroyMenu(menu)

    def post(self, hwnd, message: int) -> None:
        self._user32.PostMessageW(hwnd, message, 0, 0)

    def run_loop(self) -> None:
        message = self._w.MSG()
        while self._user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
            self._user32.TranslateMessage(ctypes.byref(message))
            self._user32.DispatchMessageW(ctypes.byref(message))

    def post_quit(self) -> None:
        self._user32.PostQuitMessage(0)
