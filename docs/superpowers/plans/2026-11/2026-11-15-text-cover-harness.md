# Текстова обкладинка — план периферії

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Кнопка «Створити текстову обкладинку» з вибором палітри в «Картці й публікації», переклади, контракт у SPEC.MD, сторінки сайту обома мовами й знімок панелі обкладинки. Разом з ядром це один PR.

**Architecture:** Ядро вже є: `POST /api/stories/{id}/publication/cover/generate` і MCP `generate_cover` (план `2026-11-15-text-cover-core.md`, коміти 7393de7..eb7a75f). Кнопка — третій шлях до того самого маршруту, поруч із завантаженням. Вона надсилає поточні значення форми, а результат обробляє так само, як завантаження: `coverId`, форма змінена, показ, повідомлення. Сервер лише вирівнюємо з карткою: обрізання пробілів до перевірки довжини й англійські тексти двох нових відмов.

**Tech Stack:** FastAPI/pydantic, ES-модулі без збирача, Node-тест із підробленим DOM (`tests/web/js/publication.mjs`), Playwright лише для знімків (`scripts/capture_screenshots.py`).

**Spec:** `docs/superpowers/specs/2026-11/2026-11-15-text-cover-design.md` (затверджено 2026-11-15), розділ «Інтерфейс» (рядок «У панелі обкладинки…») і «Документація».

## Global Constraints

- Палітри й підписи: `ink` «Чорнило» / Ink, `paper` «Папір» / Paper, `wine` «Бордо» / Wine, `forest` «Ліс» / Forest. Типово вибрано `ink`.
- Кнопка: «Створити текстову обкладинку» / «Create text cover». Розміщення: панель обкладинки під формою завантаження.
- Кнопка вимкнена `busy||!view`, як і кнопка завантаження. Під час запиту `busy=true` і статус «Створюємо обкладинку…» / «Creating cover…».
- Після успіху: `coverId=asset.id; changed(); renderCover();` і повідомлення «Обкладинку створено. Збережіть картку, щоб застосувати її.» / «Cover created. Save the card to apply it.» Картка не зберігається.
- Помилку показуємо як помилку завантаження: `notice(error.message,'error')`, а `coverId` не змінюється.
- Тіло запиту: `{palette, title, cycle_title, cycle_number, author_ids, language}` з `collect()`. Жодних інших полів, бо `DomainModel` має `extra="forbid"`.
- Ключі `i18n.json`: `m_`/`d_` + перші 12 символів SHA-1 українського тексту (UTF-8). Ключ однаковий в `uk` і `en`.
- Нові тексти відмов сервера: `Невідома палітра обкладинки` → «Unknown cover palette»; `Для обкладинки потрібна назва: задайте її в картці або у творі` → «A cover needs a title: set it in the card or in the story».
- Документація українською; маркери OpenSpec англійською. Змінену пару сторінок сайту підтверджує `python scripts/check_site.py --rehash <slug>`. Знімки беруться лише з нейтрального seed-твору.
- Гейт: `PYTHONIOENCODING=utf-8 python scripts/check_docs.py && python -m pytest -q`. Фактичний запуск записує `python scripts/verify.py` у `docs/STATUS.md`. **Не запускати `verify.py --help`**: аргументи йдуть у pytest, і скрипт переписує STATUS.

## Review Focus

1. **Назва, довша за 300 символів лише через пробіли в кінці.** Картка таку приймає, бо обрізає пробіли до перевірки, а генерація має прийняти так само, а не дати 422. Тест: задача 1.
2. **Неприйнятне значення номера циклу у формі, наприклад `0`.** Кнопка показує текст помилки 422 так само, як завантаження, і не скидає показану обкладинку. Тест: задача 2, гілка відмови.
3. **Повторне натискання, поки йде запит.** `busy` блокує другий запит, і ресурс не реєструється двічі. Тест: задача 2.
4. **Англійський інтерфейс і відмова сервера.** Відмова приходить англійською, а не українським рядком. Тест: задача 1.
5. **Обкладинка з чату поверх відкритої картки.** Щоб застосувати її, чат пише в картку `cover_id`, а відкрита сторінка підхоплює зовнішню зміну наявним механізмом `publication-sync`. Нового коду тут немає: задача 4 документує поведінку, перевіряє її наявний тест синхронізації.

