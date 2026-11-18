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
    assert 'if ($LASTEXITCODE) { exit $LASTEXITCODE }' in text  # a failed lock install must not fall through
    assert 'retention-days: 7' in text


def test_store_workflow_has_no_secrets_and_reads_only():
    text = WORKFLOW.read_text(encoding='utf-8')
    assert 'contents: read' in text
    assert 'secrets.' not in text
    assert 'contents: write' not in text
    assert 'signtool' not in text.lower()


def test_manual_run_takes_the_partner_center_identity_through_env():
    # PACKAGING-001-S09: three workflow_dispatch inputs reach the script only as environment variables.
    text = WORKFLOW.read_text(encoding='utf-8')
    for name in ('identity_name', 'publisher', 'publisher_display_name'):
        assert f'      {name}:\n' in text
        assert f'${{{{ inputs.{name} }}}}' in text
    run_lines = [line for line in text.splitlines() if 'inputs.' in line]
    assert all(line.strip().startswith(('STORE_', 'IDENTITY_', 'PUBLISHER')) for line in run_lines), run_lines
    assert '--identity-name $env:STORE_IDENTITY_NAME' in text
    assert '--publisher $env:STORE_PUBLISHER' in text
    assert '--publisher-display-name $env:STORE_PUBLISHER_DISPLAY_NAME' in text


def test_manual_identity_must_be_complete_and_needs_makeappx():
    text = WORKFLOW.read_text(encoding='utf-8')
    assert '::error::Partner Center identity needs all three inputs' in text
    assert '::error::makeappx not found; a Partner Center package cannot be built' in text
    assert "-notmatch '^CN='" in text
