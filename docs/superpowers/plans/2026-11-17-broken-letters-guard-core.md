# Пошкоджені літери «�»: ядро — план

> Виконання: superpowers:executing-plans (inline), один PR на `main`.

**Мета:** виявляти нові «�» у відповідях моделей і реагувати за категорією етапу; для Venice на етапах категорій 1–2 — запит без потоку.

**Специфікація:** `docs/superpowers/specs/2026-11/2026-11-17-broken-letters-guard-design.md` (затверджено 17.11.2026).

## Глобальні обмеження

- «Нове» слово — слово виходу з «�», якого немає серед слів входу (рівність після зрізання крайніх символів, що не є літерою, цифрою чи «�»); слова лише з «�» вхід не покривають.
- Вхід — склеєний вміст `messages` тіла запиту спроби.
- Діагностика й попередження містять лише кількість, без слів.
- Без потоку: лише `provider=='venice'` і етапи категорій 1–2; тайм-аут читання 300 с.
- Категорія 1: `memory`, `classify`, `impact_delta`, `impact_check`, `impact_part`, `review_part`. Категорія 2: `edit` з `edit_mode` `diff` або `patches`, `rewrite`, `publication_suggest`. Категорія 3: `draft`, `brief`, `prepare`, `edit` з `prose`, `timeline_summary`.

## Задача 1. Модуль виявлення

`src/storygen/generation/broken_text.py`:

- `request_source(body) -> str`;
- `known_words(source) -> frozenset`;
- `new_broken_words(output, known) -> list[str]`;
- `count_broken(text) -> int`;
- `json_strings(value)`;
- `structured_broken(text, known) -> list[str]` — `[]`, якщо JSON не розбирається;
- `broken_diff_edits(proposal, known) -> set[int]`;
- `drop_diff_edits(original, proposal, indices) -> RewriteDiff | None`;
- `stage_category(stage, edit_mode) -> 1 | 2 | 3 | None`.

Тести: `tests/generation/test_broken_text.py`, з усіма випадками з розділу «Тести» специфікації для `new_broken_words`, JSON і diff.

## Задача 2. Реакція в `execute_stage`

- Категорія 1: перевірка після складання тексту; невдача через чинну гілку `failed`, причина `broken_output` у полі етапу (`impact_failure` для `impact_*` і `review_part`, `classification_failure`, `generation_failure`).
- Категорія 3: `broken_text_warnings` (кількість); злиття в `worker.py` і `WARNING_KEYS` чату.

Тести: `tests/generation/test_broken_stage.py` з фейковим шлюзом.

## Задача 3. Категорія 2

- diff (зокрема цикл редактури) і rewrite: `drop_diff_edits` до збереження.
- patches: фільтр `CopyEdits.edits` до `apply_copyedits`.
- Публікація: фільтр полів до `parse_suggestions`.
- Попередження «Відкинуто N правок…».

Тести в тому самому файлі.

## Задача 4. Без потоку для Venice

- `generation_request`: `stream: False`, без `stream_options`.
- `OpenAIGenerationGateway.stream`: гілка без потоку з фоновим викликом, скасуванням ≤ 1 с і обліком пізньої відповіді; тайм-аут 300 с.
- `stage_started` має `streaming`.

Тести: `tests/providers/test_nonstream_venice.py`.

## Периферія (окремий план після рев'ю ядра)

Плашка в редакторах, статус у `runs.js`, i18n, промпти, SPEC, traceability, сайт.
