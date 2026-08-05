---
name: run-mri-wechat-workflow
description: Orchestrate an evidence-grounded MRI or cognitive-neuroscience paper from source selection through hybrid paper-and-method writing, QA, WeChat formatting, and draft-box delivery. Use when the user wants the complete publication-preparation workflow or asks to move an article between workflow stages; never use it to publish or mass-send automatically.
---

# Run MRI WeChat Workflow

## Runtime paths

Resolve `<plugin-root>` as the directory two levels above this `SKILL.md`. Invoke bundled scripts by their absolute path under `<plugin-root>/scripts`; do not require the active working directory to be the plugin directory. Keep the active working directory as the user's workspace.

Store persistent state outside the installed plugin. Use `MRI_WECHAT_DATA_DIR` when set; otherwise use `.mri-wechat-publisher/` in the active workspace. Pass `--db <data-dir>/workflow.db` explicitly when coordinating scheduled or concurrent jobs.

## Transactional state

Use `<plugin-root>/scripts/workflow_state_db.py` with `<data-dir>/workflow.db` as the source of truth. Do not edit `<data-dir>/automation-workflow-state.json` or `<data-dir>/publication-registry.json` directly; they are compatibility snapshots generated after each committed database change.

- Read permanent and five-round cooldown exclusions with `recommendation-exclusions`, then create a recommendation cycle with `create-cycle`.
- Record one explicit choice with `select`, or an ordered multi-selection such as `2,3` with `select-order --choices 2,3`.
- Treat selected and queued papers as permanently excluded. Treat unselected candidates as ineligible for five complete recommendation rounds, then allow them to reappear if their new score warrants it.
- The 09:30 task must atomically acquire work with `claim-writing`; if it returns `claimed=false`, including `queued_not_ready`, do not write an article before the returned `available_at`.
- Record verified article artifacts with `set-artifacts` only after `QA_PASSED`.
- After explicit draft approval, call `approve-draft`; after a verified draft save, call `record-draft`.
- Record manual publication and backend-export statistics with `record-publication` and `record-stats`.
- Never write AppID, AppSecret, access tokens, cookies, or other credentials to SQLite, snapshots, or job logs.

## Required sequence

1. Record the selected paper, DOI, source files, publication date, journal, access status, and user constraints.
2. Invoke `write-mri-paper-method-article` to create the evidence map and five-section article JSON.
3. Invoke `qa-wechat-article`; stop if it does not return `QA_PASSED`.
4. Invoke `format-wechat-article` and preserve the validated article JSON as the source of truth.
5. Show the user the title, digest, section inventory, figure inventory, and QA result. Obtain explicit approval before writing to the live draft box.
6. Invoke `save-wechat-draft` with `draft_only=true`.
7. Persist the verified draft receipt through `<plugin-root>/scripts/workflow_state_db.py record-draft`. If it returns `next_queued`, report the next queued paper; do not fetch its full text until a later `claim-writing` succeeds.
8. Return the transport used, draft identifier or visible draft title, timestamp, and any manual follow-up.

## State rules

Use only these ordered states in SQLite:

`AWAITING_SELECTION → SELECTED → WRITING → AWAITING_DRAFT_APPROVAL → DRAFT_SAVED → PUBLISHED`

Keep evidence mapping and writing stages in the job record and artifact paths. Do not skip `QA_PASSED` or explicit user draft approval. Do not execute publishing, free-publishing, mass-send, deletion, or replacement of existing live content.

## Failure behavior

- Keep the article in the last valid state.
- Report actionable API error codes without printing tokens or secrets.
- If the draft API is unavailable, switch to the logged-in browser path only when the user has already approved draft creation.
- Never interpret a successful local HTML render as a successful WeChat draft save.
