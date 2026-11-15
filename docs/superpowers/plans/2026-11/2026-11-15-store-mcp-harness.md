# Store MCP «з коробки» — обв’язка: план

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** людина зі збіркою Store підключає Obscura до Claude Desktop чи Claude Code однією кнопкою, перезапускає Claude, а чат зрозуміло пояснює межі безкоштовного видання й веде від задуму до тексту.

**Architecture:** спирається на ядро з PR #180 (`storygen.mcp.launch.Connection`, `bridge.connection_for`, `obscura-mcp.exe` з псевдонімом, STORE-MCP-001 S01–S04). Нові частини:
- `src/storygen/claude_connect.py` — чисті функції з підставними коренями тек і виконавцем процесів: команда моста, вибір і запис конфігурації Claude Desktop, `.mcpb`, Claude Code, перезапуск Claude Desktop.
- `src/storygen/web/routes_connect.py` — фіксовані дії; мосту вони заборонені.
- Блок «Підключити до Claude» у бібліотеці.
- Розпізнавання відмов межі видання й prompt `start_story` у мості.

**Tech Stack:** Python 3.12, FastAPI, Jinja2, `mcp==2.3.0` (`MCPServer.prompt`), `zipfile`, `subprocess` (лише фіксовані argv), Playwright.

**Spec:** `docs/superpowers/specs/2026-11/2026-11-15-store-mcp-out-of-box-design.md` (розділи «Підключення», «Поведінка в чаті», «Заявка → доказ», поправка 1). Ядро: `docs/superpowers/plans/2026-11/2026-11-15-store-mcp-core.md`, SPEC STORE-MCP-001.

## Global Constraints

- **Перед Task 1 PR #180 злито в `main`, а гілку плану відгалужено від `main` після злиття.**
- **Підключення дописує чи оновлює лише `mcpServers.obscura`.** Решта ключів і їхній порядок лишаються. Перед записом робиться копія `claude_desktop_config.json.obscura-backup`. Некоректний JSON не змінюється, і інтерфейс показує шлях.
- **Інтерфейс ніколи не каже, що Claude Desktop «підключено».** Він каже «запис додано у <файл>, перезапустіть Claude» або «файл підготовлено». «Підключено» — лише для Claude Code після `claude mcp get obscura` з кодом 0.
- **Дії підключення приймаються лише від локального інтерфейсу.** Запит від моста (`X-Obscura-Client: mcp`) отримує 403. Процеси запускаються лише з фіксованими argv, без оболонки й без даних із запиту.
- **Команда моста:**
  - пакет: повний шлях псевдоніма `%LOCALAPPDATA%\Microsoft\WindowsApps\obscura-mcp.exe`; для Claude Code — `obscura-mcp.exe`;
  - заморожена збірка без псевдоніма: сусідній `obscura-mcp.exe`;
  - робоча копія: `storygen-mcp.exe` поруч із `sys.executable`.
- **Ключі ніколи не потрапляють ні в конфігурацію Claude, ні в `.mcpb`, ні в повідомлення.**
- **Тексти інтерфейсу — у `src/storygen/web/static/i18n.json`, uk і en.** Файл редагується лише текстовими вставками з відступом 2, без повторної серіалізації.
- **Нові Scenario — `STORE-MCP-S05`… у SPEC STORE-MCP-001.** Кожен має запис у `docs/verification/traceability.json`. Маркер тесту `@pytest.mark.req('STORE-MCP-001')` ставиться лише на функцію.
- **«Перезапустити Claude зараз» закриває лише процеси Claude Desktop.** Це процеси з шляхом у теці встановленого пакета Claude чи в `%LOCALAPPDATA%\AnthropicClaude`. Processes Claude Code (`claude.exe` в інших теках) не чіпає ніколи.

## Рішення плану (поза специфікацією)

- **Відмова межі видання завжди двомовна (uk + en).** Специфікація просить мову твору, а двомовний текст — лише коли твір невідомий. Міст бачить відмову у відповіді на довільний запит, де мови твору немає; щоб дізнатися її, потрібен додатковий запит. Ціна: довше повідомлення в чаті. Повернення до мови твору — окремою дрібною зміною, якщо власник захоче.
- **Блок підключення стоїть у бібліотеці, бо сторінки налаштувань застосунку немає** (є лише налаштування твору). Це вибір виконавця, який специфікація дозволяє.
- **`waitlist_url` міст бере з `GET /api/app-info`.** Маркер видання лежить у `_internal` головного exe, а не в `_mcp`.

