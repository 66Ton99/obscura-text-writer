# Скіли Obscura для Claude — план основи (PR 1)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Плагін `obscura` у репозиторії: каркас, спільні правила, скіли `start-story` і `draft-scene` (обидві гілки), вимір розподілу моделей, структурні тести, ізольований стенд для прогонів, Requirement `CLAUDE-SKILLS` у SPEC.MD з traceability S01–S06.

**Architecture:** Скіли — Markdown-файли плагіна Claude Code в `integrations/claude/obscura/`. Сервер не змінюється. Структурні тести (pytest) стежать за JSON плагіна, полями frontmatter і назвами MCP-інструментів. Поведінку перевіряють прогони `claude -p` на ізольованому тестовому сервері: окрема тека даних у `C:/tmp`, `--strict-mcp-config`, `--plugin-dir`. Стенд — один модуль `scripts/skills_stand.py`, ним користуються і вимір, і сценарії.

**Tech Stack:** Markdown + YAML frontmatter, JSON, pytest, Claude Code CLI 2.1.317 (`-p`, `--plugin-dir`, `--mcp-config`, `--strict-mcp-config`, `--output-format stream-json`, `--model`, `--max-budget-usd`).

**Spec:** `docs/superpowers/specs/2026-11/2026-11-17-claude-skills-plugin-design.md` (затверджено 2026-11-17), §1–§6 і §8 п. 1.

**Відхилення від спеки (рішення плану):** спека §6 відносить прогін S06 до PR 2, але `draft-scene` з гілкою «obscura» входить у PR 1. Тож S06 проганяється тут, разом зі скілом, як того вимагає правило «PR, що додає скіл, проганяє його сценарій». Ціна помилки — один зайвий прогін.

## Global Constraints

- Тека плагіна: `integrations/claude/` — маркетплейс `obscura` (`.claude-plugin/marketplace.json`), плагін `obscura` (`obscura/.claude-plugin/plugin.json`). Встановлення: `claude plugin install obscura@obscura`.
- Frontmatter SKILL.md — лише переносні поля: `name`, `description`, `license`, `compatibility`, `metadata`, `allowed-tools`. Ні `model`, ні `effort`, ні `context`, ні `agent`.
- Плагін не містить `.mcp.json` і `mcpServers`.
- Тексти скілів англійською. `description` містить фрази наміру українською й англійською. Відповіді автору — його мовою.
- Інструменти MCP у текстах скілів пишуться як `` `назва` `` або `mcp__obscura__назва`, лише з набору `storygen.mcp.bridge.TOOLS` (26).
- Спільні правила — `obscura/shared/rules.md`. Кожен SKILL.md посилається на нього через `${CLAUDE_PLUGIN_ROOT}/shared/rules.md`.
- Прогони `claude -p` іде лише проти тестового сервера: тека даних `C:/tmp/<назва>`, вільний порт, `--strict-mcp-config`. Ніколи проти `obscura` власника (порт 8770) і ніколи з його `~/.claude.json` MCP.
- Кожен прогін має `--max-budget-usd` (вимір 1.00, сценарій 2.00).
- Документація українською; маркери OpenSpec англійською.
- Гейт: `PYTHONIOENCODING=utf-8 python scripts/check_docs.py && python -m pytest -q`. Фактичний запуск записує `python scripts/verify.py` у `docs/STATUS.md` з detached worktree у `C:/tmp`. **Не запускати `verify.py --help`.**
- Python: `C:\Projects\text-generator\.venv\Scripts\python.exe`.

## Review Focus

1. **Скіл називає інструмент, якого немає або який перейменовано** (наприклад, `get_storyy` чи старе `upload_cover` після перейменування). S03 має впасти. Тест: задача 1, `test_unknown_tool_name_is_reported`.
2. **У frontmatter з'явилося `model:`.** claude.ai відхилить пакет. S02 має впасти. Тест: задача 1, `test_claude_code_only_field_is_reported`.
3. **Стенд випадково говорить із сервером власника.** Конфіг MCP стенда містить лише `obscura` із `--url` тестового порту, а команда містить `--strict-mcp-config`. Тест: задача 2, `test_claude_command_is_isolated`.
4. **Редактор у режимі `patches` у гілці «chat»** — скіл відповідає за `result_format`, а не прозою. Перевірка: сценарій S05 запускається і з `edit_mode=patches` (задача 6).
5. **Режим «obscura» без налаштованих ролей** — скіл не викликає `start_run(confirm=true)` і пропонує налаштувати моделі. Перевірка: сценарій S06 (задача 6).

