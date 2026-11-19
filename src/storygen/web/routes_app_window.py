"""DESKTOP-001-S08: the Obscura window sends links to other sites here, and they open in the default browser.

Exists only for a desktop launch (`app.state.app_window`); elsewhere the page is already in the author's browser.
The Origin check of app.py turns away other sites; the chat may not open pages on the author's desktop.
"""
from urllib.parse import urlsplit

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from .bridge_marker import from_bridge
from .localization import diagnostic, request_locale

router = APIRouter()

NOT_A_WEB_ADDRESS = 'Відкрити у браузері можна лише адресу http або https'
AUTHOR_ONLY = 'Відкривати сторінки у браузері автора може лише сама Obscura'


class ExternalLink(BaseModel):
    url: str


def _refuse(request: Request, text: str, status: int) -> JSONResponse:
    return JSONResponse({'detail': diagnostic(text, request_locale(request)), 'detail_original': text}, status_code=status)


def web_address(url: str) -> bool:
    parts = urlsplit(url)
    return parts.scheme in {'http', 'https'} and bool(parts.netloc)


@router.post('/api/app-window/open-external')
def open_external(link: ExternalLink, request: Request):
    window = getattr(request.app.state, 'app_window', None)
    if window is None:
        return Response(status_code=404)
    if from_bridge(request):
        return _refuse(request, AUTHOR_ONLY, 403)
    if not web_address(link.url):
        return _refuse(request, NOT_A_WEB_ADDRESS, 422)
    window.open_external(link.url)
    return Response(status_code=204)
