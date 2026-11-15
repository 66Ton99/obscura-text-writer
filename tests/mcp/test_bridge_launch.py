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


@pytest.mark.req('STORE-MCP-001')
def test_running_server_is_found_through_the_record(tmp_path):
    seen, started = [], []
    connection = Connection(tmp_path, None, client_factory=factory(answering(seen)),
                            locate=Sequence('http://127.0.0.1:8770'), start=lambda: started.append(1))
    assert connection.request('GET', '/api/stories').status_code == 200
    assert seen == ['http://127.0.0.1:8770/api/stories'] and started == []
    assert connection.base == 'http://127.0.0.1:8770'


@pytest.mark.req('STORE-MCP-001')
def test_missing_server_is_started_once_and_awaited(tmp_path):
    seen, started = [], []
    locate = Sequence(None, None, 'http://127.0.0.1:8771')
    connection = Connection(tmp_path, None, client_factory=factory(answering(seen)), locate=locate,
                            start=lambda: started.append(1), wait=5, poll=0.01)
    assert connection.request('GET', '/api/stories').status_code == 200
    assert started == [1] and seen == ['http://127.0.0.1:8771/api/stories']


@pytest.mark.req('STORE-MCP-001')
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


@pytest.mark.req('STORE-MCP-001')
def test_server_that_never_answers_is_a_human_error(tmp_path):
    connection = Connection(tmp_path, None, client_factory=factory(answering([])), locate=Sequence(None),
                            start=lambda: None, wait=0.2, poll=0.01)
    with pytest.raises(launch.ObscuraUnavailable) as raised:
        connection.request('GET', '/api/stories')
    assert 'не запустилася' in str(raised.value) and 'меню «Пуск»' in str(raised.value)


@pytest.mark.req('STORE-MCP-001')
def test_unavailable_obscura_reaches_the_chat_as_a_tool_error(tmp_path):
    connection = Connection(tmp_path, None, client_factory=factory(answering([])), locate=Sequence(None),
                            start=lambda: None, wait=0.1, poll=0.01)

    async def run():
        async with Client(build_server(None, connection=connection)) as client:
            return await client.call_tool('list_stories', {})
    result = anyio.run(run)
    text = ''.join(getattr(item, 'text', '') for item in result.content)
    assert result.is_error and 'меню «Пуск»' in text and 'Traceback' not in text


@pytest.mark.req('STORE-MCP-001')
def test_stopped_server_is_found_again(tmp_path):
    seen, stopped = [], threading.Event()

    def handler(request):
        if request.url.port == 8773 and stopped.is_set():
            raise httpx.ConnectError('refused', request=request)
        seen.append(str(request.url))
        return httpx.Response(200, json=[])
    locate = Sequence('http://127.0.0.1:8773', 'http://127.0.0.1:8774')
    started = []
    connection = Connection(tmp_path, None, client_factory=factory(handler), locate=locate, start=lambda: started.append(1))
    assert connection.request('GET', '/api/stories').status_code == 200
    stopped.set()  # Obscura is closed and started again on another port between two chat calls
    assert connection.request('GET', '/api/stories').status_code == 200
    assert seen == ['http://127.0.0.1:8773/api/stories', 'http://127.0.0.1:8774/api/stories']
    assert connection.base == 'http://127.0.0.1:8774' and locate.calls == 2 and started == []


@pytest.mark.req('STORE-MCP-001')
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


@pytest.mark.req('STORE-MCP-001')
def test_explicit_url_never_starts_obscura(tmp_path):
    calls = []

    def refused(request):
        raise httpx.ConnectError('refused', request=request)
    connection = Connection(None, 'http://127.0.0.1:8799', client_factory=factory(refused),
                            locate=lambda data_dir: calls.append('locate'), start=lambda: calls.append('start'))
    with pytest.raises(httpx.ConnectError):
        connection.request('GET', '/api/stories')
    assert calls == [] and connection.base == 'http://127.0.0.1:8799'


