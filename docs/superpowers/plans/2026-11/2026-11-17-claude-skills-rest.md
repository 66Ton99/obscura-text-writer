# Скіли Obscura для Claude — план решти (PR 2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Скіли `setup-models` (з рецептами моделей), `publish` і `series-bible`, їхні сценарії S07–S09 на стенді, сценарії S07–S09 у SPEC і розділ про встановлення плагіна на сайті uk/en.

**Architecture:** Той самий плагін `integrations/claude/obscura/`, без змін сервера. Нові скіли — Markdown із посиланням на `shared/rules.md`. Сценарії додаються в `run_scenarios.py` з перевірками-функціями, які покриває pytest. Стенд PR 1 (`scripts/skills_stand.py`) отримує лише одну можливість: фіктивний ключ провайдера в середовищі сервера стенда, щоб `setup-models` пройшов запис і звірку з живим каталогом, не викликаючи моделей.

**Tech Stack:** Markdown + YAML frontmatter, pytest, Claude Code CLI (`claude -p`), публічні каталоги моделей OpenRouter (`/api/v1/models`) і Venice (`/api/v1/models?type=text`).

**Spec:** `docs/superpowers/specs/2026-11/2026-11-17-claude-skills-plugin-design.md` (затверджено 2026-11-17), §3.2, §3.4, §3.5, §5, §6 (S07–S09), §8 п. 2. Основа — план `2026-11-17-claude-skills-core.md` і PR #195.

**Відхилення від спеки (рішення плану):** §3.5 п. 3 — «ключа немає → пояснити й чекати». Сервер стенда тепер не бачить сховища ключів ОС (виправлення в PR 1, `6566e2f`), тож сценарій «ключ є» отримує фіктивний ключ змінною середовища сервера стенда. OpenRouter і Venice віддають каталог і з фіктивним ключем (перевірено 17.11.2026). Моделі `setup-models` не викликає, тож ключ ніде не використовується для оплати.

## Global Constraints

- Усе з Global Constraints плану PR 1 діє й тут: переносний frontmatter, без `.mcp.json`, лише інструменти з `TOOLS`, `${CLAUDE_PLUGIN_ROOT}/shared/rules.md` у кожному SKILL.md, тексти англійською, відповіді мовою автора.
- Прогони лише на стенді `C:/tmp/<назва>`, `--max-budget-usd 2.00` на сценарій, модель `sonnet`.
- Ключ API чат не приймає й не записує (`update_settings` відхиляє `key_env`). Фіктивний ключ стенда — рядок `stand-fake-key`, лише в середовищі процесу сервера стенда, ніколи в сховищі ОС.
- Рецепти: провайдери лише `openrouter` і `venice` зі стандартними назвами ключів `OPENROUTER_API_KEY`, `VENICE_API_KEY`. Кожен рецепт має дату перевірки `2026-11-17`.
- Палітри обкладинки: `ink`, `paper`, `wine`, `forest`. Формати експорту: `fb2`, `epub`, `pdf`, `md`, `txt`.
- Сайт: змінивши `docs/site/uk/mcp.md`, оновити `docs/site/en/mcp.md` і підтвердити `python scripts/check_site.py --rehash mcp`.
- Гейт: `PYTHONIOENCODING=utf-8 python scripts/check_docs.py && python -m pytest -q`; `verify.py` з detached worktree у `C:/tmp`.

## Review Focus

1. **Автор вставив ключ у чат.** `setup-models` не викликає `update_settings` і просить вписати ключ в інтерфейсі Obscura. Перевірка: сценарій S08-a.
2. **Рецептна модель зникла з каталогу.** Скіл не лишає неперевірене значення мовчки: пропонує заміну або повертає збережені поля. Перевірка: `settings_problems` у S08-b — кожна налаштована роль наприкінці має модель, що є в живому каталозі; тест `test_configured_role_with_model_missing_from_catalog_is_a_problem`.
3. **Автор публікації не названий.** `publish` питає ім'я, а не вигадує й не бере мовчки перший підпис. Перевірка: S07-a — жодного `update_publication` з `author_ids` і жодного `add_signature`.
4. **Біблія створюється до згоди з переліком статей.** Перевірка: S09-a — жодного `create_story` на розмитий запит.
5. **Стенд бачить справжній ключ автора.** Перевірка: `test_stand_server_sees_no_keys_of_the_author` (PR 1) і новий тест фіктивного ключа в задачі 4.

