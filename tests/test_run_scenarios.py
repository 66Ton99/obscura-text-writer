"""Checks of the skills' behaviour scenarios (CLAUDE-SKILLS S04, S05)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'integrations'/'claude'/'tools'))

from run_scenarios import creation_problems, pipeline_problems  # noqa: E402

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
