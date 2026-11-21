"""CHARACTER-TIME-S04 (#75): card search on the characters page; the JS name rule matches characters/names.py."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from storygen.characters.models import CharacterRecord
from storygen.characters.names import card_names

ROOT = Path(__file__).resolve().parents[2]
CASES = [
    ('Хазяїн', ["Інше ім'я: Джон"]), ('Хазяїн', ['- **Інші імена:** Незнайомець, хазяїн']), ('Ліна', ['Також відома як: Лінка']),
    ('John', ['Other names: Johnny, Boss', 'AKA: J']), ('Анна', ["Інше ім'я: —", 'Вік: 30']), ('Анна', ['Also known as: Ann (стара, кличка)']),
    ('Host', ['Other names: A\U0001F600, Bob']),
    ('Host', ['Other names: Alice\rAKA: Bob\x85Інше ім\'я: Ліза']),
]


@pytest.mark.req('CHARACTER-TIME')
def test_card_search_helpers_and_parity_with_server_names():
    node = shutil.which('node')
    if not node:
        pytest.skip('node is not installed')
    cases = [{'name': name, 'entries': [{'text': text} for text in texts]} for name, texts in CASES]
    result = subprocess.run([node, str(ROOT / 'tests/web/js/characters_find.mjs'), str(ROOT), json.dumps(cases, ensure_ascii=False)],
                            capture_output=True, text=True, encoding='utf-8', timeout=15)
    assert result.returncode == 0, result.stderr
    expected = [card_names(CharacterRecord.model_validate({'schema_version': 2, 'id': f'c{i}', 'name': name, 'entries': [
        {'id': f'e{i}{j}', 'text': text, 'origin': 'author'} for j, text in enumerate(texts)]})) for i, (name, texts) in enumerate(CASES)]
    assert json.loads(result.stdout) == expected