---

### Task 1: Каркас плагіна й структурні тести (S01–S03)

**Files:**
- Create: `integrations/claude/.claude-plugin/marketplace.json`
- Create: `integrations/claude/obscura/.claude-plugin/plugin.json`
- Create: `integrations/claude/obscura/shared/rules.md`
- Create: `integrations/claude/obscura/skills/start-story/SKILL.md` (каркас: frontmatter + посилання на rules; зміст — задача 3)
- Create: `integrations/claude/obscura/skills/draft-scene/SKILL.md` (каркас; зміст — задача 4)
- Create: `tests/integrations/test_claude_plugin.py`

**Interfaces:**
- Produces: `PLUGIN = ROOT/'integrations/claude/obscura'`; у тесті функції `skill_files(plugin) -> list[Path]`, `frontmatter(path) -> dict`, `tool_mentions(text) -> set[str]`, `problems(plugin) -> list[str]` — їх викликають тести на справжньому плагіні й на копії з підкинутою помилкою в `tmp_path`.
- Consumes: `storygen.mcp.bridge.TOOLS`.

- [ ] **Step 1: Написати тести**

```python
@pytest.mark.req('CLAUDE-SKILLS')
def test_marketplace_and_plugin_are_valid():
    market = json.loads((ROOT/'integrations/claude/.claude-plugin/marketplace.json').read_text(encoding='utf-8'))
    assert market['name'] == 'obscura'
    assert [p['name'] for p in market['plugins']] == ['obscura'] and market['plugins'][0]['source'] == './obscura'
    plugin = json.loads((PLUGIN/'.claude-plugin/plugin.json').read_text(encoding='utf-8'))
    assert plugin['name'] == 'obscura' and plugin['version'] and plugin['description']
    assert not (PLUGIN/'.mcp.json').exists() and 'mcpServers' not in plugin

@pytest.mark.req('CLAUDE-SKILLS')
def test_real_plugin_has_no_problems():
    assert {p.parent.name for p in skill_files(PLUGIN)} >= {'start-story', 'draft-scene'}
    assert problems(PLUGIN) == []

@pytest.mark.req('CLAUDE-SKILLS')
def test_claude_code_only_field_is_reported(tmp_path):
    copy = copy_plugin(tmp_path); add_frontmatter(copy/'skills/start-story/SKILL.md', 'model: opus')
    assert any('start-story' in p and 'model' in p for p in problems(copy))

@pytest.mark.req('CLAUDE-SKILLS')
def test_unknown_tool_name_is_reported(tmp_path):
    copy = copy_plugin(tmp_path); append(copy/'skills/draft-scene/SKILL.md', 'Call `get_storyy` and `mcp__obscura__save_drafts`.')
    found = problems(copy)
    assert any('get_storyy' in p for p in found) and any('save_drafts' in p for p in found)
```

`problems()` повертає рядок на кожну проблему:
- немає `name` чи `description`, або `name` ≠ назва теки;
- поле frontmatter поза переносним набором;
- `${CLAUDE_PLUGIN_ROOT}/shared/rules.md` не згадано;
- згадка інструмента поза `TOOLS`.

`tool_mentions(text)` бере `mcp__obscura__(\w+)` і backtick-токени `` `([a-z]+(?:_[a-z]+)+)` `` з префіксом зі списку `get_ save_ create_ update_ import_ add_ list_ start_ apply_ generate_ upload_ export_ open_ next_`.

- [ ] **Step 2: Запустити — FAIL** (`FileNotFoundError` на marketplace.json)

Run: `.venv\Scripts\python.exe -m pytest -q tests/integrations/test_claude_plugin.py`

- [ ] **Step 3: Створити файли каркаса**

- `marketplace.json`: `{"name":"obscura","owner":{"name":"Obscura"},"plugins":[{"name":"obscura","source":"./obscura","description":"…"}]}`.
- `plugin.json`: `name`, `version` `"0.1.0"`, `description`.
- `rules.md`: §2 спеки англійською:
  - мова автора;
  - одне питання через `AskUserQuestion`, а без нього — одне питання текстом із нумерованими варіантами;
  - згода перед записом;
  - позначення «my decision»;
  - прогрес;
  - перевірка сервера через `list_stories` і пояснення, якщо інструментів немає;
  - «409 → read again»;
  - затвердження прози автором.
