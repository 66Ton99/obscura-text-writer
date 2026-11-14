# Зразок звучання твору — план реалізації

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** поле «Зразок звучання» у профілі стилю, окрема секція для етапів прози, і зміна лише зразка не робить застарілими завдання сцени й оцінки.

**Architecture:** `StyleProfile.tone_sample` вилучається з JSON стилю (як `ending_goal`) і йде секцією `tone_sample` у draft, rewrite та edit у режимі переписування. Сліпі скоупи `{'brief', 'evaluation'}` не застарівають від зміни лише зразка: у транзакції збереження стилю, у `compare_snapshot` і в перевірці впливу.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, SQLite, vanilla JS, Playwright.

**Spec:** `docs/superpowers/specs/2026-11/2026-11-14-tone-sample-design.md` (затверджено 14.11.2026).

## Global Constraints

- `tone_sample: str = Field(default='', max_length=3000)`; «порожній» — `not tone_sample.strip()`.
- Мітки секції: uk «ЗРАЗОК ЗВУЧАННЯ — НЕ СЮЖЕТ: ПЕРЕЙМИ РИТМ, ЛЕКСИКУ Й БУДОВУ РЕЧЕНЬ; НЕ БЕРИ ПОДІЙ, ІМЕН ЧИ СВІТУ»; en «VOICE SAMPLE — NOT PLOT: TAKE ITS RHYTHM, VOCABULARY AND SENTENCE STRUCTURE; NOT ITS EVENTS, NAMES OR WORLD».
- `SAMPLE_BLIND_SCOPES = {'brief', 'evaluation'}`; версія без `dependency_snapshot` — не сліпа.
- Тексти ролей і контракти промптів не змінюються. Реальних модельних викликів немає.
- Твір без зразка: ті самі запити, відбитки MCP і знімки, що до зміни.

## Review Focus

1. Brief, збережений до зміни (зі знімком), після зміни лише зразка лишається свіжим — у прапорці `stale`, `needs_review` сцени й `compare_snapshot`.
2. Зміна зразка разом з іншим полем стилю робить застарілим усе, як раніше.
3. Чернетка, від якої залежить проза, застаріває, а через неї — пам’ять наступних сцен (як зараз).
4. Перевірка впливу для brief не показує зміни стилю, якщо змінився лише зразок.
5. Відбиток контексту письма MCP твору без зразка той самий, що до зміни.

---

### Task 1: Поле, секція в запитах, оцінювач

**Files:**
- Modify: `src/storygen/generation/models.py`, `src/storygen/generation/context.py`, `src/storygen/generation/context_labels.py`, `src/storygen/evaluation/story_adapter.py`
- Test: `tests/generation/test_tone_sample.py`

**Interfaces:**
- Produces: `StyleProfile.tone_sample`; `generation/models.style_without_sample(text: str) -> str` (JSON профілю без `tone_sample`), який використовують Task 2 і оцінювач.

- [ ] **Step 1: Тести** `test_draft_rewrite_and_full_edit_get_the_sample_section` (секція з міткою й текстом рівно раз, JSON стилю без ключа `tone_sample`), `test_brief_memory_and_patches_do_not_get_the_sample`, `test_evaluator_style_document_has_no_sample`, `test_story_without_sample_keeps_the_same_request` (текст запиту draft до й після: збережений профіль без поля і з порожнім полем дають однаковий `user_text`), `test_sample_longer_than_3000_is_rejected`.
- [ ] **Step 2: Запустити** — FAIL.
- [ ] **Step 3: Реалізувати.** JSON стилю — `model_dump_json(exclude={'ending_goal','tone_sample'})` завжди, коли одне з полів непорожнє (інакше текст версії як є, щоб старі запити не змінились). Секція після стилю для `draft`, `rewrite`, `edit` поза `patches`/`diff`.
- [ ] **Step 4: Запустити** `pytest tests/generation/test_tone_sample.py tests/generation/test_story_horizon.py` — PASS.
- [ ] **Step 5: Commit** `feat(style): tone sample in the prose requests`.

