# Підвал редактора для Store — план ядра

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** серверна основа зміни: ліміт проходів редактури з налаштувань редактора, підсумок прози за весь твір і полегшена статистика, а також одна функція «це видання Store» для інтерфейсу.

**Architecture:** `RoleSettings.edit_pass_limit` — нове поле ролі; `RunRequest.edit_pass_limit` стає необов'язковим і заповнюється з налаштувань однією функцією перед перевіркою готовності й перед створенням запуску. `scene_statistics` додає `story_totals` і пропускає важкі розділи за `details=False`. Інтерфейс отримує `isStoreEdition()` поверх наявного `appInfo()`. Видимі зміни підвалу — у плані периферії (пишеться після рев'ю ядра).

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, pytest; JS-модулі без збирача, Node-тести в `tests/web/js`.

**Spec:** `docs/superpowers/specs/2026-11/2026-11-19-store-footer-design.md`

## Global Constraints

- `edit_pass_limit`: ціле 1–10, типово 5; старі збережені налаштування ролі без поля читаються як 5.
- Збережений запит запуску (`runs.request_json`) завжди містить число в `edit_pass_limit`.
- `story_totals` рахує лише активні сцени; сцена без прози — 0 слів, без цілі — 0.
- Приховування в Store — лише інтерфейс; сервер у Store приймає ті самі запити, що й раніше.
- Мова повідомлень користувачу — українська через наявну локалізацію; англійська пара обов'язкова для нових рядків i18n.
- Тести не викликають реальних моделей і не чіпають теки даних власника.

## Review Focus

1. Запит MCP `start_run(action='edit')` (режим `stage`, без ліміту) — має працювати як раніше, ліміт однопрохідного етапу не впливає.
2. Повторний `POST /api/runs` з тим самим `request_id` і без ліміту після зміни налаштувань — порівняння `existing.request != request` не має давати хибний конфлікт для ідентичного запиту, зробленого до зміни налаштувань (рішення: порівнювати вже заповнений запит; зміна налаштувань між повторами — це інший запит, конфлікт допустимий).
3. Твір без збереженої ролі редактора (лише writer) — заповнення дає 5, а не помилку.
4. Статистика для сцени в архіві чи твору з архівними сценами — архівні не входять у `story_totals`.
5. `details=false` разом з `stage=…` — `stage` ігнорується без 422 (валідний `stage` усе ще перевіряється).

---

### Task 1: Ліміт проходів редактури з налаштувань редактора

**Files:**
- Modify: `src/storygen/providers/models.py` (`RoleSettings`)
- Modify: `src/storygen/run_models.py:21` (`RunRequest.edit_pass_limit`)
- Create: `src/storygen/generation/edit_pass.py`
- Modify: `src/storygen/generation/worker.py` (`enqueue` до перевірки `request_id`; `readiness` перед `preview`)
- Modify: `src/storygen/generation/readiness.py` (`preview` на вході)
- Modify: `src/storygen/mcp/bridge.py:53` (`EDITOR_FIELDS`) і опис `update_settings`
- Test: `tests/generation/test_edit_pass_settings.py` (новий), `tests/mcp/` — наявний тест полів редактора, якщо є

**Interfaces:**
- Produces: `RoleSettings.edit_pass_limit: int = Field(default=5, ge=1, le=10)`; `RunRequest.edit_pass_limit: int | None = Field(default=None, ge=1, le=10, strict=True)`; `edit_pass.resolve_edit_pass_limit(repo, request: RunRequest) -> RunRequest` — повертає той самий об'єкт, якщо ліміт уже число, інакше `request.model_copy(update={'edit_pass_limit': N})`, де N — `edit_pass_limit` ролі `editor` твору (`authoring.blueprints.get_role_settings`), або 5 без ролі редактора.

- [ ] **Step 1: Write the failing tests** (`tests/generation/test_edit_pass_settings.py`, маркер `@pytest.mark.req('EDIT-LOOP')`)