- Два SKILL.md-каркаси з `name`, `description` (тимчасовий) і рядком «Read `${CLAUDE_PLUGIN_ROOT}/shared/rules.md` first».

- [ ] **Step 4: Запустити — PASS** (4 passed)

- [ ] **Step 5: Commit** `feat(skills): obscura plugin skeleton and structural checks`

---

### Task 2: Ізольований стенд для прогонів `claude -p`

**Files:**
- Create: `scripts/skills_stand.py`
- Test: `tests/integrations/test_skills_stand.py`

**Interfaces:**
- Produces:
  - `start_stand(work: Path) -> Stand` (контекстний менеджер; `Stand.port`, `Stand.base`, `Stand.data`, `Stand.mcp_config: Path`) — сервер `storygen.server --data-dir work/data --port <вільний> --env-file work/empty.env` без `*_API_KEY` у середовищі (як `capture_screenshots.server_env`);
  - `write_mcp_config(path, port) -> Path` — `{"mcpServers":{"obscura":{"command":<venv python>,"args":["-m","storygen.mcp.bridge","--url","http://127.0.0.1:<port>"]}}}`;
  - `claude_command(prompt, *, mcp_config, plugin_dir, model, budget_usd) -> list[str]` — `claude -p <prompt> --plugin-dir <plugin_dir> --mcp-config <mcp_config> --strict-mcp-config --output-format stream-json --verbose --model <model> --max-budget-usd <budget> --permission-mode bypassPermissions`;
  - `run_claude(cmd, out: Path) -> Result` — пише stream-json у `out`, повертає `Result(tool_calls: list[tuple[str, dict]], cost_usd: float | None, usage: dict, text: str)`;
  - `tool_calls(stream_lines) -> list[tuple[str, dict]]` — назви `tool_use` без префікса `mcp__obscura__`.
- Consumes: `capture_screenshots.seed`, `free_port`, `ensure_port_free`, `wait_for`, `server_command`, `server_env`.

- [ ] **Step 1: Написати тести**

```python
def test_claude_command_is_isolated(tmp_path):
    cfg = write_mcp_config(tmp_path/'mcp.json', 9123)
    data = json.loads(cfg.read_text(encoding='utf-8'))
    assert list(data['mcpServers']) == ['obscura']
    assert data['mcpServers']['obscura']['args'][-2:] == ['--url', 'http://127.0.0.1:9123']
    cmd = claude_command('hi', mcp_config=cfg, plugin_dir=tmp_path, model='sonnet', budget_usd=1.0)
    assert '--strict-mcp-config' in cmd and cmd[cmd.index('--mcp-config')+1] == str(cfg)
    assert cmd[cmd.index('--max-budget-usd')+1] == '1.0'

def test_tool_calls_and_cost_from_stream_json():
    lines = [json.dumps({'type':'assistant','message':{'content':[{'type':'tool_use','name':'mcp__obscura__get_story','input':{'story_id':'s'}}]}}),
             json.dumps({'type':'result','total_cost_usd':0.12,'usage':{'input_tokens':10,'output_tokens':5},'result':'ok'})]
    assert tool_calls(lines) == [('get_story', {'story_id':'s'})]
    assert parse_result(lines).cost_usd == 0.12
```

- [ ] **Step 2: FAIL** (`ModuleNotFoundError: skills_stand`)

- [ ] **Step 3: Реалізувати `scripts/skills_stand.py`**

Сервер — як у `capture_screenshots.main`: `Popen`, `wait_for`, а в `finally` `terminate` → `wait(10)` → `kill`. `run_claude` бере `claude` з PATH. Модуль має `main()` з підкомандами `serve` (лише підняти стенд і надрукувати порт та шлях конфігу) і `run --prompt-file … --model … --budget …`.

- [ ] **Step 4: PASS**, потім руками: `.venv\Scripts\python.exe scripts/skills_stand.py serve --work C:/tmp/stand1`. Expected: сервер відповідає за надрукованою адресою, а Ctrl+C його зупиняє.

- [ ] **Step 5: Commit** `test(skills): isolated stand for claude -p runs`