## Review Focus

1. **Claude Code має той самий образ `claude.exe`.** Перезапуск закриває тільки процеси за шляхом із теки Claude Desktop (Task 3, `test_restart_never_touches_claude_code`).
2. **Конфігурація з `mcpServers` не-об’єктом, з BOM, з коментарями чи порожня.** Рахується некоректною: файл не змінюється, а шлях показується (Task 3, `test_unusable_config_is_left_untouched`).
3. **Обидва Claude Desktop (Store й інсталятор), а конфігурацію має лише один.** Береться наявний файл, а не новіший неіснуючий (Task 3, `test_store_and_installer_prefer_the_existing_newer_file`).
4. **Чат просить «підключи себе» чи «перезапусти Claude».** Маршрути підключення відповідають мосту 403 (Task 4, `test_bridge_cannot_use_connect_routes`).
5. **Відмова межі видання з текстом, що лише схожий на шаблон** (інша підстановка, обрізаний текст). Без збігу міст лишає вихідний текст і не вигадує платну версію (Task 1, `test_other_refusals_stay_as_they_are`).

---

### Task 1: відмови межі видання в чаті

**Files:**
- Create: `src/storygen/mcp/edition.py`
- Modify: `src/storygen/mcp/bridge.py` (у `request()` і місцях, що формують `ToolError` з `_detail`)
- Test: `tests/mcp/test_bridge_edition.py`

**Interfaces:**
- Produces:
  - `edition_refusal(detail: str, waitlist_url: str) -> str | None` — `None`, якщо `detail` не є відмовою межі;
  - `PAID_TEXT` (uk+en).

- [ ] **Step 1: тести.** Чотири тести.
  - `test_edition_texts_become_a_paid_version_hint`: параметризовано по `NO_LONG_PROSE`, `READ_ONLY`, `READ_ONLY_SERIES` і тексту, отриманому з `enforce_edition_limit` для твору з `sexual=2` у виданні `store`. Результат містить «платної версії», «paid version» і `waitlist_url`, а також вихідний текст відмови.
  - `test_empty_waitlist_has_no_link`: порожній `waitlist_url` дає текст без `https://`.
  - `test_other_refusals_stay_as_they_are`: `None` для довільного 403 і для `EDITION_LIMIT` з обрізаним кінцем.
  - `test_bridge_tool_error_carries_the_hint`: `MockTransport` відповідає на `GET /api/stories/{id}/scenes/{sid}/...` 403 з `{'detail': ..., 'detail_original': <EDITION_LIMIT>}`, а на `GET /api/app-info` — `{'waitlist_url': 'https://example.com/w'}`. Два виклики `get_scene_text` дають `is_error` з посиланням, а `app-info` запитано один раз за два виклики.
- [ ] **Step 2: запустити й побачити падіння.** `pytest tests/mcp/test_bridge_edition.py -q` → FAIL (немає модуля).
- [ ] **Step 3: реалізація.**
  - `edition.py` імпортує константи з `book/guard.py` і `rating/guard.py`. Регулярний вираз для `EDITION_LIMIT` зібрано з самої константи: кожна `{…}` → `.+?`, решта `re.escape`, якір `^…$`.
  - Текст звіряється з `detail_original`, а якщо його немає — з `detail`.
  - Текст відповіді українською й англійською разом: «Це можливість платної версії Obscura: довга проза (книги, частини, арки), серії й сцени без обмеження рейтингу.» + англійський відповідник + рядок `waitlist_url`, якщо він непорожній.
  - У `bridge.build_server`: `waitlist()` ліниво читає й кешує `GET /api/app-info`.`waitlist_url` (помилка — порожній рядок). `request()` і помилки з `_detail` спершу пробують `edition_refusal`.
- [ ] **Step 4: зелено.** `pytest tests/mcp -q` → усе PASS.
- [ ] **Step 5: коміт.** `feat(mcp): edition refusals in the chat explain the paid version` (документація: SPEC у Task 5).

### Task 2: порядок роботи в чаті й режим «чат» у Store

**Files:**
- Modify: `src/storygen/mcp/bridge.py` (`INSTRUCTIONS`, новий prompt), `src/storygen/web/app.py` (глобал шаблону `edition()`), `src/storygen/web/templates/library.html`
- Test: `tests/mcp/test_bridge_prompt.py`, `tests/web/test_library_writing_mode.py`

