"""SCENE-NARRATOR-S02, S05: the narrator line of the plan and the scene field (#214)."""
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from storygen.domain import SceneNarrator
from storygen.narration import effective_narrator, narrator_line

CARDS = [SimpleNamespace(id='j', name='Юлія'), SimpleNamespace(id='o', name='Олег'), SimpleNamespace(id='o2', name='Олег')]


def scene(beats='', narrator=None):
    return SimpleNamespace(beats=beats, narrator=narrator)


@pytest.mark.req('SCENE-NARRATOR')
@pytest.mark.parametrize('line,expected', [
    ('Оповідач: Юлія, перша особа', ('first', 'j')),
    ('- **Оповідач:** від першої особи, Юлія', ('first', 'j')),
    ('Narrator: Юлія, first person', ('first', 'j')),
    ('Оповідач: третя особа, Юлія', ('third_limited', 'j')),
    ('Оповідач: всезнаючий', ('third_omniscient', None)),
    ('Оповідач: всезнаючий, третя особа', ('third_omniscient', None)),
    ('Narrator: omniscient', ('third_omniscient', None)),
])
def test_plan_line_is_parsed(line, expected):
    narrator, source, problems = effective_narrator(scene('Хто бере участь: Юлія\n' + line), CARDS)
    assert (narrator.person, narrator.character_id) == expected and source == 'plan' and problems == []


@pytest.mark.req('SCENE-NARRATOR')
@pytest.mark.parametrize('line,problem', [
    ('Оповідач: Юлія', 'Оповідач: вкажіть лице («перша особа», «третя особа» або «всезнаючий»): Юлія'),
    ('Оповідач: третя особа', 'Оповідач: вкажіть одного героя: третя особа'),
    ('Оповідач: перша особа', 'Оповідач: вкажіть одного героя: перша особа'),
    ('Оповідач: Марта, перша особа', 'Оповідач: Невідомий персонаж: Марта'),
    ('Оповідач: Олег, перша особа', 'Оповідач: Неоднозначне ім’я: Олег'),
    ('Оповідач: всезнаючий, Юлія', 'Оповідач: всезнаючий оповідач не має героя: всезнаючий, Юлія'),
])
def test_plan_line_without_clear_meaning_is_a_problem(line, problem):
    field = SceneNarrator(person='third_omniscient')
    narrator, source, problems = effective_narrator(scene(line, field), CARDS)
    assert narrator == field and source == 'scene' and problems == [problem]


@pytest.mark.req('SCENE-NARRATOR')
def test_hero_name_with_a_comma_in_parentheses():
    # SCENE-DESCRIPTION rules: commas inside parentheses do not split the name.
    cards = [SimpleNamespace(id='j', name='Юлія (старша, лікарка)')]
    narrator, source, problems = effective_narrator(scene('Оповідач: Юлія (старша, лікарка), перша особа'), cards)
    assert narrator == SceneNarrator(person='first', character_id='j') and source == 'plan' and problems == []


@pytest.mark.req('SCENE-NARRATOR')
def test_plan_line_wins_over_the_field():
    narrator, source, _ = effective_narrator(scene('Оповідач: Юлія, перша особа', SceneNarrator(person='third_omniscient')), CARDS)
    assert narrator == SceneNarrator(person='first', character_id='j') and source == 'plan'


@pytest.mark.req('SCENE-NARRATOR')
def test_no_override_without_line_or_field():
    assert effective_narrator(scene('Хто бере участь: Юлія'), CARDS) == (None, None, [])
    assert narrator_line('Хто бере участь: Юлія') is None


@pytest.mark.req('SCENE-NARRATOR')
def test_field_validation():
    with pytest.raises(ValidationError):
        SceneNarrator(person='first')
    with pytest.raises(ValidationError):
        SceneNarrator(person='third_limited', character_id=None)
    with pytest.raises(ValidationError):
        SceneNarrator(person='third_omniscient', character_id='j')
    assert SceneNarrator(person='third_limited', character_id='o').character_id == 'o'
