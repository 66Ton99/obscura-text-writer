"""DESKTOP-001: launcher of the installed build — no console, a data folder in the user profile, a file log.

`storygen` (server.py) stays the developer entry point with a console. This one never relies on stdout or stderr:
a windowed executable has neither.
"""
import argparse
import http.client
import json
import logging
import os
import socket
import sys
import threading
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

RECORD = 'server.json'
LOOPBACK = 'http://127.0.0.1:'
PREFERRED_PORT = 8765
START_TIMEOUT = 30.0
# Seconds uvicorn waits for open connections (the run event stream) before it closes them and shuts the app down.
GRACEFUL_SHUTDOWN = 5
STOP_TIMEOUT = 30.0
logger = logging.getLogger('storygen.desktop')
_handler = None
_previous_level = None


def default_data_dir() -> Path:
    # The profile folder itself: AppData of a packaged app is removed with the app, Documents is often synced to a cloud.
    home = Path(os.environ['USERPROFILE']) if os.name == 'nt' and os.environ.get('USERPROFILE') else Path.home()
    return home / 'Obscura'


def close_logging() -> None:
    global _handler, _previous_level
    if _handler is not None:
        root = logging.getLogger()
        root.removeHandler(_handler)
        _handler.close()
        _handler = None
        if _previous_level is not None:
            root.setLevel(_previous_level)
            _previous_level = None


def configure_logging(data_dir: Path) -> Path:
    """Send every log record to <data>/logs/obscura.log; calling it again replaces the handler."""
    global _handler, _previous_level
    path = Path(data_dir) / 'logs' / 'obscura.log'
    path.parent.mkdir(parents=True, exist_ok=True)
    close_logging()
    root = logging.getLogger()
    _handler = RotatingFileHandler(path, maxBytes=1_000_000, backupCount=3, encoding='utf-8')
    _handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s'))
    _previous_level = root.level
    root.addHandler(_handler)
    root.setLevel(logging.INFO)
    return path


def choose_port(preferred: int = PREFERRED_PORT) -> int:
    for candidate in (preferred, 0):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            try:
                probe.bind(('127.0.0.1', candidate))
            except OSError:
                continue
            return probe.getsockname()[1]
    raise OSError('Немає вільного порту на 127.0.0.1')


def write_server_record(data_dir: Path, url: str, instance_id: str) -> None:
    path = Path(data_dir) / RECORD
    temporary = path.with_name(RECORD + '.tmp')
    temporary.write_text(json.dumps({'url': url, 'instance_id': instance_id, 'pid': os.getpid()}), encoding='utf-8')
    os.replace(temporary, path)


def remove_server_record(data_dir: Path) -> None:
    (Path(data_dir) / RECORD).unlink(missing_ok=True)


def _ask_loopback(port: int, path: str, timeout: float) -> bytes | None:
    """One plain HTTP GET to this computer: no proxy, no redirect, and no TLS machinery (a frozen build may not be
    able to build a TLS context this early)."""
    connection = http.client.HTTPConnection('127.0.0.1', port, timeout=timeout)
    try:
        connection.request('GET', path)
        response = connection.getresponse()
        return response.read(65536) if response.status == 200 else None
    finally:
        connection.close()


def running_server(data_dir: Path, timeout: float = 1.0) -> str | None:
    """Address of the server already running over this data folder, or None.

    The record alone proves nothing: the process may have died and another program may listen on that port. Only a
    loopback server that answers with the recorded instance id is this folder's server."""
    try:
        record = json.loads((Path(data_dir) / RECORD).read_text(encoding='utf-8'))
        url, instance_id = record['url'], record['instance_id']
        port = url[len(LOOPBACK):] if isinstance(url, str) and url.startswith(LOOPBACK) else ''
        if not (port.isascii() and port.isdigit() and isinstance(instance_id, str)):
            return None
        body = _ask_loopback(int(port), '/api/app-info', timeout)
        answer = json.loads(body) if body is not None else None
        return url if isinstance(answer, dict) and answer.get('instance_id') == instance_id else None
    except Exception:
        return None


