import shutil, subprocess
from pathlib import Path
import pytest


@pytest.mark.req('BUILD-EDITION-001')
def test_is_store_edition_helper():
    node = shutil.which('node')
    if not node:
        bundled = Path.home() / '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe'
        if not bundled.is_file():
            pytest.skip('Node required for frontend helper test')
        node = str(bundled)
    script = Path(__file__).resolve().parents[2] / 'tests/web/js/app-info-edition.mjs'
    result = subprocess.run([node, str(script)], capture_output=True, text=True, encoding='utf-8', timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