```python
def test_role_settings_default_and_bounds():
    assert RoleSettings(provider=ProviderSettings()).edit_pass_limit == 5
    with pytest.raises(ValidationError): RoleSettings(provider=ProviderSettings(), edit_pass_limit=11)

def test_old_editor_settings_read_as_five(repo_with_story):  # роль editor збережена без поля
    assert get_role_settings(repo, story.id)['editor'].edit_pass_limit == 5

def test_request_without_limit_takes_editor_setting(repo_with_story):  # editor.edit_pass_limit=2
    resolved = resolve_edit_pass_limit(repo, RunRequest(story_id=story.id, scene_id=scene.id, mode='edit_loop'))
    assert resolved.edit_pass_limit == 2

def test_explicit_limit_wins(...):  # edit_pass_limit=7 в запиті, 2 в налаштуваннях
    assert resolve_edit_pass_limit(repo, request).edit_pass_limit == 7

def test_no_editor_role_gives_five(...):
    assert resolve_edit_pass_limit(repo, request).edit_pass_limit == 5

def test_enqueued_run_stores_the_number(...):  # coordinator.enqueue без ліміту, editor=3
    assert repo.get_run(run.id).request.edit_pass_limit == 3

def test_scene_readiness_uses_the_setting(...):  # coordinator.readiness(..., operation='scene'), editor=2
    op = coordinator.readiness(story.id, scene.id, operation='scene')['operations']['scene']
    assert op['edit_pass_limit'] == 2
```

Фікстуру твору зі сценою й ролями взяти з наявних тестів `tests/generation/test_editor_loop.py` / `test_readiness_single_view.py`.

- [ ] **Step 2: Run to see them fail**

Run: `PYTHONUTF8=1 .venv/Scripts/python.exe -m pytest -q tests/generation/test_edit_pass_settings.py`
Expected: FAIL (`edit_pass_limit` немає в `RoleSettings`, модуля `edit_pass` немає).

- [ ] **Step 3: Implement** поля й `resolve_edit_pass_limit`; виклик у `Coordinator.enqueue` першим рядком після перевірки довжини `request_id` (до пошуку наявного запуску) і в `Coordinator.readiness` для кожного побудованого `request` перед `preview`; у `readiness.preview` — теж на вході, для запитів, що приходять іншими шляхами (`pending_preview` читає збережений запуск, там уже число). `EDITOR_FIELDS = ('edit_mode', 'edit_review', 'edit_pass_limit')`, опис інструмента `update_settings` згадує нове поле.

- [ ] **Step 4: Run the new tests and the affected suites**

Run: `PYTHONUTF8=1 .venv/Scripts/python.exe -m pytest -q tests/generation tests/mcp tests/web/test_runs.py tests/web/test_bridge_run_routes.py`
Expected: PASS. Наявні тести з явним `edit_pass_limit` у запиті не змінюються.

- [ ] **Step 4b: SPEC** — EDIT-LOOP (ліміт з налаштувань редактора, якщо запит без нього), опис налаштувань ролі й MCP `update_settings`; traceability: нові тести до відповідних Scenario; `scripts/check_docs.py` без помилок.

- [ ] **Step 5: Commit** — `feat(runs): edit pass limit comes from the editor settings when a request has none`

### Task 2: Підсумок прози за весь твір і статистика без розбору контексту

**Files:**
- Modify: `src/storygen/application/statistics.py` (`scene_statistics`)
- Modify: маршрут `GET /api/scenes/{scene_id}/statistics` (файл знайти за `statistics?stage` у `src/storygen/web/routes_*.py`)
- Test: `tests/web/test_scene_statistics_api.py`

**Interfaces:**
- Produces: `scene_statistics(repo, scene_id, stage, editor_source_head=None, editor_source_version_id=None, *, details=True) -> dict`; відповідь завжди має `story_totals: {'prose_words': int, 'target_words': int, 'scenes': int}`; за `details=False` у відповіді немає ключів `memory`, `context`, `last_usage`. Параметр запиту `details: bool = True`.