def uvicorn_server(app, port: int):
    import uvicorn
    # log_config=None: uvicorn's default config writes to stderr, which a windowed process does not have.
    # access_log=False: request lines carry search text and file names that do not belong in a support log.
    # timeout_graceful_shutdown: an open run event stream must not keep "Quit" from reaching the app shutdown.
    return uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port, workers=1, log_config=None, access_log=False,
                                         timeout_graceful_shutdown=GRACEFUL_SHUTDOWN))


def _default_alert(text: str) -> None:
    """Tell the person why nothing opened: a message box for a windowed process, stderr for a console one."""
    try:
        if sys.stderr is not None:
            print(text, file=sys.stderr)
        elif os.name == 'nt':
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, text, 'Obscura', 0x10)
    except Exception:
        pass


def _wait_until_started(server, thread) -> bool:
    deadline = time.monotonic() + START_TIMEOUT
    while time.monotonic() < deadline:
        if server.started:
            return True
        if not thread.is_alive():
            return False
        time.sleep(0.05)
    return False


def _already_running(data_dir: Path, seconds: float) -> str | None:
    deadline = time.monotonic() + seconds
    while True:
        url = running_server(data_dir)
        if url or time.monotonic() >= deadline:
            return url
        time.sleep(0.5)


def main(argv=None, *, opener=None, window=None, tray=None, serve=None, alert=None) -> int:
    """Exit codes: 0 — ran or already running, 2 — invalid build edition marker, 3 — no backup before a migration,
    4 — the server did not start. A refused start is reported through `alert` with the path of the log.
    `window(url, data_dir)` makes the Obscura window (DESKTOP-001-S07, default `AppWindow`); a plain `opener(url)`
    stands in for it in tests."""
    parser = argparse.ArgumentParser(description='Obscura Text Writer')
    parser.add_argument('--data-dir', type=Path, default=None)
    parser.add_argument('--env-file', type=Path, default=None, help='file with provider keys; default: .env in the data folder')
    parser.add_argument('--no-tray', action='store_true')
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--self-check', type=Path, default=None, metavar='REPORT')
    args = parser.parse_args(argv)
    if args.self_check is not None:
        # PACKAGING-001-S01: the build asks the built application what it can do; nothing is started or touched.
        from .self_check import run_checks
        report = run_checks()
        args.self_check.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        return 0 if report['ok'] else 5
    alert = alert or _default_alert
    data_dir = (args.data_dir or default_data_dir()).resolve()
    try:
        log = configure_logging(data_dir)
    except OSError as error:
        alert(f'Obscura не може створити теку даних {data_dir}: {type(error).__name__}')
        return 4
    try:
        code, reason = _run(args, data_dir, _window_factory(opener, window, data_dir), tray, serve or uvicorn_server)
    except Exception:
        logger.exception('Запуск зупинено через непередбачену помилку')
        code, reason = 4, 'Запуск зупинено через непередбачену помилку.'
    finally:
        close_logging()
    if code:
        alert(f'{reason}\n\nПодробиці в журналі: {log}')
    return code


def _refresh_skills(data_dir: Path) -> None:
    """STORE-MCP-001 S14: refresh the skills copy Claude Code reads, if the author connected it; never fails the launch."""
    try:
        from . import claude_connect, skill_bundles
        from .build_manifest import project_version
        source = skill_bundles.marketplace_source(frozen=getattr(sys, 'frozen', False), executable=Path(sys.executable),
                                                  checkout=Path(__file__).resolve().parents[2])
        claude_connect.refresh_marketplace(source, claude_connect.marketplace_target(data_dir), project_version())
    except Exception:  # noqa: BLE001 - a background helper: the log is the only place for it
        logger.exception('Скіли Claude: оновлення копії не вдалося')


class _OpenerWindow:
    """A window that is only a call to `opener`: nothing to bring forward or to close."""

    def __init__(self, url, opener):
        self.url, self._opener = url, opener

    def show(self):
        self._opener(self.url)

    def close(self):
        pass

    def open_external(self, url):
        self._opener(url)


def _window_factory(opener, window, data_dir: Path):
    def make(url):
        if window is not None:
            return window(url, data_dir)
        if opener is not None:
            return _OpenerWindow(url, opener)
        from .app_window import AppWindow
        return AppWindow(url, data_dir)
    return make


