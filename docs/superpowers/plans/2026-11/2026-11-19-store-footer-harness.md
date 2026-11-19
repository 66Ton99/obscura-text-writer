# Підвал редактора для Store — план периферії

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** видимі зміни підвалу: ліміт проходів у налаштуваннях редактора, «Взяти як прозу» й «Редагувати» на основній панелі, рядок прози за весь твір, «Текст, що пише модель» з автоматичним розгортанням, скорочений підвал і історія версій у Store, SPEC і сайт.

**Architecture:** ядро (план `2026-11-19-store-footer-core.md`) уже дає `RoleSettings.edit_pass_limit`, заповнення ліміту на сервері, `story_totals`, `details=false` і `isStoreEdition()`. Шаблон `story.html` не рендерить `#run-options` і `.workspace-extra` за `edition() == 'store'`; JS-модулі терплять відсутність цих вузлів. Статистика й історія читають `isStoreEdition()` один раз при встановленні.

**Tech Stack:** Jinja, JS-модулі без збирача, Node-тести `tests/web/js/*.mjs` (через pytest-обгортки), Playwright `tests/web/browser/*.spec.mjs` (фікстури `server.py`: `/test-fixture`, `/test-build-edition`), pytest.

**Spec:** `docs/superpowers/specs/2026-11/2026-11-19-store-footer-design.md`

## Global Constraints

- Нові рядки інтерфейсу — іменовані ключі i18n з парою uk/en (`workspace.*`, `stats.*`, `history.*`); значення наявних `m_…` ключів не переписувати.
- Приховування в Store — лише інтерфейс; сервер приймає ті самі запити.
- Повне видання: історія версій, статистика з розбором контексту, «Параметри запуску» й «Додаткові дії» лишаються (без кнопки «Видалити сцену» й без поля ліміту проходів).
- «Повернути цю версію» шле `content_format` версії явно; ідентичний текст+формат — повідомлення «Текст уже такий самий» / "The text is already the same", без нової версії.
- Тести не викликають реальних моделей і не чіпають теки даних власника; знімки сайту — лише нейтральні приклади.

## Review Focus

1. Store-сторінка без `#generation-controls`/`#pause-each`/`#run-options`: `runs.js` і `budget.js` не падають, основна дія й «Пауза/Скасувати» в рядку стану працюють.
2. «Повернути» версії Markdown поверх plain-голови (і навпаки) — нова голова має формат версії, а не голови.
3. «Повернути» версії, яка вже є головою, — кнопка вимкнена з причиною; інша версія з тим самим текстом і форматом — повідомлення без нової версії.
4. Перемикання сцени під час завантаження статистики Store — старий відгук не малює рядок прози чужої сцени (наявний `epoch`).
5. Етап без `stage_finished` (скасування, помилка) — «Текст, що пише модель» згортається на завершальному стані запуску.

---

### Task 1: Ліміт проходів у налаштуваннях редактора, без поля в підвалі

**Files:**
- Modify: `src/storygen/web/static/settings.js` (форма ролі `editor`: поле й збереження)
- Modify: `src/storygen/web/static/runs.js` (без `#edit-pass-limit`, без `edit_pass_limit` у запиті, без імпорту `edit-pass-limit.js`)
- Modify: `src/storygen/web/static/workspace-route.js` (телеметрія без `#edit-pass-limit`, прибрати слухача `input`)
- Modify: `src/storygen/web/static/run-readiness.js` (`editorLoopOperation`)
- Delete: `src/storygen/web/static/edit-pass-limit.js`, `tests/web/js/edit-pass-limit.mjs`, `tests/web/test_edit_pass_limit.py`
- Modify: `tests/web/js/run_readiness.mjs`, `tests/web/browser/edit-pass-limit.spec.mjs`, `tests/web/browser/workspace-telemetry.spec.mjs`
- Modify: `src/storygen/web/static/i18n.json` (підказка поля)
- SPEC: EDIT-LOOP-REVIEW-S02 (переписати: значення зберігається в налаштуваннях редактора твору); traceability; сайт `docs/site/{uk,en}/` — сторінка налаштувань моделей (знайти за «Режим редактора»/«Editor mode»).

**Interfaces:**
- Consumes: `RoleSettings.edit_pass_limit` (1–10, типово 5) у `GET /api/stories/{id}/settings` → `roles.editor.edit_pass_limit`; readiness `edit_loop` уже повертає `calls` = заповнений ліміт, `scene`/`remaining` — `edit_pass_limit` і `calls` з ним.
- Produces: `editorLoopOperation(operation) -> operation` — додає лише попередження `m_61c8ee57393c`, `calls` не змінює.