### Task 2: Застарілість

**Files:**
- Modify: `src/storygen/storage/authoring.py` (`publish_writing_settings`), `src/storygen/storage/snapshots.py` (`compare_snapshot`, `SAMPLE_BLIND_SCOPES`), `src/storygen/impact/planning.py` (`document`, `changed`)
- Test: `tests/generation/test_tone_sample_staleness.py`

**Interfaces:**
- Consumes: `style_without_sample`.
- Produces: `storage/snapshots.SAMPLE_BLIND_SCOPES`, `storage/snapshots.sample_only_change(view, old_id, new_id) -> bool`.

- [ ] **Step 1: Тести** (brief і draft зберігаються з `build_context` + `save_version(..., dependency_snapshot=...)`):
  - `test_sample_change_keeps_brief_fresh` — після `update_story_profile` зі зміною лише зразка: `repo.get_version(brief).stale is False`, `compare_snapshot` brief порожній, сцена без `needs_review` від brief;
  - `test_sample_change_stales_the_draft` — draft `stale`;
  - `test_other_style_change_still_stales_brief`;
  - `test_brief_without_snapshot_goes_stale` (версія без знімка — як раніше);
  - `test_impact_capture_of_brief_ignores_a_sample_change` — `capture_target(view, brief)` не має зміненого `SourceChange` з `input_field == 'style_version_id'`.
- [ ] **Step 2: Запустити** — FAIL.
- [ ] **Step 3: Реалізувати.** Транзакція: якщо обидві версії є й `sample_only_change`, сід — прямі цілі `dependency_edges` старої версії, крім сліпих; сіди позначаються застарілими (з `needs_review` сцени) і `invalidate_in_transaction(repo, db, seeds)`. `compare_snapshot`: селектор стилю у сліпому скоупі — зміна лише якщо `not sample_only_change`. Перевірка впливу: у сліпому скоупі документ стилю — `style_without_sample`, `changed` — за текстом.
- [ ] **Step 4: Запустити** `pytest tests/generation tests/impact tests/storage -q` — PASS.
- [ ] **Step 5: Commit** `feat(style): a sample-only change keeps briefs and evaluations fresh`.

### Task 3: Налаштування, MCP, переклади

**Files:**
- Modify: `src/storygen/web/templates/settings.html`, `src/storygen/web/static/settings.js` (лічильник), `src/storygen/web/static/i18n.json`, `src/storygen/mcp/bridge.py` (`WRITING_FIELDS`), `src/storygen/application/writing_context.py`
- Test: `tests/generation/test_tone_sample.py` (MCP), `tests/web/browser/settings.spec.mjs`

- [ ] **Step 1: Тести** `test_mcp_writing_settings_carry_the_sample`, `test_writing_context_has_sample_only_when_set` (відбиток без зразка незмінний); Playwright: поле в «Письмі», лічильник «N / 3000», збереження.
- [ ] **Step 2: Запустити** — FAIL.
- [ ] **Step 3: Реалізувати.** `<textarea name="tone_sample" maxlength="3000" rows="6">` під «Тоном» із підказкою й лічильником; `tone_sample` у `WRITING_FIELDS`; `_content` додає `tone_sample` лише за непорожнього.
- [ ] **Step 4: Запустити** pytest і `cd frontend && npx playwright test settings` — PASS.
- [ ] **Step 5: Commit** `feat(style): tone sample in settings and MCP`.

### Task 4: SPEC, сайт, журнал

- [ ] SPEC.MD: вимога `STYLE-SAMPLE-001` після CONTEXT-005, сценарії S01 (запити), S02 (застарілість), S03 (налаштування й MCP); traceability.
- [ ] Сайт `writing-tools` uk/en: абзац про «Зразок звучання» з нейтральним прикладом; `check_site.py --rehash writing-tools`.
- [ ] Журнал виконання; статус специфікації.
- [ ] `check_docs.py` — узгоджено. Commit `docs(style): tone sample in SPEC, site and journal`.
