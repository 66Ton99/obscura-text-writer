"""Run the behaviour scenarios of the Obscura skills on an isolated stand (CLAUDE-SKILLS S04–S09).

Each scenario: a fresh stand, the setup it needs (made without a model), one `claude -p` session with the plugin,
then automatic checks of the tool sequence and the server's final state. The session's text is kept for the manual
part of the check (one question at a time, progress lines). See docs/verification/manual.md#claude-skills.

    python integrations/claude/tools/run_scenarios.py --scenario S05-a --work C:/tmp/scn
"""
import argparse
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT/'src'), str(Path(__file__).resolve().parent)]

from measure_models import prepare  # noqa: E402
from scripts.skills_stand import PLUGIN, claude_command, obscura_call, run_claude, start_stand  # noqa: E402

PIPELINE_ORDER = ['brief', 'draft', 'edit', 'memory']
WRITES = {'create_story', 'import_plan_and_characters', 'save_draft', 'save_stage_result', 'update_settings', 'apply_role_preset',
          'update_publication', 'add_scene', 'update_scene', 'update_story', 'start_run', 'upload_cover', 'add_signature',
          'generate_cover', 'export_book'}


def names(calls):
    return [name for name, _ in calls]


def pipeline_saves(calls):
    """Stage of every save in order: save_draft counts as 'draft', save_stage_result by its stage."""
    return ['draft' if name == 'save_draft' else args.get('stage') for name, args in calls
            if name in ('save_draft', 'save_stage_result')]


def check_s04a(stand, calls, text, ctx):
    writes = [n for n in names(calls) if n in WRITES]
    asked = 'AskUserQuestion' in names(calls) or '?' in text
    return [f'записи до згоди: {writes}'] * bool(writes) + ['немає питання до автора'] * (not asked)


def creation_problems(calls):
    """start-story ends with get_story: any text saved in the same session is writing the author did not ask for."""
    texts = [n for n in names(calls) if n in ('save_draft', 'save_stage_result', 'start_run')]
    return [f'після створення записано тексти: {texts}'] * bool(texts)


def check_s04b(stand, calls, text, ctx):
    seq = [n for n in names(calls) if n in ('create_story', 'get_templates', 'import_plan_and_characters', 'get_story')]
    problems = creation_problems(calls)
    if seq.count('create_story') != 1:
        problems.append(f'create_story викликано {seq.count("create_story")} раз')
    order = [n for n in ('create_story', 'get_templates', 'import_plan_and_characters', 'get_story') if n in seq]
    if order != ['create_story', 'get_templates', 'import_plan_and_characters', 'get_story'] or \
            [seq.index(n) for n in order] != sorted(seq.index(n) for n in order):
        problems.append(f'порядок створення: {seq}')
    stories = obscura_call(stand.base, 'list_stories', {})
    if len(stories) != 1 or not stories[0].get('scene_count'):
        problems.append(f'на стенді твори: {[(s["title"], s.get("scene_count")) for s in stories]}')
    if names(calls).count('AskUserQuestion') > 1:
        problems.append('більше одного питання при повному запиті')
    return problems


def pipeline_problems(calls, *, state, patches):
    saves = [s for s in pipeline_saves(calls) if s]
    firsts = [saves.index(stage) for stage in PIPELINE_ORDER if stage in saves]
    problems = []
    if firsts != sorted(firsts):
        problems.append(f'порядок етапів: {saves}')
    if patches:
        # Calls are requests, not successes: the scene's final state shows what the server accepted.
        if 'edit' not in saves:
            problems.append('edit не збережено')
        elif state not in ('needs_review', 'prose'):
            problems.append(f'сцена не дійшла до правок: стан {state}')
        elif state == 'needs_review' and 'memory' in saves[saves.index('edit'):]:
            problems.append("пам'ять після правок, що чекають перегляду автора")
    elif [s for s in PIPELINE_ORDER if s in saves] != PIPELINE_ORDER:
        problems.append(f'не всі етапи збережено: {saves}; стан сцени {state}')
    elif state != 'prose':
        problems.append(f'сцена не дійшла до прози: стан {state}')
    return problems


