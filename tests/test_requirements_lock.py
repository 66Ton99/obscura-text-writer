"""The documented source install (lock file, then `pip install --no-deps -e ".[web,publication]"`)
must not miss any dependency the server needs (RUNTIME-001-S02)."""
from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
# Extras the user guide installs with --no-deps (docs/site/*/install.md, README.md).
DOCUMENTED_EXTRAS = ('web', 'publication')


def _name(requirement: str) -> str:
    match = re.match(r'\s*([A-Za-z0-9][A-Za-z0-9._-]*)', requirement)
    assert match, requirement
    return re.sub(r'[-_.]+', '-', match.group(1)).lower()


def _locked() -> set[str]:
    lines = (ROOT / 'requirements-lock.txt').read_text(encoding='utf-8').splitlines()
    return {_name(line) for line in lines if line.strip() and not line.lstrip().startswith('#')}


@pytest.mark.req('RUNTIME-001')
def test_lock_covers_core_and_documented_extras() -> None:
    project = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))['project']
    needed = list(project['dependencies'])
    for extra in DOCUMENTED_EXTRAS:
        needed += project['optional-dependencies'][extra]
    missing = sorted({_name(req) for req in needed} - _locked())
    assert not missing, f'requirements-lock.txt не закріплює залежності: {missing}'


@pytest.mark.req('RUNTIME-001')
def test_install_guides_use_lock_then_no_deps_with_documented_extras() -> None:
    extras = ','.join(DOCUMENTED_EXTRAS)
    for path in ('README.md', 'docs/site/uk/install.md', 'docs/site/en/install.md'):
        text = (ROOT / path).read_text(encoding='utf-8')
        assert 'pip install -r requirements-lock.txt' in text, path
        assert f'pip install --no-deps -e ".[{extras}]"' in text, path
