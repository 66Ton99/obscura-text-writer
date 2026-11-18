# Окреме вікно Obscura — план

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (обрано виконання в цій сесії). Кроки — `- [ ]`.

**Goal:** desktop-запуск відкриває Obscura в окремому вікні Edge `--app` з профілем `<тека даних>/.window`, повторний клік по значку виводить це вікно наперед, «Вийти» його закриває, зовнішні посилання йдуть у браузер за замовчуванням.

**Architecture:** новий `storygen/app_window.py` (логіка + `Win32Windows`, єдине місце `ctypes`, підмінюється в тестах); `desktop._run` і трей отримують об’єкт вікна замість `webbrowser.open`; маршрут `POST /api/app-window/open-external` і `static/app-window.js` лише для desktop-запуску; `storage.integrity.regular_files` і `backup` оминають кореневу `.window`.

**Tech Stack:** Python 3.12, FastAPI, Jinja, `ctypes`, pytest, Playwright (браузерний тест скрипту).

**Spec:** `docs/superpowers/specs/2026-11/2026-11-19-app-window-design.md` (затверджено 19.11.2026).

## Global Constraints

- Тести не запускають справжній Edge і не чіпають `%USERPROFILE%\Obscura`; Windows API лише через підмінений `api`.
- Прапорці запуску рівно: `--user-data-dir=<профіль>`, `--app=<url>`, `--no-first-run`, `--no-default-browser-check`.
- Профіль: `<тека даних>/.window`; виняток з копій і перевірки цілісності — лише коренева тека.
- `open-external`: лише абсолютні `http`/`https` (інакше 422); без desktop-вікна — 404.
- Звичайний `storygen` і `--no-browser` поводяться як раніше.

## Review Focus

1. Процес профілю живий, але без видимих вікон (Edge ще стартує / вікно закрито, процес завершується) → запускається нове вікно, а не «фокус у нікуди».
2. Шлях профілю з кирилицею й іншим регістром у командному рядку → процес знаходиться (порівняння без регістру, з лапками й без).
3. Edge відсутній або запуск кидає `OSError` → `webbrowser.open(url)`, запис у журнал, без винятку в трей.
4. Посилання `mailto:`/`javascript:` і відносні посилання не перехоплюються; `window.open` на внутрішню сцену лишається у вікні.
5. Тека `.window` з reparse point чи заблокованим файлом не ламає `fsck` і резервну копію.

## Ruling (відхилення від тіла специфікації)

Маршрут `POST /api/app-window/show` для другого запуску не потрібен: пошук процесу профілю за командним рядком дає другому запуску знайти й вивести наперед те саме вікно напряму. Тіло специфікації оновлюється в тому ж PR; розділ власника не змінюється.

### Task 1: модуль вікна

**Files:** Create `src/storygen/app_window.py`; Test `tests/test_app_window.py`.

**Interfaces — Produces:**
- `profile_dir(data_dir: Path) -> Path`
- `edge_path() -> Path | None`
- `launch_args(edge: Path, profile: Path, url: str) -> list[str]`
- `class AppWindow(url, data_dir, *, api=None, edge=edge_path, fallback=webbrowser.open)`: `show() -> None`, `close() -> None`, `open_external(url: str) -> None`
- `api` протокол: `profile_pids(profile: Path) -> list[int]`, `visible_windows(pid) -> list[int]`, `is_minimized(hwnd) -> bool`, `restore(hwnd)`, `focus(hwnd)`, `close_window(hwnd)`, `launch(args) -> None`, `hide_folder(path)`

- [ ] тести: перший `show()` запускає Edge з точними аргументами й створює профіль; живий процес із вікном → `restore` лише згорнутому + `focus`, без запуску; процес без вікон → запуск; кілька процесів → вікно того, що має вікна; без Edge / `OSError` запуску → `fallback(url)`; `close()` закриває всі вікна всіх процесів профілю; `open_external` → `fallback`; командний рядок із лапками, кирилицею й іншим регістром відповідає профілю (`matches_profile(command_line, profile) -> bool`).
- [ ] побачити падіння; реалізувати; зелено; коміт.

### Task 2: запуск, трей, «Вийти», копії

**Files:** Modify `src/storygen/desktop.py`, `src/storygen/desktop_tray.py`, `src/storygen/storage/integrity.py`, `src/storygen/storage/backup.py`; Tests `tests/test_desktop.py`, `tests/test_desktop_tray.py`, `tests/storage/…` (новий тест копій).

- `desktop.main(..., opener=None, window=None)`: `window(url, data_dir)` — фабрика об’єкта з `show/close/open_external`; без обох — `AppWindow`; переданий `opener` загортається (сумісність тестів).
- `app.state.app_window` — об’єкт вікна (для маршруту Task 3).
- `run_tray(url, data_dir, backups_dir, stop, *, opener=webbrowser.open)`; «Відкрити Obscura» → `opener`; desktop передає `window.show`, а `stop` для трея — `window.close()` + зупинка сервера.
- Другий запуск і програна гонка — `window.show()` замість `opener(url)`.
- `regular_files(root, skip=())`; `check_integrity` і `create_backup` передають `skip={'.window'}` (коренева тека).
- [ ] тести: трей отримує `opener` і «Вийти» закриває вікно; другий запуск показує вікно через фабрику; копія без `.window/…`, але з `stories/x/.window/note.txt`; `check_integrity` чистий із junction у `.window`.
- [ ] падіння → реалізація → зелено → коміт.

### Task 3: зовнішні посилання

**Files:** Modify `src/storygen/web/app.py` (або новий `web/routes_app_window.py`), `src/storygen/web/templates/base.html`; Create `src/storygen/web/static/app-window.js`; Tests `tests/web/test_app_window_routes.py`, `tests/web/browser/app-window.spec.mjs`.

- [ ] тести: 404 без вікна; 422 для `ftp:`/відносної; 204 і `open_external(url)` для `https://…`; Origin чужого сайту → 403 (наявна перевірка); сторінка підключає скрипт лише з вікном; браузерний тест: клік по зовнішньому посиланню шле запит і не навігує, `mailto:` і внутрішні посилання не чіпаються, `window.open` зовнішнього → запит, внутрішнього → як раніше.
- [ ] падіння → реалізація → зелено → коміт.

### Task 4: документація

- SPEC: DESKTOP-001-S07, S08, S04, S06, модулі, відомі обмеження 9; тіло специфікації — ruling; traceability; `manual.md#desktop-launcher` і `#store-package-install` (кроки вікна); сайт `install.md` uk/en + rehash; журнал.
- [ ] `check_docs.py`, повний gate, коміт.
