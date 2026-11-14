# Біблія світу: план ядра

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** позначка біблії серії, пам’ять біблії «лише факти, до 10» і біблія як пряме джерело знімка кожної книги.

**Architecture:** `Story.series_bible` у JSON твору; біблія — окреме джерело знімка поза `plan_merge`-вибором головної книги; знімок зберігає `bible_keys`; режим пам’яті біблії — узагальнення режиму спогаду межею `fact_limit`.

**Tech Stack:** Python 3.12, Pydantic, SQLite, pytest.

**Spec:** `docs/superpowers/specs/2026-11/2026-11-14-world-bible-design.md` (затверджено злиттям PR #170).

## Global Constraints

- Серія без біблії й книга поза серією: ті самі джерела, знімки, запити й відбитки, що до зміни.
- Біблія: `series_id` задано, `series_number is None`, `series_start is None`, `series_start_version_id is None`; одна на серію, зокрема серед творів у кошику.
- `BIBLE_FACT_LIMIT=10`; загальна межа додавань пам’яті — 12 без змін; старі межі `flashback: True` без `fact_limit` перевіряються з межею 6.
- `SERIES_START_SCHEMA` лишається 1; `bible_keys` — необов’язкове поле знімка.
- Обв’язка (HTTP, екран, налаштування, MCP, преамбула, браузерний тест «сцена без плану», сайт) — окремий план.

## Review Focus

- Книга 2 після зміни факту біблії: у знімку немає старої копії з книги 1 і є новий факт (S02).
- Біблія з `series_number is None` ніде не потрапляє в `numbers`/`moments`/`main` (TypeError у тайбрейкері).
- Приквел: факти біблії в журналі «минуле», а не в `future`; `save_decisions` не дає зробити їх «майбутнім».
- Серія без біблії: знімок книги 2 байт у байт той самий, книга 1 без знімка.
- Біблія в кошику не є джерелом, але місце біблії займає.

---

### Task 1: Позначка біблії

**Files:** `src/storygen/domain.py`, `src/storygen/storage/series.py`, `src/storygen/book/protagonists.py`; test `tests/series/test_series_bible_entity.py`.

**Interfaces:**
- Produces: `Story.series_bible: bool = False`; `set_story_series(repo, story_id, series_id, number, start, expected_revision, *, bible=False) -> Story`; `create_bible(repo, series_id, title) -> Story`; `SERIES_BIBLE_TAKEN = 'У серії вже є біблія світу'`; `SERIES_BIBLE_FIELDS = 'Біблія світу не має номера й «Початку»'`.

- [ ] Тести: біблія ставиться (`bible=True`, номер і старт `None`), з номером/стартом — `ValueError(SERIES_BIBLE_FIELDS)`; друга біблія в тій самій серії, зокрема коли перша в кошику, — `ValueError(SERIES_BIBLE_TAKEN)`; книга зі знімком, що стає біблією, втрачає `series_start_version_id`; вихід із серії знімає позначку; `delete_series` з біблією — `SERIES_NOT_EMPTY`; `create_bible` дає біблію без номера; `scene_tracked` біблії — `[]` навіть з картками й явним протагоністом.
- [ ] Запустити — FAIL.
- [ ] Реалізувати: поле; у `set_story_series` перевірка пари лише для `bible=False`; для біблії — серія задана, номер і старт `None`, унікальність серед `_books`; оновлення пише `series_bible`, для біблії — `series_start_version_id=None`; знімок під час входу не береться для біблії. `scene_tracked` повертає `[]` для `story.series_bible`.
- [ ] Запустити тести файлу й `tests/series` — PASS. Коміт.

### Task 2: Пам’ять біблії

**Files:** `src/storygen/memory/wire_v4.py`, `src/storygen/generation/context.py`, `src/storygen/generation/context_labels.py`, `src/storygen/storage/snapshots.py`, `src/storygen/dependency_models.py`; test `tests/series/test_series_bible_memory.py`.

**Interfaces:**
- Consumes: `Story.series_bible`.
- Produces: `BIBLE_FACT_LIMIT=10`; `schema_bounds_v4(..., flashback=False, fact_limit=None)` — за `fact_limit` межі як у спогаду з `'fact_limit': fact_limit`; селектор `scene/<id>/series_bible` (лише `True`, у скоупі `memory`); мітка `bible_facts`.

- [ ] Тести: запит пам’яті сцени біблії має мітку `bible_facts`, секцію чинних тверджень і фрагменти, не має секцій ядра й ліній; межі мають `fact_limit == 10`, схема `facts.add.maxItems == 10`, решта — 0; `check_v4` приймає 10 фактів, відхиляє 11 (`add_limit`) і будь-який стан (`flashback_only_facts`); старі межі `{'flashback': True}` без `fact_limit` відхиляють 7 фактів; сцена-спогад у біблії — межа 10; запит пам’яті звичайної книги не змінився (мітки немає, селектора `series_bible` немає); позначка біблії, поставлена після збереження пам’яті, робить її застарілою через `compare_snapshot`.
- [ ] FAIL.
- [ ] Реалізувати: `fact_limit` у межах, `check_v4` і схемі (`bounds.get('fact_limit', FLASHBACK_FACT_LIMIT)`); у `build_context` для біблії `tracked=[]`, межі з `fact_limit=BIBLE_FACT_LIMIT`, секції: мітка, чинні твердження, дозволені ID, фрагменти; селектор у `FLASHBACK_SCOPES`-подібному `BIBLE_SCOPES={'memory'}` з типовим `False` у `compare_snapshot` і `selector_value`.
- [ ] PASS (`tests/series`, `tests/generation`, `tests/memory`). Коміт.

### Task 3: Біблія — джерело знімка

**Files:** `src/storygen/book/series.py`, `src/storygen/storage/series.py`; test `tests/series/test_series_bible_snapshot.py`.

**Interfaces:**
- Consumes: Task 1.
- Produces: `series_bible_source(stories, story) -> Story | None`; `snapshot_sources(stories, story) -> list` (біблія першою, далі `start_sources`); `StartMemory.bible_keys: list[str]`; поле знімка `bible_keys`.

- [ ] Тести:
  - книга 1 входить у серію з дописаною біблією — знімок з джерелом-біблією й `bible_keys`; без біблії — знімка немає, як і раніше;
  - біблія без підсумку — стан `no_summary` з джерелом-біблією; біблія в кошику — не джерело;
  - книга 2 (книга 1 зі знімком біблії): факт біблії один раз; після зміни факту біблії (нова пам’ять сцени біблії) й оновлення знімка книги 2 — старого факту немає, новий є; стан книг після зміни біблії — `source_changed`;
  - поява біблії в серії, де книга 2 вже має знімок, — `source_changed`, знімок не змінився; книга 1 без знімка — `source_finished`;
  - книга 3 після приквела в серії з біблією: головна книга лишається головною (конфлікт книги 1 з приквелом — перемагає книга 1);
  - приквел: факти біблії в журналі знімка, не в `future`; `save_decisions({ключ біблії: 'future'})` — `ValueError`;
  - серія без біблії: знімок книги 2 і `series_status` ті самі, що до зміни (порівняння payload).
- [ ] FAIL.
- [ ] Реалізувати: `_source_rows` і `_snapshot_status` за `snapshot_sources`; у `start_memory` рядок біблії окремо: з журналу кожної книги-джерела вилучаються події з ключами з `bible_keys` її знімка; `main`, `numbers`, `moments` — лише серед книг; журнал біблії — перша гілка `plan_merge`, у конфлікті з біблією перемагає біблія; одне джерело — як є. `_snapshot` пише `bible_keys` (ключі `replay_memory` журналу біблії) і для приквела ставить їм `'past'` поверх перенесених позначок. `save_decisions` відхиляє `'future'` для `bible_keys`. `set_story_series` бере знімок під час входу, коли `snapshot_sources` непорожній (замість `number > 1`).
- [ ] PASS (`tests/series`). Коміт.

### Task 4: SPEC і перевірки

**Files:** `SPEC.MD`, `docs/verification/traceability.json`, журнал.

- [ ] `SERIES-BIBLE-001` після `SERIES-001`: технічний опис ядра, інваріанти, сумісність (поле `series_bible` у JSON твору; попередня збірка не читає твори, збережені новою), відомі обмеження (обв’язки ще немає); сценарії S01–S05, S07 з тестами. Запис у журналі.
- [ ] `check_docs.py` — узгоджено; `verify.py` у `C:\tmp\sp-verify` → `docs/STATUS.md`.
- [ ] Самоперевірка гілки, перехресна перевірка, PR на `main` з «Refs #31».
