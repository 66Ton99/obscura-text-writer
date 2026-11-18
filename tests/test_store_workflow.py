"""The Store build workflow (PACKAGING-001-S07): text checks, no PyYAML (it reads `on:` as True)."""
from pathlib import Path

import pytest

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


def _build_step_script():
    lines = WORKFLOW.read_text(encoding='utf-8').splitlines()
    start = lines.index('      - name: Build')
    run = next(i for i in range(start, len(lines)) if lines[i].strip() == 'run: |')
    body = []
    for line in lines[run + 1:]:
        if line.strip() and not line.startswith('          '):
            break
        body.append(line[10:])
    return '\n'.join(body)


STUB = '''function python { $global:CALLS += ,($args -join ' '); $global:LASTEXITCODE = 0 }
$global:CALLS = @()
'''


def _run_build_step(tmp_path, **env):
    import os
    import shutil
    import subprocess
    shell = shutil.which('pwsh') or shutil.which('powershell')
    if shell is None:
        pytest.skip('PowerShell is not available')
    script = tmp_path / 'build.ps1'
    record = tmp_path / 'calls.txt'
    script.write_text(STUB + _build_step_script().replace(
        'exit $LASTEXITCODE', f"$global:CALLS | Set-Content -Encoding utf8 '{record}'\nexit $LASTEXITCODE"
    ).replace('exit 1 }', f"Set-Content -Encoding utf8 '{record}' -Value ''; exit 1 }}"), encoding='utf-8-sig')
    full = {**os.environ, 'RUNNER_TEMP': str(tmp_path), 'MAKEAPPX': '', 'STORE_IDENTITY_NAME': '',
            'STORE_PUBLISHER': '', 'STORE_PUBLISHER_DISPLAY_NAME': '', **env}
    done = subprocess.run([shell, '-NoProfile', '-NonInteractive', '-File', str(script)], env=full,
                          capture_output=True, text=True, timeout=60)
    calls = [line for line in record.read_text(encoding='utf-8-sig').splitlines() if line.strip()] if record.exists() else None
    return done.returncode, done.stdout, calls


IDENTITY = {'STORE_IDENTITY_NAME': 'Example.App', 'STORE_PUBLISHER': 'CN=00000000-0000-0000-0000-000000000000',
            'STORE_PUBLISHER_DISPLAY_NAME': 'Example Publisher'}


@pytest.mark.parametrize('env, message', [
    ({'STORE_IDENTITY_NAME': 'Example.App', 'MAKEAPPX': 'makeappx.exe'}, 'needs all three inputs'),
    ({**IDENTITY, 'STORE_PUBLISHER': 'Example', 'MAKEAPPX': 'makeappx.exe'}, 'must start with CN='),
    (IDENTITY, 'makeappx not found'),
])
def test_rejected_identity_stops_before_building(tmp_path, env, message):
    code, out, calls = _run_build_step(tmp_path, **env)
    assert code == 1
    assert '::error::' in out and message in out
    assert calls == []


def test_complete_identity_builds_with_it(tmp_path):
    code, _, calls = _run_build_step(tmp_path, MAKEAPPX='makeappx.exe', **IDENTITY)
    assert code == 0
    assert len(calls) == 1
    assert '--identity-name Example.App' in calls[0]
    assert '--publisher CN=00000000-0000-0000-0000-000000000000' in calls[0]
    assert '--publisher-display-name Example Publisher' in calls[0]
    assert 'Obscura.CI' not in calls[0]


def test_empty_identity_keeps_the_test_identity(tmp_path):
    code, _, calls = _run_build_step(tmp_path, MAKEAPPX='makeappx.exe')
    assert code == 0 and len(calls) == 1 and '--identity-name Obscura.CI' in calls[0]
    code, out, calls = _run_build_step(tmp_path)
    assert code == 0 and len(calls) == 1 and '--skip-msix' in calls[0] and '::warning::' in out
