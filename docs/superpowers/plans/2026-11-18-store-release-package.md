# Store 1.0, PR 2: пакет, ліцензійний фільтр, CI і залишок #119 — план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** пакет Store 1.0.0 збирається й проходить самоперевірку в GitHub Actions, має теку `claude\` зі скілами, справжні значки й повні ліцензії, а дрібні пункти #119 закрито.

**Architecture:** чисті функції в `src/storygen/packaging.py` (таблиця винятків GPL, перелік файлів плагіна, вкладення ліцензій `tokenizers`) викликає `scripts/build_store.py`; новий робочий процес `.github/workflows/store-build.yml` запускає той самий скрипт на `windows-latest` з офіційним CPython 3.12. Дрібні доробки — точкові зміни у своїх модулях.

**Tech Stack:** Python 3.12, PyInstaller 6.22.3, pytest, Python Playwright (рендер значків), Pillow, GitHub Actions.

**Порядок:** спершу ліцензійний фільтр і CI з чернеткою PR (Task 1–2), бо Smart App Control не дає запускати свіжі збірки локально й довести Task 3–6 можна лише в CI; далі пакет і решта.

**Spec:** `docs/superpowers/specs/2026-11/2026-11-17-store-release-design.md` (розділи 6, 7, 7а, 7б, 8, 9; обидві поправки затверджено 18.11.2026).

## Global Constraints

- Тести не чіпають справжніх `~/.claude`, `%APPDATA%\Claude`, `%USERPROFILE%\Obscura`, сховища ключів ОС; жодних модельних викликів.
- Жодних секретів у робочому процесі CI; `permissions: contents: read`; без підпису й публікації.
- Будь-яка GPL-бібліотека поза таблицею винятків MUST зупиняти збирання; виняток діє лише за точного збігу заявленої ліцензії.
- Версія проєкту й плагіна — `1.0.0`; версія пакета — `1.0.0.0`.
- Розміри значків — як у `packaging.ASSETS`: `StoreLogo.png` 50, `Square44x44Logo.png` 44, `Square150x150Logo.png` 150.
- Сайт: uk і en змінюються парою, далі `python scripts/check_site.py --rehash <slug>`.
- SPEC.MD і `docs/verification/traceability.json` — у тому самому коміті, що й код; `PYTHONIOENCODING=utf-8 .venv/Scripts/python scripts/check_docs.py` зелений.
- Нові Scenario `STORE-MCP` — з наступного вільного номера після `S16`; `PACKAGING-001`, `DESKTOP-001`, `SECURITY-002` — з наступного вільного у своїх вимогах.

## Review Focus

