# MCP «з коробки» у Store: план ядра

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** міст MCP сам знаходить запущену Obscura й тихо запускає її, якщо її немає, а пакет MSIX несе консольний `obscura-mcp.exe` зі сталим псевдонімом запуску.

**Architecture:** новий модуль `storygen/mcp/launch.py` (пошук сервера за `server.json` і автозапуск) під `build_server` через ліниве з’єднання; `build_store.py` заморожує другий консольний артефакт мосту з власною текою вмісту й кладе його поруч з `Obscura.exe`; маніфест отримує `uap3:AppExecutionAlias`. Обв’язка (кнопки підключення, `.mcpb`, поведінка в чаті) — окремий план після рев’ю ядра й результатів Кроку 0.

**Tech Stack:** Python 3.12, httpx, `mcp==2.3.0`, PyInstaller 6, MSIX (`makeappx`), pytest.

**Spec:** `docs/superpowers/specs/2026-11/2026-11-15-store-mcp-out-of-box-design.md` (PR #178).

## Global Constraints

- Робоча копія з явним `--url` поводиться як зараз: без пошуку й без автозапуску.
- Тека даних моста — та сама, що в `desktop.default_data_dir()` (`%USERPROFILE%\Obscura`); прапорець `--data-dir` для нестандартної теки.
- Автозапуск: `--no-browser`, без вікна консолі, без ключів у аргументах; очікування готовності до 30 с.
- Автозапуск ліниво: на першому виклику інструмента, не на старті мосту.
- Тексти помилок для людини — українською (як решта `ToolError` мосту).
- Пакет: `storygen.mcp` і `mcp` лишаються виключеними з основного `Obscura.exe`; міст — окремий консольний exe.
- `scripts/check_docs.py` і pytest зелені; SPEC.MD і traceability в тому самому PR.

## Review Focus

- Obscura зупинили посеред розмови: наступний виклик інструмента знаходить або запускає її знову, а не тримає мертву адресу.
- `server.json` вказує на чужий процес на тому самому порту (інший `instance_id`): міст не працює з ним, а запускає Obscura.
- Два виклики інструментів одночасно під час автозапуску: Obscura запускається один раз.
- Obscura не відповіла за 30 с: людський текст із порадою відкрити її з меню «Пуск», без трасування.
- Збірка без `makeappx` (`--skip-msix`) усе одно містить `obscura-mcp.exe` і перевіряє його.

---

### Task 1: пошук сервера й автозапуск у мосту

**Files:**
- Create: `src/storygen/mcp/launch.py`
- Modify: `src/storygen/mcp/bridge.py` (`build_server`, `main`)
- Test: `tests/mcp/test_bridge_launch.py`

**Interfaces:**
- Produces: `class Connection` у `launch.py`: `Connection(data_dir: Path | None, explicit_url: str | None, *, start: Callable[[], None] = start_obscura, locate: Callable[[Path], str | None] = desktop.running_server, wait: float = 30.0, client_factory: Callable[[str], httpx.Client])` — `client_factory` обов’язковий (`bridge.main` передає `build_client`), щоб `launch.py` не імпортував `bridge.py` (циклічний імпорт); метод `request(method: str, path: str, **kwargs) -> httpx.Response`; властивість `base: str` (адреса для текстів помилок; до першого пошуку — `DEFAULT_URL`). `start_obscura() -> None`. `build_server(http: httpx.Client | None, client_name: str | None = None, *, connection: Connection | None = None)` — рівно одне з `http`/`connection`; наявні тести з `http` не змінюються.
- Consumes: `desktop.running_server(data_dir, timeout) -> str | None`, `desktop.default_data_dir()`.

- [ ] **Step 1: Write the failing tests** у `tests/mcp/test_bridge_launch.py` (усі з `@pytest.mark.req('STORE-MCP')`, фальшиві `locate`/`start`, `httpx.MockTransport`):
  - `test_running_server_is_found_through_the_record` — `locate` дає `http://127.0.0.1:8770`; запит іде на цю адресу; `start` не викликано.
  - `test_missing_server_is_started_once_and_awaited` — `locate` дає `None` двічі, потім адресу; `start` викликано рівно один раз; запит успішний.
  - `test_concurrent_calls_start_obscura_once` — два потоки викликають `request` під час автозапуску; `start` викликано один раз.
  - `test_server_that_never_answers_is_a_human_error` — `locate` завжди `None`, `wait=0.2`; `ToolError` містить «не запустилася» і «меню «Пуск»», не містить `Traceback`.
  - `test_stopped_server_is_found_again` — перший запит успішний; транспорт дає `ConnectError`; `locate` повертає нову адресу; другий запит іде на нову адресу.
  - `test_explicit_url_never_starts_obscura` — `explicit_url` задано, транспорт дає `ConnectError`; `ToolError` як у наявному `test_server_not_running_is_a_tool_error_with_the_address`; `start` і `locate` не викликано.
  - `test_nothing_happens_before_the_first_tool_call` — `build_server(None, connection=c)` і `list_tools`; `locate`/`start` не викликано.
  - `test_start_obscura_runs_the_sibling_exe_without_browser` — `sys.frozen=True`, `sys.executable` у тимчасовій теці з файлом `Obscura.exe`; перехоплений `subprocess.Popen` отримує `[<тека>\Obscura.exe, '--no-browser']` і прапорці без консолі (`CREATE_NO_WINDOW | DETACHED_PROCESS` на Windows).
  - `test_start_obscura_in_a_checkout_uses_the_desktop_script` — не frozen: `[sys.executable, '-m', 'storygen.desktop', '--no-browser']`.
- [ ] **Step 2: Run, expect FAIL** — `pytest -q tests/mcp/test_bridge_launch.py` → `ModuleNotFoundError: storygen.mcp.launch`.
- [ ] **Step 3: Implement `launch.py`** — `Connection` з `threading.Lock` навколо пошуку й запуску; кешує `httpx.Client`; на `httpx.TransportError` (не для `explicit_url`) скидає клієнт, повторює пошук/запуск один раз і повторює запит. `start_obscura`: frozen → `Path(sys.executable).with_name('Obscura.exe')`; інакше `sys.executable -m storygen.desktop`; завжди `--no-browser`; `close_fds=True`, stdin/stdout/stderr → `DEVNULL` (stdout мосту — канал MCP).
- [ ] **Step 4: Wire `bridge.py`** — `send` у `build_server` бере `connection.request` або `http.request`; текст помилки мертвої адреси — з `connection.base`. `main`: `--url` за замовчуванням `None`; `--data-dir`; без `--url` → `Connection(data_dir, None)`, з `--url` → `Connection(None, check_url(url))`.
- [ ] **Step 5: Run, expect PASS** — `pytest -q tests/mcp` (нові й наявні тести мосту).
- [ ] **Step 6: Commit** — `feat(mcp): the bridge finds a running Obscura and starts it quietly`.

### Task 2: міст у пакеті MSIX

**Files:**
- Modify: `src/storygen/packaging.py` (`pyinstaller_args`, `appx_manifest`, нова `bridge_pyinstaller_args`), `scripts/build_store.py` (перевірка мосту — окремим запуском `--help`, `self_check.py` не змінюється)
- Test: `tests/test_packaging.py`

**Interfaces:**
- Produces: `packaging.BRIDGE_NAME = 'obscura-mcp'`, `packaging.BRIDGE_CONTENTS = '_mcp'`; `bridge_pyinstaller_args(entry, dist, work, hooks, source) -> list[str]` (консольний: без `--noconsole`, `--contents-directory _mcp`, `--hidden-import storygen.mcp.bridge`, без виключення `storygen.mcp`/`mcp`); `appx_manifest(..., bridge_executable: str | None = 'obscura-mcp.exe')` додає в `Application` розширення `uap3:AppExecutionAlias` з `uap3:ExecutionAlias Alias="obscura-mcp.exe"` і `Executable="obscura-mcp.exe"` (простір імен `uap3` у `IgnorableNamespaces` не додавати — він потрібен для розбору).
- Consumes: `Task 1` — точка входу `storygen.mcp.bridge:main`.

- [ ] **Step 1: Write the failing tests** у `tests/test_packaging.py` (`@pytest.mark.req('STORE-MCP')`):
  - `test_bridge_is_frozen_as_a_console_exe_with_its_own_contents` — `bridge_pyinstaller_args(...)`: є `--onedir`, `--contents-directory`, `_mcp`, `--name`, `obscura-mcp`; немає `--noconsole`; немає `--exclude-module storygen.mcp` і `mcp`.
  - `test_main_exe_still_excludes_the_bridge` — `pyinstaller_args(...)` досі має `--exclude-module storygen.mcp` і `mcp`.
  - `test_manifest_declares_the_bridge_alias` — розбір XML `appx_manifest(...)`: є `uap3:ExecutionAlias` з `Alias="obscura-mcp.exe"`; розширення має `Executable="obscura-mcp.exe"`; `xmlns:uap3` оголошено.
  - `test_manifest_without_bridge_has_no_alias` — `bridge_executable=None` → без `AppExecutionAlias` (зворотна сумісність тестів).
- [ ] **Step 2: Run, expect FAIL** — `pytest -q tests/test_packaging.py -k bridge` → `AttributeError: bridge_pyinstaller_args`.
- [ ] **Step 3: Implement** — `build_store.py`: друга заморозка в окрему `dist` (`out/bridge-dist`) з точкою входу `from storygen.mcp.bridge import main\nmain()\n`; копіювати `obscura-mcp.exe` і `_mcp` у `target`; ліцензійні повідомлення будувати з об’єднання `toc_sources` обох заморозок; перевірка мосту після копіювання: `obscura-mcp.exe --help` з кодом 0 і `storygen-mcp` у виводі (тайм-аут `SELF_CHECK_TIMEOUT`), інакше `Refused`. Підсумок збирання — поле `bridge` (розмір теки `_mcp` у МБ).
- [ ] **Step 4: Run, expect PASS** — `pytest -q tests/test_packaging.py`.
- [ ] **Step 5: Manual build check** — `python scripts/build_store.py --skip-msix --out C:\tmp\store-mcp-build ...` (аргументи як у `docs/packaging.md`); у теці збірки є `obscura-mcp.exe` і `_mcp`; `obscura-mcp.exe --help` працює; `THIRD-PARTY-NOTICES.txt` містить `mcp`. Записати розмір у журнал.
- [ ] **Step 6: Commit** — `feat(packaging): the Store package carries the MCP bridge with an execution alias`.

### Task 3: специфікація, документація, ручна процедура

**Files:**
- Modify: `SPEC.MD` (нова `STORE-MCP-001` після MCP-BRIDGE; PACKAGING-001 і DESKTOP-001 — технічний опис), `docs/verification/traceability.json`, `docs/verification/manual.md`, `docs/packaging.md`, `docs/site/{uk,en}/mcp.md`, журнал `docs/superpowers/plans/2026-10-20-remediation-progress.md`

- [ ] **Step 1: SPEC.MD** — `STORE-MCP-001` з Scenario: `STORE-MCP-S01` пошук сервера за записом (тести 1, 6, 7 Task 1), `S02` автозапуск один раз і очікування (2, 3, 8, 9), `S03` людська помилка й повторний пошук (4, 5), `S04` склад пакета й псевдонім (тести Task 2 + ручна процедура). Відомі обмеження: кнопки підключення, `.mcpb`, поведінка в чаті — план обв’язки; запуск через псевдонім із пакета перевіряється лише вручну.
- [ ] **Step 2: traceability** — чотири записи; `S04` з `manual` на `manual.md#store-mcp-package`.
- [ ] **Step 3: manual.md** — розділ `store-mcp-package`: підписати й встановити пакет; у новому терміналі `obscura-mcp.exe --help` за псевдонімом; закрити Obscura (вийти з трею); у Claude Code `claude mcp add --scope user obscura-store -- obscura-mcp.exe` і попросити список творів — Obscura запускається у трей без вікна консолі й браузера; прибрати тимчасовий запис.
- [ ] **Step 4: Сайт `mcp` uk/en** — `--url` тепер необов’язковий: міст сам знаходить і запускає Obscura; зайнятий порт більше не потребує `--url`. `python scripts/check_site.py --rehash mcp`.
- [ ] **Step 5: `docs/packaging.md`** — пакет містить міст; прибрати «У пакет не входять MCP-міст».
- [ ] **Step 6: Check** — `PYTHONIOENCODING=utf-8 python scripts/check_docs.py` → «узгоджені».
- [ ] **Step 7: Commit** — `docs(store-mcp): STORE-MCP-001, packaging and site`.