- [ ] **Step 1: Write the failing tests** (маркер `@pytest.mark.req('R18-STATS')`)

```python
def test_story_totals_sum_active_scenes(tmp_path):
    # три сцени: проза 3 слова + ціль 10; без прози + ціль 5; проза 2 слова + ціль 0; четверта в кошику з прозою
    body = client.get(f'/api/scenes/{s1.id}/statistics?stage=draft').json()
    assert body['story_totals'] == {'prose_words': 5, 'target_words': 15, 'scenes': 3}

def test_details_false_skips_memory_context_and_usage(tmp_path):
    body = client.get(f'/api/scenes/{s1.id}/statistics?stage=draft&details=false').json()
    assert 'memory' not in body and 'context' not in body and 'last_usage' not in body
    assert body['materials'] and body['story_totals']
```

Наявний `test_statistics_get_has_no_writes_or_dispatch` доповнити запитом із `details=false`: так само без записів і викликів.

- [ ] **Step 2: Run to see them fail**

Run: `PYTHONUTF8=1 .venv/Scripts/python.exe -m pytest -q tests/web/test_scene_statistics_api.py`
Expected: FAIL (`story_totals` відсутній; `details` ігнорується).

- [ ] **Step 3: Implement** `story_totals` (слова голови прози через `text_statistics` для кожної активної сцени з `repo.list_scenes(story_id)`, `target_words or 0`) і пропуск обчислень `memory`/`context`/`last_usage` за `details=False`.

- [ ] **Step 4: Run**

Run: `PYTHONUTF8=1 .venv/Scripts/python.exe -m pytest -q tests/web/test_scene_statistics_api.py tests/web/test_scene_statistics_ui.py`
Expected: PASS.

- [ ] **Step 4b: SPEC** — R18-STATS: `story_totals`, параметр `details`; traceability для нових тестів; `scripts/check_docs.py` без помилок.

- [ ] **Step 5: Commit** — `feat(statistics): whole-story prose totals and a light response without context details`

### Task 3: `isStoreEdition()` для інтерфейсу

**Files:**
- Modify: `src/storygen/web/static/app-info.js`
- Test: `tests/web/js/app-info-edition.mjs` (новий) + запуск через наявний шаблон Node-тестів у pytest (`tests/web/test_edit_pass_limit.py` показує, як шукати `node`)

**Interfaces:**
- Consumes: `appInfo(): Promise<{edition, long_prose, …}>` з `app-info.js`.
- Produces: `export async function isStoreEdition(): Promise<boolean>` — `true` лише для `edition === 'store'`; помилка `appInfo()` → `false` (повне видання як безпечний типовий вигляд, бо нічого не ховається).

- [ ] **Step 1: Write the failing test** — Node-модуль підміняє `fetch` для `/api/app-info`: `{edition:'store'}` → `true`; `{edition:'full'}` → `false`; відмова `fetch` → `false`.
- [ ] **Step 2: Run** `PYTHONUTF8=1 .venv/Scripts/python.exe -m pytest -q tests/web/test_app_info_edition.py` — Expected: FAIL (`isStoreEdition` немає).
- [ ] **Step 3: Implement** `isStoreEdition` в `app-info.js`.
- [ ] **Step 4: Run** той самий тест — Expected: PASS.
- [ ] **Step 5: Commit** — `feat(ui): isStoreEdition helper on top of app info`

---

Після трьох задач — рев'ю ядра цілком; план периферії (підвал у Store, рядок прози, «Текст, що пише модель», історія Store, «Взяти як прозу» / «Редагувати», поле ліміту в налаштуваннях і прибирання його з підвалу, «Видалити сцену», SPEC, traceability, сайт) пишеться на основі ядра як воно є.
