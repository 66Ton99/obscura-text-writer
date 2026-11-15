"""STORE-MCP: the bridge finds the running Obscura of a data folder and starts it quietly when it is not running.

Discovery reuses the desktop record (`server.json` + `instance_id`, DESKTOP-001), so a busy port 8765 needs no
manual address. The start is lazy (the first tool call) and happens once even when several calls arrive together.
"""
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable

import httpx

DEFAULT_URL = 'http://127.0.0.1:8765'
START_TIMEOUT = 30.0
START_FAILED = ('Obscura не запустилася за {seconds} с. Відкрийте Obscura з меню «Пуск» і повторіть запит; '
                'якщо вона не відкривається, подробиці є в журналі теки творів (logs/obscura.log).')
DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_BREAKAWAY_FROM_JOB = 0x01000000


class ObscuraUnavailable(Exception):
    """Obscura did not answer after a quiet start; the text is meant for the person in the chat."""


def _locate(data_dir: Path) -> str | None:
    from ..desktop import running_server
    return running_server(data_dir)


def start_obscura(data_dir: Path) -> None:
    """Start Obscura without a browser window, detached from the bridge so that it outlives the chat session."""
    if getattr(sys, 'frozen', False):
        argv = [str(Path(sys.executable).with_name('Obscura.exe'))]
    else:
        argv = [sys.executable, '-m', 'storygen.desktop']
    argv += ['--no-browser', '--data-dir', str(data_dir)]
    # stdout of the bridge is the MCP channel: the child must never inherit it.
    options = {'stdin': subprocess.DEVNULL, 'stdout': subprocess.DEVNULL, 'stderr': subprocess.DEVNULL, 'close_fds': True}
    if sys.platform != 'win32':
        subprocess.Popen(argv, start_new_session=True, **options)
        return
    flags = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    try:
        # A chat client may run the bridge in a job that kills its children on exit; Obscura should stay in the tray.
        subprocess.Popen(argv, creationflags=flags | CREATE_BREAKAWAY_FROM_JOB, **options)
    except OSError:
        subprocess.Popen(argv, creationflags=flags, **options)


class Connection:
    """HTTP access to Obscura: a fixed `explicit_url`, or the server of `data_dir`, found or started on demand."""

    def __init__(self, data_dir: Path | None, explicit_url: str | None, *, client_factory: Callable[[str], httpx.Client],
                 locate: Callable[[Path], str | None] = _locate, start: Callable[[], None] | None = None,
                 wait: float = START_TIMEOUT, poll: float = 0.25):
        if (data_dir is None) == (explicit_url is None):
            raise ValueError('Connection needs exactly one of data_dir and explicit_url')
        self._data_dir, self._explicit = data_dir, explicit_url
        self._factory, self._locate, self._wait, self._poll = client_factory, locate, wait, poll
        self._start = start or (lambda: start_obscura(data_dir))
        self._lock = threading.Lock()
        self._client: httpx.Client | None = None
        self._url: str | None = explicit_url

    @property
    def base(self) -> str:
        return (self._url or DEFAULT_URL).rstrip('/')

    def request(self, method: str, path: str, **kwargs) -> httpx.Response:
        client = self._ready()
        if self._explicit:
            return client.request(method, path, **kwargs)
        try:
            return client.request(method, path, **kwargs)
        except httpx.ConnectError:
            # The connection was refused, so the request never reached Obscura: find or start it again, once.
            self._forget(client)
            return self._ready().request(method, path, **kwargs)

    def close(self) -> None:
        with self._lock:
            if self._client is not None:
                self._client.close()
                self._client = None

    def _forget(self, client: httpx.Client) -> None:
        with self._lock:
            if self._client is client:
                client.close()
                self._client = None

    def _ready(self) -> httpx.Client:
        with self._lock:
            if self._client is None:
                self._url = self._explicit or self._find()
                self._client = self._factory(self._url)
            return self._client

    def _find(self) -> str:
        url = self._locate(self._data_dir)
        if url:
            return url
        self._start()
        deadline = time.monotonic() + self._wait
        while time.monotonic() < deadline:
            time.sleep(self._poll)
            url = self._locate(self._data_dir)
            if url:
                return url
        raise ObscuraUnavailable(START_FAILED.format(seconds=round(self._wait)))
