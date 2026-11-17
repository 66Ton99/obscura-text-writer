"""Measure who should do the brief and memory stages in chat mode (CLAUDE-SKILLS, spec §4).

Each run gets a fresh stand. The script itself (no model) brings the fixture scene to the stage under test; one
`claude -p` session then does exactly that stage. Variants:
  A  opus; for memory the prompt also carries the scene text "you just wrote" (a main session with it in context)
  B  sonnet, material only from get_stage_task
  C  haiku, the same
Prints one JSON line per run and keeps the stream, the saved stage result and the run summary in --work.

    python integrations/claude/tools/measure_models.py --variant B --stage memory --runs 3 --work C:/tmp/msr
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT/'src')]

from scripts.skills_stand import PLUGIN, claude_command, obscura_call, run_claude, start_stand  # noqa: E402

FIXTURE = Path(__file__).resolve().parent/'fixture'
MODELS = {'A': 'opus', 'B': 'sonnet', 'C': 'haiku'}
SETUP_BRIEF = {
    'objective': 'Анна знаходить лист без підпису з попередженням і вирішує чатувати в четвер.',
    'beats': ['Анна відкриває скриньку й знаходить конверт без марки й підпису.',
              'Петро приходить через зламаний човен і просить ключ від човнової хати.',
              'Вони читають лист разом; Петро розповідає про нічного чужинця; Анна вирішує чатувати в четвер.'],
    'constraints': [], 'proposed_changes': [], 'introduced': []}


def fixture(name):
    return (FIXTURE/name).read_text(encoding='utf-8')


def prepare(base, stage, writing_mode='chat'):
    """A story with the fixture plan; for memory also brief, draft and prose saved without a model."""
    story = obscura_call(base, 'create_story', {'title': 'Лист на пристані', 'language': 'uk', 'writing_mode': writing_mode,
                                                'content_rating': {'sexual': 0, 'violence': 0, 'themes': 0}})
    obscura_call(base, 'import_plan_and_characters', {'story_id': story['id'], 'plan_markdown': fixture('plan.md'),
                                                      'characters_markdown': fixture('characters.md')})
    scene = obscura_call(base, 'get_story', {'story_id': story['id']})['scenes'][0]['id']
    if stage == 'memory':
        task = obscura_call(base, 'get_stage_task', {'scene_id': scene, 'stage': 'brief'})
        obscura_call(base, 'save_stage_result', {'scene_id': scene, 'stage': 'brief',
                                                 'task_fingerprint': task['task_fingerprint'], 'result': SETUP_BRIEF})
        context = obscura_call(base, 'get_scene_context', {'scene_id': scene})
        obscura_call(base, 'save_draft', {'scene_id': scene, 'text': fixture('prose.md'), 'draft_version_id': None,
                                          'expected_revision': context['revision'],
                                          'context_fingerprint': context['context_fingerprint']})
        task = obscura_call(base, 'get_stage_task', {'scene_id': scene, 'stage': 'edit'})
        if task['result_format'] != 'prose':
            raise SystemExit(f"очікувався edit у форматі prose, а не {task['result_format']}")
        obscura_call(base, 'save_stage_result', {'scene_id': scene, 'stage': 'edit',
                                                 'task_fingerprint': task['task_fingerprint'], 'result': fixture('prose.md')})
    return story['id'], scene


def prompt(variant, stage, story, scene):
    text = (f'Use the Obscura tools and the obscura:draft-scene skill (chat mode). Story {story}, scene {scene}. '
            f'Do ONLY the {stage} stage of this scene: get_stage_task with stage "{stage}", read all of its material '
            f'(follow next_offset until it is null), answer exactly in the required format, and save it with '
            f'save_stage_result (model="{MODELS[variant]}"). If the save is refused, fix the violations and save again. '
            f'Do not do any other stage, do not ask questions, and end with one line: done.')
    if variant == 'A' and stage == 'memory':
        text += '\n\nThis is the scene text you just wrote and edited (it is already saved in Obscura):\n\n' + fixture('prose.md')
    return text


def measure(variant, stage, run, work, budget):
    work = Path(work)/f'{variant}-{stage}-{run}'
    with start_stand(work) as stand:
        story, scene = prepare(stand.base, stage)
        result = run_claude(claude_command(prompt(variant, stage, story, scene), mcp_config=stand.mcp_config,
                                           plugin_dir=PLUGIN, model=MODELS[variant], budget_usd=budget), work/'run.jsonl')
        saved = obscura_call(stand.base, 'get_scene_text', {'scene_id': scene, 'material': stage})
        (work/f'{stage}.json').write_text(json.dumps(saved, ensure_ascii=False, indent=2), encoding='utf-8')
    usage = result.usage or {}
    row = {'variant': variant, 'model': MODELS[variant], 'stage': stage, 'run': run, 'cost_usd': result.cost_usd,
           'input_tokens': usage.get('input_tokens', 0) + usage.get('cache_read_input_tokens', 0)
           + usage.get('cache_creation_input_tokens', 0),
           'output_tokens': usage.get('output_tokens'), 'is_error': result.is_error,
           'refusals': [e for e in result.errors if e[0] == 'save_stage_result'],
           'saved': bool(saved.get('text') or saved.get('content')), 'dir': str(work)}
    (work/'summary.json').write_text(json.dumps(row, ensure_ascii=False, indent=2), encoding='utf-8')
    return row


def main(argv=None):
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description='Вимір розподілу моделей на brief і memory (CLAUDE-SKILLS §4).')
    parser.add_argument('--variant', choices=sorted(MODELS), required=True)
    parser.add_argument('--stage', choices=['brief', 'memory'], required=True)
    parser.add_argument('--runs', type=int, default=3)
    parser.add_argument('--first-run', type=int, default=1)
    parser.add_argument('--budget', type=float, default=1.0)
    parser.add_argument('--work', required=True)
    parser.add_argument('--prepare-only', action='store_true', help='лише підготувати сцену, без claude')
    args = parser.parse_args(argv)
    if args.prepare_only:
        with start_stand(Path(args.work)/'prepare') as stand:
            story, scene = prepare(stand.base, args.stage)
            task = obscura_call(stand.base, 'get_stage_task', {'scene_id': scene, 'stage': args.stage, 'max_chars': 1000})
            print(json.dumps({'story': story, 'scene': scene, 'stage': task['stage'], 'total_chars': task['total_chars']}))
        return 0
    for run in range(args.first_run, args.first_run + args.runs):
        print(json.dumps(measure(args.variant, args.stage, run, args.work, args.budget), ensure_ascii=False), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
