"""Checks of the skills' behaviour scenarios (CLAUDE-SKILLS S04–S09)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'integrations'/'claude'/'tools'))

from run_scenarios import (bible_problems, creation_problems, pipeline_problems, publish_problems,  # noqa: E402
                           settings_problems, verdict)
from scripts.skills_stand import Result  # noqa: E402

CREATE = [('create_story', {}), ('get_templates', {}), ('import_plan_and_characters', {}), ('get_story', {})]


@pytest.mark.req('CLAUDE-SKILLS')
def test_creation_alone_has_no_problems():
    assert creation_problems(CREATE) == []


@pytest.mark.req('CLAUDE-SKILLS')
def test_writing_scenes_after_creation_is_a_problem():
    calls = CREATE + [('save_draft', {}), ('save_stage_result', {'stage': 'brief'})]
    assert creation_problems(calls) == ["після створення записано тексти: ['save_draft', 'save_stage_result']"]


@pytest.mark.req('CLAUDE-SKILLS')
def test_patches_scenario_without_edit_is_a_problem_not_a_crash():
    calls = [('save_stage_result', {'stage': 'brief'}), ('save_draft', {})]
    assert pipeline_problems(calls, state='draft', patches=True) == ['edit не збережено']


@pytest.mark.req('CLAUDE-SKILLS')
def test_memory_after_edit_awaiting_review_is_a_problem():
    calls = [('save_stage_result', {'stage': 'brief'}), ('save_draft', {}), ('save_stage_result', {'stage': 'edit'}),
             ('save_stage_result', {'stage': 'memory'})]
    assert pipeline_problems(calls, state='needs_review', patches=True) == ["пам'ять після правок, що чекають перегляду автора"]


FULL = [('save_stage_result', {'stage': 'brief'}), ('save_draft', {}), ('save_stage_result', {'stage': 'edit'}),
        ('save_stage_result', {'stage': 'memory'})]


@pytest.mark.req('CLAUDE-SKILLS')
def test_attempted_saves_without_finished_prose_are_a_problem():
    assert pipeline_problems(FULL, state='draft', patches=False) == ['сцена не дійшла до прози: стан draft']
    assert pipeline_problems(FULL[2:3], state='no_text', patches=True) == ['сцена не дійшла до правок: стан no_text']


@pytest.mark.req('CLAUDE-SKILLS')
def test_failed_claude_session_never_passes():
    failed = Result(tool_calls=[], cost_usd=0.0, usage={}, text='Requested model is unavailable', is_error=True, errors=[])
    assert verdict([], failed) == ['сесія claude завершилась помилкою']
    ok = Result(tool_calls=[], cost_usd=0.0, usage={}, text='done', is_error=False, errors=[])
    assert verdict([], ok) == []


@pytest.mark.req('CLAUDE-SKILLS')
def test_publish_without_author_never_sets_one():
    calls = [('get_publication', {}), ('update_publication', {'fields': {'author_ids': ['x']}})]
    assert publish_problems(calls, author_given=False, palette=None) == ['автора записано без відповіді автора']


@pytest.mark.req('CLAUDE-SKILLS')
def test_publish_without_author_never_adds_a_signature():
    assert publish_problems([('add_signature', {'display_name': 'Хтось'})], author_given=False, palette=None) ==         ['автора записано без відповіді автора']


@pytest.mark.req('CLAUDE-SKILLS')
def test_publish_cover_uses_the_named_palette():
    calls = [('add_signature', {'display_name': 'Ірина Коваль'}), ('update_publication', {'fields': {'author_ids': ['s1']}}),
             ('generate_cover', {'palette': 'ink'}), ('update_publication', {'fields': {'cover_id': 'c1'}})]
    assert publish_problems(calls, author_given=True, palette='forest') == ["обкладинка не в палітрі forest: ['ink']"]


@pytest.mark.req('CLAUDE-SKILLS')
def test_publish_cover_must_be_set_on_the_card():
    calls = [('update_publication', {'fields': {'author_ids': ['s1']}}), ('generate_cover', {'palette': 'forest'})]
    assert publish_problems(calls, author_given=True, palette='forest') == ['обкладинку не поставлено в картку']


@pytest.mark.req('CLAUDE-SKILLS')
def test_publish_with_cover_set_has_no_problems():
    calls = [('update_publication', {'fields': {'author_ids': ['s1']}}), ('generate_cover', {'palette': 'forest'}),
             ('update_publication', {'fields': {'cover_id': 'c1'}})]
    assert publish_problems(calls, author_given=True, palette='forest') == []


@pytest.mark.req('CLAUDE-SKILLS')
def test_key_pasted_in_chat_means_no_settings_writes():
    calls = [('get_settings', {}), ('update_settings', {'section': 'writer', 'fields': {'provider': 'openrouter', 'model': 'm'}})]
    assert settings_problems(calls, roles_after={}, catalog_ids=None) == ['налаштування змінено, хоча ключ мав іти в інтерфейс']


@pytest.mark.req('CLAUDE-SKILLS')
def test_configured_role_with_model_missing_from_catalog_is_a_problem():
    calls = [('update_settings', {'section': 'writer'}), ('get_settings', {'models_for_role': 'writer'})]
    roles = {'writer': {'provider': 'openrouter', 'model': 'gone/model'}}
    assert settings_problems(calls, roles_after=roles, catalog_ids={'openrouter': {'deepseek/deepseek-v4-flash'}}) ==         ['роль writer: моделі gone/model немає в каталозі openrouter']


@pytest.mark.req('CLAUDE-SKILLS')
def test_roles_written_without_any_check_are_a_problem():
    roles = {'writer': {'provider': 'openrouter', 'model': 'deepseek/deepseek-v4-flash'}}
    assert settings_problems([('update_settings', {'section': 'writer'})], roles_after=roles,
                             catalog_ids={'openrouter': {'deepseek/deepseek-v4-flash'}}) == ['жодної звірки з каталогом (models_for_role)']


@pytest.mark.req('CLAUDE-SKILLS')
def test_recipe_with_same_writer_and_editor_is_a_problem():
    calls = [('update_settings', {}), ('get_settings', {'models_for_role': 'writer'})]
    roles = {role: {'provider': 'openrouter', 'model': 'deepseek/deepseek-v4-flash'} for role in ('planner', 'writer', 'editor', 'memory')}
    assert settings_problems(calls, roles_after=roles, catalog_ids={'openrouter': {'deepseek/deepseek-v4-flash'}}) ==         ['письменник і редактор — одна модель']


@pytest.mark.req('CLAUDE-SKILLS')
def test_bible_created_before_consent_is_a_problem():
    assert bible_problems([('create_story', {})], None, consent=False) == ['біблію створено до згоди з переліком статей']


@pytest.mark.req('CLAUDE-SKILLS')
def test_bible_with_consent_must_be_marked_as_bible():
    calls = [('create_story', {}), ('get_templates', {}), ('import_plan_and_characters', {}), ('get_story', {})]
    assert bible_problems(calls, {'title': 'Маяки', 'number': None, 'bible': False}, consent=True) == ['твір не позначено як біблію серії']


@pytest.mark.req('CLAUDE-SKILLS')
def test_bible_with_consent_writes_no_articles():
    calls = [('create_story', {}), ('get_templates', {}), ('import_plan_and_characters', {}), ('get_story', {}), ('save_draft', {})]
    assert bible_problems(calls, {'title': 'Маяки', 'number': None, 'bible': True}, consent=True) ==         ["після створення записано тексти: ['save_draft']"]