---

### Task 1: Сервер — пробіли до перевірки й переклади відмов

**Files:**
- Modify: `src/storygen/web/routes_publication.py` (клас `CoverGenerate`)
- Modify: `src/storygen/web/static/i18n.json` (два `d_`-ключі в `uk` і `en`)
- Test: `tests/web/test_publication_api.py`, `tests/web/test_localization.py`

**Interfaces:**
- Consumes: `CoverGenerate`, маршрут `generate_cover` з ядра; `localization.diagnostic(text, locale)`.
- Produces: `CoverGenerate` обрізає пробіли в `title`, `cycle_title`, `language` до перевірки `max_length`, як `PublicationData.strip_text`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/web/test_publication_api.py
def test_generate_cover_strips_text_before_limits(client):
    story=client.post('/api/stories',json={'title':'Маяк'}).json()
    response=client.post(f"/api/stories/{story['id']}/publication/cover/generate",
        json={'palette':'ink','title':'Н'*300+'  ','cycle_title':' Цикл ','language':' uk '})
    assert response.status_code==200
    assert response.json()['width']==1600

# tests/web/test_localization.py
def test_text_cover_refusals_are_translated():
    from storygen.web.localization import diagnostic
    assert diagnostic('Невідома палітра обкладинки','en')=='Unknown cover palette'
    assert diagnostic('Для обкладинки потрібна назва: задайте її в картці або у творі','en')==\
        'A cover needs a title: set it in the card or in the story'
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m pytest tests/web/test_publication_api.py::test_generate_cover_strips_text_before_limits tests/web/test_localization.py::test_text_cover_refusals_are_translated -q`
Expected: 2 failed (422 у першому, неперекладений рядок у другому).

- [ ] **Step 3: Implement**

`CoverGenerate`: `@field_validator('title','cycle_title','language',mode='before')`, який повертає `value.strip()` для рядків. В `i18n.json` додати `d_<sha1[:12]>` для обох текстів у `uk` (оригінал) і `en` (переклад з Global Constraints).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/web/test_publication_api.py tests/web/test_localization.py tests/storage/test_publication.py -q`
Expected: усі passed.

- [ ] **Step 5: Commit**

`fix(cover): strip generate fields before limits; English refusals`

### Task 2: Кнопка й палітра в картці

**Files:**
- Modify: `src/storygen/web/templates/publication.html` (панель обкладинки, після `#publication-cover-form`)
- Modify: `src/storygen/web/static/publication.js` (`state()`, новий обробник)
- Modify: `src/storygen/web/static/i18n.json` (`m_`-ключі: «Палітра», 4 назви палітр, кнопка, статус, повідомлення успіху)
- Test: `tests/web/js/publication.mjs` (запускає `tests/web/test_publication_ui.py::test_publication_dirty_async_save_conflict_and_upload`)

**Interfaces:**
- Consumes: `POST ${base}/cover/generate` (задача 1); `collect()`, `changed()`, `renderCover()`, `state()`, `api`, `json`, `notice`, `msg`, `t` з `publication.js`.
- Produces: елементи `#publication-cover-palette` (`<select>` з `value` ∈ `ink|paper|wine|forest`) і `#publication-cover-generate` (`<button type="button">`). Скрипт знімків (задача 4) натискає саме їх.

- [ ] **Step 1: Write the failing test** (дописати в `publication.mjs` після наявної перевірки завантаження)

Підготовка: додати `'cover-palette','cover-generate'` до списку вузлів; `nodes['#publication-cover-palette'].value='ink'`. У підробленому `fetch` перед гілкою `endsWith('/cover')` додати гілку `url.endsWith('/cover/generate')`: записати `generateBody=JSON.parse(options.body)`, лічильник `generateCalls++`, відповідь `{id:'generated'}`, або `{detail:'cycle_number: має бути ≥ 1'}` з `ok=false`, коли `generateFailure`.