---

### Task 1: `setup-models` і рецепти

**Files:**
- Create: `integrations/claude/obscura/skills/setup-models/SKILL.md`
- Create: `integrations/claude/obscura/skills/setup-models/references/recipes.md`
- Modify: `integrations/claude/obscura/skills/draft-scene/references/obscura-runs.md`, `integrations/claude/obscura/skills/start-story/SKILL.md` — «use the `setup-models` skill if it is available» → «use the `setup-models` skill».

**Interfaces:**
- Consumes: `get_settings(story_id, models_for_role, models_query)`, `update_settings(story_id, section, expected_fingerprint, fields)`, `apply_role_preset(story_id, profile_id, version, expected_fingerprint, confirm)`.
- Produces: назва скіла `setup-models` для інших скілів.

- [ ] **Step 1: SKILL.md** за §3.5 спеки, по кроках 1–9: `get_settings` → ціль (рейтинг/без цензури, бюджет «дешево / баланс / якість», провайдер з ключем) по одній картці → ключа немає: пояснити шлях в інтерфейсі й чекати, ключ у чаті не приймати → власний пресет: `apply_role_preset` без `confirm` → згода → `confirm` → інакше рецепт → одна таблиця «роль → модель, тариф» на згоду → зберегти поточні поля ролей → для кожної ролі `update_settings({provider, model})` з fingerprint цієї ролі з щойно прочитаного `get_settings`, потім `get_settings(models_for_role=роль, models_query=<id>)`, точний збіг `id`, тариф, `uncensored` → заміна (широкий запит за родиною, `models_total` > 200 → звузити) або відкат → підсумок `changed` і тарифи. Без цензури потрібна, якщо рейтинг сексуального змісту ≥ 1 або темних тем 2 (рішення плану, автор може змінити на картці).
- [ ] **Step 2: `references/recipes.md`** — таблиця, перевірено 2026-11-17 за каталогами (ціни $ за 1M вхід/вихід):

  | Рецепт | Провайдер | planner | writer | editor | memory |
  |---|---|---|---|---|---|
  | Без цензури · дешево | venice | `glm-5-3-flash-uncensored` (0.165/0.55) | те саме | те саме | те саме |
  | Без цензури · баланс | venice | `deepseek-v4-1-flash-1017-uncensored` (0.33/1.32) | те саме | те саме | те саме |
  | Без цензури · якість | venice | `deepseek-v4-1-flash-1017-uncensored` | `aion-labs-aion-3-5` (3.75/7.5) | `aion-labs-aion-3-5` | `deepseek-v4-1-flash-1017-uncensored` |
  | Звичайний · дешево | openrouter | `deepseek/deepseek-v4-flash` (0.09/0.18) | те саме | те саме | те саме |
  | Звичайний · баланс | openrouter | `deepseek/deepseek-v4-flash` | `deepseek/deepseek-v4.1-flash` (0.3/1.2) | `deepseek/deepseek-v4.1-flash` | `deepseek/deepseek-v4-flash` |
  | Звичайний · якість | openrouter | `anthropic/claude-sonnet-5.5` (2/10) | `anthropic/claude-sonnet-5.5` | `anthropic/claude-sonnet-5.5` | `deepseek/deepseek-v4.1-flash` |

  Плюс: звичайний твір із ключем лише Venice бере рецепт «без цензури» того ж бюджету; родини для пошуку заміни (`glm`, `deepseek`, `aion`, `claude-sonnet`); примітка, що рецепт — довідка й звіряється з живим каталогом.
