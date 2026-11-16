# Список очікування платної версії: ядро (Worker) — план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cloudflare Worker, який приймає форму списку очікування, перевіряє її й Turnstile, пише адресу в D1 без дублів, повертає людину на сторінку з якорем результату й щодня видаляє записи, старші за 24 місяці.

**Architecture:** Новий каталог `workers/waitlist/` поза застосунком: ES-модуль `src/index.js` з чистою `handle(request, env, deps)` і `purge(env, now)`, схема `schema.sql`, конфігурація `wrangler.toml`. Тести — `node --test` на фейковій D1 і фейковій перевірці Turnstile. Тест pytest один раз запускає Node з репортером junit і для кожного сценарію перевіряє, що його тести Node пройшли, тож сценарії потрапляють у traceability.

**Tech Stack:** JavaScript (ES-модуль, API Workers: `Request`, `Response`, `fetch`, `FormData`), `node:test`/`node:assert` (Node ≥ 22), Python 3.12 + pytest, `tomllib`.

**Spec:** `docs/superpowers/specs/2026-11/2026-11-16-paid-page-waitlist-design.md` (затверджено, PR #189).

**Межа ядра.** Це перший із двох планів (`detent:pr-slicing`: спершу ядро, потім периферія). Сюди не входять: збирач сайту й форма, сторінка `paid`, «Приватність», `docs/waitlist.md`, `docs/packaging.md`, сценарії S07 і S08 та розгортання. Їх дасть план периферії після злиття й рев'ю ядра. Ядро нічого не публікує й не розгортає: код Worker лежить у репозиторії, поки власник не виконає кроків із периферії.

## Global Constraints

- Залежностей npm немає: лише вбудовані `node:test`, `node:assert`. `workers/waitlist/package.json` = `{"private": true, "type": "module"}`.
- Таблиця, рівно як у специфікації:

  ```sql
  CREATE TABLE IF NOT EXISTS waitlist (
    email TEXT PRIMARY KEY,
    lang TEXT NOT NULL CHECK (lang IN ('uk','en')),
    privacy_edition TEXT NOT NULL,
    created_at TEXT NOT NULL
  );
  ```
- Запис: `INSERT INTO waitlist (email, lang, privacy_edition, created_at) VALUES (?, ?, ?, ?) ON CONFLICT(email) DO NOTHING`. `created_at` — `YYYY-MM-DDTHH:MM:SSZ` (UTC, до секунди).
- Змінні Worker: `ALLOWED_ORIGINS = "https://obscurawriter.com"` (через кому, пробіли обрізаються), `RETENTION_MONTHS = "24"`, `PRIVACY_EDITION` = дата редакції `docs/site/uk/privacy.md` у форматі `YYYY-MM-DD` (зараз `2026-11-15`). Секрет `TURNSTILE_SECRET` у файлах репозиторію не з'являється ніколи.
- Переадресація: `303`, `Location: <Origin запиту>/<'' | 'en/'>paid.html#waitlist-<ok|invalid|captcha|error>`.
- Відмови без переадресації (`403`, `405`, `413`, `415`) — `text/plain; charset=utf-8`, тіло рівно `REFUSAL` (див. Task 1).
- Ні email, ні токен Turnstile не потрапляють у журнал Worker (`console.*`).
- Документація українською; OpenSpec-маркери англійською. Кожен Scenario у traceability; `check_docs.py` проходить.
- Коміти закінчуються `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` і містять «Refs #119» та примітку про користувацьку документацію (у ядрі: «не потрібна — Worker ще не розгорнуто, сторінки сайту змінює план периферії»).

## Review Focus

1. **`RETENTION_MONTHS` порожній, нечисловий чи ≤ 0** (помилка в `wrangler.toml`). Очікувано: `purge` нічого не видаляє й пише в журнал помилку. Межа, обчислена з `NaN`, не повинна видалити всю таблицю.
2. **Адреса з пробілами по краях і великими літерами** (`  Ann@Example.COM `). Очікувано: записується `ann@example.com`, повтор у будь-якому регістрі — той самий `ok` без другого рядка.
3. **Запит без заголовка `Origin` або з `Origin: null`** (деякі розширення приватності, перехід із `file://`). Очікувано: `403` з текстом `REFUSAL`, без виклику Turnstile й D1.
4. **Тіло понад 4096 байтів без `Content-Length`** (chunked). Очікувано: `413` — розмір перевіряється за прочитаними байтами, а не лише за заголовком.
5. **Кирилиця чи керівні символи в адресі** (`тест@приклад.укр`, табуляція всередині `a\tb@c.d`; пробіли й переноси по краях прибирає `trim`). Очікувано: `invalid` — правило з Task 1 дозволяє лише видимі символи ASCII без пробілів. Міжнародні домени (IDN) людина вводить у вигляді punycode; браузер з `type="email"` перетворює їх сам.

Пункти 1–5 мають тести: 1 — у задачі 2, 2–5 — у задачі 1.

---

### Task 1: Worker приймає форму

**Files:**
- Create: `workers/waitlist/package.json`, `workers/waitlist/src/index.js`, `workers/waitlist/schema.sql`, `workers/waitlist/wrangler.toml`, `workers/waitlist/test/index.test.mjs`
- Create: `tests/test_waitlist_worker.py`
- Modify: `SPEC.MD` (зміст після рядка `- [DOCS-SITE — …](#docs-site)`; новий розділ одразу після сценарію `DOCS-SITE-S10`, перед `## MCP-BRIDGE`), `docs/verification/traceability.json`

**Interfaces:**
- Produces (`src/index.js`):
  - `export const REFUSAL` = `'Запит відхилено. Якщо ви заповнювали форму на obscurawriter.com, напишіть на privacy@obscurawriter.com.\nRequest refused. If you were filling in the form on obscurawriter.com, write to privacy@obscurawriter.com.\n'`;
  - `export function normalizeEmail(raw: string): string | null` — `trim`, нижній регістр; `null`, якщо довжина > 254 або не відповідає `/^[\x21-\x3f\x41-\x7e]+@[\x21-\x2d\x2f-\x3f\x41-\x7e]+(\.[\x21-\x2d\x2f-\x3f\x41-\x7e]+)+$/` (один `@`, видимі ASCII без пробілів, домен із крапкою, без порожніх частин домену);
  - `export function allowedOrigins(env): string[]`;
  - `export async function handle(request: Request, env, deps = {}): Promise<Response>`, де `deps.verify(token: string, ip: string | null): Promise<{success: boolean, hostname?: string}>` (типово — `verifyTurnstile`), `deps.now(): Date` (типово — `new Date()`), `deps.log(entry: object)` (типово — `console.log(JSON.stringify(entry))`);
  - `export async function verifyTurnstile(token, ip, env)` — `POST https://challenges.cloudflare.com/turnstile/v0/siteverify` з `FormData` (`secret`, `response`, `remoteip`, якщо є), повертає розібраний JSON; помилка мережі чи не-200 → виняток;
  - `export default { fetch(request, env) }` → `handle(request, env, {verify: (t, ip) => verifyTurnstile(t, ip, env)})`.
- `env.DB` — прив'язка D1: `env.DB.prepare(sql).bind(...values).run()`.

Порядок у `handle` (кожен крок зупиняє обробку):
1. метод не `POST` або шлях не `/` → `405`;
2. `Origin` немає в `allowedOrigins(env)` → `403`;
3. `Content-Type` не починається з `application/x-www-form-urlencoded` → `415`;
4. `Content-Length` > 4096 або прочитане тіло > 4096 байтів (`TextEncoder`) → `413`;
5. розбір `URLSearchParams`: `lang` (`en` → `en`, будь-що інше → `uk`), `email` через `normalizeEmail`, `consent === 'yes'`, токен `cf-turnstile-response`;
6. email `null` або немає згоди → `invalid` (без `verify` і D1);
7. порожній токен, `verify` повернула `success !== true` або `hostname` ≠ `new URL(origin).hostname` → `captcha`; виняток у `verify` → `error`;
8. запис у D1 → `ok`; виняток D1 → `error`.

Журнал: один запис `{state}` на кожну переадресацію (і `{state, error: <назва класу помилки>}` для `error`), `{refused: <код>}` на відмову.

- [ ] **Step 1: Write the failing Node tests**

`workers/waitlist/test/index.test.mjs` з допоміжними `fakeDb({fail})` (записує `[sql, values]`, `run()` кидає `Error('D1 down')` з `fail`), `form(fields, {origin, type, body})` (будує `Request('https://waitlist.obscurawriter.com/', {method: 'POST', …})`), `env()` (`ALLOWED_ORIGINS: 'https://obscurawriter.com, http://localhost:8000'`, `PRIVACY_EDITION: '2026-11-15'`, `DB`) і `deps({verify, logs})` з `now = () => new Date('2026-11-16T10:20:30.456Z')`. Назва кожного тесту починається з ID сценарію:

```js
test('S01: new address is recorded and redirects to the page language', async () => {
  const db = fakeDb(); const logs = [];
  const res = await handle(form({email: 'ann@example.com', consent: 'yes', lang: 'en', 'cf-turnstile-response': 't'}), env(db), deps({logs}));
  assert.equal(res.status, 303);
  assert.equal(res.headers.get('Location'), 'https://obscurawriter.com/en/paid.html#waitlist-ok');
  assert.deepEqual(db.calls[0][1], ['ann@example.com', 'en', '2026-11-15', '2026-11-16T10:20:30Z']);
  assert.match(db.calls[0][0], /ON CONFLICT\(email\) DO NOTHING/);
});
```

Інші тести (кожен з такими ж точними перевірками статусу, `Location` чи тіла й викликів):
- `S01: unknown lang falls back to uk` → `Location` `https://obscurawriter.com/paid.html#waitlist-ok`, `lang` у D1 `uk`;
- `S01: localhost origin redirects back to localhost` → `http://localhost:8000/paid.html#waitlist-ok`, `verify` отримала `hostname`-перевірку проти `localhost` (фейк повертає `{success: true, hostname: 'localhost'}`);
- `S02: same address in another case gives the same ok` → `'  Ann@Example.COM '` записується як `ann@example.com`, `Location` той самий `#waitlist-ok`;
- `S03: invalid email or missing consent gives invalid without verify or D1` — таблиця входів: `''`, `'no-at'`, `'a@b'`, `'a@@b.c'`, `'a b@c.d'`, `'тест@приклад.укр'`, `'a\tb@c.d'`, 255-символьна адреса, коректна адреса без `consent`, з `consent=on`; для кожного `#waitlist-invalid`, `verify` не викликана, `db.calls` порожній;
- `S04: turnstile failure, wrong hostname or empty token gives captcha without a row` — `{success: false}`, `{success: true, hostname: 'evil.example'}`, порожній токен → `#waitlist-captcha`, `db.calls` порожній;
- `S05: refusals are plain text without redirect` — `GET` → 405; `POST /other` → 405; `Origin` відсутній, `null`, `https://www.obscurawriter.com` → 403; `Content-Type: application/json` → 415; `Content-Length: 5000` → 413; тіло 5000 байтів без `Content-Length` → 413. Для кожного: немає `Location`, `Content-Type` `text/plain; charset=utf-8`, тіло `=== REFUSAL`, `verify` не викликана, `db.calls` порожній;
- `S06: D1 or network failure gives error and logs no address` — `fakeDb({fail: true})` і `verify`, що кидає `TypeError('fetch failed')` → `#waitlist-error`; `JSON.stringify(logs)` не містить `ann@example.com` і токена `t`.

- [ ] **Step 2: Run the Node tests to verify they fail**

Run: `node --test workers/waitlist/test/index.test.mjs`
Expected: FAIL — `Cannot find module …/src/index.js` (або `handle is not a function`).

- [ ] **Step 3: Implement `handle`, `normalizeEmail`, `allowedOrigins`, `verifyTurnstile` і `REFUSAL` у `workers/waitlist/src/index.js`; додати `package.json`, `schema.sql` (Global Constraints), `wrangler.toml`**

`wrangler.toml`:

```toml
name = "obscura-waitlist"
main = "src/index.js"
compatibility_date = "2026-11-01"

[vars]
ALLOWED_ORIGINS = "https://obscurawriter.com"
RETENTION_MONTHS = "24"
PRIVACY_EDITION = "2026-11-15"

[[d1_databases]]
binding = "DB"
database_name = "obscura-waitlist"
database_id = "REPLACE_WITH_DATABASE_ID"

[[routes]]
pattern = "waitlist.obscurawriter.com"
custom_domain = true
```

Над `[vars]` — коментар: `TURNSTILE_SECRET` задається лише `wrangler secret put`; `database_id` вписує власник після `d1 create` (план периферії).

- [ ] **Step 4: Run the Node tests to verify they pass**

Run: `node --test workers/waitlist/test/index.test.mjs`
Expected: PASS, усі тести `S01`–`S06`, 0 failed.

- [ ] **Step 5: Write the failing pytest wrapper**

`tests/test_waitlist_worker.py`:
- фікстура `node_results` (scope `module`) запускає `['node', '--test', '--test-reporter=junit', '--test-reporter-destination=<tmp>/junit.xml', 'workers/waitlist/test/index.test.mjs']` з `cwd` = корінь репозиторію, таймаут 120 с; `shutil.which('node') is None` → `pytest.fail('Node.js ≥ 22 потрібен для тестів Worker списку очікування')` (не `skip`); розбирає `junit.xml` (`xml.etree.ElementTree`) у `dict[name, passed: bool]` (тест пройшов, якщо в `testcase` немає `failure`, `error`, `skipped`);
- допоміжна `assert_scenario(results, prefix)`: є хоч один тест із назвою, що починається з `f'{prefix}:'`, і всі такі пройшли (повідомлення — назви непройдених);
- тести з `@pytest.mark.req('WAITLIST-001')`: `test_s01_new_address_is_recorded`, `test_s02_repeat_address_changes_nothing`, `test_s03_invalid_form_skips_turnstile`, `test_s04_turnstile_refusal_writes_nothing`, `test_s05_foreign_requests_are_refused`, `test_s06_failure_logs_no_address` — кожен викликає `assert_scenario(node_results, 'S0N')`;
- `test_privacy_edition_matches_site` (`req('WAITLIST-001')`): `tomllib` читає `workers/waitlist/wrangler.toml`, `vars.PRIVACY_EDITION` дорівнює даті з рядка `Редакція від DD.MM.YYYY` у `docs/site/uk/privacy.md`, перетвореній на `YYYY-MM-DD`;
- `test_wrangler_config_keeps_no_secret` (`req('WAITLIST-001')`): у `wrangler.toml` немає рядка `TURNSTILE_SECRET =`, `ALLOWED_ORIGINS` = `https://obscurawriter.com`, є `custom_domain = true` для `waitlist.obscurawriter.com`.

- [ ] **Step 6: Run pytest to verify the marker fails before SPEC exists**

Run: `.venv/Scripts/python.exe -m pytest -p no:cacheprovider --basetemp=C:/tmp/wl-t1a tests/test_waitlist_worker.py -q`
Expected: 8 passed (Node-тести вже зелені). Потім `PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/check_docs.py` — FAIL: маркер `WAITLIST-001` посилається на невідому вимогу.

- [ ] **Step 7: Add `WAITLIST-001` to SPEC.MD and traceability**

Розділ `## WAITLIST-001. Список очікування платної версії` з `<a id="waitlist-001"></a>`, `### Requirement: WAITLIST-001 — Список очікування платної версії`. Текст вимоги (SHALL/MUST) переносить із розділу специфікації «Дизайн → Worker» такі пункти:
- компонент поза застосунком;
- поля форми й правило email;
- порядок перевірок і стани;
- `ALLOWED_ORIGINS`, переадресація на перевірений `Origin`, відмови з `REFUSAL`;
- таблиця й запис без дублів;
- журнал без адрес;
- секрет лише через `wrangler secret put`;
- `PRIVACY_EDITION` = редакція «Приватності».

Технічний опис — модуль, функції, тест-обгортка junit. Відомі обмеження: немає підтвердження листом; розгортання вручну; форма й сторінка — план периферії (до його злиття Worker не розгорнуто).

Сценарії `WAITLIST-001-S01` … `S06` з якорями `waitlist-001-s01`… — GIVEN/WHEN/THEN за переліком SPEC-сценаріїв специфікації (S01 — запис і `303` мовою сторінки, S02 — повтор без змін, S03 — `invalid` без Turnstile, S04 — `captcha` без запису, S05 — відмови `403/405/413/415` з текстом, S06 — `error` без адреси в журналі).

Traceability — шість записів `WAITLIST-001-S01…S06` з `tests` = відповідний `tests/test_waitlist_worker.py::test_s0N_…`. Для S01 додати `test_privacy_edition_matches_site`, для S05 — `test_wrangler_config_keeps_no_secret`.

- [ ] **Step 8: Run checks to verify they pass**

Run: `PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/check_docs.py` → Expected: `Структура SPEC, матриця, тести, markers і локальні посилання узгоджені.`
Run: `.venv/Scripts/python.exe -m pytest -p no:cacheprovider --basetemp=C:/tmp/wl-t1b tests/test_waitlist_worker.py -q` → Expected: 8 passed.

- [ ] **Step 9: Commit**

```bash
git add workers/waitlist tests/test_waitlist_worker.py SPEC.MD docs/verification/traceability.json
git commit -m "feat(waitlist): Worker accepts the waitlist form (WAITLIST-001)"
```

(тіло коміту — за Global Constraints.)

---

### Task 2: Щоденне видалення застарілих записів

**Files:**
- Modify: `workers/waitlist/src/index.js`, `workers/waitlist/wrangler.toml`, `workers/waitlist/test/index.test.mjs`, `tests/test_waitlist_worker.py`, `SPEC.MD`, `docs/verification/traceability.json`

**Interfaces:**
- Consumes: `fakeDb`, `deps` і журнал із Task 1.
- Produces:
  - `export function retentionCutoff(now: Date, months: string): string | null` — `months` як ціле > 0 (`/^\d+$/` і `> 0`), інакше `null`; межа = `now` з `setUTCMonth(getUTCMonth() - months)` у форматі `created_at` (`YYYY-MM-DDTHH:MM:SSZ`);
  - `export async function purge(env, now: Date, log = defaultLog): Promise<number | null>` — `null` межа → `log({purge: 'invalid RETENTION_MONTHS'})`, повертає `null`, D1 не викликається; інакше `DELETE FROM waitlist WHERE created_at < ?` з межею, повертає `meta.changes` (0, якщо немає), журнал `{purged: n}`;
  - у `export default` додається `scheduled(event, env, ctx) { ctx.waitUntil(purge(env, new Date(event.scheduledTime))) }`.

- [ ] **Step 1: Write the failing Node tests**

- `S09: purge deletes rows older than the retention period` — `retentionCutoff(new Date('2028-11-16T03:17:00Z'), '24')` === `'2026-11-16T03:17:00Z'`; `purge` з фейковою D1 (`run()` повертає `{meta: {changes: 3}}`) викликає `DELETE FROM waitlist WHERE created_at < ?` з `['2026-11-16T03:17:00Z']` і повертає 3;
- `S09: invalid RETENTION_MONTHS deletes nothing` — для `''`, `'abc'`, `'0'`, `'-1'`, `'1.5'`: `purge` повертає `null`, `db.calls` порожній, у журналі `{purge: 'invalid RETENTION_MONTHS'}`;
- `S09: scheduled hands purge to waitUntil` — фейковий `ctx.waitUntil` отримує проміс, після `await` у фейковій D1 є один `DELETE`.

- [ ] **Step 2: Run them to verify they fail**

Run: `node --test workers/waitlist/test/index.test.mjs`
Expected: FAIL — `retentionCutoff`/`purge` не експортовано.

- [ ] **Step 3: Implement `retentionCutoff`, `purge`, `scheduled`; у `wrangler.toml` додати**

```toml
[triggers]
crons = ["17 3 * * *"]
```

- [ ] **Step 4: Run the Node tests to verify they pass**

Run: `node --test workers/waitlist/test/index.test.mjs`
Expected: PASS, разом із тестами Task 1.

- [ ] **Step 5: Add `test_s09_old_rows_are_purged_daily` (`req('WAITLIST-001')`) у `tests/test_waitlist_worker.py`**

Він викликає `assert_scenario(node_results, 'S09')` і перевіряє, що `wrangler.toml` має `triggers.crons == ['17 3 * * *']` і `vars.RETENTION_MONTHS == '24'`.

- [ ] **Step 6: SPEC і traceability**

У вимогу WAITLIST-001 додається речення про щоденне видалення (`RETENTION_MONTHS`, хибне значення нічого не видаляє) і сценарій `WAITLIST-001-S09` з якорем `waitlist-001-s09`. Номери S07 і S08 лишаються вільними для плану периферії. Traceability: `WAITLIST-001-S09` → `tests/test_waitlist_worker.py::test_s09_old_rows_are_purged_daily`.

- [ ] **Step 7: Run checks**

Run: `PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/check_docs.py` → Expected: узгоджені.
Run: `.venv/Scripts/python.exe -m pytest -p no:cacheprovider --basetemp=C:/tmp/wl-t2 tests/test_waitlist_worker.py -q` → Expected: 9 passed.

- [ ] **Step 8: Commit**

```bash
git add workers/waitlist tests/test_waitlist_worker.py SPEC.MD docs/verification/traceability.json
git commit -m "feat(waitlist): purge rows older than the retention period daily (WAITLIST-001-S09)"
```

---

### Task 3: Перевірка й журнал

**Files:**
- Modify: `docs/STATUS.md` (через `verify.py`), `docs/superpowers/plans/2026-10-20-remediation-progress.md`

- [ ] **Step 1: Повний pytest**

Run (у фоні): `.venv/Scripts/python.exe -m pytest -p no:cacheprovider --basetemp=C:/tmp/wl-full -q > <scratchpad>/pytest-full.log`
Expected: 0 failed (зараз на `main` 3491 passed, 1 skipped; додається 9).

- [ ] **Step 2: `verify.py` в окремому worktree `C:\tmp\sp-verify`**

Процедура з AGENTS/журналу: `git worktree add --detach C:/tmp/sp-verify HEAD`, перехід `.venv` (`mklink /J`), запуск `scripts/verify.py` у фоні, копіювання `docs/STATUS.md` назад, прибирання (`rmdir` переходу, `git worktree remove --force`).
Expected: `failed 0`; дата й коміт у `docs/STATUS.md`.

- [ ] **Step 3: Запис у журнал**

Розділ `### 16.11.2026 — Store, специфікація 3: список очікування, ядро`:
- специфікація й план (PR);
- що зроблено за задачами;
- рішення виконавця (`Ruling:` з ledger);
- результат `verify.py`;
- що лишається плану периферії.

- [ ] **Step 4: Commit**

```bash
git add docs/STATUS.md docs/superpowers/plans/2026-10-20-remediation-progress.md
git commit -m "docs(status): verify.py on the waitlist Worker core"
```
