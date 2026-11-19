"""Render the Store package icons from the web favicon (PACKAGING-001).

Draws src/storygen/web/static/favicon.svg in headless Chromium (Python Playwright) at every size in
packaging.ASSETS with a transparent background and writes the PNG files into store_build/msix/Assets.
It also writes src/storygen/web/static/app-icon.png (256 px), from which the tray icon is scaled (DESKTOP-001-S04).
Run again whenever the favicon changes; needs `python -m playwright install chromium` once.
"""
import argparse
import base64
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from storygen.packaging import ASSETS  # noqa: E402

SOURCE = ROOT / 'src' / 'storygen' / 'web' / 'static' / 'favicon.svg'
APP_ICON, APP_ICON_SIZE = ROOT / 'src' / 'storygen' / 'web' / 'static' / 'app-icon.png', 256


def page_html(svg: bytes, size: int) -> str:
    data = base64.b64encode(svg).decode('ascii')
    return (f'<!doctype html><html><body style="margin:0;background:transparent">'
            f'<img src="data:image/svg+xml;base64,{data}" width="{size}" height="{size}" style="display:block">'
            f'</body></html>')


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--out', type=Path, default=ROOT / 'store_build' / 'msix' / 'Assets')
    args = parser.parse_args(argv)
    from playwright.sync_api import sync_playwright

    svg = SOURCE.read_bytes()
    args.out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            targets = [(args.out / name, size) for name, size in ASSETS.items()] + [(APP_ICON, APP_ICON_SIZE)]
            for path, size in targets:
                page = browser.new_page(viewport={'width': size, 'height': size}, device_scale_factor=1)
                page.set_content(page_html(svg, size))
                page.wait_for_load_state('load')
                page.screenshot(path=str(path), omit_background=True,
                                clip={'x': 0, 'y': 0, 'width': size, 'height': size})
                page.close()
                print(f'{path.name}: {size}x{size}')
        finally:
            browser.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
