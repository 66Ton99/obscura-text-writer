"""PLAN-PREAMBLE-S01/S02: the plan preamble is replaced only when the scene split stays the same (neutral examples)."""
import pytest
from storygen.plan_sections import PreambleError, preamble_editable, replace_preamble, split_plan

MD = '# Маяк\n\nТон: тихий.\n\n## Сцена 1: Лист\nОпис\n## Сцена 2: Шторм\nОпис\n'
PLAIN = '# Маяк\nТон.\nСцена 1: Лист\nОпис\nСцена 2: Шторм\nОпис\n'


def sections(text):
    return [s.text for s in split_plan(text)[1]]


@pytest.mark.parametrize('text,new', [(MD, 'Тон: похмурий.'), (PLAIN, '# Маяк\nТон: похмурий.\n'),
                                      ('# Маяк\r\nТон.\r\nСцена 1: Лист\r\nОпис\r\n', '# Маяк\r\nТон 2')])
def test_replacement_keeps_scenes(text, new):
    candidate, old = replace_preamble(text, new)
    assert old == split_plan(text)[0]
    preamble = split_plan(candidate)[0]
    assert preamble.strip() == new.replace('\r\n', '\n').strip() and '\r' not in preamble
    assert sections(candidate) == sections(text)


def test_new_preamble_is_separated_from_the_first_scene():
    candidate, _ = replace_preamble(MD, 'Тон')
    assert candidate.startswith('Тон\n\n## Сцена 1: Лист')


def test_clearing_the_preamble_leaves_only_scenes():
    candidate, _ = replace_preamble(PLAIN, '  \n')
    assert split_plan(candidate)[0] == '' and sections(candidate) == sections(PLAIN)


@pytest.mark.parametrize('text,new', [(MD, '# Маяк\n\n## Тон\nпохмурий'), (PLAIN, '# Маяк\n# Тон\nпохмурий'),
                                      (PLAIN, '# Маяк\nСцена 5: зайва')])
def test_a_preamble_that_changes_the_split_is_refused(text, new):
    with pytest.raises(PreambleError) as error:
        replace_preamble(text, new)
    assert error.value.reason == 'boundary'


def test_a_plan_without_scene_boundaries_has_no_editable_preamble():
    with pytest.raises(PreambleError) as error:
        replace_preamble('Просто текст без сцен\n', 'Вказівки')
    assert error.value.reason == 'no_scenes'
    assert not preamble_editable('Просто текст без сцен\n')
    assert preamble_editable(MD) and preamble_editable(PLAIN)
