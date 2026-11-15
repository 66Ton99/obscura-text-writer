"""R16-COVER: text cover (title, series and number, authors) drawn with Pillow and the bundled Noto Serif.

Pillow is imported lazily, like publication/covers.py, so cards and MD/TXT keep working without it.
"""
import io
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from typing import NamedTuple

WIDTH, HEIGHT = 1600, 2560
LIMIT = WIDTH - 2 * 120
ELLIPSIS = '…'
NO_PILLOW = 'Для обкладинок установіть storygen[publication] (Pillow)'


class Palette(NamedTuple):
    background: str
    text: str
    accent: str


PALETTES = {
    'ink': Palette('#1c2433', '#efe6d2', '#c9a24a'),
    'paper': Palette('#f2ece0', '#1f1f1f', '#8a2a2a'),
    'wine': Palette('#5b1a1f', '#f3e9dc', '#d9b26a'),
    'forest': Palette('#1f3a2e', '#eef0e6', '#b8c48a'),
}


@dataclass(frozen=True)
class Line:
    text: str
    size: int
    bold: bool
    y: int


def book_word(language: str) -> str:
    tag = language.lower()
    return 'Книга' if tag == 'uk' or tag.startswith('uk-') else 'Book'


def series_text(cycle_title: str, cycle_number: int | None, language: str) -> str:
    if not cycle_title:
        return ''
    text = cycle_title if cycle_number is None else f'{cycle_title} · {book_word(language)} {cycle_number}'
    return text.upper()


@lru_cache(maxsize=64)
def font(size: int, bold: bool):
    try:
        from PIL import ImageFont
    except ImportError:
        raise ValueError(NO_PILLOW) from None
    name = 'NotoSerif-Bold.ttf' if bold else 'NotoSerif-Regular.ttf'
    blob = (resources.files('storygen.publication') / 'resources' / 'fonts' / name).read_bytes()
    return ImageFont.truetype(io.BytesIO(blob), size)


def _measure():
    from PIL import Image, ImageDraw
    draw = ImageDraw.Draw(Image.new('RGB', (1, 1)))
    return lambda text, size, bold: draw.textlength(text, font=font(size, bold))


def _wrap(text, size, bold, max_lines, width):
    """Greedy word wrap; a word wider than LIMIT is split by characters; overflow cuts the last line with '…'."""
    fits = lambda value: width(value, size, bold) <= LIMIT
    lines, current = [], ''
    for word in text.split():
        candidate = f'{current} {word}'.strip()
        if fits(candidate):
            current = candidate
            continue
        if current:
            lines.append(current)
        current = ''
        while not fits(word):
            low, high = 1, len(word) - 1  # longest prefix that fits, by binary search
            while low < high:
                middle = (low + high + 1) // 2
                low, high = (middle, high) if fits(word[:middle]) else (low, middle - 1)
            lines.append(word[:low])
            word = word[low:]
        current = word
    if current:
        lines.append(current)
    if len(lines) <= max_lines:
        return lines, False
    lines = lines[:max_lines]
    last = lines[-1]
    low, high = 0, len(last)  # longest prefix that still fits with the ellipsis
    while low < high:
        middle = (low + high + 1) // 2
        low, high = (middle, high) if fits(last[:middle].rstrip() + ELLIPSIS) else (low, middle - 1)
    lines[-1] = last[:low].rstrip() + ELLIPSIS
    return lines, True


def _shrinking(text, sizes, bold, max_lines, width):
    for size in sizes:
        lines, cut = _wrap(text, size, bold, max_lines, width)
        if not cut:
            return lines, size
    return lines, size


def _block(lines, size, bold, center):
    step = int(size * 1.2)
    top = center - step * len(lines) / 2
    return [Line(text, size, bold, int(top + step * index + step / 2)) for index, text in enumerate(lines)]


def layout_text_cover(*, title: str, series: str, authors: list[str]) -> list[Line]:
    width = _measure()
    result = []
    if series:
        lines, _ = _wrap(series, 70, False, 2, width)
        result += [Line(text, 70, False, 220 + 84 * index) for index, text in enumerate(lines)]
    lines, size = _shrinking(title, range(220, 89, -10), True, 6, width)
    result += _block(lines, size, True, 1280)
    if authors:
        lines, size = _shrinking(', '.join(authors), range(90, 59, -10), False, 2, width)
        result += _block(lines, size, False, 2320)
    return result


def render_text_cover(*, title: str, series: str, authors: list[str], palette: str) -> bytes:
    if palette not in PALETTES:
        raise ValueError('Невідома палітра обкладинки')
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        raise ValueError(NO_PILLOW) from None
    colors = PALETTES[palette]
    lines = layout_text_cover(title=title, series=series, authors=authors)
    image = Image.new('RGB', (WIDTH, HEIGHT), colors.background)
    draw = ImageDraw.Draw(image)
    title_lines = [line for line in lines if line.bold]
    for line in lines:
        is_series = not line.bold and line.y < title_lines[0].y
        draw.text((WIDTH / 2, line.y), line.text, font=font(line.size, line.bold),
                  fill=colors.accent if is_series else colors.text, anchor='mm')
    half = int(title_lines[0].size * 1.2) / 2
    for y in (title_lines[0].y - half - 90, title_lines[-1].y + half + 60):
        draw.line((WIDTH / 2 - 180, y, WIDTH / 2 + 180, y), fill=colors.accent, width=5)
    output = io.BytesIO()
    image.save(output, format='PNG', optimize=True)
    return output.getvalue()
