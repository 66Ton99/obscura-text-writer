"""DESKTOP-001-S04: the tray icon of the installed build — the only visible handle of a process without a window."""
import io
import locale
import os
import webbrowser
from pathlib import Path
from typing import Callable

from . import win_tray
from .web.localization import translate
from .win_tray import TrayUnavailable  # noqa: F401 - re-exported for desktop.py


def system_locale() -> str:
    try:
        name = (locale.getlocale()[0] or '').lower()
    except Exception:
        name = ''
    return 'uk' if name.startswith(('uk', 'ukrainian')) else 'en'


def reveal(path: Path) -> None:
    if os.name == 'nt':
        os.startfile(str(path))  # noqa: S606 - opens a folder of this application in Explorer
    else:
        webbrowser.open(Path(path).as_uri())


def menu_items(url: str, data_dir: Path, backups_dir: Path, stop: Callable[[], None], *, opener=webbrowser.open,
               reveal=reveal, locale: str = 'uk') -> list[tuple[str, Callable[[], None]]]:
    """Labels and actions in menu order; the first one is the default (double-click) action."""
    items = [(translate('desktop.tray.open', locale), lambda: opener(url)),
             (translate('desktop.tray.folder', locale), lambda: reveal(data_dir))]
    if Path(backups_dir).is_dir():
        items.append((translate('desktop.tray.backups', locale), lambda: reveal(backups_dir)))
    items.append((translate('desktop.tray.quit', locale), stop))
    return items


def _image(size: int = 64):
    from PIL import Image, ImageDraw
    image = Image.new('RGBA', (size, size), (92, 26, 43, 255))
    draw = ImageDraw.Draw(image)
    margin = round(size * 14 / 64)
    draw.ellipse((margin, margin, size - margin, size - margin), outline=(245, 238, 228, 255), width=max(1, round(size * 6 / 64)))
    return image


def icon_png(size: int) -> bytes:
    """The tray picture as PNG in the system's small-icon size."""
    buffer = io.BytesIO()
    _image(size).save(buffer, format='PNG')
    return buffer.getvalue()


_api_factory = win_tray.Win32Api


def run_tray(url: str, data_dir: Path, backups_dir: Path, stop: Callable[[], None]) -> None:
    """Show the icon and block until "Quit"; raises TrayUnavailable when there is no tray to show."""
    if os.name != 'nt':
        raise TrayUnavailable()
    holder, stopped = {}, []

    def quit_application():
        if stopped:  # a second "Quit" while the server is still stopping does nothing
            return
        stopped.append(True)
        stop()
        holder['icon'].close()
    items = menu_items(url, data_dir, backups_dir, quit_application, locale=system_locale())
    holder['icon'] = win_tray.NotifyIcon(_api_factory(), 'Obscura', icon_png, items)
    holder['icon'].run()
