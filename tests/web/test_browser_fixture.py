"""CODEX-SKILLS: synthetic browser startup owns its profiles before create_app."""
import os
from pathlib import Path

import pytest


@pytest.mark.req('CODEX-SKILLS')
def test_browser_fixture_creates_missing_root_and_isolates_before_app(tmp_path, monkeypatch):
    from tests.web.browser import server
    monkeypatch.setattr(server.sys, 'argv', ['server.py','8976'])
    test_root = tmp_path/'absent'/'browser-root'
    assert not test_root.exists()
    monkeypatch.setenv('OBSCURA_BROWSER_TEST_ROOT', str(test_root))
    for key in ('HOME','USERPROFILE','CODEX_HOME'):
        monkeypatch.setenv(key, os.environ.get(key,''))
    class Prepared(Exception):
        pass
    observed = []
    def app(settings, **kwargs):
        root = Path(settings.data_dir).parent
        assert root.parent == test_root
        profile = root/'home'
        assert profile.is_dir()
        assert Path(os.environ['HOME']) == Path(os.environ['USERPROFILE']) == profile
        assert Path(os.environ['CODEX_HOME']) == root/'codex'
        assert Path(settings.env_file) == root/'absent.env'
        assert not Path(settings.env_file).exists()
        assert kwargs['gateway_factory'] is kwargs['evaluator_factory'] is server.forbidden_gateway
        observed.append(root)
        raise Prepared
    monkeypatch.setattr(server, 'create_app', app)
    with pytest.raises(Prepared):
        server.main()
    assert observed and test_root.is_dir()
    assert not observed[0].exists()