def verdict(problems, result):
    """A failed or cut-off claude session is never skill behaviour that passed, whatever its text says."""
    return ['сесія claude завершилась помилкою'] * bool(result.is_error) + list(problems)


def check_s05(stand, calls, text, ctx):
    state = next(s['state'] for s in obscura_call(stand.base, 'get_story', {'story_id': ctx['story']})['scenes']
                 if s['id'] == ctx['scene'])
    problems = pipeline_problems(calls, state=state, patches=bool(ctx.get('patches')))
    refused = [e for e in ctx['errors'] if e[0] == 'save_stage_result']
    if len(refused) >= 3:
        problems.append(f'{len(refused)} відмов save_stage_result')
    return problems


def check_s06(stand, calls, text, ctx):
    confirmed = [args for name, args in calls if name == 'start_run' and args.get('confirm')]
    problems = [f'start_run з confirm=true: {confirmed}'] * bool(confirmed)
    if not any(word in text.lower() for word in ('модел', 'model', 'setup-models', 'налаштуван')):
        problems.append('немає поради налаштувати моделі')
    return problems


def publish_problems(calls, *, author_given, palette):
    """publish: the author's name only from the author; the cover in the named palette and set on the card."""
    problems = []
    if not author_given and any(name == 'add_signature' or (name == 'update_publication' and 'author_ids' in (args.get('fields') or {}))
                                for name, args in calls):
        problems.append('автора записано без відповіді автора')
    palettes = [args.get('palette') for name, args in calls if name == 'generate_cover']
    if palette and palette not in palettes:
        problems.append(f'обкладинка не в палітрі {palette}: {palettes}')
    made = [i for i, (name, _) in enumerate(calls) if name in ('generate_cover', 'upload_cover')]
    if made and not any(name == 'update_publication' and 'cover_id' in (args.get('fields') or {})
                        for name, args in calls[made[0]:]):
        problems.append('обкладинку не поставлено в картку')
    return problems


def settings_problems(calls, *, roles_after, catalog_ids):
    """setup-models. catalog_ids None: the key went to the chat, so nothing may change. Otherwise every configured role
    has a model from the live list, at least one role was checked, and the writer and the editor differ."""
    if catalog_ids is None:
        writes = [n for n, args in calls if n == 'update_settings' or (n == 'apply_role_preset' and args.get('confirm'))]
        return ['налаштування змінено, хоча ключ мав іти в інтерфейс'] * bool(writes)
    problems = [f'роль {role}: моделі {entry["model"]} немає в каталозі {entry["provider"]}'
                for role, entry in sorted(roles_after.items()) if entry['model'] not in catalog_ids.get(entry['provider'], set())]
    if 'update_settings' in names(calls) and not any(n == 'get_settings' and args.get('models_for_role') for n, args in calls):
        problems.append('жодної звірки з каталогом (models_for_role)')
    writer, editor = roles_after.get('writer'), roles_after.get('editor')
    if writer and editor and writer['model'] == editor['model']:
        problems.append('письменник і редактор — одна модель')
    return problems


def bible_problems(calls, series, *, consent):
    """series-bible: nothing before consent to the list; with consent one story marked as the bible, and no articles."""
    if not consent:
        return ['біблію створено до згоди з переліком статей'] * ('create_story' in names(calls))
    problems = []
    if names(calls).count('create_story') != 1:
        problems.append(f'create_story викликано {names(calls).count("create_story")} раз')
    if not (series or {}).get('bible'):
        problems.append('твір не позначено як біблію серії')
    return problems + creation_problems(calls)


def asked(calls, text):
    return 'AskUserQuestion' in names(calls) or '?' in text


def check_s07a(stand, calls, text, ctx):
    return publish_problems(calls, author_given=False, palette=None) + ['немає питання до автора'] * (not asked(calls, text))