- [ ] **Step 1: Failing tests.**
  - `run_readiness.mjs`: `editorLoopOperation({ready:true,calls:4,roles:{…},warnings:[]}).calls === 4` і попередження додане; прибрати перевірки меж 0/11/2.5/NaN і перерахунку `remaining`.
  - `edit-pass-limit.spec.mjs` (замінити): на `/stories/{id}/settings` форма `form[data-role="editor"]` має `input[name="edit_pass_limit"]` зі значенням `5`; заповнити `3`, зберегти (кнопка `.scope-submit` форми), повернутися на `/stories/{id}` → `#workspace-telemetry` на вкладці «Draft» містить `up to 3 calls`; `#edit-pass-limit` відсутній (`toHaveCount(0)`).
  - `workspace-telemetry.spec.mjs`: прибрати рядки 11–12 (зміну `#edit-pass-limit`).
- [ ] **Step 2: Run** `PYTHONUTF8=1 .venv/Scripts/python.exe -m pytest -q tests/web/test_run_readiness*.py` (обгортка `run_readiness.mjs`; знайти `grep -l run_readiness tests/web/*.py`) і браузерний `edit-pass-limit.spec.mjs` — Expected: FAIL.
- [ ] **Step 3: Implement.** Поле в формі редактора: `<label><span data-i18n="m_6c1316f99476">…</span><input name="edit_pass_limit" type="number" min="1" max="10" step="1" required></label>` + `<small class="settings-hint" data-i18n="settings.edit_pass_limit_hint">` («Скільки разів редактор може пройти чернетку за один запуск. Кожен прохід — окремий виклик моделі.» / "How many times the editor may pass over the draft in one run. Each pass is a separate model call."); заповнення `config.edit_pass_limit??5`; збереження `settings.edit_pass_limit=Number(...)`. `runs.js::start`: `operation=editorLoopOperation(operation)` для `edit_loop|scene|remaining`; `request.edit_workflow='loop'` лишається, `edit_pass_limit` не додається. `workspace-route.js`: `info=editorLoopOperation(info)`.
- [ ] **Step 4: Run** Node/pytest-обгортки `tests/web` повністю і браузерні `edit-pass-limit`, `workspace-telemetry` — Expected: PASS.
- [ ] **Step 5: SPEC/сайт/check_docs, commit** — `feat(settings): edit pass limit lives in the editor model settings`.

### Task 2: Основна панель — «Взяти як прозу», «Редагувати»; без «Видалити сцену» в підвалі

**Files:**
- Modify: `src/storygen/web/templates/story.html` (кнопки `#workspace-use-draft` і `#workspace-edit-prose` переїжджають у `.editor-toolbar` перед `#workspace-primary`; `#workspace-scene-actions` прибрати)
- Modify: `src/storygen/web/static/workspace-route.js` (видимість `#workspace-use-draft`: `state.mode==='draft' && !!state.scene?.heads.draft`; вимкнення як у `#workspace-edit-prose`)
- Modify: `src/storygen/web/static/workspace-state.js::primaryAction` (повтор на `draft`)
- Modify: `src/storygen/web/static/trash.js` (без кнопки в підвалі; іконка в списку лишається)
- Modify: `src/storygen/web/static/i18n.json` (`workspace.take_as_prose`: «Взяти як прозу» / "Use as prose"; `workspace.edit_again`: «Редагувати» / "Edit"; `workspace.save_and_edit` не потрібен — наявний `m_71957284c5de`)
- Test: `tests/web/js/workspace_route.mjs`, `tests/web/browser/store-footer.spec.mjs` (новий), `tests/web/browser/scene-delete.spec.mjs`

**Interfaces:**
- Produces: `primaryAction(state)` для `mode==='draft'` з головою прози: `label = state.dirty ? t('m_71957284c5de') : t('workspace.edit_again')`; інші вкладки без змін.

**Ruling (записати в журнал):** `#workspace-edit-prose` (повторна редактура прози на вкладці «Проза») теж лежить у `.workspace-extra`, яку Store не рендерить; специфікація її не ховає, тож вона переїжджає на основну панель разом із «Взяти як прозу».

- [ ] **Step 1: Failing tests.**
  - `workspace_route.mjs`: стан `mode:'draft'`, `heads:{draft:'d',prose:'p'}`, `dirty:false` → `primaryAction(state).label === 'Редагувати'`; `dirty:true` → `'Зберегти й редагувати'`; наявна перевірка `/новий варіант пам/` лишається.
  - `store-footer.spec.mjs`, тест «take as prose sits left of the primary action on the draft tab»: фікстура з чернеткою (`/test-fixture` + `POST /api/scenes/{id}/draft`), вкладка Draft → `#workspace-use-draft` видима і в DOM передує `#workspace-primary` (`compareDocumentPosition`); вкладка Plan → прихована; клік → діалог → прийняти → вкладка Prose з текстом чернетки.
  - `scene-delete.spec.mjs`: `page.locator('.workspace-extra button', {hasText:'Delete scene'})` — `toHaveCount(0)`.
