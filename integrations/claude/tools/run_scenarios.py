"""Run the behaviour scenarios of the Obscura skills on an isolated stand (CLAUDE-SKILLS S04–S06).

Each scenario: a fresh stand, the setup it needs (made without a model), one `claude -p` session with the plugin,
then automatic checks of the tool sequence and the server's final state. The session's text is kept for the manual
part of the check (one question at a time, progress lines). See docs/verification/manual.md#claude-skills.

    python integrations/claude/tools/run_scenarios.py --scenario S05-a --work C:/tmp/scn
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT/'src'), str(Path(__file__).resolve().parent)]

from measure_models import prepare  # noqa: E402
from scripts.skills_stand import PLUGIN, claude_command, obscura_call, run_claude, start_stand  # noqa: E402

PIPELINE_ORDER = ['brief', 'draft', 'edit', 'memory']
WRITES = {'create_story', 'import_plan_and_characters', 'save_draft', 'save_stage_result', 'update_settings', 'apply_role_preset',
          'update_publication', 'add_scene', 'update_scene', 'update_story'}


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


def check_s04b(stand, calls, text, ctx):
    seq = [n for n in names(calls) if n in ('create_story', 'get_templates', 'import_plan_and_characters', 'get_story')]
    problems = []
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


def check_s05(stand, calls, text, ctx):
    saves = [s for s in pipeline_saves(calls) if s]
    firsts = [saves.index(stage) for stage in PIPELINE_ORDER if stage in saves]
    problems = []
    if firsts != sorted(firsts):
        problems.append(f'порядок етапів: {saves}')
    state = next(s['state'] for s in obscura_call(stand.base, 'get_story', {'story_id': ctx['story']})['scenes']
                 if s['id'] == ctx['scene'])
    if ctx.get('patches'):
        if 'edit' not in saves:
            problems.append('edit не збережено')
        if state == 'needs_review' and 'memory' in saves[saves.index('edit'):]:
            problems.append('пам\'ять після правок, що чекають перегляду автора')
    elif [s for s in PIPELINE_ORDER if s in saves] != PIPELINE_ORDER:
        problems.append(f'не всі етапи збережено: {saves}; стан сцени {state}')
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


def setup_patches(base, story):
    settings = obscura_call(base, 'get_settings', {'story_id': story})
    obscura_call(base, 'update_settings', {'story_id': story, 'section': 'editor',
                                           'expected_fingerprint': settings['roles']['editor']['fingerprint'],
                                           'fields': {'provider': 'openrouter', 'model': 'test/editor', 'edit_mode': 'patches'}})


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
}


def run(scenario, work, model, budget):
    spec = SCENARIOS[scenario]
    work = Path(work)/scenario
    with start_stand(work) as stand:
        ctx = {}
        if spec['setup']:
            ctx['story'], ctx['scene'] = prepare(stand.base, 'brief', 'obscura' if spec['setup'] == 'obscura' else 'chat')
            if spec['setup'] == 'patches':
                setup_patches(stand.base, ctx['story'])
                ctx['patches'] = True
        result = run_claude(claude_command(spec['prompt'], mcp_config=stand.mcp_config, plugin_dir=PLUGIN, model=model,
                                           budget_usd=budget), work/'run.jsonl')
        ctx['errors'] = result.errors
        problems = spec['check'](stand, result.tool_calls, result.text, ctx)
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
