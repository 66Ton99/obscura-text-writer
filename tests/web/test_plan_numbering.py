import shutil
import subprocess
from pathlib import Path
import pytest


@pytest.mark.req('PLAN-NUMBERING')
def test_plan_numbering_rules():
    """PLAN-NUMBERING-S01..S03: list detection, renumbering and Enter continuation, without touching parsed plan lines."""
    node=shutil.which('node')
    if not node:pytest.skip('Node потрібен для перевірки ES module')
    root=Path(__file__).resolve().parents[2]
    result=subprocess.run([node,str(root/'tests/web/js/plan_numbering.mjs'),str(root)],capture_output=True,encoding='utf-8',errors='replace',timeout=15)
    assert result.returncode==0,result.stderr
