import shutil
import subprocess
from pathlib import Path
import pytest


@pytest.mark.req('BRIEF-FORM')
def test_brief_form_rules():
    """BRIEF-FORM-S01..S04: brief JSON to form model and back, planner numbers, empty items and list operations."""
    node=shutil.which('node')
    if not node:pytest.skip('Node потрібен для перевірки ES module')
    root=Path(__file__).resolve().parents[2]
    result=subprocess.run([node,str(root/'tests/web/js/brief_form.mjs'),str(root)],capture_output=True,encoding='utf-8',errors='replace',timeout=15)
    assert result.returncode==0,result.stderr