- [ ] **Step 2: Run** — Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `tests/web` Node-обгортки й браузерні `store-footer`, `scene-delete`, `save-and-run`, `workspace-layout` — Expected: PASS.
- [ ] **Step 5: SPEC R20-WORKSPACE (основна панель, підпис «Редагувати»), WORKSPACE-TOOLS-S05 (видалення лише зі списку), traceability, сайт `workspace.md` uk/en; commit** — `feat(workspace): take-as-prose and Edit on the main panel; scene delete only in the list`.

### Task 3: Рядок прози за весь твір і статистика Store

**Files:**
- Modify: `src/storygen/web/static/scene-statistics.js`
- Modify: `src/storygen/web/static/i18n.json` (`stats.prose_line`: «Поточна проза: {p0} / {p1} цільових слів ({p2} / {p3} весь твір)» / "Current prose: {p0} / {p1} target words ({p2} / {p3} whole story)")
- Test: `tests/web/js/scene-statistics.mjs` (+ обгортка `tests/web/test_scene_statistics_ui.py`)

**Interfaces:**
- Consumes: відповідь статистики `story_totals: {prose_words, target_words, scenes}`; `?details=false` без `memory/context/last_usage`; `isStoreEdition()`.
- Produces: `installSceneStatistics({state,api,document,store=false})` — `store` передає викликач (`editor.js`/місце встановлення бере `await isStoreEdition()`); у Store: немає `select` етапу, запит `?details=false` без `stage`, `render` малює таблицю матеріалів і рядок прози.

- [ ] **Step 1: Failing tests** у `scene-statistics.mjs`: (а) повне видання — після `load()` текст рядка прози дорівнює `Поточна проза: 3 / 400 цільових слів (24200 / 30000 весь твір)` для `story_totals {prose_words:24200,target_words:30000}`; фраза «не підсумовуються» відсутня; (б) `store:true` — URL запиту містить `details=false` і не містить `stage=`; у `details` немає `select`; у тілі немає заголовків контексту/пам'яті (`m_36a0e97c4ec2`, `m_c6cecc869f8a`, `m_fc489ce88b97`).
- [ ] **Step 2: Run** `pytest -q tests/web/test_scene_statistics_ui.py` — Expected: FAIL.
- [ ] **Step 3: Implement**; знайти місце виклику `installSceneStatistics` і передати `store`.
- [ ] **Step 4: Run** той самий тест + `tests/web/test_localization.py` — Expected: PASS.
- [ ] **Step 5: SPEC R18-STATS (рядок прози; правило підсумовування — у тексті вимоги й на сайті), сайт `writing-tools.md` uk/en «Статистика сцени»; commit** — `feat(statistics): whole-story prose line; Store shows materials only`.

### Task 4: «Текст, що пише модель» розгортається на час етапу

**Files:**
- Modify: `src/storygen/web/templates/story.html` (підпис `details.workspace-output` → ключ `workspace.model_text`: «Текст, що пише модель» / "Text the model is writing")
- Modify: `src/storygen/web/static/runs.js` (`follow`)
- Test: `tests/web/js/runs_follow.mjs` (+ наявна pytest-обгортка)

**Interfaces:**
- Produces: у `follow()` `const output=live.closest?.('details')`; `stage_started` → `output.open=true`; `stage_finished` → `output.open=false`; завершальний стан (гілка `terminal.has(current.run.state)`) → `output.open=false`.

- [ ] **Step 1: Failing test** у `runs_follow.mjs` (новий режим або розширення наявного потоку подій): після `stage_started` `open===true`, після `stage_finished` `false`, після нового `stage_started` знову `true`, після `state` з `cancelled` — `false`.
- [ ] **Step 2: Run** — Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** обгортку `runs_follow` і `test_localization.py` — Expected: PASS.
- [ ] **Step 5: SPEC R20-WORKSPACE (опис блоку), сайт `workspace.md`; commit** — `feat(workspace): the model text block opens while a stage runs`.

### Task 5: Підвал Store — без «Параметрів запуску» й «Додаткових дій»

**Files:**
- Modify: `src/storygen/web/templates/story.html` (`{% if edition() != 'store' %}` навколо `#run-options` і `.workspace-extra`)
- Modify: `src/storygen/web/static/runs.js` (`controls` може бути `null` → відокремлений `div`; `#pause-each` через `?.checked`)
- Test: `tests/web/browser/store-footer.spec.mjs`

