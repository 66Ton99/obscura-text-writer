"""The Store build workflow (PACKAGING-001-S07): text checks, no PyYAML (it reads `on:` as True)."""
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / '.github' / 'workflows' / 'store-build.yml'


def test_store_workflow_builds_on_windows_with_official_python():
    text = WORKFLOW.read_text(encoding='utf-8')
    assert 'runs-on: windows-latest' in text
    assert "python-version: '3.12'" in text
    assert 'python scripts/build_store.py' in text
    assert 'workflow_dispatch' in text and 'pull_request' in text
    assert '--report-url' in text  # a Store edition refuses to build without it


def test_store_workflow_packs_a_test_identity_or_skips_msix():
    text = WORKFLOW.read_text(encoding='utf-8')
    assert '--identity-name Obscura.CI' in text
    assert '--skip-msix' in text
    assert '::warning::' in text
    assert 'actions/upload-artifact' in text
    assert 'retention-days: 7' in text


def test_store_workflow_has_no_secrets_and_reads_only():
    text = WORKFLOW.read_text(encoding='utf-8')
    assert 'contents: read' in text
    assert 'secrets.' not in text
    assert 'contents: write' not in text
    assert 'signtool' not in text.lower()
