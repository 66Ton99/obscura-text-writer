"""WAITLIST-001: the waitlist Worker. Node runs workers/waitlist/test once with the junit reporter; each
scenario test here checks that the Node tests named with its id passed. Without Node the tests fail, not skip."""
import re
import shutil
import subprocess
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / 'workers' / 'waitlist'


@pytest.fixture(scope='module')
def node_results(tmp_path_factory):
    node = shutil.which('node')
    if node is None:
        pytest.fail('Node.js ≥ 22 потрібен для тестів Worker списку очікування')
    report = tmp_path_factory.mktemp('waitlist-node') / 'junit.xml'
    subprocess.run([node, '--test', '--test-reporter=junit', f'--test-reporter-destination={report}',
                    str(WORKER / 'test' / 'index.test.mjs')], cwd=ROOT, capture_output=True, timeout=120)
    assert report.exists(), 'Node не записав звіт junit'
    results = {}
    for case in ET.parse(report).getroot().iter('testcase'):
        results[case.get('name')] = not any(case.find(tag) is not None for tag in ('failure', 'error', 'skipped'))
    return results


def assert_scenario(results, prefix):
    names = [name for name in results if name.startswith(f'{prefix}:')]
    assert names, f'немає тестів Node для {prefix}'
    failed = [name for name in names if not results[name]]
    assert not failed, failed


def wrangler():
    return tomllib.loads((WORKER / 'wrangler.toml').read_text(encoding='utf-8'))


@pytest.mark.req('WAITLIST-001')
def test_s01_new_address_is_recorded(node_results):
    assert_scenario(node_results, 'S01')


@pytest.mark.req('WAITLIST-001')
def test_s02_repeat_address_changes_nothing(node_results):
    assert_scenario(node_results, 'S02')


@pytest.mark.req('WAITLIST-001')
def test_s03_invalid_form_skips_turnstile(node_results):
    assert_scenario(node_results, 'S03')


@pytest.mark.req('WAITLIST-001')
def test_s04_turnstile_refusal_writes_nothing(node_results):
    assert_scenario(node_results, 'S04')


@pytest.mark.req('WAITLIST-001')
def test_s05_foreign_requests_are_refused(node_results):
    assert_scenario(node_results, 'S05')


@pytest.mark.req('WAITLIST-001')
def test_s06_failure_logs_no_address(node_results):
    assert_scenario(node_results, 'S06')


@pytest.mark.req('WAITLIST-001')
def test_s09_old_rows_are_purged_daily(node_results):
    assert_scenario(node_results, 'S09')
    config = wrangler()
    assert config['triggers']['crons'] == ['17 3 * * *']
    assert config['vars']['RETENTION_MONTHS'] == '24'


@pytest.mark.req('WAITLIST-001')
def test_privacy_edition_matches_site():
    privacy = (ROOT / 'docs' / 'site' / 'uk' / 'privacy.md').read_text(encoding='utf-8')
    day, month, year = re.search(r'Редакція від (\d{2})\.(\d{2})\.(\d{4})', privacy).groups()
    assert wrangler()['vars']['PRIVACY_EDITION'] == f'{year}-{month}-{day}'


@pytest.mark.req('WAITLIST-001')
def test_wrangler_config_keeps_no_secret():
    text = (WORKER / 'wrangler.toml').read_text(encoding='utf-8')
    assert not re.search(r'^\s*TURNSTILE_SECRET\s*=', text, re.MULTILINE)
    config = wrangler()
    assert config['vars']['ALLOWED_ORIGINS'] == 'https://obscurawriter.com'
    assert {'pattern': 'waitlist.obscurawriter.com', 'custom_domain': True} in config['routes']