**Interfaces:**
- Produces:
  - MCP prompt `start_story(idea: str = '')`;
  - глобал шаблонів `edition() -> str`.

- [ ] **Step 1: тести.** Три тести.
  - `test_start_story_prompt_walks_from_idea_to_the_obscura_window`: `list_prompts` містить `start_story`, а `get_prompt` з `idea` повертає текст, де в порядку згадано `create_story`, `get_templates`, `import_plan_and_characters`, `save_draft`, `next_steps` і ідею.
  - `test_instructions_offer_the_obscura_link`: `INSTRUCTIONS` згадує `next_steps` як посилання на твір у вікні Obscura.
  - `test_store_library_preselects_chat` (TestClient, видання підмінено як у наявних тестах BUILD-EDITION): у `store` вибрано `<option value="chat" selected`, у `full` — `obscura`.
- [ ] **Step 2: падіння.** `pytest tests/mcp/test_bridge_prompt.py tests/web/test_library_writing_mode.py -q` → FAIL.
- [ ] **Step 3: реалізація.**
  - `@server.prompt(name='start_story')` — короткий текст для Claude, а не для людини: задум → `create_story(writing_mode='chat')` → `get_templates` → план і персонажі → `import_plan_and_characters` → сцени: `get_scene_context` → `save_draft` → після сцени `next_steps` і запропонувати людині відкрити посилання, щоб читати й правити у вікні Obscura.
  - `INSTRUCTIONS` доповнено одним реченням про посилання.
  - `library.html`: `selected` за `edition() == 'store'`.
- [ ] **Step 4: зелено.** Ті самі тести + `pytest tests/mcp tests/web -q`.
- [ ] **Step 5: коміт.** `feat(store-mcp): start_story prompt and chat mode by default in Store`.

### Task 3: модуль підключення Claude

**Files:**
- Create: `src/storygen/claude_connect.py`
- Test: `tests/connect/test_claude_connect.py` (новий каталог з `__init__.py`, якщо його вимагає наявна структура)

**Interfaces:**
- Produces (усе з явними коренями для тестів):
  - `@dataclass Roots(local_appdata: Path, appdata: Path, userprofile: Path)`; `Roots.current()`.
  - `bridge_command(roots, *, frozen: bool, executable: Path, data_dir: Path, default_data_dir: Path, desktop_launched: bool, base_url: str) -> list[str]` — `[command, *args]`. Аргументи такі:
    - без аргументів для пакета з типовою текою;
    - `--data-dir <тека>`, якщо `desktop_launched` і тека не типова (або робоча копія під `storygen-desktop`);
    - `--url <base_url>` для `storygen` робочої копії.

    `desktop_launched` = `server.json` теки має `instance_id` цього застосунку.
  - `@dataclass DesktopConfig(path: Path, variant: Literal['store','installer'])`; `find_desktop_config(roots) -> DesktopConfig | None`. Store: каталог `local_appdata/Packages/Claude_*` і файл `local_appdata/Claude-Data/claude_*/claude_desktop_config.json`. Інсталятор: `local_appdata/AnthropicClaude` і `appdata/Claude/claude_desktop_config.json`. Обидва встановлені — новіший серед наявних файлів.
  - `write_desktop_entry(config: Path, command: list[str]) -> Literal['added','updated','unchanged']`; помилка — `UnusableConfig(path)`. Атомарний запис (тимчасовий файл + `replace`), `ensure_ascii=False`, `indent=2`, копія перед кожним записом, що змінює файл. Після запису файл читається знову, і `mcpServers.obscura.command` звіряється з командою.
  - `build_mcpb(target: Path, command: list[str], launcher: Path, icon: Path, version: str) -> Path`. Manifest 0.3 як у Зонді 5:
    - `server.type: binary`;
    - `entry_point: server/obscura-mcp.exe` — копія `launcher`, тобто exe-запускача моста без `_mcp`;
    - `mcp_config.command/args` = `command`;
    - `compatibility.platforms: ['win32']`.
  - `find_claude_code(roots, which=shutil.which) -> Path | None` шукає `claude` на `PATH`, потім `userprofile/.local/bin/claude.exe`.
  - `connect_claude_code(claude: Path, command: list[str], run=subprocess.run) -> bool`. Послідовність: `remove --scope user obscura` (код ігнорується) → `add --scope user obscura -- <command…>` → `get obscura`: код 0 і команда є у виводі. Тайм-аут кожного виклику 30 с.
  - `restart_desktop(variant, *, list_processes, stop, start) -> None`. `list_processes() -> list[tuple[int, Path]]` повертає процеси `claude.exe`. Зупиняються лише ті, чий шлях у теці пакета Claude чи `local_appdata/AnthropicClaude`. Запуск:
    - Store: псевдонім `local_appdata/Microsoft/WindowsApps/claude-desktop.exe`, якщо він є, інакше `explorer.exe shell:AppsFolder\<PackageFamilyName>!<AppId>` з `AppxManifest.xml` пакета;
    - інсталятор: `local_appdata/AnthropicClaude/claude.exe`.

    Справжні `list_processes`/`stop` — через фіксований скрипт PowerShell (`Get-CimInstance Win32_Process -Filter "Name='claude.exe'"`, `Stop-Process -Id`).

