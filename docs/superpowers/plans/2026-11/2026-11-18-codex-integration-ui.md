# Інтеграція Codex — план периферії: кнопка й клієнтське приймання

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Додати в бібліотеку підключення MCP до Codex і окреме встановлення скілів із checkout, перевірити обидва клієнти без моделей та залежність у Store-збірці.

**Architecture:** Маршрути й окремий ES-модуль викликають перевірені codex_connect, codex_skills і codex_skill_install. Стан файла відділено від живого підключення клієнта. Чинні Claude-маршрути, обробники та очікування тестів не змінюються.

**Tech Stack:** FastAPI, Jinja2, ES modules, i18n.json, pytest, Playwright 1.64.1, MCP 2.3.0, чинний build_store.py/PyInstaller.

**Spec:** [2026-11-17-codex-integration-design.md](../../specs/2026-11/2026-11-17-codex-integration-design.md), затверджено 17.11.2026.

**Основа:** [план основи](2026-11-17-codex-integration-core.md), реалізований до f76a6b8; повний verify.py — 3668 passed, 0 failed/errors, 2 skipped, source_changed=false. Незалежне рев’ю: 10 Important виправлено одним TDD-проходом, 2 Minor відкладено. Перевірені інтерфейси нижче — фактичні, не прогноз.

**Статус:** чекає на перегляд власником. Нативний спосіб виконання вже обраний; повторно обирати його не потрібно.

## Global Constraints

