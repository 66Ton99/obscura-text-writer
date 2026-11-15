from pathlib import Path

STATIC = Path(__file__).resolve().parents[2] / 'src/storygen/web/static'


def rule(css, selector):
    return css.split(selector + ' {', 1)[1].split('}', 1)[0]


def test_wrapped_primary_button_stays_on_the_right_on_desktop():
    """A long primary label wraps to its own line; on desktop it keeps to the right edge under Save, not the left."""
    css = (STATIC / 'app.css').read_text(encoding='utf-8')
    assert 'margin-left: auto' in rule(css, '.workspace-primary-wrap')
    mobile = css[css.index('@media(max-width: 720px)'):]
    assert 'margin-left: 0' in rule(mobile, '  .workspace-primary-wrap')  # phones keep the full-width left button
