"""STORE-MCP: the bridge finds a running Obscura through its record and starts it quietly when it is not running."""
import subprocess
import sys
import threading

import anyio
import httpx
import pytest

pytest.importorskip('mcp')
from mcp import Client  # noqa: E402

from storygen.mcp import launch  # noqa: E402
from storygen.mcp.bridge import build_server  # noqa: E402
from storygen.mcp.launch import Connection  # noqa: E402

pytestmark = pytest.mark.req('STORE-MCP')


def answering(seen):
    def handler(request):
        seen.append(str(request.url))
        return httpx.Response(200, json=[])
    return handler


def factory(handler):
    return lambda url: httpx.Client(base_url=url, transport=httpx.MockTransport(handler))


class Sequence:
    """`locate` returning the given answers in order and then the last one forever."""

    def __init__(self, *answers):
        self.answers, self.calls = list(answers), 0

    def __call__(self, data_dir):
        self.calls += 1
        return self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]


def test_running_server_is_found_through_the_record(tmp_path):
    seen, started = [], []
    connection = Connection(tmp_path, None, client_factory=factory(answering(seen)),
                            locate=Sequence('http://127.0.0.1:8770'), start=lambda: started.append(1))
    assert connection.request('GET', '/api/stories').status_code == 200
    assert seen == ['http://127.0.0.1:8770/api/stories'] and started == []
    assert connection.base == 'http://127.0.0.1:8770'


def test_missing_server_is_started_once_and_awaited(tmp_path):
    seen, started = [], []
    locate = Sequence(None, None, 'http://127.0.0.1:8771')
    connection = Connection(tmp_path, None, client_factory=factory(answering(seen)), locate=locate,
                            start=lambda: started.append(1), wait=5, poll=0.01)
    assert connection.request('GET', '/api/stories').status_code == 200
    assert started == [1] and seen == ['http://127.0.0.1:8771/api/stories']