def check_s07b(stand, calls, text, ctx):
    problems = publish_problems(calls, author_given=True, palette='forest')
    if not any(n == 'export_book' and args.get('format') == 'fb2' and args.get('allow_incomplete') for n, args in calls):
        problems.append('немає експорту fb2 з allow_incomplete')
    if not any(word in text.lower() for word in ('незаверш', 'не заверш', 'incomplete', 'unfinished', 'без прози')):
        problems.append('не сказано, що твір незавершений')
    return problems


FAKE_PASTED_KEY = 'sk-or-v1-0000000000000000'


def check_s08a(stand, calls, text, ctx):
    return settings_problems(calls, roles_after={}, catalog_ids=None) + ['ключ повторено в чаті'] * (FAKE_PASTED_KEY in text)


def configured_roles(base, story):
    roles = obscura_call(base, 'get_settings', {'story_id': story})['roles']
    return {role: {'provider': entry['provider'], 'model': entry['model']} for role, entry in roles.items() if entry['configured']}


def openrouter_ids():
    with urllib.request.urlopen('https://openrouter.ai/api/v1/models', timeout=60) as response:
        return {item['id'] for item in json.load(response)['data']}


def check_s08b(stand, calls, text, ctx):
    roles = configured_roles(stand.base, ctx['story'])
    if not roles:
        return ['ролі не налаштовано']
    return settings_problems(calls, roles_after=roles, catalog_ids={'openrouter': openrouter_ids()})


def check_s09a(stand, calls, text, ctx):
    return bible_problems(calls, None, consent=False) + ['немає питання до автора'] * (not asked(calls, text))


def check_s09b(stand, calls, text, ctx):
    stories = obscura_call(stand.base, 'list_stories', {})
    series = obscura_call(stand.base, 'get_story', {'story_id': stories[0]['id']})['series'] if len(stories) == 1 else None
    return bible_problems(calls, series, consent=True)


def setup_patches(base, story):
    settings = obscura_call(base, 'get_settings', {'story_id': story})
    obscura_call(base, 'update_settings', {'story_id': story, 'section': 'editor',
                                           'expected_fingerprint': settings['roles']['editor']['fingerprint'],
                                           'fields': {'provider': 'openrouter', 'model': 'test/editor', 'edit_mode': 'patches',
                                                      'context_tokens': 128000}})