```js
// Незбережена назва потрапляє в запит; картка не зберігається; повторне натискання поки busy ігнорується.
const putsBefore=putCalls;            // лічильник PUT додати у гілку options.method==='PUT'
fields.title.value='Незбережена назва';form.handlers.input({target:{name:'title'}});
nodes['#publication-cover-palette'].value='wine';
hold=true;                             // наявний механізм затримки: тут він тримає й generate
const first=nodes['#publication-cover-generate'].onclick();
await nodes['#publication-cover-generate'].onclick();
release();await first;
assert.equal(generateCalls,1,'Busy blocks a second generate');
assert.deepEqual(Object.keys(generateBody).sort(),['author_ids','cycle_number','cycle_title','language','palette','title']);
assert.equal(generateBody.title,'Незбережена назва');assert.equal(generateBody.palette,'wine');
assert.equal(nodes['#publication-cover'].src,'/api/stories/story/publication/covers/generated');
assert.equal(putCalls,putsBefore,'Generating never saves the card');
assert.equal(nodes['#publication-save'].disabled,false,'The generated cover makes the form dirty');
// Відмова: повідомлення помилки, показана обкладинка лишається.
generateFailure=true;await nodes['#publication-cover-generate'].onclick();
assert.equal(nodes['#publication-cover'].src,'/api/stories/story/publication/covers/generated');
assert.equal(notice.dataset.kind,'error');
```

`hold`/`release` зараз стоять лише в гілці PUT. Поширити їх на гілку generate (або завести окремий `holdGenerate`). Рішення за виконавцем, у тесті головне — тримати перший запит, поки йде друге натискання.

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest tests/web/test_publication_ui.py -q`
Expected: FAIL (`onclick` у `#publication-cover-generate` не визначено).

- [ ] **Step 3: Implement**

- Шаблон: `<div class="actions">` із `<label>` «Палітра» + `<select id="publication-cover-palette">` (4 `<option>` у порядку з Global Constraints, `ink` вибрано) і `<button type="button" id="publication-cover-generate" class="secondary">`. Підписи через `data-i18n`, як сусідні елементи.
- `state()`: `#publication-cover-generate` вимкнена за `busy||!view`.
- Обробник `onclick`: якщо `busy||!view`, повернутися. Тіло збирається з `collect()` (`title`, `cycle_title`, `cycle_number`, `author_ids`, `language`) і `palette`. Далі `busy=true; state(t(статус))` і `api(base+'/cover/generate',json('POST',body))`. Успіх, помилка й `finally` — як в обробнику завантаження.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/web/test_publication_ui.py tests/web/test_localization.py -q`
Expected: passed.

- [ ] **Step 5: Check in the real app**

Запустити сервер на копії даних у `C:\tmp\cover-ui`, відкрити картку нейтрального твору у вбудованому браузері, змінити назву, не зберігаючи, вибрати «Ліс», натиснути кнопку. Очікування: показано обкладинку з новою назвою, статус «є незбережені зміни». Після «Оновити дані» й відмови від змін обкладинка зникає, бо картку не змінено.

- [ ] **Step 6: Commit**

`feat(cover): text cover button with palette in the publication card`

### Task 3: Контракт у SPEC.MD і traceability

**Files:**
- Modify: `SPEC.MD` (R16-COVER: новий Scenario після S03; технічний опис)
- Modify: `docs/verification/traceability.json`

**Interfaces:**
- Consumes: назви тестів із задач 1–2.
- Produces: Scenario `R16-COVER-S04`.

- [ ] **Step 1: Add the Scenario**

```markdown
#### Scenario: R16-COVER-S04 — Кнопка текстової обкладинки в картці

- GIVEN відкрита картка з незбереженими правками й вибраною палітрою
- WHEN автор натискає «Створити текстову обкладинку»
- THEN запит несе поточні значення форми, показ і форма поводяться як після завантаження, а картка змінюється лише явним Save
- AND повторне натискання під час запиту не створює другого ресурсу, а відмова показується без зміни показаної обкладинки.
```

Технічний опис R16-COVER доповнити одним реченням про кнопку (елементи, тіло запиту з `collect()`, `busy`) і про те, що `CoverGenerate` обрізає пробіли до перевірки довжини, як `PublicationData`.

- [ ] **Step 2: Traceability**

Додати запис `R16-COVER-S04` з тестами `tests/web/test_publication_ui.py::test_publication_dirty_async_save_conflict_and_upload` і `tests/web/test_publication_api.py::test_generate_cover_strips_text_before_limits`. У `scope` S03 прибрати фразу «Кнопку в картці підтверджує план периферії.» і додати `tests/web/test_localization.py::test_text_cover_refusals_are_translated`.

- [ ] **Step 3: Verify**

Run: `PYTHONIOENCODING=utf-8 python scripts/check_docs.py`
Expected: без помилок.

- [ ] **Step 4: Commit**

`docs(spec): R16-COVER-S04 text cover button`

### Task 4: Сайт і знімок

**Files:**
- Modify: `docs/site/uk/publication.md`, `docs/site/en/publication.md`
- Modify: `docs/site/uk/mcp.md`, `docs/site/en/mcp.md`
- Modify: `scripts/capture_screenshots.py` (`capture()`: новий знімок `publication-cover-desktop.png`)
- Create: `docs/images/site/{uk,en}/publication-cover-desktop.png`
- Modify: `docs/site/sync.json` (через `--rehash`)

**Interfaces:**
- Consumes: `#publication-cover-palette`, `#publication-cover-generate`, `#publication-cover` (задача 2).

