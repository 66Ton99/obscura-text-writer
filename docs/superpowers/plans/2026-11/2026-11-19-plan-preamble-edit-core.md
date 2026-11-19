# План основи: редагування вступу плану

Специфікація: `docs/superpowers/specs/2026-11/2026-11-19-plan-preamble-edit-design.md` (затверджено 2026-11-19).
Виконання: inline (`superpowers:executing-plans`), один PR разом з обв’язкою.

## Основа

1. **`plan_sections.replace_preamble(text, new)`** → `(candidate, old_preamble)` або `PreambleError(reason)`.
   - Нормалізація нового вступу: CRLF → LF; порожній після `strip()` → `''`; інакше закінчується `\n`, і ще одним `\n`, якщо решта плану не починається порожнім рядком.
   - `candidate = new + text[len(old):]`; `split_plan(candidate)` мусить дати `new` і ті самі тексти секцій, інакше `reason='boundary'`; план, для якого жоден непорожній вступ не проходить цю перевірку (немає меж сцен), — `reason='no_scenes'`.
   - `preamble_editable(text)` — пробна заміна на `'x\n'`.
   - Тести: випадки П3 зі специфікації.
2. **`storage/plan_preamble.py`**: `read_plan_preamble(repo, story_id)` → `{text, plan_version_id, editable, reason}`; `replace_plan_preamble(repo, story_id, expected_plan_version_id, text)`.
   - Підготовка: CAS-перевірка, `replace_preamble`, рядки серії у виданні `long_prose` → `ValueError`, однаковий вступ за `strip()` → без змін; `save_version(..., [previous.id])`.
   - Публікація: `BEGIN IMMEDIATE`, повторний CAS → `RevisionConflict`, `active_sources`, `invalidate_in_transaction([previous], exclude={new}, preserve=плани сцен|канон|картки)`, `_touch_story`.
   - Тести: нова версія не `stale`, сцени з прозою застарівають, канон ні, CAS 409, відмова нічого не змінює, нові вказівки в контексті.
3. **API**: `GET/PUT /api/stories/{id}/plan-preamble` у `routes_stories.py`; тести через `TestClient`.

## Обв’язка (після основи)

4. Панель «Загальні вказівки з плану» в налаштуваннях → «Письмо», тексти uk/en.
5. MCP: `get_story` повертає вступ; `update_story` приймає `plan_preamble` + `plan_version_id`.
6. SPEC.MD (`PLAN-PREAMBLE`), traceability, `docs/site/{uk,en}/imports.md` і `mcp.md`, STATUS.