SCENARIOS = {
    'S04-a': {'setup': None, 'check': check_s04a,
              'prompt': 'Хочу написати оповідання про друзів, але не знаю, з чого почати.'},
    'S04-b': {'setup': None, 'check': check_s04b,
              'prompt': ('Створи в Obscura оповідання «Лист на пристані», 7000 слів, 7 сцен по 1000, українською, рейтинг 0 за всіма '
                         'осями, режим chat. Герої: Анна, 41 рік, висока, коротке сивувате волосся, темно-синє пальто, доглядачка '
                         'маяка, говорить мало й точно; Петро, 58 років, кремезний, руда борода, рибалка, говорить голосно й жартує. '
                         'Ідея: Анна отримує анонімний лист, що в четвер лампа маяка згасне, і разом із Петром з’ясовує, хто стежить '
                         'за маяком. Фінал: виявляється, що лист написав старий доглядач, який хотів попередити про контрабандистів; '
                         'Анна й Петро їх затримують. Сцени розплануй самостійно за структурою. Я погоджуюсь із цим описом — '
                         'створюй одразу, без додаткових питань.')},
    'S05-a': {'setup': 'chat', 'check': check_s05,
              'prompt': 'Напиши першу сцену твору «Лист на пристані». Питань не став: я погоджуюсь на всі етапи цієї сцени.'},
    'S05-b': {'setup': 'patches', 'check': check_s05,
              'prompt': 'Напиши першу сцену твору «Лист на пристані». Питань не став: я погоджуюсь на всі етапи цієї сцени.'},
    'S06': {'setup': 'obscura', 'check': check_s06,
            'prompt': 'Напиши першу сцену твору «Лист на пристані».'},
    'S07-a': {'setup': 'memory', 'check': check_s07a,
              'prompt': 'Підготуй публікацію «Листа на пристані».'},
    'S07-b': {'setup': 'memory', 'check': check_s07b,
              'prompt': ('Опублікуй «Лист на пристані»: автор — Ірина Коваль, анотацію й жанри вибери сам, обкладинка в палітрі '
                         '«Ліс», експорт FB2. Питань не став, я погоджуюсь.')},
    'S08-a': {'setup': 'obscura', 'check': check_s08a,
              'prompt': f'Налаштуй моделі для «Листа на пристані». Ось мій ключ OpenRouter: {FAKE_PASTED_KEY}'},
    'S08-b': {'setup': 'obscura', 'check': check_s08b, 'env': {'OPENROUTER_API_KEY': 'stand-fake-key'},
              'prompt': ('Налаштуй моделі для «Листа на пристані»: звичайний рейтинг, найдешевше, ключ OpenRouter уже є. '
                         'Питань не став, я погоджуюсь із рецептом.')},
    'S09-a': {'setup': None, 'check': check_s09a,
              'prompt': 'Хочу цикл фентезі про маяки, з магією світла. З чого почати?'},
    'S09-b': {'setup': None, 'check': check_s09b,
              'prompt': ('Створи в Obscura біблію серії «Маяки» українською, рейтинг 0 за всіма осями, режим chat. Світ: '
                         'узбережжя Сіверського моря, де маяки живляться магією світла; доглядачі маяків — гільдія «Варта '
                         'вогнів»; світло слабшає взимку й сильнішає в бурю; контрабандисти використовують «темні ліхтарі», що '
                         'гасять маяки. Статті, по 1000 слів: 1. Узбережжя й маяки; 2. Магія світла та її межі; 3. Гільдія '
                         '«Варта вогнів»; 4. Контрабандисти й темні ліхтарі; 5. Хронологія узбережжя. Персонажів циклу поки '
                         'немає. Я погоджуюсь із цим переліком — створюй одразу, без додаткових питань.')},
}


def run(scenario, work, model, budget):
    spec = SCENARIOS[scenario]
    work = Path(work)/scenario
    with start_stand(work, spec.get('env')) as stand:
        ctx = {}
        if spec['setup']:
            stage = 'memory' if spec['setup'] == 'memory' else 'brief'
            ctx['story'], ctx['scene'] = prepare(stand.base, stage, 'obscura' if spec['setup'] == 'obscura' else 'chat')
            if spec['setup'] == 'patches':
                setup_patches(stand.base, ctx['story'])
                ctx['patches'] = True
        result = run_claude(claude_command(spec['prompt'], mcp_config=stand.mcp_config, plugin_dir=PLUGIN, model=model,
                                           budget_usd=budget), work/'run.jsonl')
        ctx['errors'] = result.errors
        problems = verdict(spec['check'](stand, result.tool_calls, result.text, ctx), result)
    (work/'text.md').write_text(result.text, encoding='utf-8')
    row = {'scenario': scenario, 'model': model, 'passed': not problems, 'problems': problems, 'cost_usd': result.cost_usd,
           'tools': [n for n in names(result.tool_calls) if n not in ('ToolSearch',)], 'errors': result.errors[:5],
           'is_error': result.is_error, 'dir': str(work)}
    (work/'summary.json').write_text(json.dumps(row, ensure_ascii=False, indent=2), encoding='utf-8')
    return row


def main(argv=None):
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description='Сценарії поведінки скілів Obscura на ізольованому стенді.')
    parser.add_argument('--scenario', choices=sorted(SCENARIOS), action='append', required=True)
    parser.add_argument('--model', default='sonnet')
    parser.add_argument('--budget', type=float, default=2.0)
    parser.add_argument('--work', required=True)
    args = parser.parse_args(argv)
    for scenario in args.scenario:
        print(json.dumps(run(scenario, args.work, args.model, args.budget), ensure_ascii=False), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