- [ ] **Step 1: Pages**

- `publication.md`, пункт «Обкладинка». Додати другий спосіб: «Створити текстову обкладинку» малює обкладинку з назви, циклу з номером і авторів того, що зараз у формі. Палітри: «Чорнило», «Папір», «Бордо», «Ліс». Обкладинка сама не перемальовується після зміни назви. Довгий текст обрізається «…». Після пункту — зображення `../../images/site/uk/publication-cover-desktop.png` з alt-текстом.
- `mcp.md`: «двадцять п’ять» → «двадцять шість» (en: twenty-five → twenty-six). Новий пункт списку — «текстова обкладинка з картки публікації в одній із чотирьох палітр». Підходить, коли чат не має доступу до файлів, як-от Claude Desktop зі збірки Microsoft Store. У «Публікація з чату» — одне речення: чат може попросити Obscura намалювати текстову обкладинку зі збереженої картки, і вона стає частиною картки, лише коли чат запише її `cover_id`.
- Англійські сторінки — той самий зміст. Обидва слаги підтвердити: `python scripts/check_site.py --rehash publication` і `python scripts/check_site.py --rehash mcp`.

- [ ] **Step 2: Screenshot**

У `capture()` після знімка `publication-desktop.png` (лише desktop) на тій самій сторінці картки: вибрати `wine` у `#publication-cover-palette`, натиснути `#publication-cover-generate`, дочекатися видимого `#publication-cover`. Далі `scroll_into_view_if_needed()` для секції `section[aria-labelledby=publication-cover-title]` і знімок саме цієї секції через `locator.screenshot`. Назва твору береться з seed («Маяк на пристані» / «Lighthouse pier»), автора немає. Запуск: `python scripts/capture_screenshots.py --work-dir C:/tmp/cover-shots`. Скрипт перезнімає всі сторінки, тож у коміт іде лише `publication-cover-desktop.png` обома мовами. Решту змінених PNG повернути `git checkout -- <file>`: вони без змін у коді, різниця лише в пікселях. Подивитися обидва знімки очима.

- [ ] **Step 3: Verify**

Run: `PYTHONIOENCODING=utf-8 python scripts/check_docs.py && python -m pytest tests/test_docs_site.py tests/test_capture_screenshots.py -q`
Expected: без помилок, passed.

- [ ] **Step 4: Commit**

`docs(site): text cover in publication and MCP pages, cover screenshot`

### Task 5: Гейт, STATUS і журнал

**Files:**
- Modify: `docs/STATUS.md` (через `verify.py`)
- Modify: `docs/superpowers/plans/2026-10-20-remediation-progress.md` (запис «Текстова обкладинка…»: периферія, перевірки)

- [ ] **Step 1: Full gate**

Run: `PYTHONIOENCODING=utf-8 python scripts/check_docs.py` і `python scripts/verify.py` (у фоні, близько 12 хв).
Expected: check_docs без помилок; `result.json` зі `state: passed`, `failed: 0`; `docs/STATUS.md` оновлено.

- [ ] **Step 2: Journal and commit**

Дописати до запису журналу периферію, кількість тестів зі STATUS і відкладені дрібниці ядра: дублікати `author_ids` дають 400 замість 422, бо кнопка дублікатів не створює. У таблиці компонентів дизайн-спеки стара сигнатура — виправити поправкою за `spec-format.md` → «Amendments».

`docs(status): verify.py for the text cover`