1. **Метадані винятку змінилися** (нова версія PyInstaller переписала поле `License` або класифікатори) — збирання має відмовити з назвою пакета, а не пропустити. Тест у Task 1.
2. **Плагін у робочій копії містить невідстежуваний файл** (наприклад, `evals/` чи чернетка) — у пакет потрапляють лише відстежувані файли з фільтра `USER_FILES`. Тест у Task 3.
3. **Міст у збірці не бачить `claude\`** (тека скопійована після перевірки або не поруч з exe) — `check_bridge` має відмовити, якщо самоперевірка друкує `guide: absent`. Тест у Task 3.
4. **Назва змінної ключа з пробілами чи малими літерами** (`  venice_api_key `) — форма зберігає `VENICE_API_KEY`; порожнє поле дає типову назву. Тест у Task 7.
5. **`.env` лежить не в корені, а в підтеці теки творів** — у копію не потрапляє жоден файл з назвою `.env`, незалежно від глибини. Тест у Task 7.

---

### Task 1: Таблиця винятків GPL-перевірки

**Files:**
- Modify: `src/storygen/packaging.py` (`copyleft_distributions`, нова `COPYLEFT_EXCEPTIONS`)
- Test: `tests/test_packaging.py`
- Modify: `pyproject.toml` (extra `build`: `pyinstaller==6.22.3`, `pyinstaller-hooks-contrib==2026.10` — саме ці версії перевірено пробою П7; таблиця винятків звіряє їхні точні метадані, тож незакріплена версія в CI могла б мати інші)
- Modify: `SPEC.MD` (`PACKAGING-001`: Requirement про GPL-перевірку, новий Scenario), `docs/verification/traceability.json`

**Interfaces:**
- Produces: `COPYLEFT_EXCEPTIONS: dict[str, tuple[frozenset[str], str]]` — нормалізована назва → (точний набір заявлених текстів ліцензії, причина); `copyleft_distributions(names, *, lookup=distribution) -> list[str]` — сигнатура без змін.

Заявлені тексти — ті самі, що функція вже збирає: `License-Expression`, `License` і класифікатори `License ::` (порожні рядки відкидаються). Виняток діє, лише якщо `frozenset` заявлених текстів дорівнює очікуваному.
- `pyinstaller`: `{'GPLv2-or-later with a special exception which allows to use PyInstaller to build and distribute non-free programs (including commercial ones)', 'License :: OSI Approved :: GNU General Public License v2 (GPLv2)'}`; причина — «Bootloader Exception (COPYING.txt): у збірку потрапляють лише загрузчик і пов’язані файли».
- `pyinstaller-hooks-contrib`: `{'License :: OSI Approved :: Apache Software License', 'License :: OSI Approved :: GNU General Public License v2 (GPLv2)'}`; причина — «runtime hooks, що потрапляють у збірку, під Apache-2.0 (LICENSE, розділ Runtime hooks)».

- [ ] **Step 1: Написати тести, що падають**

```python
def test_copyleft_exceptions_pass_only_with_the_exact_declared_licence():
    pyi = packaging.COPYLEFT_EXCEPTIONS['pyinstaller'][0]
    hooks = packaging.COPYLEFT_EXCEPTIONS['pyinstaller-hooks-contrib'][0]
    def dist(name, texts):
        licence = [t for t in texts if not t.startswith('License ::')]
        return MetadataDistribution(name, License=licence[0] if licence else None,
                                    Classifier=[t for t in texts if t.startswith('License ::')])
    table = {
        'pyinstaller': dist('pyinstaller', pyi),
        'pyinstaller-hooks-contrib': dist('pyinstaller-hooks-contrib', hooks),
        'PyInstaller_Hooks.Contrib': dist('PyInstaller_Hooks.Contrib', hooks),  # same name, other spelling
    }
    assert copyleft_distributions(list(table), lookup=table.__getitem__) == []

def test_copyleft_exception_with_changed_licence_is_refused():
    table = {'pyinstaller': MetadataDistribution('pyinstaller', License='GPL-3.0-only')}
    assert copyleft_distributions(['pyinstaller'], lookup=table.__getitem__) == ['pyinstaller']

def test_copyleft_exception_table_names_a_reason_for_each_entry():
    assert set(packaging.COPYLEFT_EXCEPTIONS) == {'pyinstaller', 'pyinstaller-hooks-contrib'}
    assert all(reason.strip() for _, reason in packaging.COPYLEFT_EXCEPTIONS.values())

def test_installed_freezer_matches_the_exception_table():
    pytest.importorskip('PyInstaller')
    assert copyleft_distributions(['pyinstaller', 'pyinstaller-hooks-contrib']) == []