def _run(args, data_dir: Path, make_window, tray, serve) -> tuple[int, str | None]:
    from . import build_edition
    try:
        build_edition.current()
    except ValueError as error:
        # BUILD-EDITION-001-S04: nothing but the log is created for a build with a broken marker.
        logger.error('%s', error)
        return 2, str(error)

    def open_page(url):
        # DESKTOP-001-S07: a second launch finds the window of the first one by its Edge profile and brings it forward.
        if not args.no_browser:
            make_window(url).show()
    url = running_server(data_dir)
    if url:
        logger.info('Сервер цієї теки даних уже працює: %s', url)
        open_page(url)
        return 0, None
    from .application.settings import AppSettings
    from .storage.pre_migration import PreMigrationBackupFailed, backup_before_migration
    from .web.app import create_app
    try:
        copy = backup_before_migration(data_dir)
    except PreMigrationBackupFailed as error:
        # DESKTOP-001-S03: without a verified copy the database is not opened, so it is not migrated.
        logger.error('%s', error)
        return 3, str(error)
    if copy is not None:
        logger.info('Перед оновленням бази створено резервну копію: %s', copy)
    port = choose_port()
    env_file = args.env_file.resolve() if args.env_file else data_dir / '.env'
    app = create_app(AppSettings(data_dir=data_dir, env_file=env_file, port=port))
    window = make_window(f'{LOOPBACK}{port}')
    app.state.app_window = window  # DESKTOP-001-S08: the page sends external links here
    server = serve(app, port)
    thread = threading.Thread(target=_serve, args=(server,), name='obscura-server', daemon=True)
    thread.start()
    wrote_record = False

    def stop():
        server.should_exit = True
    try:
        if not _wait_until_started(server, thread):
            # Most often another launch of this very folder won the race for the data folder lock: open that one.
            url = _already_running(data_dir, 5.0)
            if url:
                logger.info('Сервер цієї теки даних уже працює: %s', url)
                open_page(url)
                return 0, None
            logger.error('Сервер не стартував на порту %s', port)
            return 4, 'Obscura не вдалося запустити.'
        url = f'{LOOPBACK}{port}'
        write_server_record(data_dir, url, app.state.instance_id)
        wrote_record = True
        threading.Thread(target=_refresh_skills, args=(data_dir,), name='obscura-skills', daemon=True).start()
        logger.info('Сервер працює: %s; тека даних: %s', url, data_dir)
        # DESKTOP-001-S07: a window left by a crashed run may show an old address; it gives way to a fresh one.
        replace_stale = getattr(window, 'replace_stale', None)
        if replace_stale:
            replace_stale()
        if not args.no_browser:
            window.show()
        if not args.no_tray:
            from .desktop_tray import TrayUnavailable, run_tray
            from .storage.pre_migration import backups_dir
            try:
                # Blocks until "Quit"; a stand-in is injected by tests.
                def quit_application():
                    window.close()  # the server stops, so the window would be dead
                    stop()
                (tray or run_tray)(url, data_dir, backups_dir(data_dir), quit_application, opener=lambda *_: window.show())
                return 0, None
            except TrayUnavailable:
                logger.warning('Значок у треї недоступний; застосунок працює без нього, доки процес не зупинять')
        while thread.is_alive():
            thread.join(0.5)
        return 0, None
    except KeyboardInterrupt:
        return 0, None
    finally:
        stop()
        thread.join(STOP_TIMEOUT)
        # Only the record this process wrote is its to remove: a failed second start must not hide the first instance.
        if wrote_record:
            remove_server_record(data_dir)
        if thread.is_alive():
            logger.error('Сервер не завершився за %s с; процес завершується примусово', int(STOP_TIMEOUT))
        else:
            logger.info('Сервер зупинено')


def _serve(server) -> None:
    try:
        server.run()
    except BaseException:  # uvicorn exits the thread with SystemExit when it cannot bind
        logger.exception('Сервер завершився з помилкою')


if __name__ == '__main__':
    raise SystemExit(main())
