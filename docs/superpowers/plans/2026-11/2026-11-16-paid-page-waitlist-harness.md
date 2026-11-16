# Список очікування платної версії: периферія (сайт, «Приватність», розгортання) — план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Сторінка сайту «Платна версія» (uk/en) з формою на Worker списку очікування, нова редакція «Приватності», інструкція розгортання для власника й запобіжник, який не дає опублікувати сайт із непрацюючою формою.

**Architecture:** Збирач сайту (`scripts/build_site.py`) додає фіксований фрагмент форми після markdown сторінки, позначеної в маніфесті `"form": "waitlist"`, і скрипт Turnstile лише на ній. `check_site.py` перевіряє розділ `waitlist` і якір «Приватності», а новий режим `--publish` у задачі публікації workflow відмовляє, поки в репозиторії лишаються заглушки ключа Turnstile чи `database_id` або `localhost` у `ALLOWED_ORIGINS`. Worker з ядра (PR #192) не змінюється, крім дати `PRIVACY_EDITION`.

**Tech Stack:** Python 3.12 (`markdown-it-py`, `tomllib`, `html`), pytest, GitHub Actions, Cloudflare Wrangler (лише у власника).

**Spec:** `docs/superpowers/specs/2026-11/2026-11-16-paid-page-waitlist-design.md` (затверджено, PR #189). Ядро: `docs/superpowers/plans/2026-11/2026-11-16-paid-page-waitlist-core.md` (реалізовано, PR #192).

**Що дало рев'ю ядра.** Фінальне рев'ю ядра (самоперевірка) і cross-review (5 зауважень, усі виправлено) не залишили відкритих пунктів для периферії. Звідти в цей план переходять лише два факти: тести Worker без Node падають, а `CONTRIBUTING.md` каже, що JS-перевірки без Node пропускаються (задача 4); і `handle(request, env, deps)` замість `handle(request, env, verify)` зі специфікації (SPEC уже описує фактичний підпис).

## Global Constraints

- Маніфест: сторінка `{"slug": "paid", "title": {"uk": "Платна версія", "en": "Paid version"}, "form": "waitlist"}` одразу перед `legal`; розділ `"waitlist": {"action": "https://waitlist.obscurawriter.com/", "sitekey": "<ключ>"}`. До кроків власника `sitekey` = `"REPLACE_WITH_SITEKEY"`.
- `form` — необов'язкове поле сторінки з єдиним допустимим значенням `waitlist`. Сторінка з `form` без розділу `waitlist`, з `action`, що не починається з `https://`, чи з `sitekey` поза `^[0-9A-Za-z_-]+$` → `ValueError` збирача, текст починається з `site.json: `.
- Скрипт Turnstile: рівно `<script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>`, лише на сторінках з `form`. Решта сторінок побайтово така сама, як без `form`.
- Якір розділу «Список очікування» в «Приватності»: `список-очікування` (uk, заголовок `## Список очікування`), `waitlist` (en, `## Waitlist`). Константа `WAITLIST_PRIVACY_ANCHOR = {'uk': 'список-очікування', 'en': 'waitlist'}` у `scripts/site_common.py`.
- Нова редакція «Приватності»: одна дата `DD.MM.YYYY` — день коміту задачі 3. Вона однакова в `uk/privacy.md` («Редакція від …»), `en/privacy.md` («Version of …») і `PRIVACY_EDITION` (`YYYY-MM-DD`) у `wrangler.toml`.
- Збірка Store: `--waitlist-url https://obscurawriter.com/paid.html`.
- У закоміченому `wrangler.toml` `ALLOWED_ORIGINS` завжди рівно `"https://obscurawriter.com"`; `localhost` додається лише локально на час перевірки S08 і не комітиться.
- Ні секрет Turnstile, ні токени Cloudflare не потрапляють у репозиторій, чат чи журнал. Публічний ключ віджета й `database_id` не секрети: їх комітять.
- Сторінки сайту парами: після зміни сторінки `python scripts/check_site.py --rehash <slug>`. Документація українською, OpenSpec-маркери англійською. Кожен Scenario у traceability; `check_docs.py` проходить.
- Коміти закінчуються `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`, містять «Refs #119» і примітку про користувацьку документацію. Останній PR видачі (#119) — пізніший, тож тут не `Closes`.

## Review Focus

1. **PR зливають до кроків власника** (заглушка `sitekey` чи `database_id`). Очікувано: задача публікації workflow зупиняється на `check_site.py --publish` до збирання, тож на `obscurawriter.com` лишається попередня версія сайту без мертвої форми. Тест — задача 2.
2. **Власник забув повернути `wrangler.toml` після перевірки з `localhost`** і закомітив його. Очікувано: `--publish` відмовляє (`ALLOWED_ORIGINS` ≠ `base_url` без скісної риски), а тест ядра `test_wrangler_config_keeps_no_secret` червоніє. Тест — задача 2.
3. **Українська сторінка повертається з `#waitlist-ok`, а `site.js` переводить на англійську без якоря.** Очікувано: цього не стається, бо форма надсилає `lang` тієї сторінки, на якій людина вже лишилася, а рішення `site.js` для тієї самої людини й браузера те саме. Окремого тесту немає: це наслідок DOCS-SITE-S09; виконавець перевіряє лише, що поле `lang` дорівнює мові сторінки (тест задачі 1).
4. **Якір «Приватності» перейменовано** (заголовок змінили в одній мові). Очікувано: `check_site.py` падає з назвою мови й якоря, бо посилання з фрагмента форми markdown-перевірка не бачить. Тест — задача 1.
5. **Відвідувач без JavaScript.** Очікувано: `<noscript>` пояснює, що форма потребує JavaScript; блоки результатів приховані CSS і без `:target` не показуються. Тест — задача 1 (наявність `<noscript>` обома мовами).

---

### Task 1: Збирач малює форму списку очікування

**Files:**
- Modify: `scripts/site_common.py` (константа якоря), `scripts/build_site.py`, `scripts/check_site.py`, `docs/site/template.html`, `docs/site/site.css`
- Create: `tests/test_site_waitlist.py`
- Modify: `SPEC.MD` (WAITLIST-001: абзац про форму, Scenario S07), `docs/verification/traceability.json`

**Interfaces:**
- Produces (`scripts/build_site.py`):
  - `TURNSTILE_SCRIPT` — рядок скрипту з Global Constraints;
  - `waitlist_settings(manifest) -> dict` — повертає розділ `waitlist` або кидає `ValueError` за правилами Global Constraints;
  - `page_form(page) -> str | None` — `None` без `form`, `'waitlist'` з ним, `ValueError` для іншого значення;
  - `waitlist_form(manifest, lang) -> str` — HTML фрагмента;
  - `page_html(template, manifest, lang, slug, content, scripts='')` — новий параметр `scripts` підставляється в `{scripts}` шаблону.
- `docs/site/template.html`: рядок `<script src="{base}site.js"></script>` лишається, за ним одразу `{scripts}</head>` (порожній `scripts` дає ті самі байти, що й зараз).

Фрагмент (`waitlist_form`), значення атрибутів екрановані `html.escape(…, quote=True)`:

```html
<section class="waitlist" aria-labelledby="waitlist-form">
<h2 id="waitlist-form">{заголовок}</h2>
<p class="waitlist-result" id="waitlist-ok" role="status">{ok}</p>
<p class="waitlist-result" id="waitlist-invalid" role="alert">{invalid}</p>
<p class="waitlist-result" id="waitlist-captcha" role="alert">{captcha}</p>
<p class="waitlist-result" id="waitlist-error" role="alert">{error з mailto:privacy@obscurawriter.com}</p>
<form class="waitlist-form" method="post" action="{action}">
<input type="hidden" name="lang" value="{lang}">
<label for="waitlist-email">{адреса}</label>
<input id="waitlist-email" type="email" name="email" required autocomplete="email" maxlength="254">
<label class="waitlist-consent"><input type="checkbox" name="consent" value="yes" required> {згода з посиланням privacy.html#{WAITLIST_PRIVACY_ANCHOR[lang]}}</label>
<div class="cf-turnstile" data-sitekey="{sitekey}"></div>
<button type="submit">{кнопка}</button>
</form>
<noscript><p>{без JavaScript}</p></noscript>
</section>
```

Тексти (точні, живуть у збирачі, словник `WAITLIST_TEXT[lang]`):

| Ключ | uk | en |
|---|---|---|
| заголовок | Повідомити мене | Notify me |
| адреса | Електронна пошта | Email |
| згода | Погоджуюся, щоб мою адресу зберігали для одного листа про вихід платної версії, як описано в розділі «[Список очікування](…)» сторінки «Приватність». | I agree that my address is kept for one email about the paid version's release, as described in the «[Waitlist](…)» section of the Privacy page. |
| кнопка | Записатися | Sign up |
| ok | Готово: ви в списку. Ми напишемо один раз, коли вийде платна версія. | Done: you are on the list. We will write once, when the paid version is released. |
| invalid | Перевірте адресу й позначку згоди та надішліть форму ще раз. | Check the address and the consent box, then send the form again. |
| captcha | Перевірка Cloudflare не пройшла або застаріла. Оновіть сторінку й спробуйте ще раз. | The Cloudflare check failed or expired. Reload the page and try again. |
| error | Не вдалося записати адресу. Спробуйте пізніше або напишіть на privacy@obscurawriter.com. | The address could not be saved. Try again later or write to privacy@obscurawriter.com. |
| без JavaScript | Форма потребує JavaScript: без нього перевірку Cloudflare Turnstile не пройти. | The form needs JavaScript: the Cloudflare Turnstile check cannot run without it. |

`site.css`: `.waitlist-result { display: none; }`, `.waitlist-result:target { display: block; }` і стилі поля, позначки й кнопки на змінних теми (`--border`, `--accent`, `--surface`) — на розсуд виконавця, з `width: 100%` поля на вузькому екрані.

`check_site.py::check`: для кожної сторінки з `form` — `waitlist_settings` (помилка `ValueError` стає рядком помилки), сторінка `privacy` є в маніфесті, і для кожної мови якір `WAITLIST_PRIVACY_ANCHOR[lang]` є серед `page_anchors` її `privacy.md`. Текст помилки: `<slug>: фрагмент форми посилається на privacy.html#<якір> (<lang>), а такого якоря немає`.

- [ ] **Step 1: Write the failing tests** — `tests/test_site_waitlist.py`, кожен тест `@pytest.mark.req('WAITLIST-001')`, фікстура сайту з `make_site` (`from tests.test_docs_site import make_site`) плюс сторінки `paid` (з `form`) і `privacy` (з заголовками `## Список очікування` / `## Waitlist`) та розділом `waitlist` з `sitekey` `1x00000000000000000000AA`:
  - `test_s07_form_only_on_the_form_page`: у `paid.html` і `en/paid.html` є `action="https://waitlist.obscurawriter.com/"`, `data-sitekey="1x00000000000000000000AA"`, `TURNSTILE_SCRIPT`, `name="lang" value="uk"` / `value="en"`, чотири `id="waitlist-<стан>"`, `href="privacy.html#список-очікування"` / `href="privacy.html#waitlist"`, `mailto:privacy@obscurawriter.com`, `<noscript>`; в `install.html` і `en/install.html` немає ні `challenges.cloudflare.com`, ні `waitlist-form`;
  - `test_s07_other_pages_unchanged_by_the_form`: та сама фікстура, зібрана з `form` і без нього (поле видалено з маніфесту); `install.html`, `privacy.html` і їхні `en/` побайтово рівні між збірками;
  - `test_s07_bad_waitlist_section_stops_the_build` (parametrize: немає розділу `waitlist`; `action` `http://waitlist.obscurawriter.com/`; `sitekey` `'a b'`; `form` `"other"`): `pytest.raises(ValueError, match='site.json')`;
  - `test_s07_missing_privacy_anchor_fails_the_check`: англійський заголовок перейменовано на `## Mailing list`, `check_site.check(root)` містить рядок з `privacy.html#waitlist (en)`; після `--rehash` сторінок з правильними заголовками помилок немає.
- [ ] **Step 2: Run to verify they fail**
  Run: `PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m pytest tests/test_site_waitlist.py -q -p no:cacheprovider --basetemp=C:/tmp/wl-h1`
  Expected: FAIL (`ImportError` на `TURNSTILE_SCRIPT` або відсутній `action` у HTML).
- [ ] **Step 3: Implement** функції з Interfaces, шаблон, CSS і перевірку в `check_site.py`.
- [ ] **Step 4: Run to verify they pass** — та сама команда плюс `tests/test_docs_site.py`. Expected: PASS, без змін наявних тестів DOCS-SITE.
- [ ] **Step 5: SPEC і traceability.** У WAITLIST-001 після абзацу про видалення — абзац про форму сайту (ознака `form`, розділ `waitlist`, фрагмент і тексти в збирачі, скрипт Turnstile лише на цій сторінці, перевірка якоря). Scenario `WAITLIST-001-S07 — Форма на сайті` (GIVEN маніфест зі сторінкою `paid` з `form` і розділом `waitlist`; WHEN сайт зібрано; THEN форма, скрипт Turnstile, поле `lang` мови сторінки й чотири блоки результатів є лише на `paid` обома мовами, решта сторінок побайтово ті самі; AND без розділу `waitlist`, з `action` не `https://`, з хибним `sitekey` чи іншим `form` збірка відмовляє, а без якоря «Приватності» будь-якою мовою падає `check_site.py`). Запис S07 у traceability → чотири тести вище.
- [ ] **Step 6: Commit** — `feat(site): render the waitlist form from the manifest`, примітка: «Користувацька документація: не потрібна в цьому коміті — сторінку paid і "Приватність" додає наступний коміт цього PR».

### Task 2: Запобіжник публікації

**Files:**
- Modify: `scripts/check_site.py`, `.github/workflows/site.yml`, `tests/test_site_waitlist.py`, `tests/test_docs_site.py` (`test_workflow_publishes_only_from_main`)
- Modify: `SPEC.MD` (WAITLIST-001: абзац про запобіжник, Scenario S10; DOCS-SITE: абзац workflow), `docs/verification/traceability.json`

**Interfaces:**
- Consumes: `waitlist_settings` (задача 1).
- Produces: `check_site.publication_problems(root) -> list[str]`; CLI `python scripts/check_site.py --publish` друкує проблеми й повертає 1, без проблем — `Сайт готовий до публікації.` і 0. Маніфест без сторінок з `form` проблем не має.

Правила `publication_problems` (кожне порушення — окремий рядок):
- `sitekey` відповідає `^0x[0-9A-Za-z_-]{16,}$` (справжній ключ віджета; заглушка й тестові ключі `1x…` не проходять);
- `workers/waitlist/wrangler.toml` (`tomllib`): `d1_databases[0].database_id` відповідає `^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$`;
- `vars.ALLOWED_ORIGINS` дорівнює `base_url` маніфесту без кінцевої `/`;
- хост `action` дорівнює `pattern` маршруту з `custom_domain = true`.

`site.yml`, задача `deploy`: новий крок `run: python scripts/check_site.py --publish` з тією самою умовою `steps.fresh.outputs.current == 'true'`, після встановлення markdown-it-py і до `build_site.py`. До `paths` обох тригерів додати `workers/waitlist/wrangler.toml`.

- [ ] **Step 1: Write the failing tests** (`@pytest.mark.req('WAITLIST-001')`, фікстура з `base_url` і копією `wrangler.toml` під `tmp_path/workers/waitlist/`):
  - `test_s10_placeholders_block_publication`: заглушки `REPLACE_WITH_SITEKEY` і `REPLACE_WITH_DATABASE_ID` → два рядки (про `sitekey` і `database_id`); тестовий ключ `1x00000000000000000000AA` → рядок про `sitekey`;
  - `test_s10_localhost_origin_blocks_publication`: `ALLOWED_ORIGINS = "https://obscurawriter.com,http://localhost:8000"` → рядок про `ALLOWED_ORIGINS`;
  - `test_s10_ready_site_publishes`: ключ `0x4AAAAAAAexampleexample`, `database_id` `01234567-89ab-cdef-0123-456789abcdef`, рідний `ALLOWED_ORIGINS` → `[]`; `main(['--publish'])` з `ROOT` підміненим на фікстуру повертає 0;
  - у `test_workflow_publishes_only_from_main`: у кроках `deploy` команда `check_site.py --publish` стоїть раніше за `build_site.py`.
- [ ] **Step 2: Run to verify they fail** — `… -m pytest tests/test_site_waitlist.py tests/test_docs_site.py -q -p no:cacheprovider --basetemp=C:/tmp/wl-h2`. Expected: FAIL (`AttributeError: publication_problems`, крок відсутній у workflow).
- [ ] **Step 3: Implement** `publication_problems`, прапорець `--publish`, крок і `paths` workflow.
- [ ] **Step 4: Run to verify they pass** — та сама команда. Expected: PASS.
- [ ] **Step 5: SPEC і traceability.** WAITLIST-001: абзац про `--publish` (поки ключ віджета, `database_id` чи `ALLOWED_ORIGINS` не готові, задача публікації зупиняється до збирання, а опублікованою лишається попередня версія сайту). DOCS-SITE, абзац workflow: крок `check_site.py --publish` перед збиранням у `deploy`. Scenario `WAITLIST-001-S10 — Сайт не публікується з непрацюючою формою` за правилами вище; traceability → три тести S10 і тест workflow.
- [ ] **Step 6: Commit** — `feat(site): block publishing while the waitlist is not configured`, примітка про документацію як у задачі 1.

### Task 3: Сторінка «Платна версія», «Приватність» і збирання

**Files:**
- Create: `docs/site/uk/paid.md`, `docs/site/en/paid.md`
- Modify: `docs/site/site.json`, `docs/site/uk/privacy.md`, `docs/site/en/privacy.md`, `docs/site/sync.json` (через `--rehash paid` і `--rehash privacy`), `workers/waitlist/wrangler.toml` (`PRIVACY_EDITION`), `docs/packaging.md`
- Modify: `tests/test_waitlist_worker.py` (`test_privacy_edition_matches_site`), `tests/test_docs_site.py` (`test_privacy_and_report_pages_carry_their_addresses`)
- Modify: `SPEC.MD` (DOCS-SITE: абзац про `privacy`/`report`, S10), `docs/verification/traceability.json`

**Interfaces:**
- Consumes: ознака `form` і розділ `waitlist` (задача 1).

Зміст `paid.md` (обидві мови, по суті однаково):
- що дає платна версія: довга проза (частини й арки), серії книг, межа рейтингу рівня 2 за всіма осями — як у версії з вихідного коду; посилання на [Частини й арки](book-structure.md), [Серії книг](series.md), [Віковий рейтинг](content-rating.md);
- ціни й дати ще немає;
- лист буде один, коли платна версія вийде; потім адресу видаляють;
- що зберігається і як видалити запис — посилання `privacy.md#список-очікування` (en: `privacy.md#waitlist`).
Форму збирач додає сам після цього тексту; markdown про неї не пише.

«Приватність» (обидві мови, нова дата з Global Constraints):
- «Цей сайт», перший пункт замінити: сайт без облікових записів, cookies, аналітики й рекламних пікселів; єдина форма — на сторінці «Платна версія»; там Cloudflare Turnstile перевіряє, що форму заповнює людина, і обробляє технічні дані браузера за політикою приватності Cloudflare; мова запам'ятовується лише в `localStorage`, як і раніше;
- новий розділ `## Список очікування` / `## Waitlist` після «Листи»: що зберігається (адреса, мова сторінки, дата запису, редакція «Приватності», з якою ви погодилися; IP-адреса передається лише Turnstile для перевірки й не зберігається); мета — один лист про вихід платної версії; підстава — ваша згода; де — Cloudflare D1 у юрисдикції ЄС; строк — до листа про вихід, не довше 24 місяців від запису, старіші записи видаляються автоматично щодня; відкликання й видалення — лист на privacy@obscurawriter.com;
- «Ваші права»: додати запис у списку очікування до того, що можна запитати й видалити.

- [ ] **Step 1: Write the failing tests:**
  - `test_privacy_edition_matches_site`: крім української, з `en/privacy.md` читається `Version of (\d{2})\.(\d{2})\.(\d{4})`, і обидві дати дорівнюють `PRIVACY_EDITION`;
  - `test_privacy_and_report_pages_carry_their_addresses`: `paid` є в маніфесті одразу перед `legal` і має `form == 'waitlist'`; `privacy.md` обома мовами містить заголовок розділу списку очікування; `docs/packaging.md` містить `--waitlist-url https://obscurawriter.com/paid.html`.
- [ ] **Step 2: Run to verify they fail** — `… -m pytest tests/test_waitlist_worker.py tests/test_docs_site.py -q -p no:cacheprovider --basetemp=C:/tmp/wl-h3`. Expected: FAIL на `paid`/`--waitlist-url`.
- [ ] **Step 3: Write the pages,** маніфест (сторінка й розділ `waitlist` із `REPLACE_WITH_SITEKEY`), нову дату в обох `privacy.md` і `wrangler.toml`, рядок `--waitlist-url` у `docs/packaging.md` з поясненням (сторінка сайту зі списком очікування; англійська — `…/en/paid.html`, у збірку передається одна адреса). Потім `--rehash paid` і `--rehash privacy`.
- [ ] **Step 4: Run** — та сама команда, потім `PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/check_docs.py` і `… scripts/build_site.py --out C:/tmp/wl-site`. Expected: PASS, `check_docs` без помилок, збірка пише `paid.html` і `en/paid.html`. Переглянути `C:/tmp/wl-site/paid.html` у вбудованому браузері (`python -m http.server` у тій теці): форма видна, блоки результатів приховані, `#waitlist-ok` у адресі показує лише свій блок.
- [ ] **Step 5: SPEC і traceability.** DOCS-SITE, абзац про `privacy`/`report`: додати сторінку `paid` (адреса `--waitlist-url` збірки Store, форма WAITLIST-001); речення «сайт не має форм, cookies…» → «сайт не має cookies, аналітики й рекламних пікселів; єдина форма — список очікування на сторінці `paid` (WAITLIST-001)». DOCS-SITE-S10: `paid` у маніфесті, розділ списку очікування в `privacy` обома мовами, `--waitlist-url https://obscurawriter.com/paid.html` у `docs/packaging.md`. PACKAGING-001 адрес сайту не перелічує (їх описує DOCS-SITE), тож не змінюється.
- [ ] **Step 6: Commit** — `feat(site): paid version page and the waitlist privacy section`, примітка: «Користувацька документація: нова сторінка paid uk/en, нова редакція privacy uk/en (пари підтверджено --rehash); docs/packaging.md — --waitlist-url».

### Task 4: Інструкція розгортання, ручна перевірка, SPEC

**Files:**
- Create: `docs/waitlist.md`
- Modify: `docs/verification/manual.md` (новий розділ `waitlist-live`), `docs/verification/traceability.json` (S08), `CONTRIBUTING.md` (рядки 15–16), `SPEC.MD` (WAITLIST-001: відомі обмеження, S08), журнал `docs/superpowers/plans/2026-10-20-remediation-progress.md`

`docs/waitlist.md` (розробницький документ, не сайт), розділи:
1. **Що потрібно:** акаунт Cloudflare із зоною `obscurawriter.com`, Node.js; усе на Free. Якщо панель на будь-якому кроці просить оплату — зупинитися й написати в PR.
2. **Кроки власника** (з теки `workers/waitlist`):
   1. `npx wrangler login`;
   2. `npx wrangler d1 create obscura-waitlist --jurisdiction=eu` → `database_id`;
   3. `npx wrangler d1 execute obscura-waitlist --remote --file schema.sql`;
   4. панель → Turnstile → новий віджет «Managed», хости `obscurawriter.com` і `localhost` → публічний ключ (sitekey) і секрет;
   5. `database_id` і sitekey (не секрети) — написати в PR або закомітити в `wrangler.toml` / `docs/site/site.json`; секрет — нікуди, крім наступного кроку;
   6. `npx wrangler secret put TURNSTILE_SECRET` (вставити секрет у запит wrangler);
   7. `npx wrangler deploy` з гілки PR, бо `PRIVACY_EDITION` має збігатися з редакцією «Приватності», яку покаже сайт; деплой прив'язує `waitlist.obscurawriter.com` і щоденний cron.
3. **Перевірка наживо до злиття (S08)** — посилання на `docs/verification/manual.md#waitlist-live`.
4. **Після злиття:** та сама перевірка на `https://obscurawriter.com/paid.html` і `…/en/paid.html`; хост `localhost` прибрати з віджета.
5. **SQL** (консоль D1 або `npx wrangler d1 execute obscura-waitlist --remote --command "…"`): лічильник `SELECT COUNT(*) FROM waitlist WHERE created_at >= '<YYYY-MM-DD>T00:00:00Z';`; вивантаження `SELECT email, lang FROM waitlist ORDER BY created_at;`; видалення на запит `DELETE FROM waitlist WHERE email = '<адреса в нижньому регістрі>';`; після листа про вихід `DELETE FROM waitlist;`.
6. **Якщо Custom Domain попросить оплату:** прибрати `[[routes]]` з `wrangler.toml`, задеплоїти на `https://obscura-waitlist.<піддомен>.workers.dev/`, вписати цю адресу в `action` маніфесту, а в правилі `--publish` про маршрут — дозволити `workers.dev` (окрема зміна цього репозиторію, не робота власника).

`manual.md#waitlist-live` — «Список очікування: перевірка наживо»:
1. У теці `workers/waitlist` тимчасово змінити `ALLOWED_ORIGINS` на `"https://obscurawriter.com,http://localhost:8000"` і виконати `npx wrangler deploy`.
2. `python scripts/build_site.py --out C:\tmp\wl-site`, у `C:\tmp\wl-site` — `python -m http.server 8000`; відкрити `http://localhost:8000/paid.html`.
3. Записати нейтральну адресу з позначкою згоди → `#waitlist-ok`; ту саму адресу великими літерами → знову `#waitlist-ok`; адресу без `@` (обійти перевірку браузера можна, прибравши `type="email"` в інструментах розробника) → `#waitlist-invalid`; без позначки згоди браузер не надсилає форму. Те саме на `/en/paid.html` → англійська сторінка.
4. У консолі D1: один рядок на адресу, `lang` відповідає сторінці, `privacy_edition` = дата редакції, `created_at` у UTC; у панелі D1 видно юрисдикцію `eu`. Видалити тестові рядки.
5. `git restore workers/waitlist/wrangler.toml`, знову `npx wrangler deploy`; у панелі Worker → Settings → Variables `ALLOWED_ORIGINS` рівно `https://obscurawriter.com`.
6. Наявність процедури не є фактичним PASS; результат записується в журналі виконання.

- [ ] **Step 1:** написати `docs/waitlist.md` і розділ `manual.md`.
- [ ] **Step 2:** `CONTRIBUTING.md` рядки 15–16 → «Для JavaScript-перевірок потрібен Node.js у PATH. Їх запускають pytest-обгортки з потрібними аргументами. Без Node.js більшість цих перевірок пропускається, а тести Worker списку очікування (`tests/test_waitlist_worker.py`) падають: вони єдиний доказ сценаріїв WAITLIST-001.»
- [ ] **Step 3: SPEC.** WAITLIST-001: у «Відомих обмеженнях» речення «Форма на сайті, сторінка `paid`, нова редакція «Приватності» й інструкція розгортання — окремий план периферії; до нього Worker не розгорнуто й не опубліковано» замінити на «Розгортання й перевірку наживо описує `docs/waitlist.md`; лист про вихід платної версії власник надсилає сам, поза цим компонентом». Scenario `WAITLIST-001-S08 — Перевірка наживо` (GIVEN Worker розгорнуто з тимчасовим `localhost`; WHEN форму надіслано з локальної збірки сайту; THEN нова адреса, повтор і хибна адреса дають `ok`, `ok`, `invalid`, у D1 один рядок у юрисдикції `eu`; AND після перевірки `ALLOWED_ORIGINS` знову рівно `https://obscurawriter.com`). Traceability S08: `tests: []`, `manual.procedure` `docs/verification/manual.md#waitlist-live`, `reason` «Потрібні акаунт Cloudflare власника, розгорнутий Worker, справжня база D1 і віджет Turnstile; локальні тести не мають цих сервісів.»
- [ ] **Step 4: Run** `PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/check_docs.py` і повний `… -m pytest -q -p no:cacheprovider --basetemp=C:/tmp/wl-h4`. Expected: `check_docs` без помилок; pytest без падінь.
- [ ] **Step 5: Commit** — `docs(waitlist): owner deployment steps and the live check`, примітка: «Користувацька документація: сайт оновлено в попередньому коміті; тут — розробницькі docs/waitlist.md, manual.md, CONTRIBUTING».

Після задачі 4: фінальне рев'ю гілки, cross-review, `verify.py`, PR у статусі **draft** з поясненням, що зливати лише після задачі 5.

### Task 5: Значення власника й перевірка наживо (після кроків власника)

Починається, коли власник виконав кроки 1–4 з `docs/waitlist.md` і дав `database_id` та sitekey.

- [ ] **Step 1:** вписати `database_id` у `wrangler.toml` і sitekey у `site.json`; `python scripts/check_site.py --publish` → `Сайт готовий до публікації.`; комміт `chore(waitlist): owner's database id and Turnstile site key`.
- [ ] **Step 2:** оновити основну теку до вершини гілки; власник робить кроки 6–7 і процедуру `manual.md#waitlist-live`.
- [ ] **Step 3:** записати в журнал фактичний результат S08 зі слів власника (без адрес); якщо щось не пройшло — виправлення окремим комітом із тестом.
- [ ] **Step 4:** `verify.py` за звичною процедурою, `docs/STATUS.md`, коміт, PR із draft у ready. Після злиття — перевірка на `obscurawriter.com` (крок 4 `docs/waitlist.md`) і запис у журнал.
