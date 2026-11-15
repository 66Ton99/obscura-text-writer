"""R16-COVER-S03: text cover layout and rendering (Pillow + bundled Noto Serif)."""
import io

import pytest
from PIL import Image, ImageDraw

from storygen.publication.covers import image_info
from storygen.publication import text_cover as tc

LIMIT = 1360


def widths_ok(lines):
    draw = ImageDraw.Draw(Image.new('RGB', (1, 1)))
    return all(draw.textlength(line.text, font=tc.font(line.size, line.bold)) <= LIMIT for line in lines)


def test_palettes_are_the_four_approved():
    assert list(tc.PALETTES) == ['ink', 'paper', 'wine', 'forest']
    assert tc.PALETTES['ink'] == ('#1c2433', '#efe6d2', '#c9a24a')
    assert tc.PALETTES['paper'] == ('#f2ece0', '#1f1f1f', '#8a2a2a')
    assert tc.PALETTES['wine'] == ('#5b1a1f', '#f3e9dc', '#d9b26a')
    assert tc.PALETTES['forest'] == ('#1f3a2e', '#eef0e6', '#b8c48a')


@pytest.mark.parametrize('tag,word', [('uk', 'Книга'), ('UK', 'Книга'), ('uk-UA', 'Книга'), ('UK-UA', 'Книга'),
                                      ('en', 'Book'), ('pl', 'Book'), ('ukx', 'Book')])
def test_book_word_ignores_case(tag, word):
    assert tc.book_word(tag) == word


def test_series_text():
    assert tc.series_text('Десяточники', 1, 'uk') == 'ДЕСЯТОЧНИКИ · КНИГА 1'
    assert tc.series_text('Tens', 2, 'en') == 'TENS · BOOK 2'
    assert tc.series_text('Десяточники', None, 'uk') == 'ДЕСЯТОЧНИКИ'
    assert tc.series_text('', 3, 'uk') == ''


@pytest.mark.parametrize('palette', ['ink', 'paper', 'wine', 'forest'])
def test_render_is_a_valid_cover(palette):
    png = tc.render_text_cover(title='Десяточка', series='ДЕСЯТОЧНИКИ · КНИГА 1', authors=["Ім'я Автора"], palette=palette)
    assert image_info(png) == ('image/png', 1600, 2560)
    with Image.open(io.BytesIO(png)) as image:
        assert image.convert('RGB').getpixel((5, 5)) == Image.new('RGB', (1, 1), tc.PALETTES[palette].background).getpixel((0, 0))


def test_short_title_is_one_line_at_220():
    lines = [line for line in tc.layout_text_cover(title='Десяточка', series='', authors=[]) if line.bold]
    assert [(line.text, line.size) for line in lines] == [('Десяточка', 220)]


def test_empty_series_and_authors_draw_only_the_title():
    lines = tc.layout_text_cover(title='Маяк', series='', authors=[])
    assert lines and all(line.bold for line in lines)


@pytest.mark.parametrize('title', ['а' * 300, ('довгеслово ' * 30).strip()], ids=['no-spaces', 'words'])
def test_huge_title_fits_and_is_cut(title):
    lines = [line for line in tc.layout_text_cover(title=title, series='', authors=[]) if line.bold]
    assert 1 <= len(lines) <= 6 and lines[0].size >= 90 and widths_ok(lines)


def test_huge_title_ends_with_ellipsis():
    lines = [line for line in tc.layout_text_cover(title='а' * 300, series='', authors=[]) if line.bold]
    assert lines[-1].text.endswith('…') and lines[0].size == 90


def test_many_authors_and_long_series_are_cut_within_margins():
    authors = [f'Автор Номер{i:02d} Дуже Довге Прізвище' for i in range(20)]
    lines = tc.layout_text_cover(title='Маяк', series='Ц' * 300, authors=authors)
    series = [line for line in lines if not line.bold and line.y < 1280]
    names = [line for line in lines if not line.bold and line.y > 1280]
    assert len(series) == 2 and series[-1].text.endswith('…')
    assert len(names) == 2 and names[-1].text.endswith('…') and names[0].size >= 60
    assert widths_ok(lines)


def test_unknown_palette():
    with pytest.raises(ValueError, match='палітра'):
        tc.render_text_cover(title='Маяк', series='', authors=[], palette='neon')