```

Наявний `test_copyleft_is_found_by_expression_licence_or_classifier` лишається без змін (будь-яка інша GPL відмовляє).

- [ ] **Step 2: Переконатися, що падають**

Run: `.venv/Scripts/python -m pytest tests/test_packaging.py -k copyleft -q`
Expected: FAIL — `AttributeError: COPYLEFT_EXCEPTIONS` у трьох нових тестах.

- [ ] **Step 3: Реалізувати `COPYLEFT_EXCEPTIONS` і звірку в `copyleft_distributions`**

Звіряти за `_normal(name)`; виняток пропускає дистрибутив лише за `frozenset(declared) == expected`.

- [ ] **Step 4: Переконатися, що проходять**

Run: `.venv/Scripts/python -m pytest tests/test_packaging.py -q`
Expected: PASS

- [ ] **Step 5: SPEC і traceability**

У `PACKAGING-001` описати таблицю винятків із причинами, Scenario «точна ліцензія — пропуск; змінена — відмова; інша GPL — відмова» → три тести вище. Прибрати з відомих обмежень (якщо є) згадку, що будь-яка збірка відмовляє.

Run: `PYTHONIOENCODING=utf-8 .venv/Scripts/python scripts/check_docs.py`
Expected: «…узгоджені».

- [ ] **Step 6: Commit** — `fix(packaging): accept PyInstaller under its exact exception licences`

---

### Task 2: Збирання в GitHub Actions

**Files:**
- Create: `.github/workflows/store-build.yml`
- Test: `tests/test_store_workflow.py`
- Modify: `SPEC.MD` (`PACKAGING-001`: Scenario про CI), traceability, `docs/packaging.md`

Вміст робочого процесу (рішення зі спеки 7б):
- `on: workflow_dispatch` і `pull_request` (гілки `main`) з `paths`: `scripts/build_store.py`, `src/storygen/packaging*.py`, `store_build/**`, `integrations/claude/**`, `pyproject.toml`, `requirements-lock.txt`, `.github/workflows/store-build.yml`.
- `permissions: contents: read`; `runs-on: windows-latest`; `timeout-minutes: 45`.
- Кроки: `actions/checkout@v4`; `actions/setup-python@v5` з `python-version: '3.12'`; `python -m pip install -r requirements-lock.txt`; `python -m pip install -e ".[web,publication,local-tokens,desktop,mcp,build]"`; `python scripts/build_store.py --out ${{ runner.temp }}/obscura-build --skip-msix`; `actions/upload-artifact@v4` з `if: always()`: `self-check.json`, `BUILD-OK.json`, `BUILD-FAILED.txt`, `pyinstaller*.log`, `Obscura/THIRD-PARTY-NOTICES.txt`, тека `Obscura/` (окремий артефакт, `retention-days: 7`).
- MSIX у CI не пакується (`--skip-msix`): ідентичності Partner Center ще немає. Ruling у журнал.

- [ ] **Step 1:** Тест, що падає: YAML (через `yaml`, якщо є; інакше перевірка рядків) містить `permissions: contents: read`, `python-version: '3.12'`, `--skip-msix`, жодного `secrets.`. → FAIL (файла немає).
- [ ] **Step 2:** Створити робочий процес.
- [ ] **Step 3:** Тест → PASS. Справжній запуск — на PR (Task 9): `gh run watch` не опитувати; результат брати з `gh run view` після сповіщення CI.
- [ ] **Step 4:** SPEC/traceability (Scenario посилається на тест YAML і на ручну перевірку артефакту), `docs/packaging.md` — розділ «Збирання в CI».
- [ ] **Step 5: Commit** — `ci(store): build and self-check the Store package on Windows`

---

### Task 3: Плагін `claude\` у пакеті та перевірка провідника

**Files:**
- Modify: `src/storygen/packaging.py` (нова `plugin_files`)
- Modify: `scripts/build_store.py` (копіювання до `check_bridge`, перевірка `guide: ok`, рядок звіту)
- Test: `tests/test_packaging.py`
- Modify: `SPEC.MD` (`STORE-MCP-001`, `PACKAGING-001`), traceability

**Interfaces:**
- Consumes: `skill_bundles.USER_FILES`, `skill_bundles.skill_names(plugin)`, `skill_bundles.bundle_files(plugin, skill)` (з PR 1).
- Produces: `plugin_files(root: Path, tracked: list[str]) -> list[str]` — шляхи відносно `integrations/claude`, лише відстежувані й лише під `USER_FILES`; `ValueError`, якщо немає `obscura/.claude-plugin/plugin.json` або `bundle_files` будь-якого скіла кидає `BundleError`. `build_store.tracked_files(path: str) -> list[str]` (узагальнення `tracked_package_files`).

- [ ] **Step 1: Тести, що падають**

Фікстура `plugin_tree(tmp_path)` у `tests/test_packaging.py` створює в `tmp_path/integrations/claude`: `.claude-plugin/marketplace.json`, `obscura/.claude-plugin/plugin.json`, `obscura/shared/rules.md`, `obscura/skills/start-story/SKILL.md` (з посиланням `${CLAUDE_PLUGIN_ROOT}/shared/rules.md`), `obscura/evals/x.json`, і повертає `(root, tracked)`, де `tracked` — усі ці шляхи відносно `root` у POSIX-формі (аналог `git ls-files`).

- `test_plugin_files_are_tracked_user_files_only`: додатково створити `obscura/skills/start-story/draft.tmp`, не додаючи до `tracked`; `plugin_files(root, tracked)` дорівнює рівно `['.claude-plugin/marketplace.json', 'obscura/.claude-plugin/plugin.json', 'obscura/shared/rules.md', 'obscura/skills/start-story/SKILL.md']`.
- `test_plugin_files_refuse_a_plugin_without_manifest`: видалити `plugin.json` → `pytest.raises(ValueError, match='plugin.json')`.
- `test_plugin_files_refuse_a_cross_skill_reference`: другий скіл `draft-scene/SKILL.md` з посиланням `${CLAUDE_PLUGIN_ROOT}/skills/start-story/SKILL.md` → `pytest.raises(ValueError, match='draft-scene')`.
- `test_repository_plugin_files_hold_every_skill`: `plugin_files(ROOT, <git ls-files integrations/claude, шляхи без префікса>)` містить `obscura/skills/<s>/SKILL.md` для кожного з `start-story`, `draft-scene`, `publish`, `series-bible`, `setup-models`.
- `test_bridge_check_requires_the_guide`: `monkeypatch.setattr(build_store.subprocess, 'run', fake)`, де `fake` повертає `CompletedProcess(args, 0, stdout=b'storygen-mcp\n')` для `--help` і `stdout=b'storygen-mcp: ok\nguide: absent\n'` для `--self-check` → `pytest.raises(build_store.Refused, match='провідник')`; з `guide: ok` — без винятку.

- [ ] **Step 2: Переконатися, що падають** — `pytest tests/test_packaging.py -k "plugin_files or bridge_check" -q` → FAIL (`AttributeError`, перевірка не відмовляє).

- [ ] **Step 3: Реалізувати**

`build_store.build`: після копіювання моста, до `check_bridge`, скопіювати кожен файл `plugin_files` з `integrations/claude/` у `target/'claude'`. `check_bridge` додатково вимагає `b'guide: ok'` у відповіді на `--self-check`, інакше `Refused('міст MCP не бачить провідника (тека claude\\ поруч з exe)')`. У `summary` додати `'plugin_files': files` (повний перелік, спека 6: окремий рядок звіту збирання) і вивести кількість у консоль. `package_data_manifest` не змінюється.

- [ ] **Step 4: Переконатися, що проходять** — `pytest tests/test_packaging.py -q` → PASS.

- [ ] **Step 5: SPEC, traceability, `check_docs.py`**; знести з відомих обмежень `STORE-MCP-001`/`CLAUDE-SKILLS` «у замороженій збірці скілів немає».

- [ ] **Step 6: Commit** — `feat(store): ship the Claude plugin next to Obscura.exe`

---

### Task 4: Версія 1.0.0

**Files:** `pyproject.toml`, `integrations/claude/obscura/.claude-plugin/plugin.json`, тести, що жорстко пишуть `0.1.0` як версію проєкту (не як довільну версію в `sync_marketplace`), `SPEC.MD` якщо згадує 0.1.0.

- [ ] **Step 1:** Тест `test_package_version_of_the_project_is_1_0_0_0` у `tests/test_packaging.py`: `package_version(project['version']) == '1.0.0.0'`. Запустити → FAIL.
- [ ] **Step 2:** Змінити версії. `EXPORTER['version']` у `publication/book.py` не чіпати (це версія формату експорту в manifest, а не версія пакета) — записати ruling у журнал.
- [ ] **Step 3:** `pytest tests/test_packaging.py tests/test_claude_plugin.py -q` → PASS; `grep -rn '0\.1\.0' SPEC.MD docs/site` — оновити лише згадки версії застосунку.
- [ ] **Step 4: Commit** — `chore(release): version 1.0.0`

---

### Task 5: Значки пакета з `favicon.svg`

**Files:**
- Create: `scripts/make_store_assets.py`
- Modify (binary): `store_build/msix/Assets/{StoreLogo,Square44x44Logo,Square150x150Logo}.png`
- Test: `tests/test_packaging.py::test_package_assets_exist_with_the_declared_sizes` (посилити)
- Docs: `docs/packaging.md` (як перегенерувати)

**Interfaces:** `make_store_assets.main(argv=None) -> int`; аргумент `--out` (типово `store_build/msix/Assets`); джерело — `src/storygen/web/static/favicon.svg` (перевірити шлях `git ls-files | grep favicon.svg`).

- [ ] **Step 1:** Посилити тест: кожен файл має розмір із `ASSETS` (уже є) **і** понад 8 різних кольорів пікселів (Pillow 12.3.0 є в `requirements-lock.txt`). Запустити → FAIL на заглушках.
- [ ] **Step 2:** Скрипт: Python Playwright 1.64.0 (є в `requirements-lock.txt` і `.venv`), Chromium, сторінка `<img src=data:svg>` розміром N×N з прозорим фоном, `page.screenshot(omit_background=True, clip=…)` для кожного розміру. Запустити: `.venv/Scripts/python scripts/make_store_assets.py`.
- [ ] **Step 3:** Тест → PASS. Переглянути PNG через Read (зображення), переконатися, що емблему видно.
- [ ] **Step 4: Commit** — `feat(store): package icons rendered from the favicon`

---

### Task 6: Повні ліцензії `tokenizers`

**Files:**
- Create: `scripts/tokenizers_notices.py`, `store_build/licenses/tokenizers-0.23.3.txt`
- Modify: `src/storygen/packaging.py` (`LICENSE_FALLBACKS` → вкладений файл), `scripts/build_store.py` (передати теку ліцензій)
- Test: `tests/test_packaging.py`, `tests/test_tokenizers_notices.py`

**Interfaces:**
- Produces: `packaging.BUNDLED_LICENSES = Path('store_build/licenses')`; `third_party_notices(names, *, lookup=distribution, runtime_license='', licenses_dir: Path | None = None) -> str` — для дистрибутива без ліцензійного файла шукає `<licenses_dir>/<name>-<version>.txt` і вкладає його текст; якщо файла немає — `ValueError('Немає тексту ліцензії для: tokenizers 0.23.3')`.
- `tokenizers_notices.py`: `crates_for_windows(lock_text: str, root: str) -> list[tuple[str, str]]` (crate, версія з `Cargo.lock` тегу `v0.23.3`, `bindings/python`, лише залежності, досяжні з кореня з урахуванням `cfg(windows)`; якщо фільтр `cfg` неможливо застосувати з `Cargo.lock` — брати всі досяжні й записати це ruling'ом); `license_texts(crate_archive: bytes) -> dict[str, str]` (файли `LICENSE*`/`COPYING*`/`NOTICE*` з кореня архіву `.crate`); `MANUAL: dict[str, tuple[str, str]]` — crate без файлів → (SPDX-текст, причина); crate без файлів і без запису в `MANUAL` — помилка скрипта.

- [ ] **Step 1:** Тести `tokenizers_notices` на фікстурах (маленький `Cargo.lock`, `tar.gz` у пам’яті): досяжність, вибір файлів, відмова на crate без файлів поза `MANUAL`. Тести `third_party_notices` з `licenses_dir`: файл вкладається; відсутній файл → `ValueError`. → FAIL.
- [ ] **Step 2:** Реалізувати обидва.
- [ ] **Step 3:** Тести → PASS.
- [ ] **Step 4: Згенерувати файл (мережа: GitHub raw `Cargo.lock` і `https://static.crates.io/crates/<name>/<name>-<version>.crate`; лише читання публічних архівів, без виконання їхнього коду).** Run: `.venv/Scripts/python scripts/tokenizers_notices.py --out store_build/licenses/tokenizers-0.23.3.txt`. Файл починається з повного тексту Apache-2.0 `tokenizers`, далі розділи `<crate> <version>`.
- [ ] **Step 5:** `docs/packaging.md` — як перегенерувати при оновленні `tokenizers`. SPEC `PACKAGING-001` — Scenario «встановлена версія без свого файла зупиняє збирання». Traceability, `check_docs.py`.
- [ ] **Step 6: Commit** — `feat(packaging): bundle tokenizers and Rust crate licences`

---

### Task 7: Дрібні доробки #119

**Files / Interfaces:**
- `src/storygen/providers/client.py`, `src/storygen/evaluation/gateway.py`, `src/storygen/web/static/i18n.json` — новий сталий текст без підстановок (діагностики перекладаються за точним текстом, `localization.diagnostic`): «Ключ провайдера не знайдено: збережіть його в налаштуваннях підключення (сховище ключів) або задайте змінною середовища.»; запис `d_f6ea99967250` в `i18n.json` замінюється на цей текст з англійською парою «Provider key not found: save it in the connection settings (key store) or set it as an environment variable.». Значення ключа ніколи не друкується.
- Назва змінної ключа нормалізується в інтерфейсі при збереженні (спека: «при збереженні»), а не під час кожного читання моделі: `src/storygen/web/static/settings-connection.js` (рядок 9, `values.key_env`) і `evaluator-form-state.js` (`api_key_env`) — `trim().toUpperCase()`, порожнє значення лишається порожнім і далі дає типову назву. Збережені профілі й заморожені конфігурації запусків не змінюються. Тест — у `tests/web/browser/provider-key.spec.mjs`.
- `src/storygen/desktop_tray.py::system_locale()` — на Windows `ctypes.windll.kernel32.GetUserDefaultUILanguage()`; первинна мова `0x22` (українська) → `uk`, інакше `en`; поза Windows — як зараз через `locale`. Функція `ui_language(langid: int) -> str` — чиста, для тесту.
- `src/storygen/storage/backup.py::create_backup` — пропускати будь-який файл з назвою `.env` на будь-якій глибині (`relative.name == '.env'`); `restore` не змінюється.
- Тест експорту твору з сексуальним рівнем 2 у виданні `store`: рейтинг записаний напряму через репозиторій (як після імпорту чи відновлення), `POST /api/stories/{id}/export` → 200, manifest `age_rating == '18+'`. Розмістити в `tests/web/test_long_prose_guard.py` поруч із `test_structured_book_reads_and_exports_in_store` або в тесті експорту рейтингу — за наявною фікстурою `store_edition`.
- SPEC: `SECURITY-002` (текст помилки, нормалізація назви), `DESKTOP-001` (мова трея; копія без `.env`), `BUILD-EDITION-001`/`RATING-001` (експорт рівня 2 у Store) — Scenario й traceability.

- [ ] **Step 1:** Тести, що падають, по одному на пункт: `test_missing_key_message_points_to_the_key_store`, browser-тест «назва ключа зберігається великими літерами» (`'  venice_api_key '` → у запиті збереження `VENICE_API_KEY`; порожнє поле → типова назва), `test_tray_language_follows_the_windows_ui_language` (`ui_language(0x0422) == 'uk'`, `ui_language(0x0409) == 'en'`), `test_backup_skips_env_files_at_any_depth`, `test_store_exports_a_level_two_story`. → FAIL (крім тесту експорту, якщо поведінка вже правильна — тоді він фіксує наявну поведінку; записати це в журнал).
- [ ] **Step 2:** Реалізувати.
- [ ] **Step 3:** `pytest` для зачеплених файлів → PASS.
- [ ] **Step 4:** SPEC, traceability, `check_docs.py`.
- [ ] **Step 5: Commit** — `fix(store): key hints, key name case, tray language, backups without .env`

---

### Task 8: Сайт, ручні процедури, журнал

**Files:** `docs/site/{uk,en}/install.md`, `docs/site/{uk,en}/mcp.md`, `docs/verification/manual.md`, `docs/packaging.md`, `docs/STATUS.md`, журнал `docs/superpowers/plans/2026-10-20-remediation-progress.md`.

- [ ] **Step 1:** `install`: розділ «Microsoft Store» без посилання з позначкою «незабаром» / «coming soon»; прибрати «Інсталятор … з’явиться згодом» або узгодити з новим розділом. `mcp`: у розділі «Версія з Microsoft Store» додати, що скіли Claude Code і ZIP-и Desktop є і в цій версії; прибрати будь-яку згадку, що в Store скілів немає.
- [ ] **Step 2:** `check_site.py --rehash install`, `--rehash mcp`.
- [ ] **Step 3:** `manual.md`, розділ «Встановлення зібраного пакета»: перший крок — перевірити, чи Smart App Control пропускає самопідписаний пакет; якщо ні — приватний тестовий випуск у Partner Center. Далі: запуск із «Пуск», трей (мова меню), сховище ключів, кнопки підключення, скіли в новій сесії Claude Code, ZIP у Desktop, WACK. Окремо — перевірка артефакту CI.
- [ ] **Step 4:** `docs/packaging.md`: постійне середовище `.venv-store` на офіційному CPython 3.12 (команда створення з `%LOCALAPPDATA%\Programs\Python\Python312\python.exe`, встановлення з `requirements-lock.txt`, перевірка `python -c "import sys; print(sys.base_prefix)"`), значки, ліцензії, CI. Пункт #119 про зайнятий порт 8765 закривається без коду (міст читає `server.json`, STORE-MCP-001) — записати в журнал.
- [ ] **Step 5:** `check_docs.py`; commit — `docs(store): install, MCP and manual checks for the 1.0 package`.

---

### Task 9: Перевірка, рев’ю, PR

- [ ] `scripts/verify.py` (у фоні, вивід у файл) → 0 failed; результат у `docs/STATUS.md`.
- [ ] Фінальне рев’ю гілки (субагент Opus) з Review Focus; Critical/Important — один прохід RED→GREEN.
- [ ] Cross-review `--author claude` у фоні, triage-таблиця в PR.
- [ ] Оновити опис чернетки PR: оновлені сторінки (`install`, `mcp` uk/en), `manual.md`, `packaging.md`; посилання на задачі за рішенням власника (див. питання при передачі плану: `Closes #200` і `Refs #119` чи інакше). Перевірити, що останній запуск `store-build` зелений, `self-check.json` має `"ok": true`, а `.msix` (якщо зібрано) містить `claude\obscura\.claude-plugin\plugin.json` і три значки. Перевести PR у ready.
- [ ] Після злиття — синхронізація основної теки без `reset --hard`/`clean`.
