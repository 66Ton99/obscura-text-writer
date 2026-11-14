# Біблія світу: план обв’язки

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** біблію видно й можна ставити в застосунку, через HTTP, MCP і преамбулу плану; «сцена без плану» перевірена в браузері.

**Architecture:** поверх ядра (PR #171): поле `bible` у `PATCH /api/stories/{id}/series`, «Нова біблія світу», стан `bible` у `series_status`, позначка біблії у фактах приквела й MCP; UI — налаштування книги, рядок серії, екран серії, діалог фактів.

**Tech Stack:** FastAPI, vanilla JS-модулі, Playwright, pytest.

**Spec:** `docs/superpowers/specs/2026-11/2026-11-14-world-bible-design.md` (затверджено, PR #170). Ядро: `docs/superpowers/plans/2026-11/2026-11-14-world-bible-core.md`.

## Global Constraints

- Довга проза: записи відхиляються без неї (`require_long_prose`), сторінки серій — 404, як зараз.
- Серія без біблії: ті самі відповіді API й екран, що до зміни (крім нових необов’язкових полів).
- Тексти інтерфейсу — `i18n.json` uk і en; сайт `series` — пара uk/en, `check_site.py --rehash series`.
- Нейтральні приклади в тестах і на сайті.

## Review Focus

- Книга, що була біблією, після зняття позначки знову може отримати номер (форма надсилає `bible:false` і номер).
- `Номер: біблія` з `Початок:` чи за наявної біблії — попередження й імпорт без серії, а не помилка імпорту.
- Діалог фактів приквела не дає перемкнути факт біблії й не надсилає його ключ.
- Екран серії з біблією: вісь і «поза віссю» без біблії, біблія окремим блоком; «Видалити серію» недоступне.
- Стан `bible` не показує кнопку «Оновити з попередньої книги».

---

### Task 1: API, MCP, преамбула

**Files:** `src/storygen/web/routes_series.py`, `src/storygen/book/series.py`, `src/storygen/storage/series.py`, `src/storygen/plan_sections.py`, `src/storygen/mcp/bridge.py`; test `tests/series/test_series_bible_harness.py`.

**Interfaces:**
- Produces: `StorySeries.bible: bool = False`; `POST /api/series/{id}/bible {title}` → твір-біблія (друга — 422); `series_status(biblе) -> SeriesStatus('bible', summary=<причина або None>)` (нове поле `summary: str | None`); `GET /api/series/{id}` — рядки книг з `bible`, поле `bible` (ID або `None`); `start_facts` — `bible: bool` у кожному рядку; MCP `get_story.series.bible`; `SeriesLines.bible: bool`, `number: int | None`; `SERIES_BIBLE_PLAN_TAKEN`.

- [ ] Тести: PATCH із `bible:true` ставить біблію, з номером — 422; PATCH книги-біблії з `bible:false` і номером повертає її в книги; «Нова біблія світу» й друга — 422; без довгої прози — відмова; стан біблії `bible` і `summary` (без підсумку — причина, дописана — `None`); `GET /api/series/{id}` має `bible` і рядок біблії з `number: None`, а вісь без неї; факти приквела мають `bible: true` для ключа біблії; MCP `get_story` біблії — `bible: true`, `number: None`; преамбула `Серія: Сага` + `Номер: біблія` (і `Number: bible`) ставить біблію, з `Початок:` — `SERIES_LINES_INVALID`, за наявної біблії — попередження й імпорт без серії; рядки без біблії — як раніше.
- [ ] FAIL → реалізувати → PASS (`tests/series`, `tests/web`, `tests/mcp`, `tests/authoring`). Коміт.

### Task 2: Інтерфейс

**Files:** `src/storygen/web/static/series-settings.js`, `series-status.js`, `story-series.js`, `series-page.js`, `series-facts.js`, `book-structure-panel.js`, `src/storygen/web/templates/settings.html`, `series.html`, `src/storygen/web/static/i18n.json`, стилі за потреби; tests `tests/web/browser/series-bible.spec.mjs`, `tests/web/browser/scene-without-plan.spec.mjs`.

- [ ] Playwright (desktop і mobile): налаштування книги — прапорець «Біблія світу» ховає номер і `Початок`, «Зберегти» робить твір біблією, рядок під назвою — «Серія «…», біблія світу»; екран серії — «Нова біблія світу» створює біблію, блок біблії над книгами зі станом підсумку, вісь без біблії, кнопка «Нова біблія світу» зникає; нова сцена (звичайна книга й біблія) — «Додати сцену», вкладка «Проза», текст, «Зберегти» → «Збережено», голова прози є, помилки немає.
- [ ] Реалізувати: прапорець у `#story-series-form`; `statusText` для `bible`; рядок серії; блок `#series-bible` і кнопка `#series-new-bible`; у діалозі фактів факт біблії — без перемикача, з поясненням «завжди минуле», ключ не входить у змінені; у панелі структури книги для біблії поле протагоніста сховано. Ключі `i18n.json` uk/en.
- [ ] Playwright PASS; `tests/web` PASS. Коміт.

### Task 3: Документація й перевірки

- [ ] SPEC.MD SERIES-BIBLE-001: технічний опис обв’язки, відомі обмеження без «обв’язки ще немає», S06 з браузерним тестом, новий S08 «Інтерфейс, HTTP, MCP і преамбула»; traceability; `manual.md#series-bible-browser`; сайт `series` uk/en з нейтральним прикладом, `check_site.py --rehash series`; журнал.
- [ ] `check_docs.py`; `verify.py` у `C:\tmp\sp-verify` → `docs/STATUS.md`; самоперевірка; перехресна перевірка; PR на `main` з «Refs #31».