def test_concurrent_calls_start_obscura_once(tmp_path):
    started, ready = [], threading.Event()

    def locate(data_dir):
        return 'http://127.0.0.1:8772' if ready.is_set() else None

    def start():
        started.append(1)
        threading.Timer(0.2, ready.set).start()
    connection = Connection(tmp_path, None, client_factory=factory(answering([])), locate=locate, start=start, wait=5, poll=0.01)
    results = []
    threads = [threading.Thread(target=lambda: results.append(connection.request('GET', '/api/stories').status_code)) for _ in range(3)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(10)
    assert started == [1] and results == [200, 200, 200]


def test_server_that_never_answers_is_a_human_error(tmp_path):
    connection = Connection(tmp_path, None, client_factory=factory(answering([])), locate=Sequence(None),
                            start=lambda: None, wait=0.2, poll=0.01)
    with pytest.raises(launch.ObscuraUnavailable) as raised:
        connection.request('GET', '/api/stories')
    assert 'не запустилася' in str(raised.value) and 'меню «Пуск»' in str(raised.value)


def test_unavailable_obscura_reaches_the_chat_as_a_tool_error(tmp_path):
    connection = Connection(tmp_path, None, client_factory=factory(answering([])), locate=Sequence(None),
                            start=lambda: None, wait=0.1, poll=0.01)

    async def run():
        async with Client(build_server(None, connection=connection)) as client:
            return await client.call_tool('list_stories', {})
    result = anyio.run(run)
    text = ''.join(getattr(item, 'text', '') for item in result.content)
    assert result.is_error and 'меню «Пуск»' in text and 'Traceback' not in text


def test_stopped_server_is_found_again(tmp_path):
    seen = []

    def handler(request):
        if request.url.port == 8773:
            raise httpx.ConnectError('refused', request=request)
        seen.append(str(request.url))
        return httpx.Response(200, json=[])
    locate = Sequence('http://127.0.0.1:8773', 'http://127.0.0.1:8774')
    started = []
    connection = Connection(tmp_path, None, client_factory=factory(handler), locate=locate, start=lambda: started.append(1))
    assert connection.request('GET', '/api/stories').status_code == 200
    assert seen == ['http://127.0.0.1:8774/api/stories'] and connection.base == 'http://127.0.0.1:8774' and started == []


def test_broken_answer_is_not_repeated(tmp_path):
    # Only a refused connection is retried: a request that may have reached Obscura is never sent twice.
    sent = []

    def handler(request):
        sent.append(1)
        raise httpx.ReadError('cut', request=request)
    connection = Connection(tmp_path, None, client_factory=factory(handler), locate=Sequence('http://127.0.0.1:8775'),
                            start=lambda: None)
    with pytest.raises(httpx.ReadError):
        connection.request('POST', '/api/stories')
    assert sent == [1]


def test_explicit_url_never_starts_obscura(tmp_path):
    calls = []

    def refused(request):
        raise httpx.ConnectError('refused', request=request)
    connection = Connection(None, 'http://127.0.0.1:8799', client_factory=factory(refused),
                            locate=lambda data_dir: calls.append('locate'), start=lambda: calls.append('start'))
    with pytest.raises(httpx.ConnectError):
        connection.request('GET', '/api/stories')
    assert calls == [] and connection.base == 'http://127.0.0.1:8799'


def test_nothing_happens_before_the_first_tool_call(tmp_path):
    calls = []
    connection = Connection(tmp_path, None, client_factory=factory(answering([])),
                            locate=lambda data_dir: calls.append('locate'), start=lambda: calls.append('start'))

    async def run():
        async with Client(build_server(None, connection=connection)) as client:
            return [tool.name for tool in (await client.list_tools()).tools]
    assert 'list_stories' in anyio.run(run)
    assert calls == []


def test_start_obscura_runs_the_sibling_exe_without_browser(tmp_path, monkeypatch):
    (tmp_path / 'Obscura.exe').write_bytes(b'')
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setattr(sys, 'executable', str(tmp_path / 'obscura-mcp.exe'))
    calls = []
    monkeypatch.setattr(launch.subprocess, 'Popen', lambda argv, **kwargs: calls.append((argv, kwargs)))
    launch.start_obscura(tmp_path / 'data')
    argv, kwargs = calls[0]
    assert argv == [str(tmp_path / 'Obscura.exe'), '--no-browser', '--data-dir', str(tmp_path / 'data')]
    assert kwargs['stdin'] is kwargs['stdout'] is kwargs['stderr'] is subprocess.DEVNULL
    if sys.platform == 'win32':
        assert kwargs['creationflags'] & subprocess.DETACHED_PROCESS


def test_start_obscura_in_a_checkout_uses_the_desktop_module(tmp_path, monkeypatch):
    monkeypatch.delattr(sys, 'frozen', raising=False)
    calls = []
    monkeypatch.setattr(launch.subprocess, 'Popen', lambda argv, **kwargs: calls.append(argv))
    launch.start_obscura(tmp_path)
    assert calls == [[sys.executable, '-m', 'storygen.desktop', '--no-browser', '--data-dir', str(tmp_path)]]


def test_start_falls_back_when_the_job_forbids_breakaway(tmp_path, monkeypatch):
    if sys.platform != 'win32':
        pytest.skip('job objects are Windows-only')
    monkeypatch.delattr(sys, 'frozen', raising=False)
    flags = []

    def popen(argv, **kwargs):
        flags.append(kwargs['creationflags'])
        if kwargs['creationflags'] & launch.CREATE_BREAKAWAY_FROM_JOB:
            raise PermissionError('breakaway denied')
    monkeypatch.setattr(launch.subprocess, 'Popen', popen)
    launch.start_obscura(tmp_path)
    assert len(flags) == 2 and not flags[1] & launch.CREATE_BREAKAWAY_FROM_JOB