- Окремий worktree C:/tmp; Python — C:/Projects/text-generator/.venv/Scripts/python.exe. Перед виконанням звірити origin/main і зміни R-39; не відновлювати стару версію Claude поверх паралельної роботи.
- Не змінювати integrations/claude/obscura/**, scripts/build_store.py, src/storygen/packaging*.py, store_build/**. Скіли Store поза обсягом; перевірка frozen-залежності дозволена без зміни пакування.
- Усі процеси — фіксовані argv, без shell або полів HTTP-запиту. Маршрути Codex взагалі не запускають Codex/моделі/перезапуск клієнта.
- X-Obscura-Client: mcp на всіх /api/connect/* → 403 до дій; сторонній Origin на POST → 403. Ключі, TOML/env та traceback не потрапляють у JSON чи DOM.
- Профілі pytest, браузерного стенда, CLI й app-server — тимчасові; наші Windows прогони у C:/tmp. Справжні ~/.codex і ~/.agents не використовувати навіть для проб.
- Жодного turn/start, codex exec, claude -p, модельних сценаріїв або start_run(confirm=true). Дозволені локальні діагностичні RPC й list_stories нейтрального стенда без моделі.
- Кожна задача — RED→GREEN, актуальні SPEC/traceability в тому самому коміті, check_docs.py, журнал. Сайт uk/en парами й check_site.py --rehash mcp.
- Це продовження одного PR інтеграції на main; до завершення всіх критеріїв PR лишається draft. Злиття — після готової інтеграції та фінального review/gate.

## Наявні інтерфейси

- codex_connect: config_path(userprofile, codex_home) → Path; config_status(path, command) → {state,path}; write_config → ConfigResult(result,path,backup,created); powershell_command(command) → str.
- codex_skills: generate_skills(source) → SkillBundle(files,sources,generator_version); GenerationError. Рівно п’ять obscura-* назв.
- codex_skill_install: install_skills(bundle,userprofile) → InstallReport(result,installed,restored,conflicts,backups,errors). result = installed/unchanged/conflict/partial/failed; installed — лише фактично змінені цим викликом теки.
- claude_connect.Roots.current і bridge_command — повторно використовуються без зміни. build_edition.current().edition визначає Store; getattr(sys,'frozen',False) відділяє frozen від checkout.

## UX-бриф (impeccable, режим Operate)

- Автор обирає свій клієнт у бібліотеці; успіх першої дії — перевірений MCP-запис, другої — п’ять перевірених скілів. Повідомлення не називає файл живим підключенням.
- Візуальна основа — чинні PRODUCT.md/DESIGN.md, library.html і блок Claude. Поруч додається окремий details Codex з тим самим оформленням; власні DOM-id/data-атрибути, без зміни заголовків чи обробників Claude.
- Дві незалежні дії: «Підключити до Codex» і «Встановити скіли Codex». Натискання першої не встановлює скіли. У Store друга неактивна з поясненням. Автоматичних restart або додаткової модальної згоди немає.
- Стани: перевірка, відсутня конфігурація, збережено/unchanged, установлені/unchanged скіли, conflict, partial/failed, джерела недоступні. Під час операції кнопки Codex disabled; повідомлення в aria-live, клавіатура й mobile збережені.
- Копії, конфліктні назви й довгі шляхи показуються звичайним текстом із переносом; команда — textContent і кнопка копіювання. UA/EN перемикає також уже показаний результат.

## Review Focus

1. GET status не створює профілів/замків і не «лікує» malformed конфігурацію — Task 1, test_status_is_read_only.
2. Тіло POST/Host не змінює шлях, команду чи порт; bridge/Origin відмовляються до дій — Task 1, test_request_cannot_choose_destinations_or_bridge_url.
3. MCP успішний, але скіли конфліктують: результат не стає загальним «підключено» — Task 2, independent actions and conflict state.
4. Після перемикання UA/EN старий error/partial результат перекладається, шлях не псується й не стає HTML — Task 2, language switch and literal paths.
5. Store/frozen не шукає джерел у пакеті R-39; MCP працює незалежно — Task 1/2, test_store_skills_are_unsupported_without_touching_sources.

### Task 1: Read-only стан скілів і маршрути Codex

**Files:** src/storygen/codex_skill_install.py, новий src/storygen/web/routes_codex_connect.py; app.py, long_prose_guard.py, i18n.json; tests/test_codex_skill_install.py і новий tests/web/test_codex_connect_routes.py; SPEC/traceability/журнал.

**Interfaces:**
- Додати inspect_skills(bundle: SkillBundle, userprofile: Path) → SkillStatus(state,present,conflicts,versions), де state=missing/current/outdated/conflict; тільки читання, з тими самими guard/manifest-перевірками. present/conflicts — tuple назв; versions — name→generator_version.
- _roots() → Roots; _command(request,roots) → list[str] передає bridge_command канонічний http://127.0.0.1:<settings.port>, а не request.base_url.
- _skill_source() → Path|None: лише integrations/claude/obscura власного checkout; Store або frozen → None. Жодних джерел чи destination з HTTP.
- GET /api/connect/codex/status → {mcp:{state,path},skills:{available,state,present,conflicts,versions},command}.
- POST /api/connect/codex → ConfigResult-поля плюс command; POST /api/connect/codex/skills → InstallReport-поля плюс names усіх п’яти перевірених скілів.
- HTTP: success 200; config format/deprecated bearer_token 422; unsupported/source drift/conflict 409; I/O/failed/partial 500. detail — локалізований безпечний текст, reason — фіксований код.

- [ ] 1. RED для inspect_skills: missing не створює .agents; current після реальної установки; outdated для старої керованої версії/частини відсутніх тек; conflict для правки/junction; не повертає вміст файлів. Реалізувати через наявні приватні guard/payload/manifest засоби без виклику install_skills.
- [ ] 2. RED для реальних маршрутів: test_mcp_save_and_repeat, test_status_is_read_only, test_skills_install_and_repeat, test_corrupt_config_is_untouched, test_partial_report_keeps_backups, test_store_skills_are_unsupported_without_touching_sources. Усі корені задає isolated_codex/fixture, не справжня home.
- [ ] 3. Додати test_request_cannot_choose_destinations_or_bridge_url: Host localhost/127.0.0.1 та чужий порт дають однаковий argv із settings.port; JSON command/source/destination/url ігнорується. Для GET/обох POST mcp-header → 403; для POST чужий Origin → 403, без нових файлів чи виклику запису.
- [ ] 4. Реалізувати маршрути; app.py включає router і для codex-prefix повертає окреме «Підключення до Codex виконує лише автор в Obscura», не змінюючи Claude-відповідей. Обидва POST додати в long_prose_guard.ALLOWED як налаштування застосунку, не твору; чинні тести повноти маршрутів мусять пройти.
- [ ] 5. STORE-MCP-S13 — захист і серверний контракт, CODEX-SKILLS-S05 — Store unsupported; concrete traceability. Запустити нові тести, tests/web/test_connect_routes.py, tests/web/test_long_prose_guard.py, check_docs.py. Коміт feat(codex): expose owner-only connection routes.

### Task 2: Блок Codex, локалізація та браузерна ізоляція

**Files:** library.html, новий static/codex-connect.js, i18n.json, DESIGN.md; tests/web/browser/server.py, новий codex-connect.spec.mjs, за потреби вузький тест ізоляції browser server; SPEC/traceability/журнал.

- [ ] 1. До нового GET у браузері ізолювати тестовий server.py: TemporaryDirectory Windows-прогонів у C:/tmp через явний тестовий root, HOME/USERPROFILE/CODEX_HOME — під ним до create_app. Зберегти absent.env, MemorySecretStore і synthetic gateways. Навіть наявні browser specs не повинні читати справжній Codex після появи нового блоку.
- [ ] 2. RED browser scenarios: independent actions and saved-file wording; missing config command to copy; conflict/partial lists; Store unsupported while MCP enabled; language switch and literal paths. Мережеві відповіді мокуються лише для станів; позитивний HTTP-контракт уже перевірено реально в Task 1. Клавіатура, disabled під час pending, clipboard fallback і довгий шлях перевіряються на desktop/mobile.
- [ ] 3. Додати details #codex-connect поруч із #claude-connect, class чинного оформлення й власні data-codex-action. ES-модуль використовує api/notice/t; не додає data-connect до чужого обробника, не викликає endpoint Claude. Створює DOM через textContent та локалізовані data-i18n/data-i18n-params.
- [ ] 4. Успіх MCP: «Налаштування Codex збережено. Відкрийте нову сесію або перезапустіть Codex» / “Codex settings saved. Open a new session or restart Codex.” Після скілів показати п’ять назв; після conflict/partial — конкретні назви й копії, без success. Store: «Скіли Codex поки встановлюються лише з робочої копії».
- [ ] 5. Запустити з frontend Playwright codex-connect.spec.mjs і незмінений claude-connect.spec.mjs для desktop/mobile. У worktree підготувати власні залежності або перевірений .venv-junction до проектної venv; не змінювати чужі теки. Python нового сервера має бачити web-залежність tomlkit.
- [ ] 6. Один візуальний прохід desktop/mobile на нейтральній бібліотеці, одна спільна правка й не більше одного підтверджувального проходу. Перед UI-редагуванням прочитати impeccable craft-floor; після завершення — detect --json по змінених UI-файлах один раз. Зберегти артефакти в C:/tmp, без авторських творів.
- [ ] 7. Доповнити STORE-MCP-S13/CODEX-SKILLS-S05 browser traceability, DESIGN.md — тільки новий операційний блок. check_docs.py; коміт feat(codex): add library connection controls.

### Task 3: Приймання двома клієнтами без моделей і frozen-залежність

**Files:** docs/verification/manual.md, CODEX-SKILLS-S04 у SPEC/traceability, журнал; вузькі діагностичні артефакти поза репозиторієм. Нової продуктової команди не потрібно.

- [ ] 1. Підготувати нейтральний scripts/skills_stand.py serve --work <C:/tmp/...> за чинним stand_env: ключі прибрані, OS keyring вимкнений, .env автора не читається. Установити скіли тільки у fixture-профіль та fixture repo/.agents/skills.
- [ ] 2. Для CLI й app-packaged codex.exe окремо записати --version та generate-json-schema --out <C:/tmp/...>. Проба 0.166.0 вже підтвердила skills/list(cwds,forceReload), mcpServerStatus/list і mcpServer/tool/call(server,threadId,tool,arguments); thread/start має ephemeral. Схему іншої версії перевірити, не вгадувати.
- [ ] 3. До запуску довести ізоляцію CODEX_HOME і домашньої теки для кожного процесу за офіційною реалізацією/діагностикою; прибрати API-key env, обрати файлове сховище облікових даних у порожньому профілі, не OS store. Не запускати клієнт, який може прочитати справжні ~/.codex/.agents. GUI-процес автора не закривати й не перезапускати.
- [ ] 4. Через app-server stdio: initialize/initialized; skills/list із fixture cwd і forceReload=true → п’ять names, правильні fixture paths, errors=[]; окремо repo й user scope. Створити лише ephemeral thread у fixture cwd (без turn/start); дочекатися MCP catalog нейтрального сервера і викликати list_stories через mcpServer/tool/call. Це діагностичний виклик інструмента, не модель. Записати JSON-доказ кожної версії/профілю; GUI discovery, якщо перевірено лише backend, позначити окремо як неперевірене.
- [ ] 5. Якщо ізольований застосунок/потрібний RPC недоступний, не підміняти тестом справжнього профілю чи модельним ходом. Зафіксувати конкретний невиконаний критерій і повернути питання власнику до злиття. Файловий configured не є доказом клієнтського підключення.
- [ ] 6. Перевірити dependency/license gate; запустити чинний build_store.py --out <нова C:/tmp/...> --edition store --skip-msix із чинними потрібними параметрами конфігурації збирання. Прочитати його --help й чинну процедуру перед запуском; не вгадувати report-url/publisher і не змінювати packaging-файли. Підтвердити freeze/import tomlkit та наявні self-check, без MSIX-публікації/Store upload.
- [ ] 7. CODEX-SKILLS-S04 отримує конкретну ручну процедуру з версіями, шляхами fixture та причиною ручної перевірки; виконане й невиконане записати окремо. Freeze або live-критерій без успіху не оголошувати готовим. Коміт docs(codex): record isolated client acceptance.

### Task 4: Інструкції кнопок, повний gate та доставка

**Files:** docs/site/{uk,en}/mcp.md, sync.json, SPEC.MD, traceability, docs/STATUS.md, журнал; PR на main.

- [ ] 1. Оновити uk/en: кнопка MCP та окрема установка скілів, збережено проти підключено, нова сесія, backup, conflict/partial, Store unsupported, ручний CLI з основи. Пояснити, що кнопка може створити конфігурацію до встановлення Codex й явно вмикає obscura/замінює HTTP на stdio. Наявні Claude-інструкції узгодити з main/R-39 без їх переписування.
- [ ] 2. Переглянути потребу знімків: чинна mcp-сторінка текстова й не має застарілого зображення панелі; обов’язкові нейтральні desktop/mobile QA-артефакти вже дає Task 2, приватні матеріали в документацію не входять. Підтвердити пару check_site.py --rehash mcp.
- [ ] 3. Звірити нові сценарії з реальними тестами/процедурами; check_docs.py, browser Codex/Claude, повний verify.py на стабільному дереві. STATUS містить фактичний SHA/argv/JUnit; skipped не passed. Звірити diff заборонених Claude/packaging файлів.
- [ ] 4. Незалежне цілісне рев’ю периферії; Important/Critical одним RED→GREEN fix pass, Minor — окремо в журнал. Після ребейзу на актуальний main і gate — detent cross-review --author codex до переведення PR із draft у ready, з фактичним marker і triage. Для зовнішнього рев’ю дотриматися актуального дозволу/автоматичної перевірки, не обходити відмову.
- [ ] 5. Commit/push, PR тільки на main. До оновлення C:/Projects/text-generator перевірити локальні зміни, перетини й резервні копії; без reset --hard/clean. Після оновлення перевірити SHA, файли й потрібні smoke-тести. Завершення всього пакета — злитий перевірений PR та синхронізована основна тека, або явний опис конкретного блокера.

## Самоперевірка

План використовує реальні ConfigResult/SkillBundle/InstallReport основи; додатковий SkillStatus визначено повністю. Кожен Review Focus має тест. UI, профілі клієнтів, frozen-залежність і документація мають окремі докази; жоден не вважається готовим лише через наявність процедури. Дві Minor основи (чутливість тесту editable install та частковий --output) лишаються відкладеними, не додані потай до цього обсягу.
