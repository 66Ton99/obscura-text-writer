"""STORE-MCP-001 S08–S11: fixed actions of the «Connect to Claude» block. The bridge is refused before these run (app.py)."""
import json
import os
import shlex
import sys
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from .. import claude_connect as cc
from .localization import diagnostic, request_locale

router = APIRouter()

CONNECT_OWNER_ONLY = 'Підключення до Claude виконує лише автор в Obscura'
NO_DESKTOP_CONFIG = 'Файла налаштувань Claude Desktop немає: запустіть Claude Desktop хоч раз і повторіть'
UNUSABLE_CONFIG = 'Файл налаштувань Claude Desktop має невідомий формат; Obscura його не змінювала'
NO_LAUNCHER = 'Не знайдено програму моста MCP поруч з Obscura'


def _roots() -> cc.Roots:
    return cc.Roots.current()


def _open_folder(path: Path) -> None:
    if sys.platform == 'win32':
        os.startfile(path)  # noqa: S606 — a fixed folder inside the stories folder


def _launcher(command: list[str]) -> Path:
    # The executable the .mcpb carries as its entry point: the bridge next to Obscura (the alias itself is a 0-byte link).
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).with_name(cc.ALIAS)
    return Path(command[0])


def _refusal(request: Request, text: str, status: int, **extra) -> JSONResponse:
    return JSONResponse({'detail': diagnostic(text, request_locale(request)), 'detail_original': text, **extra}, status_code=status)


def _desktop_launched(request: Request) -> bool:
    try:
        record = json.loads((Path(request.app.state.settings.data_dir) / 'server.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return False
    return isinstance(record, dict) and record.get('instance_id') == request.app.state.instance_id


def _command(request: Request, roots: cc.Roots) -> list[str]:
    from ..desktop import default_data_dir
    return cc.bridge_command(roots, frozen=getattr(sys, 'frozen', False), executable=Path(sys.executable),
                             data_dir=Path(request.app.state.settings.data_dir), default_data_dir=default_data_dir(),
                             desktop_launched=_desktop_launched(request), base_url=str(request.base_url).rstrip('/'))


@router.get('/api/connect/status')
def status(request: Request):
    roots = _roots()
    command = _command(request, roots)
    config = cc.find_desktop_config(roots)
    desktop = None
    if config is not None:
        try:
            entry = json.loads(config.path.read_text(encoding='utf-8')).get('mcpServers', {}).get(cc.ENTRY)
        except (OSError, ValueError, AttributeError):
            entry = None
        desktop = {'path': str(config.path), 'variant': config.variant, 'has_entry': entry == cc.desktop_entry(command)}
    return {'desktop': desktop, 'code': {'found': cc.find_claude_code(roots) is not None}}


@router.post('/api/connect/claude-desktop')
def connect_desktop(request: Request):
    roots = _roots()
    config = cc.find_desktop_config(roots)
    if config is None:
        return _refusal(request, NO_DESKTOP_CONFIG, 404, fallback=True)
    try:
        result = cc.write_desktop_entry(config.path, _command(request, roots))
    except cc.UnusableConfig as error:
        return _refusal(request, UNUSABLE_CONFIG, 422, fallback=True, path=str(error.path))
    return {'result': result, 'path': str(config.path), 'variant': config.variant}


@router.post('/api/connect/claude-desktop/bundle')
def desktop_bundle(request: Request):
    from ..build_manifest import project_version
    command = _command(request, _roots())
    launcher = _launcher(command)
    if not launcher.is_file():
        return _refusal(request, NO_LAUNCHER, 409)
    target = cc.build_mcpb(Path(request.app.state.settings.data_dir) / 'claude' / 'obscura.mcpb', command, launcher,
                           project_version())
    _open_folder(target.parent)
    return {'path': str(target)}


@router.post('/api/connect/claude-code')
def connect_code(request: Request):
    roots = _roots()
    command = cc.claude_code_command(roots, _command(request, roots))
    manual = 'claude mcp add --scope user obscura -- ' + ' '.join(shlex.quote(part) for part in command)
    claude = cc.find_claude_code(roots)
    if claude is None:
        return JSONResponse({'found': False, 'command': manual}, status_code=404)
    return {'found': True, 'connected': cc.connect_claude_code(claude, command), 'command': manual}


@router.post('/api/connect/claude-desktop/restart')
def restart_desktop(request: Request):
    roots = _roots()
    config = cc.find_desktop_config(roots)
    if config is None:
        return _refusal(request, NO_DESKTOP_CONFIG, 404, fallback=True)
    return {'started': cc.restart_desktop(config, roots)}
