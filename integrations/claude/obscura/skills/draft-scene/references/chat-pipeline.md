# Chat mode: the scene pipeline

In `chat` mode you do the work of Obscura's four roles yourself. Each stage reaches the same server checks as a model answer would.

## The four stages, in this order

The order is required. An error such as "Спершу завершіть попередній етап…" ("finish the previous stage first") means a stage was skipped.

### 1. Brief

- `get_stage_task(scene_id, 'brief')`. Read `instructions` and the whole `material`. If `next_offset` is not null, call again with `offset=next_offset` until it is.
- Answer as JSON in the format the instructions give: `objective`, `beats`, `constraints`, `proposed_changes`, `introduced`. `introduced` holds the ids of characters the hero meets for the first time in this scene.
- `save_stage_result(scene_id, 'brief', task_fingerprint, result, model=<your model name>)`.

### 2. Draft

- `get_scene_context(scene_id)` gives `instructions`, the context, `revision` and `context_fingerprint`.
- `get_scene_text(scene_id, 'draft')`:
  - **no draft yet:** `draft_version_id` is `null`;
  - **a draft exists:** write on top of the text you read, because it may hold the author's edits.
- Write the scene in the scene's language. Keep to the brief, the plan and the continuity checklist.
- `save_draft(scene_id, text, expected_revision=<revision>, context_fingerprint, draft_version_id, model=<your model name>)`. The field is `expected_revision`, not `revision`.

### 3. Edit

- `get_stage_task(scene_id, 'edit')`. Look at `result_format`. It follows the editor's mode in the story's settings:
  - **`prose`**: return the whole edited prose. It becomes the scene's prose.
  - **`patches`**: return structured point edits, exactly as the instructions describe.
  - **`diff`**: return the changes in the form the instructions describe.

  Never send prose when the format is `patches` or `diff`. The server rejects it.
- While editing, apply the language checks from `continuity.md`.
- `save_stage_result(scene_id, 'edit', task_fingerprint, result, model=…)`.
- **If the answer has `state=needs_review`, or `get_story` shows the scene as `needs_review`:** the edits wait for the author's decision. Stop. Ask the author to review the edits in Obscura. Continue only after they say they are done.

### 4. Memory

- `get_stage_task(scene_id, 'memory')`. The material is long, so read all of it in parts with `offset` and `max_chars` of at most 20000, until `next_offset` is null.
- Answer as JSON in the version and format the instructions give:
  - fill every core slot;
  - add at most 3 new items per category;
  - use `update` and `retire` only with a `claim_id` from the material.
- `save_stage_result(scene_id, 'memory', task_fingerprint, result, model=…)`.
- **If the server asks the author to confirm the previous memory:** stop and ask the author to confirm it in Obscura.

## When the server refuses

- **A rejected stage result** lists all violations together. Fix them and save again with the same `task_fingerprint`.
- **After three refusals in a row,** stop and show the violations to the author.
- **409:** the task is stale or needs the author. Take the task again with `get_stage_task`.
- **Limits:** `max_chars` takes 1000–20000. Larger values give 422.

## Model routing

| Step | Claude Code | Claude Desktop |
|---|---|---|
| brief | main session (pending measurement) | main session |
| draft | Opus level: if the session model is weaker, give the step to a subagent with model `opus` | suggest that the author picks the strongest model |
| edit | as draft | as draft |
| memory | main session (pending measurement) | main session |

**Brief for a subagent.** A subagent does not see the conversation and cannot ask the author anything. Give it everything it needs:
- `scene_id` and the stage;
- the style requirements;
- the author's decisions from the conversation that concern this scene;
- the continuity notes;
- the exact result expected: which tool to call and with which fields;
- the instruction to stop and report instead of guessing.

You report progress to the author, not the subagent.
