"""R26-CLI-LANG-S02 (#32): a refused start speaks the Windows display language; technical detail stays in the English log."""
import pytest

from storygen import build_edition, desktop, desktop_tray
from tests.test_desktop import _old_schema, close_desktop_logging  # noqa: F401 - autouse fixture

UK = {
    'marker': 'Ця збірка Obscura пошкоджена: файл видання не читається. Перевстановіть застосунок.',
    'backup': 'Резервну копію перед оновленням бази не створено, тому базу не змінено.',
    'server': 'Obscura не вдалося запустити.',
    'unexpected': 'Запуск зупинено через непередбачену помилку.',
}
EN = {
    'marker': 'This Obscura build is damaged: its edition file cannot be read. Reinstall the app.',
    'backup': 'No backup could be made before updating the database, so the database was not changed.',
    'server': 'Obscura could not start.',
    'unexpected': 'The start was stopped by an unexpected error.',
}
LOG = {'uk': 'Подробиці в журналі: {}', 'en': 'Details in the log: {}'}


class Dead:
    started, should_exit = False, False

    def run(self):
        raise RuntimeError('cannot bind')


def refuse(tmp_path, monkeypatch, case):
    data, serve = tmp_path / 'data', None
    if case == 'marker':
        def broken():
            raise ValueError('Invalid build edition file build_edition.json: unknown edition or extra fields')
        monkeypatch.setattr(build_edition, 'current', broken)
    elif case == 'backup':
        data = _old_schema(tmp_path)
        (tmp_path / (data.name + '-backups')).write_text('not a folder', encoding='utf-8')
    elif case == 'server':
        serve = lambda app, port: Dead()  # noqa: E731
    else:
        def boom(*args):
            raise KeyError('secret detail')
        monkeypatch.setattr(desktop, '_run', boom)
    alerts = []
    code = desktop.main(['--data-dir', str(data), '--no-browser', '--no-tray'], serve=serve, alert=alerts.append)
    return code, alerts, data / 'logs' / 'obscura.log'


@pytest.mark.req('R26-CLI-LANG')
@pytest.mark.parametrize('locale,texts', [('uk', UK), ('en', EN)])
@pytest.mark.parametrize('case,code', [('marker', 2), ('backup', 3), ('server', 4), ('unexpected', 4)])
def test_refused_start_alert_follows_the_windows_language(tmp_path, monkeypatch, locale, texts, case, code):
    monkeypatch.setattr(desktop_tray, 'system_locale', lambda: locale)
    got, alerts, log = refuse(tmp_path, monkeypatch, case)
    assert (got, alerts) == (code, [texts[case] + '\n\n' + LOG[locale].format(log)])


@pytest.mark.req('R26-CLI-LANG')
def test_technical_reason_goes_to_the_log_not_the_alert(tmp_path, monkeypatch):
    monkeypatch.setattr(desktop_tray, 'system_locale', lambda: 'uk')
    code, alerts, log = refuse(tmp_path, monkeypatch, 'marker')
    assert code == 2 and 'unknown edition' in log.read_text(encoding='utf-8') and 'unknown edition' not in alerts[0]


@pytest.mark.req('R26-CLI-LANG')
@pytest.mark.parametrize('locale,expected', [('uk', 'Obscura не може створити теку даних {}'),
                                             ('en', 'Obscura cannot create the data folder {}')])
def test_data_folder_alert_names_the_folder(tmp_path, monkeypatch, locale, expected):
    monkeypatch.setattr(desktop_tray, 'system_locale', lambda: locale)
    blocker = tmp_path / 'file'
    blocker.write_text('x', encoding='utf-8')
    data = blocker / 'data'
    alerts = []
    assert desktop.main(['--data-dir', str(data), '--no-browser', '--no-tray'], alert=alerts.append) == 4
    prefix = expected.split('{}')[0]
    assert len(alerts) == 1 and alerts[0].startswith(prefix + str(data.resolve()) + ' (') and '{p' not in alerts[0]


@pytest.mark.req('R26-CLI-LANG')
def test_alert_survives_a_failing_language_lookup(tmp_path, monkeypatch):
    def broken():
        raise OSError('no language')
    monkeypatch.setattr(desktop_tray, 'system_locale', broken)
    code, alerts, log = refuse(tmp_path, monkeypatch, 'server')
    assert (code, alerts) == (4, [EN['server'] + '\n\n' + LOG['en'].format(log)])