- [ ] **Step 1: тести.**
  - `test_command_for_package_is_the_alias`;
  - `test_command_for_checkout_server_is_the_url`;
  - `test_command_for_desktop_launcher_passes_a_custom_folder`;
  - `test_store_config_is_found_by_package`;
  - `test_store_and_installer_prefer_the_existing_newer_file`;
  - `test_missing_config_is_none`;
  - `test_entry_is_added_beside_other_keys_in_order` (інші сервери й ключі `preferences` лишаються; копія збігається з файлом до запису);
  - `test_existing_entry_is_updated_or_left_unchanged` (`unchanged` не пише й не робить копії);
  - `test_unusable_config_is_left_untouched` (параметризовано: некоректний JSON, BOM, `mcpServers: []`, корінь-масив, порожній файл; вміст і час зміни ті самі);
  - `test_mcpb_manifest_and_files`;
  - `test_claude_code_sequence_and_check` (фіксовані argv без `shell=True`; `get` з чужою командою дає `False`);
  - `test_claude_code_missing_is_none`;
  - `test_restart_never_touches_claude_code` (процеси в `userprofile/.local/bin` і в теці пакета: зупинено лише другий, `start` викликано один раз);
  - `test_restart_store_falls_back_to_apps_folder`.
- [ ] **Step 2: падіння.** `pytest tests/connect -q` → FAIL.
- [ ] **Step 3: реалізація** за інтерфейсами. Стан і дані — лише у файлах Claude й у `data_dir/claude/obscura.mcpb`.
- [ ] **Step 4: зелено.** `pytest tests/connect -q`.
- [ ] **Step 5: коміт.** `feat(store-mcp): Claude Desktop and Claude Code connection module`.

### Task 4: маршрути й блок «Підключити до Claude»

**Files:**
- Create: `src/storygen/web/routes_connect.py`, `src/storygen/web/static/claude-connect.js`, `tests/web/test_connect_routes.py`, `tests/web/browser/claude-connect.spec.mjs`
- Modify:
  - `src/storygen/web/app.py` (роутер);
  - `src/storygen/web/bridge_marker.py` (`_AUTHOR_ONLY` + `connect/.*`);
  - `src/storygen/web/templates/library.html`;
  - `src/storygen/web/static/i18n.json`;
  - `src/storygen/web/static/app.css`.

**Interfaces:**
- Consumes: усе з Task 3.
- Produces (усі POST без тіла з даними процесів):
  - `GET /api/connect/status` → `{desktop: {config: str|null, variant, has_entry: bool}, code: {found: bool, connected: bool|null}}`;
  - `POST /api/connect/claude-desktop` → `{result: added|updated|unchanged, path}`. Без файлу: 404 з `fallback: true` і текстом «Запустіть Claude Desktop хоч раз і повторіть». Некоректний файл: 422 з `path`;
  - `POST /api/connect/claude-desktop/bundle` → `{path}` (+ відкрити теку через `os.startfile` на Windows);
  - `POST /api/connect/claude-code` → `{connected: bool}` або 404 `{command: "claude mcp add --scope user obscura -- …"}`;
  - `POST /api/connect/claude-desktop/restart` → 202.