@pytest.mark.req('STORE-MCP-001')
def test_nothing_happens_before_the_first_tool_call(tmp_path):
    calls = []
    connection = Connection(tmp_path, None, client_factory=factory(answering([])),
                            locate=lambda data_dir: calls.append('locate'), start=lambda: calls.append('start'))

    async def run():
        async with Client(build_server(None, connection=connection)) as client:
            return [tool.name for tool in (await client.list_tools()).tools]
    assert 'list_stories' in anyio.run(run)
    assert calls == []


@pytest.mark.req('STORE-MCP-001')
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


@pytest.mark.req('STORE-MCP-001')
@pytest.mark.skipif(sys.platform != 'win32', reason='process creation flags are Windows-only')
def test_start_obscura_detaches_from_the_bridge(tmp_path, monkeypatch):
    monkeypatch.delattr(sys, 'frozen', raising=False)
    calls = []
    monkeypatch.setattr(launch.subprocess, 'Popen', lambda argv, **kwargs: calls.append(kwargs))
    launch.start_obscura(tmp_path)
    flags = calls[0]['creationflags']
    assert flags & launch.DETACHED_PROCESS and flags & launch.CREATE_NEW_PROCESS_GROUP and flags & launch.CREATE_BREAKAWAY_FROM_JOB


@pytest.mark.req('STORE-MCP-001')
def test_start_obscura_in_a_checkout_uses_the_desktop_module(tmp_path, monkeypatch):
    monkeypatch.delattr(sys, 'frozen', raising=False)
    calls = []
    monkeypatch.setattr(launch.subprocess, 'Popen', lambda argv, **kwargs: calls.append(argv))
    launch.start_obscura(tmp_path)
    assert calls == [[sys.executable, '-m', 'storygen.desktop', '--no-browser', '--data-dir', str(tmp_path)]]


@pytest.mark.req('STORE-MCP-001')
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


@pytest.mark.req('STORE-MCP-001')
def test_help_survives_a_legacy_code_page(monkeypatch):
    # A client reads the bridge through pipes, which Windows opens in the ANSI code page, not UTF-8.
    import io
    from storygen.mcp import bridge
    raw = io.BytesIO()
    monkeypatch.setattr(sys, 'stdout', io.TextIOWrapper(raw, encoding='cp1250'))
    with pytest.raises(SystemExit) as exited:
        bridge.main(['--help'])
    sys.stdout.flush()
    assert exited.value.code == 0 and 'storygen-mcp' in raw.getvalue().decode('utf-8') and 'тека творів' in raw.getvalue().decode('utf-8')


@pytest.mark.req('STORE-MCP-001')
def test_checkout_without_arguments_keeps_the_old_address(monkeypatch):
    # The checkout's `storygen` serves ./data on 8765 and writes no record: searching %USERPROFILE%\Obscura there would
    # start a second Obscura over another library.
    from storygen.mcp import bridge
    monkeypatch.delattr(sys, 'frozen', raising=False)
    connection = bridge.connection_for(None, None)
    assert connection.base == launch.DEFAULT_URL and connection._explicit == launch.DEFAULT_URL and connection._data_dir is None


@pytest.mark.req('STORE-MCP-001')
def test_installed_bridge_and_explicit_folder_search_the_record(tmp_path, monkeypatch):
    from storygen.mcp import bridge
    assert bridge.connection_for(None, tmp_path)._data_dir == tmp_path.resolve()
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setattr('storygen.desktop.default_data_dir', lambda: tmp_path)
    assert bridge.connection_for(None, None)._data_dir == tmp_path.resolve()


@pytest.mark.req('STORE-MCP-001')
def test_self_check_builds_the_http_client_and_exits(capsys):
    # The build runs this next to Obscura.exe: `--help` alone never creates the TLS context the first tool call needs.
    from storygen.mcp import bridge
    with pytest.raises(SystemExit) as exited:
        bridge.main(['--self-check'])
    assert exited.value.code == 0 and 'storygen-mcp: ok' in capsys.readouterr().out
