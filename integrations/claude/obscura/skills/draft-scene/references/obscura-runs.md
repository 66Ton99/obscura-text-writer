# Obscura mode: runs of Obscura's own models

In `obscura` mode Obscura's models write the texts, and each run costs the author money at the providers' prices. You never write the scene text yourself. You start runs, watch them, and keep the author informed.

## Before the first run

- `get_settings(story_id)`: the four roles (planner, writer, editor, memory) must be configured and their keys present.
- If a role is not configured or its key is missing, stop. Suggest choosing models: use the `setup-models` skill. Never call `start_run` with `confirm=true` in that state.

## A scene is four runs

`start_run` runs exactly one stage. A scene therefore needs four runs: `brief` → `draft` → `edit` → `memory`. Take the next stage from the scene's state in `get_story`, not from memory of earlier calls. The state `prose` does not show whether memory is done: rely on the runs you watched in this conversation, and if unsure, say so in the preview card instead of starting a second memory run.

Before the first stage of a scene, ask one card:
- **«Покроково»** (step by step): consent before every stage.
- **«Усю сцену»** (the whole scene): one consent for all four stages.

  Before you ask for that consent, show the preview of the first stage and say that the next three will be similar.

## Each stage

1. `start_run(story_id, action=<stage>, scene_id)` **without** `confirm`. Show the preview to the author:
   - readiness;
   - models;
   - number of calls;
   - warnings;
   - budget.
2. **Consent:** the author's yes for this stage, or the whole-scene consent. Then call `start_run(..., confirm=true)`. Pass `budget_limit_usd` if the author named a limit.
3. **Watch:** `get_run(run_id)` again and again until the state is final. Write one progress line whenever the state changes. Do not wait inside a single call.
4. **Result:** `get_scene_text(scene_id, <material of the stage>)` and one line of summary.

## Stops and the author's decisions

- **After `brief`, step by step:** show the brief briefly and ask whether to write the draft.
- **After `edit`:** if the edits wait for review, or the server asks to confirm the memory, ask the author to do it in Obscura and wait.
- **A run fails, is cancelled or hits the budget:** show the reason. Do not start the next stage without new consent.
- **The author asks to stop:** `get_run(run_id, cancel=true)` cancels a run that chat started.

## Progress

For example:

> Сцена 2 з 7: чернетка — модель пише (running) → готово, 980 слів → далі редактура.