- [ ] **Step 1: тести** (TestClient; модуль Task 3 підмінено через `app.state.claude_connect` або `monkeypatch` на функціях модуля).
  - `test_desktop_entry_is_written_and_reported_with_its_file`;
  - `test_missing_config_offers_the_fallback`;
  - `test_unusable_config_names_the_file`;
  - `test_bundle_is_built_in_the_data_folder`;
  - `test_claude_code_connected_or_command_to_copy`;
  - `test_restart_runs_only_the_fixed_action`;
  - `test_bridge_cannot_use_connect_routes` (усі POST з `X-Obscura-Client: mcp` → 403, модуль не викликано);
  - `test_foreign_origin_is_refused` (наявне правило походження: POST з `Origin: https://evil.example` → 403).

  Playwright `claude-connect.spec.mjs` (desktop і mobile, маршрути перехоплено `page.route`). Сценарій:
  1. Блок видно в бібліотеці.
  2. «Підключити Claude Desktop» показує «Запис додано у …» і дві кнопки: «Перезапустити Claude зараз» (із попередженням, що відкрита розмова закриється, і підтвердженням) та «Перезапущу сам», яка розкриває пояснення про вихід через значок Claude у треї.
  3. 404 показує запасний шлях із кроками Settings → Desktop app → Extensions. Посилання «Інший спосіб» поруч із кнопкою Desktop веде на той самий запасний шлях і за наявного файлу конфігурації.
  4. Claude Code без `claude` показує команду з кнопкою «Копіювати».
  5. Англійська локаль перекладає блок.
- [ ] **Step 2: падіння.** `pytest tests/web/test_connect_routes.py -q` → FAIL.
- [ ] **Step 3: реалізація.**
  - Блок `<section class="claude-connect">` іде над формою нового твору; у виданні `store` він завжди розгорнутий, в інших — `<details>`.
  - `desktop_launched` маршрут визначає порівнянням `server.json` теки з `app.state.instance_id` (без HTTP до себе).
  - Тексти — ключі `connect.*` uk/en.
  - Повідомлення про Claude Desktop ніколи не містить слова «підключено» (Global Constraints).
- [ ] **Step 4: зелено.** `pytest tests/web -q` і `cd frontend; npx playwright test claude-connect` з `PYTHONPATH=<тека>/src`.
- [ ] **Step 5: коміт.** `feat(store-mcp): connect Claude from the library`.

### Task 5: специфікація, сайт, ручна процедура

**Files:**
- Modify: `SPEC.MD` (STORE-MCP-001), `docs/verification/traceability.json`, `docs/verification/manual.md`, `docs/site/{uk,en}/mcp.md`, `docs/site/{uk,en}/install.md`, журнал `docs/superpowers/plans/2026-10-20-remediation-progress.md`

- [ ] **Step 1: SPEC.** Нові Scenario:
  - `S05` межа видання з посиланням (Task 1);
  - `S06` `start_story` і посилання (Task 2);
  - `S07` Store — режим «чат» (Task 2);
  - `S08` запис у конфігурацію Claude Desktop: вибір файлу, копія, лише `obscura`, некоректний файл не змінюється (Task 3–4);
  - `S09` запасний `.mcpb` (Task 3–4);
  - `S10` Claude Code (Task 3–4);
  - `S11` перезапуск лише Claude Desktop і заборона маршрутів мосту (Task 3–4).

  Таблиця «Заявка → доказ» зі специфікації переходить у технічний опис. З відомих обмежень STORE-MCP-001 прибрати пункт «кнопки… — наступний план». Додати: формат конфігурації Claude може змінитися; `.mcpb` показує стандартне попередження Claude.
- [ ] **Step 2: traceability** — записи `S05`–`S11`. `S04` доповнено ручним кроком підключення кнопкою. Playwright у `manual` з причиною.
- [ ] **Step 3: manual.md** — `store-mcp-package` доповнити так:
  1. Кнопка «Підключити Claude Desktop», «Перезапустити Claude зараз», у Claude попросити список творів.
  2. Кнопка Claude Code, нова сесія, список творів.
  3. Вийти з Obscura через трей, попросити Claude продовжити історію: Obscura запускається сама.
  4. Наприкінці прибрати записи й сертифікат.

  Окремо `claude-connect-browser` для Playwright.
- [ ] **Step 4: сайт.**
  - `mcp` uk/en: розділ «Версія з Microsoft Store» — кнопка в бібліотеці, перезапуск, запасний `.mcpb`, межі безкоштовного видання;
  - `install` uk/en: посилання на нього;
  - `python scripts/check_site.py --rehash mcp` і `--rehash install`.
- [ ] **Step 5: перевірка.** `PYTHONIOENCODING=utf-8 python scripts/check_docs.py` → «узгоджені».
- [ ] **Step 6: коміт.** `docs(store-mcp): connection, chat behaviour and Store page`.