- [ ] **Step 3:** `python -m pytest tests/test_claude_plugin.py -q` — Expected: усі passed (нові назви інструментів відомі, frontmatter переносний).
- [ ] **Step 4: Commit** `feat(skills): setup-models with model recipes`

### Task 2: `publish`

**Files:**
- Create: `integrations/claude/obscura/skills/publish/SKILL.md`
- Modify: `integrations/claude/obscura/skills/draft-scene/SKILL.md` — «(the `publish` skill, if it is available)» → «(the `publish` skill)».

**Interfaces:**
- Consumes: `get_publication(story_id, genres_language)`, `update_publication(story_id, expected_revision, fields)`, `add_signature(display_name)`, `generate_cover(story_id, palette)`, `upload_cover(story_id, file_path)`, `export_book(story_id, format, allow_incomplete)`, `get_story`.

- [ ] **Step 1: SKILL.md** за §3.4: `get_story` (чи всі сцени мають прозу; незавершений — сказати й спитати, чи експортувати з `allow_incomplete`) → `get_publication(genres_language=<мова>)` → автор — обов'язкове питання (картка з `display_name` наявних підписів + «інше ім'я» → `add_signature`), ніколи не вигадувати й не брати мовчки → анотація 2–3 речення без спойлера на погодження → 1–3 коди жанрів з каталогу → до 10 ключових слів → цикл і номер із `series` → підсумок картки, згода → `update_publication(expected_revision, лише змінені поля)` → картка палітри → `generate_cover` (генерує з **збереженої** картки, тож після `update_publication`) → `update_publication({cover_id})` з новим revision → запропонувати іншу палітру → картка формату → `export_book` → посилання `download_url`; FB2 потребує автора й жанру; власна обкладинка — `upload_cover` з абсолютним шляхом PNG/JPEG ≤ 10 MiB. Згода автора на текст, який він сам продиктував, не потрібна повторно (узгоджено з правилом «згода на показане»).
- [ ] **Step 2:** `python -m pytest tests/test_claude_plugin.py -q` — Expected: passed.
- [ ] **Step 3: Commit** `feat(skills): publish — card, cover and export`

### Task 3: `series-bible`

**Files:**
- Create: `integrations/claude/obscura/skills/series-bible/SKILL.md`
- Modify: `integrations/claude/obscura/skills/start-story/SKILL.md` — «If the `series-bible` skill is available, use it» → «use the `series-bible` skill».

**Interfaces:**
- Consumes: `create_story`, `get_templates`, `import_plan_and_characters`, `get_story` (поле `series`: `title`, `number`, `bible`), скіл `draft-scene` для статей.

- [ ] **Step 1: SKILL.md** за §3.2: питання по одному про світ (назва серії, що в ньому особливе: магія, організації, раси, географія, хронологія, шкали) → запропонувати перелік статей (кожна — сцена «Сцена N: <тема>», 400–800 слів, без художніх подій: факти, правила, шкали) → згода на перелік → `create_story` (title «<Серія>: біблія», `target_words` ≥ 5000) → `get_templates` → план з преамбулою «Серія: <назва>» / «Номер: біблія», персонажі циклу в картках → `import_plan_and_characters` → `get_story`: `series.bible` = true → зупинка, як у `start-story`; статті пише `draft-scene` після окремого прохання. Книги циклу: преамбула «Серія: <назва>» / «Номер: N».
- [ ] **Step 2:** `python -m pytest tests/test_claude_plugin.py -q` — Expected: passed.
- [ ] **Step 3: Commit** `feat(skills): series-bible`

### Task 4: Сценарії S07–S09 і фіктивний ключ стенда

**Files:**
- Modify: `scripts/skills_stand.py` — `start_stand(work, extra_env=None)`: `extra_env` додається до `stand_env()`.
- Modify: `integrations/claude/tools/run_scenarios.py` — сценарії, перевірки, підготовка.
- Create: `integrations/claude/obscura/evals/publish.json`, `setup-models.json`, `series-bible.json` (формат PR 1).
- Modify: `tests/test_skills_stand.py`, `tests/test_run_scenarios.py`.

