"""SCENE-NARRATOR (#214): the narrator of a scene from its «Оповідач:» plan line or its field. Pure, no IO."""
import re

from .domain import SceneNarrator
from .scene_description import resolve_participants, split_participants

LINE=re.compile(r'(?i)^(?:[-*]\s+)?(?:Оповідач|Narrator)\s*:\s*(.*)$')
# Longest first: «всезнаючий, третя особа» is omniscient, not limited.
PERSONS=(
    ('third_omniscient',re.compile(r'(?i)\b(?:всезнаюч\w*|всевідаюч\w*|omniscient)\b')),
    ('first',re.compile(r'(?i)(?:від\s+)?\b(?:перш\w+\s+особ\w*|first\s+person)\b')),
    ('third_limited',re.compile(r'(?i)(?:від\s+)?\b(?:трет\w+\s+особ\w*|third\s+person)\b')),
)
THIRD=PERSONS[2][1]


def narrator_line(text):
    """The text after the first «Оповідач:»/«Narrator:» line of a plan, or None."""
    for line in (text or '').splitlines():
        match=LINE.match(line.replace('**','').strip())
        if match:return match.group(1).strip()
    return None


def parse_narrator(value,cards):
    """(SceneNarrator | None, problem | None) for the text of a narrator line; there are no defaults."""
    person=next((name for name,pattern in PERSONS if pattern.search(value)),None)
    if person is None:return None,'Оповідач: вкажіть лице («перша особа», «третя особа» або «всезнаючий»): '+value[:120]
    rest=PERSONS[[name for name,_ in PERSONS].index(person)][1].sub(' ',value)
    if person=='third_omniscient':rest=THIRD.sub(' ',rest)
    # SCENE-DESCRIPTION rules: commas inside parentheses belong to the name.
    names=[name for name in (part.strip(' .') for part in split_participants(rest)) if name]
    if person=='third_omniscient':
        if names:return None,'Оповідач: всезнаючий оповідач не має героя: '+value[:120]
        return SceneNarrator(person=person),None
    if len(names)!=1:return None,'Оповідач: вкажіть одного героя: '+value[:120]
    ids,problems=resolve_participants(names,cards)
    if problems:return None,'Оповідач: '+problems[0]
    return SceneNarrator(person=person,character_id=ids[0]),None


def effective_narrator(scene,cards):
    """(narrator, source 'plan'|'scene'|None, problems): the plan line wins; a line that does not parse leaves the field."""
    problems=[]
    value=narrator_line(scene.beats)
    if value is not None:
        narrator,problem=parse_narrator(value,cards)
        if narrator:return narrator,'plan',[]
        problems.append(problem)
    field=getattr(scene,'narrator',None)
    return (field,'scene' if field else None,problems)


NOT_IN_CAST='Оповідача немає серед учасників сцени: {name}.'


def narrator_value(narrator):
    """The selector value of a narrator (SCENE-NARRATOR-S04): «person:character_id», «third_omniscient» or None."""
    if narrator is None:return None
    return narrator.person+(':'+narrator.character_id if narrator.character_id else '')


def narrator_section(scene,cards,language='uk',scenes=None):
    """(section text or None, warnings) for the writing stages: the effective narrator with the card name, never an ID."""
    from .generation.context_labels import label
    narrator,_,problems=effective_narrator(scene,cards)
    warnings=list(problems)
    if narrator is None:return None,warnings
    from .characters.names import scene_names
    # CHARACTER-NAMES: the name current in the scene when the story's scenes are known.
    names=scene_names(cards,scenes,scene) if scenes is not None else {card.id:card.name for card in cards}
    name=names.get(narrator.character_id) or label('memory_protagonist',language) if narrator.character_id else ''
    if narrator.character_id and narrator.character_id not in scene.character_ids:
        warnings.append(NOT_IN_CAST.format(name=name))
    return label('narrator',language)+'\n'+label('narrator_'+narrator.person,language,name=name),warnings


def narrator_card(scene,cards):
    """Fields of the scene card (SCENE-NARRATOR-S03, S07): effective narrator, its source and problems, with the warning
    for a hero outside the cast."""
    narrator,source,problems=effective_narrator(scene,cards)
    names={card.id:card.name for card in cards}
    warnings=list(problems)
    if narrator and narrator.character_id and narrator.character_id not in scene.character_ids:
        warnings.append(NOT_IN_CAST.format(name=names.get(narrator.character_id,narrator.character_id)))
    return {'narrator_effective':narrator.model_dump() if narrator else None,'narrator_source':source,'narrator_problems':warnings}
