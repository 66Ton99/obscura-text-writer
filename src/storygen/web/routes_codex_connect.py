"""Owner-only Codex configuration; paths and argv come exclusively from the server."""
import os
import sys
from dataclasses import asdict
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from .. import build_edition, claude_connect as cc
from ..codex_connect import CodexConfigError, config_path, config_status, powershell_command, write_config
from ..codex_skill_install import inspect_skills, install_skills
from ..codex_skills import GenerationError, NAMES, generate_skills
from .localization import diagnostic, request_locale
from .routes_connect import _desktop_launched

router = APIRouter()
CONNECT_OWNER_ONLY = 'Підключення до Codex виконує лише автор в Obscura'
CONFIG_ERROR = 'Не вдалося зберегти налаштування Codex; перевірте файл і повторіть'
SKILLS_ERROR = 'Не вдалося встановити всі скіли Codex; перевірте конфлікти та резервні копії'
UNAVAILABLE = 'Скіли Codex доступні лише з checkout Obscura'


def _roots() -> cc.Roots:
    return cc.Roots.current()


def _command(request: Request, roots: cc.Roots) -> list[str]:
    from ..desktop import default_data_dir
    return cc.bridge_command(roots, frozen=getattr(sys, 'frozen', False), executable=Path(sys.executable),
                             data_dir=Path(request.app.state.settings.data_dir), default_data_dir=default_data_dir(),
                             desktop_launched=_desktop_launched(request),
                             base_url=f'http://127.0.0.1:{request.app.state.settings.port}')


def _skill_source() -> Path | None:
    if build_edition.current().edition == 'store' or getattr(sys, 'frozen', False):
        return None
    source = Path(__file__).resolve().parents[3]/'integrations/claude/obscura'
    return source if source.is_dir() else None


def _error(request, text, reason, status, **fields):
    return JSONResponse(jsonable_encoder(dict(fields, reason=reason,
        detail=diagnostic(text, request_locale(request)), detail_original=text)), status_code=status)


@router.get('/api/connect/codex/status')
def status(request: Request):
    try:
        roots = _roots()
        command = _command(request, roots)
        path = config_path(roots.userprofile, os.environ.get('CODEX_HOME'))
        source = _skill_source()
        skills = dict(available=False, state='unsupported', present=[], conflicts=[], versions={})
        if source is not None:
            skills = dict(asdict(inspect_skills(generate_skills(source), roots.userprofile)), available=True)
        return dict(mcp=config_status(path, command), skills=skills, command=powershell_command(command))
    except CodexConfigError as error:
        return _error(request, CONFIG_ERROR, str(error), 422)
    except GenerationError:
        return _error(request, SKILLS_ERROR, 'skill_source_invalid', 409)
    except OSError:
        return _error(request, CONFIG_ERROR, 'access_failed', 500)


@router.post('/api/connect/codex')
def connect(request: Request):
    try:
        roots = _roots()
        command = _command(request, roots)
        result = write_config(config_path(roots.userprofile, os.environ.get('CODEX_HOME')), command)
        return dict(asdict(result), command=powershell_command(command))
    except CodexConfigError as error:
        reason = str(error)
        return _error(request, CONFIG_ERROR, reason, 409 if reason.startswith('config_changed') else 422)
    except OSError:
        return _error(request, CONFIG_ERROR, 'config_io_failed', 500)


@router.post('/api/connect/codex/skills')
def skills(request: Request):
    try:
        roots = _roots()
        source = _skill_source()
        if source is None:
            return _error(request, UNAVAILABLE, 'skills_unsupported', 409)
        report = install_skills(generate_skills(source), roots.userprofile)
        fields = dict(asdict(report), names=['obscura-'+name for name in NAMES])
        if report.result in ('installed', 'unchanged'):
            return fields
        return _error(request, SKILLS_ERROR, 'skills_'+report.result,
                      409 if report.result == 'conflict' else 500, **fields)
    except GenerationError:
        return _error(request, SKILLS_ERROR, 'skill_source_invalid', 409)
    except OSError:
        return _error(request, SKILLS_ERROR, 'skills_io_failed', 500)
