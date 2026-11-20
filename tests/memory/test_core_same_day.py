"""CONTEXT-002-S07: the clothing line of the core shows the previous value of the same story day (#225)."""
from storygen.memory.journal import MemoryEvent, MemoryJournal
from storygen.memory.projection import memory_items, project_memory

SUFFIX=' (читачеві невідомо: якщо знадобиться, введи в тексті як нове)'
NUMBERS={'p1':1,'p2':2,'p3':3}


def ev(id,text,*,op='update',slot='clothing',source='p2',kind='prose',quote='доказ',claim='clo',category='character_states'):
    return MemoryEvent(event_id='e'+id,claim_id=claim,operation=op,category=category,text=text,character_ids=['h'],
        source_version_id=source,quote=quote,slot=slot,source_kind=kind)


def journal(*events):
    return MemoryJournal(schema_version=3,source_prose_ids=['p1','p2','p3'],events=list(events))


def core(j,*,scene_day='day:2',days=None,hidden=(),language='uk'):
    days={1:'day:1',2:'day:2',3:'day:2'} if days is None else days
    text=project_memory(j,[],NUMBERS,tracked=['h'],names={'h':'Ганна'},hidden_claim_ids=hidden,language=language,
        scene_day=scene_day,source_days=days).text
    return text.split('\n\n')[0].splitlines()[1:] if text.startswith(('ЯДРО','CORE')) else []


def dressed_then_undressed():
    return journal(ev('1','Піжама',op='add',source='p1'),ev('2','Сукня, сандалі'),ev('3','Гола',source='p3'))


def test_earlier_value_of_the_same_day_is_shown():
    assert core(dressed_then_undressed())==['одяг: Гола (раніше цього дня: Сукня, сандалі)']


def test_english_label():
    assert core(dressed_then_undressed(),language='en')==['clothing: Гола (earlier this day: Сукня, сандалі)']


def test_repeated_current_value_skips_to_last_distinct():
    j=journal(ev('1','Піжама',op='add',source='p1'),ev('2','Сукня'),ev('3','Гола',source='p2'),ev('4','Гола',source='p3'))
    assert core(j)==['одяг: Гола (раніше цього дня: Сукня)']


def test_value_of_another_day_is_not_shown():
    assert core(dressed_then_undressed(),days={1:'day:1',2:'day:1',3:'day:2'})==['одяг: Гола']


def test_no_hint_without_day_marks():
    assert core(dressed_then_undressed(),scene_day=None)==['одяг: Гола']
    assert core(dressed_then_undressed(),days={1:'day:1',2:None,3:'day:2'})==['одяг: Гола']


def test_retire_resets_history():
    j=journal(ev('1','Сукня',op='add',source='p2'),ev('2','непевно',op='retire',source='p2'),
        ev('3','Гола',op='add',claim='clo2',source='p3'))
    assert core(j)==['одяг: Гола']


def test_hidden_slot_has_no_hint():
    assert core(dressed_then_undressed(),hidden={'clo'})==[]


def test_other_slots_get_no_hint():
    j=journal(ev('1','Синці',op='add',slot='body',claim='b',source='p2'),ev('2','Шкіра чиста',slot='body',claim='b',source='p3'))
    assert core(j)==['тілесний стан: Шкіра чиста']


def test_author_unquoted_earlier_value_keeps_reader_unknown_suffix():
    j=journal(ev('1','Сукня',op='add',source='p2',kind='author',quote=None),ev('2','Гола',source='p3'))
    assert core(j)==['одяг: Гола (раніше цього дня: Сукня'+SUFFIX+')']


def test_without_days_output_is_unchanged():
    j=dressed_then_undressed()
    plain=project_memory(j,[],NUMBERS,tracked=['h'],names={'h':'Ганна'}).text
    assert 'одяг: Гола\n' in plain and 'раніше' not in plain


def test_item_text_stays_current_value():
    items,_=memory_items(dressed_then_undressed(),[],NUMBERS,tracked=['h'],scene_day='day:2',source_days={1:'day:1',2:'day:2',3:'day:2'})
    line=next(i for i in items if i.section=='core')
    assert line.text=='Гола' and line.line.endswith('(раніше цього дня: Сукня, сандалі)')