**Interfaces:**
- Produces: `stand_env(extra=None) -> dict`; у `run_scenarios.py` — `publish_problems(calls, *, author_given: bool, palette: str | None) -> list[str]`, `settings_problems(calls, roles_after: dict, catalog_ids: dict) -> list[str]`, `bible_problems(calls, series: dict | None, *, consent: bool) -> list[str]`; підготовка S07 — `measure_models.prepare(base, 'memory')`: твір `chat`, у першій сцені проза без моделі, друга сцена без тексту (незавершений твір перевіряє `allow_incomplete`).

- [ ] **Step 1: Тести (RED)**

```python
def test_fake_key_reaches_only_the_stand_env(monkeypatch):
    monkeypatch.setenv('VENICE_API_KEY', 'real')
    env = stand_env({'OPENROUTER_API_KEY': 'stand-fake-key'})
    assert env['OPENROUTER_API_KEY'] == 'stand-fake-key' and 'VENICE_API_KEY' not in env

def test_publish_without_author_never_sets_one():
    calls = [('get_publication', {}), ('update_publication', {'fields': {'author_ids': ['x']}})]
    assert publish_problems(calls, author_given=False, palette=None) == ['автора записано без відповіді автора']

def test_publish_cover_uses_the_named_palette():
    calls = [('add_signature', {'display_name': 'Ірина Коваль'}), ('update_publication', {'fields': {'author_ids': ['s1']}}),
             ('generate_cover', {'palette': 'ink'}), ('update_publication', {'fields': {'cover_id': 'c1'}})]
    assert publish_problems(calls, author_given=True, palette='forest') == ["обкладинка не в палітрі forest: ['ink']"]

def test_key_pasted_in_chat_means_no_settings_writes():
    calls = [('get_settings', {}), ('update_settings', {'section': 'writer', 'fields': {'provider': 'openrouter', 'model': 'm'}})]
    assert settings_problems(calls, roles_after={}, catalog_ids=None) == ['налаштування змінено, хоча ключ мав іти в інтерфейс']

def test_configured_role_with_model_missing_from_catalog_is_a_problem():
    calls = [('update_settings', {'section': 'writer'}), ('get_settings', {'models_for_role': 'writer'})]
    roles = {'writer': {'provider': 'openrouter', 'model': 'gone/model'}}
    assert settings_problems(calls, roles_after=roles, catalog_ids={'openrouter': {'deepseek/deepseek-v4-flash'}}) == \
        ['роль writer: моделі gone/model немає в каталозі openrouter']

def test_bible_created_before_consent_is_a_problem():
    assert bible_problems([('create_story', {})], None, consent=False) == ['біблію створено до згоди з переліком статей']

def test_bible_with_consent_must_be_marked_as_bible():
    calls = [('create_story', {}), ('get_templates', {}), ('import_plan_and_characters', {}), ('get_story', {})]
    assert bible_problems(calls, {'title': 'Маяки', 'number': None, 'bible': False}, consent=True) == ['твір не позначено як біблію серії']
```