---

### Task 3: Скіл `start-story`

**Files:**
- Modify: `integrations/claude/obscura/skills/start-story/SKILL.md`
- Create: `integrations/claude/obscura/skills/start-story/references/interview.md`

**Interfaces:**
- Consumes: `rules.md` (задача 1); інструменти `list_stories`, `create_story`, `get_templates`, `import_plan_and_characters`, `get_story`.

- [ ] **Step 1: `description`** — одне речення про задачу і фрази наміру обома мовами, наприклад: «Use when the author wants to write a story or book, has an idea, lore or a plan, or does not know where to start ("хочу написати оповідання", "не знаю, з чого почати", "write a story about…")».

- [ ] **Step 2: Тіло** за §3.1 спеки:
  - порядок воріт: герої → ідея/план/фінал → обсяг → назва → додаткові питання;
  - «лише те, чого бракує»;
  - пропозиція `series-bible` за наявності лору чи циклу (скіл з'явиться в PR 2, тож формулювання: «suggest a series bible first; if the `series-bible` skill is available, use it»);
  - модель і advisor (§3.1);
  - підсумок → згода → виклики → перевірка `writing_mode` → для режиму «obscura» без ролей порада про налаштування моделей.

- [ ] **Step 3: `references/interview.md`** містить:
  - мінімум картки героя з прикладами карток («Скільки років Михайлові?» / «неважливо, дорослий»);
  - схему структури;
  - типову сітку 7×1000 і варіанти об'єднання;
  - значення за замовчуванням для точки зору, місця й часу, рейтингу, мови.

- [ ] **Step 4: `pytest -q tests/integrations/test_claude_plugin.py`** — PASS (S03 перевіряє назви інструментів).

- [ ] **Step 5: Commit** `feat(skills): start-story`

---

### Task 4: Скіл `draft-scene`

**Files:**
- Modify: `integrations/claude/obscura/skills/draft-scene/SKILL.md`
- Create: `.../draft-scene/references/chat-pipeline.md`, `obscura-runs.md`, `continuity.md`

**Interfaces:**
- Consumes: `get_story`, `get_scene_context`, `get_scene_text`, `save_draft`, `get_stage_task`, `save_stage_result`, `start_run`, `get_run`, `next_steps`.
- Produces: таблиця «Model routing» у `chat-pipeline.md`. Рядки brief і memory до задачі 5 мають значення «main session (pending measurement)», а задача 5 їх замінює.

- [ ] **Step 1: SKILL.md**
  - `description` з фразами «пиши далі», «напиши сцену», «write the next scene»;
  - перший крок — `get_story` → `writing_mode`;
  - короткі гілки з посиланнями на references;
  - рядок прогресу після кожного етапу;
  - нагадування про затвердження прози.

- [ ] **Step 2: `chat-pipeline.md`** за §3.3 «chat»:
  - чотири кроки;
  - відповідь редактури строго за `result_format` (`prose` | `patches` | `diff`);
  - зупинка на `needs_review` і на проханні підтвердити пам'ять;
  - пам'ять частинами (`offset`, `max_chars` ≤ 20000);
  - пастки;
  - таблиця маршрутизації: draft/edit — субагент `opus`, якщо модель сесії слабша, а в Desktop Chat — порада;
  - бриф субагента: `scene_id`, вимоги до стилю, рішення автора, очікуваний результат, без питань автору.

- [ ] **Step 3: `obscura-runs.md`** за §3.3 «obscura»:
  - чотири запуски;
  - картка «Покроково / Усю сцену»;
  - перегляд без `confirm` → згода → `confirm=true`;
  - `get_run` з рядком на кожну зміну стану;
  - зупинки;
  - неготові ролі → порада налаштувати моделі.

- [ ] **Step 4: `continuity.md`** — чеклист перед сценою і перевірка мови на редактурі (§3.3).

- [ ] **Step 5: структурні тести — PASS. Commit** `feat(skills): draft-scene in chat and obscura modes`

---

### Task 5: Вимір розподілу моделей (§4 спеки)

**Files:**
- Create: `integrations/claude/tools/measure_models.py` (використовує `skills_stand`)
- Create: `integrations/claude/tools/fixture/` — нейтральний план, персонажі й еталон `expected.json`
- Modify: `integrations/claude/obscura/skills/draft-scene/references/chat-pipeline.md` (таблиця маршрутизації)
- Modify: `docs/superpowers/plans/2026-10-20-remediation-progress.md` (числа й рішення)

**Interfaces:**
- Consumes: `start_stand`, `claude_command`, `run_claude` (задача 2).
- Produces: `measure_models.py --variant {A,B,C} --runs 3 --work C:/tmp/<назва>` → JSON-рядок на прогін: `variant`, `run`, `cost_usd`, `input_tokens`, `output_tokens`, `refusals`, а також шляхи до збережених brief і memory.

- [ ] **Step 1: Фікстура й еталон до прогонів.**
  - Нейтральна сцена (≈1000 слів) з планом і двома персонажами в режимі «chat».
  - `expected.json`:
    - `brief.required` — `objective`, ключові `beats`, `introduced`;
    - `memory.required` — 8–15 фактів: хто, що, де, зміни стану, предмети.
  - Еталон закомітити окремим комітом **до** першого прогону: `test(skills): measurement fixture and expected facts`.

- [ ] **Step 2: Варіанти.** Стенд сам доводить сцену до потрібного етапу через MCP-виклики скрипта, а не моделі:
  - для brief — імпортований план;
  - для memory — brief, чернетка й проза з фікстури (edit-результат `prose`).

  Кожен варіант — окремі сесії `claude -p` на brief і на memory:
  - **A** — `--model opus`; у промпт memory додано текст сцени як «текст, який ти щойно написав». Це імітує основну сесію, що тримає сцену в контексті;
  - **B** — `--model sonnet`, лише матеріал із `get_stage_task`;
  - **C** — `--model haiku`, так само.

  Вартість і токени кожної сесії беруться з `result` stream-json.

- [ ] **Step 3: Прогнати 3×A, 3×B, 3×C.** Expected: 9 рядків JSON, сумарна вартість ≤ $9 (`--max-budget-usd 1.00` на прогін).

- [ ] **Step 4: Оцінити за еталоном** — вручну, у таблиці журналу: пропуски, вигадки, суперечності, відмови схеми. Правило вибору — §4 спеки дослівно. Якщо A не проходить правило, вимір зупиняється, а вибір виноситься до власника: це четверта підстава зупинки (план зламаний).

- [ ] **Step 5: Оновити таблицю маршрутизації** в `chat-pipeline.md`: варіант-переможець для brief і memory, дата, посилання на запис у журналі.

- [ ] **Step 6: Commit** `feat(skills): model routing from the stage measurement`

---

### Task 6: Сценарії S04–S06 і їх прогін

**Files:**
- Create: `integrations/claude/obscura/evals/start-story.json`, `draft-scene.json` (схема `skill-creator` `evals.json`: `skill_name`, `evals[{id, prompt, expected_output, assertions}]`)
- Create: `integrations/claude/tools/run_scenarios.py` (стенд + `claude -p` + друк послідовності інструментів)
- Modify: `docs/verification/manual.md` (розділ `#claude-skills`)
- Modify: журнал виконання

**Interfaces:**
- Consumes: `skills_stand` (задача 2).

- [ ] **Step 1: Сценарії**

| ID | Промпт | Твердження (за послідовністю інструментів і текстом) |
|---|---|---|
| S04-a | «Хочу написати оповідання про друзів, не знаю, з чого почати» | `create_story` і `import_plan_and_characters` відсутні; є питання (текст або `AskUserQuestion`) |
| S04-b | Повний запит: герої з віком, рисами, заняттям і манерою мовлення, план, фінал, назва, обсяг, явна згода «створюй» | рівно один `create_story`, потім `get_templates` → `import_plan_and_characters` → `get_story`; не більше одного питання |
| S05-a | Стенд: твір «chat» з імпортованим планом. «Напиши першу сцену» | порядок `get_stage_task(brief)` → `save_stage_result` → `get_scene_context` → `save_draft` → `get_stage_task(edit)` → `save_stage_result` → `get_stage_task(memory)` → `save_stage_result`; після кожного етапу рядок прогресу в тексті |
| S05-b | Те саме з `editor.edit_mode=patches` | відповідь edit за `result_format`: `save_stage_result` без помилки формату |
| S06 | Стенд: твір «obscura» без ролей. «Напиши сцену 1» | жодного `start_run` з `confirm=true`; є пропозиція налаштувати моделі |

Стенд готує стан через HTTP тестового сервера. Для S05-b роль editor ставиться з `edit_mode=patches` і фіктивним провайдером без ключа: виклику моделі не буде.

- [ ] **Step 2: `manual.md#claude-skills`** — процедура:
  - команда `run_scenarios.py --scenario <ID> --work C:/tmp/<назва>`;
  - як читати послідовність;
  - правило провалу (§6 спеки): поведінка → блокує; інфраструктура → повтор із причиною; не повторюється у двох повторах → нестабільність.

- [ ] **Step 3: Прогнати кожен сценарій** (`--model sonnet`, бюджет 2.00). Expected: усі твердження виконані. Провал через поведінку → виправити скіл і прогнати знову.

- [ ] **Step 4: Записати в журнал** дату, коміт, модель, пройдено чи ні, а для провалів — що виправлено.

- [ ] **Step 5: Commit** `test(skills): scenarios S04–S06 and their runs`

---

### Task 7: SPEC.MD, traceability, журнал

**Files:**
- Modify: `SPEC.MD`:
  - пункт змісту;
  - новий Requirement `CLAUDE-SKILLS` з якорем `claude-skills` після STORE-MCP-001, перед WRITING-MODE;
  - речення в MCP-BRIDGE.
- Modify: `docs/verification/traceability.json`
- Modify: `docs/superpowers/plans/2026-10-20-remediation-progress.md`

**Interfaces:**
- Consumes: назви тестів задач 1–2, розділ `manual.md#claude-skills` (задача 6).

- [ ] **Step 1: Requirement `CLAUDE-SKILLS — Скіли Obscura для Claude`.** Технічний текст:
  - розміщення плагіна;
  - переносні поля;
  - без конфігурації MCP;
  - спільні правила;
  - розподіл моделей у тілі скіла;
  - стенд і правило прогонів;
  - інваріант «скіли називають лише інструменти моста»;
  - відомі обмеження: рецептів і решти скілів ще немає (PR 2), результат виміру — одна сцена.

  Сценарії S01–S06 у форматі `<a id="claude-skills-s01"></a>` / `#### Scenario: CLAUDE-SKILLS-S01 — …` / GIVEN/WHEN/THEN. S07–S09 додає PR 2.

- [ ] **Step 2: MCP-BRIDGE.** Після речення про набір інструментів додати: «Перейменування чи видалення інструмента вимагає оновити скіли плагіна `obscura` ([CLAUDE-SKILLS](#claude-skills), S03).»

- [ ] **Step 3: traceability.**
  - S01–S03 → тести задачі 1.
  - S04–S06 → `manual.procedure: docs/verification/manual.md#claude-skills` з `reason` «поведінка моделі недетермінована, перевіряється прогонами `claude -p` на стенді».
  - До S05 і S06 додати `tests/integrations/test_skills_stand.py::test_claude_command_is_isolated` як перевірку ізоляції.

- [ ] **Step 4: `PYTHONIOENCODING=utf-8 python scripts/check_docs.py`** — Expected: «… узгоджені».

- [ ] **Step 5: Журнал** — запис R-35, PR 1: що зроблено, вимір, прогони, Ruling-рядки виконання.

- [ ] **Step 6: Commit** `docs(spec): CLAUDE-SKILLS requirement and traceability`

---

### Task 8: Гейт, verify, крос-рев'ю, PR

- [ ] **Step 1:** гейт `check_docs.py && pytest -q` — PASS.
- [ ] **Step 2:** `verify.py` з detached worktree `C:/tmp/wgsk` → `docs/STATUS.md` → commit `docs(status): verify.py for the skills core`.
- [ ] **Step 3:** фінальне рев'ю всієї гілки, найсильніша модель.
- [ ] **Step 4:** крос-рев'ю `npx -y @ysilvestrov/detent cross-review --author claude` у фоні; розбір зауважень.
- [ ] **Step 5:** PR на `main`. В описі:
  - марка крос-рев'ю й таблиця рішень;
  - документація: сайт оновлює PR 2 за §8 спеки, бо встановлення для користувачів ще не оголошується; SPEC оновлено.

  Без «Closes #173»: це не останній PR задачі.
- [ ] **Step 6:** оновити основну теку злиттям, без `reset --hard` і `clean`; перевірити ревізію.