- [ ] **Step 1: Failing test** «Store footer keeps only what an author needs»: `POST /test-build-edition {edition:'store'}` (afterEach — `full`), сторінка твору: `#run-options`, `.workspace-extra`, `#generation-controls` — `toHaveCount(0)`; `#scene-statistics select` — 0; `#workspace-history` є; без помилок консолі (`page.on('pageerror')`); основна дія видима. Повне видання: `#run-options` і `.workspace-extra` присутні.
- [ ] **Step 2: Run** — Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `store-footer`, `build-edition`, `save-and-run`, `workspace-cancel` — Expected: PASS.
- [ ] **Step 5: commit** — `feat(store): the Store footer hides run options and extra actions`.

### Task 6: Історія версій у Store

**Files:**
- Modify: `src/storygen/web/static/versions.js` (`render`: гілка Store)
- Modify: `src/storygen/web/static/i18n.json` (`history.kind.draft|edited|manual`: «Чернетка»/«Редактура»/«Проза» · "Draft"/"Edited"/"Prose"; `history.compare_current`: «Порівняти з поточним текстом»; `history.restore`: «Повернути цю версію»; `history.restore_confirm`; `history.already_same`: «Текст уже такий самий» / "The text is already the same"; `history.no_head`: причина вимкнення; `history.is_current`: «Це вже поточна версія»)
- Test: `tests/web/browser/store-footer.spec.mjs`

**Interfaces:**
- Consumes: `GET /api/scenes/{id}/versions` (`kind`, `created_at`, `stale`, `content_format`), `GET /api/versions/{id}`, `GET /api/versions/compare?left=&right=`, `POST /api/scenes/{id}/draft|prose` `{text, expected_revision, content_format}` → `{version, scene}`; незмінений текст — `version.id === scene.heads[material]` до виклику.
- Produces: у Store список лише `kind ∈ {draft, edited, manual}`; підпис `«{kind} · {Intl.DateTimeFormat(getLocale(),{dateStyle:'medium',timeStyle:'short'})} [· застаріла]»`; три кнопки; матеріал версії `material = kind==='draft' ? 'draft' : 'prose'`.

- [ ] **Step 1: Failing tests** (Store, фікстура: дві ручні прози з різним текстом, plain і Markdown, плюс чернетка):
  - список містить лише Draft/Prose-рядки, немає `brief`/`memory`; видимих кнопок рівно три з потрібними підписами;
  - «Compare with the current text» для старої прози показує порівняння з головою прози;
  - «Restore this version» на старій Markdown-прозі → підтвердження → голова прози нова, `GET /api/versions/{head}` має `content_format:'markdown'` і текст старої версії;
  - для поточної голови кнопка вимкнена; для іншої версії з тим самим текстом і форматом — `#notice` містить `The text is already the same`, кількість версій не зросла.
- [ ] **Step 2: Run** — Expected: FAIL.
- [ ] **Step 3: Implement** (повне видання — наявний код без змін).
- [ ] **Step 4: Run** `store-footer`, `prose-acceptance`, `core-review` — Expected: PASS.
- [ ] **Step 5: commit** — `feat(store): version history with view, compare and restore`.

### Task 7: SPEC STORE-FOOTER, traceability, сайт

**Files:**
- Modify: `SPEC.MD` (нова Requirement `STORE-FOOTER` поруч із BUILD-EDITION; Scenarios `STORE-FOOTER-S01` склад підвалу Store, `-S02` історія Store і «Повернути», `-S03` повне видання без змін; R20-WORKSPACE-S03 — «Параметри запуску» лише в повному виданні)
- Modify: `docs/verification/traceability.json` (S01–S03 → тести `store-footer.spec.mjs`; ручна процедура `store-package-install` — вигляд у зібраному пакеті)
- Modify: `docs/site/{uk,en}/` — історія версій (Store), рядок стану (параметри запуску й «Пройти решту» — лише повне видання), статистика (підсумовування)
- Run: `python scripts/check_site.py --rehash <slug>` для кожної зміненої пари; `python scripts/check_docs.py`

- [ ] **Step 1:** SPEC і traceability. **Step 2:** сайт uk/en. **Step 3:** `check_site.py --rehash`, `check_docs.py` — Expected: без помилок. **Step 4:** повний `pytest` і всі браузерні специфікації — Expected: PASS (крім відомих локалезалежних поза `PYTHONUTF8=1`). **Step 5: commit** — `docs(spec): STORE-FOOTER requirement, traceability and site pages`.