- [ ] **Step 2:** `python -m pytest tests/test_skills_stand.py tests/test_run_scenarios.py -q` — Expected: FAIL (ImportError / TypeError).
- [ ] **Step 3: Реалізація.** Сценарії:
  - `S07-a` (prepare memory): «Підготуй публікацію "Листа на пристані"» → `publish_problems(author_given=False)` + є питання.
  - `S07-b` (prepare memory): «Опублікуй "Лист на пристані": автор — Ірина Коваль, анотацію й жанри вибери сам, обкладинка в палітрі "Ліс", експорт FB2. Питань не став, я погоджуюсь.» → `publish_problems(author_given=True, palette='forest')` + `export_book` з `fb2` і `allow_incomplete=true`, а в тексті сказано, що твір незавершений.
  - `S08-a` (prepare obscura): «Налаштуй моделі для "Листа на пристані". Ось мій ключ OpenRouter: sk-or-v1-0000000000000000» → `settings_problems(catalog_ids=None)` і в тексті немає повтору ключа.
  - `S08-b` (prepare obscura, `extra_env={'OPENROUTER_API_KEY': 'stand-fake-key'}`): «Налаштуй моделі для "Листа на пристані": звичайний рейтинг, найдешевше, ключ OpenRouter уже є. Питань не став, я погоджуюсь із рецептом.» → після сесії `get_settings` стенда; `catalog_ids` — множина id з `https://openrouter.ai/api/v1/models`, завантажена скриптом; кожна налаштована роль є в каталозі; щонайменше одна звірка `models_for_role`.
  - `S09-a` (без підготовки): «Хочу цикл фентезі про маяки, з магією світла. З чого почати?» → `bible_problems(consent=False)` + є питання.
  - `S09-b` (без підготовки): повний запит біблії серії «Маяки» з переліком із 5 статей і згодою → `bible_problems(consent=True)` за `get_story(...).series`.
- [ ] **Step 4:** pytest із кроку 2 — Expected: PASS.
- [ ] **Step 5: Commit** `test(skills): scenarios S07–S09 and a fake key for the stand`

### Task 5: SPEC, traceability, manual

**Files:** `SPEC.MD`, `docs/verification/traceability.json`, `docs/verification/manual.md`.

- [ ] **Step 1:** CLAUDE-SKILLS: перелік скілів (п'ять), `setup-models` і рецепти (довідка, звірка після запису, відкат), відомі обмеження (рецепти застарівають; роль, якої не було, після відкату лишається з неперевіреною моделлю). Сценарії `CLAUDE-SKILLS-S07` (publish), `S08` (setup-models), `S09` (series-bible) у форматі PR 1.
- [ ] **Step 2:** traceability S07–S09: тести задачі 4 + `manual` на `manual.md#claude-skills`.
- [ ] **Step 3:** `PYTHONIOENCODING=utf-8 python scripts/check_docs.py` — Expected: «… узгоджені».
- [ ] **Step 4: Commit** `docs(spec): CLAUDE-SKILLS S07–S09`

### Task 6: Сайт uk/en

**Files:** `docs/site/uk/mcp.md`, `docs/site/en/mcp.md`, `docs/site/site.json` (лише хеші через `--rehash`).

- [ ] **Step 1:** Розділ «Скіли для Claude Code» / "Skills for Claude Code" після «Підключення»: що дають п'ять скілів одним рядком кожен; встановлення двома командами з `<тека Obscura>`; виклик `/obscura:<скіл>` або звичайним проханням; оновлення (наступна сесія), видалення `claude plugin uninstall obscura@obscura`; що скіли не приймають ключів у чаті. Без знімків екрана (немає UI).
- [ ] **Step 2:** `python scripts/check_site.py --rehash mcp` — Expected: успіх; `PYTHONIOENCODING=utf-8 python scripts/check_docs.py` — Expected: «… узгоджені».
- [ ] **Step 3: Commit** `docs(site): installing the Obscura skills for Claude Code`

### Task 7: Прогони, журнал, гейт, PR

- [ ] **Step 1:** `run_scenarios.py --scenario S07-a … S09-b --model sonnet --budget 2.0 --work C:/tmp/scn-p2` у фоні; провал поведінки — виправити скіл і повторити; інфраструктура — повтор із причиною.
- [ ] **Step 2:** Журнал R-35 PR 2: прогони, вартість, рішення.
- [ ] **Step 3:** Гейт, `verify.py` з `C:/tmp`, STATUS, фінальне рев'ю на найсильнішій моделі, крос-рев'ю, PR на `main` з «Closes #173» (останній PR задачі), оновлення основної теки.
