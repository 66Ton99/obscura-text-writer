"""STORE-MCP-001 S07: the new-story form chooses «Obscura writes» in every edition."""
import re

import pytest
from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.web.app import create_app


def selected_mode(tmp_path) -> str:
    with TestClient(create_app(AppSettings(data_dir=tmp_path)), base_url='http://127.0.0.1:8765') as client:
        page = client.get('/').text
    form = page[page.index('name="writing_mode"'):]
    return re.search(r'<option value="(\w+)" selected', form[:form.index('</select>')]).group(1)


@pytest.mark.req('STORE-MCP-001')
def test_store_library_preselects_obscura(tmp_path, store_edition):
    assert selected_mode(tmp_path) == 'obscura'


@pytest.mark.req('STORE-MCP-001')
def test_full_library_keeps_obscura(tmp_path):
    assert selected_mode(tmp_path) == 'obscura'
