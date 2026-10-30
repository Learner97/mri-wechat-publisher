---
name: run-mri-wechat-workflow
description: Orchestrate an evidence-grounded MRI or cognitive-neuroscience paper from ranked recommendation and metadata-only full-text availability checks through source upload, full-text validation, hybrid paper-and-method writing, QA, WeChat formatting, and draft-box delivery. Use for the complete publication-preparation workflow or any transition between recommendation, source, writing, review, and draft stages; never publish or mass-send automatically.
---

# Run MRI WeChat Workflow

## Runtime paths

Resolve `<plugin-root>` as the directory two levels above this `SKILL.md`. Invoke bundled scripts by their absolute path under `<plugin-root>/scripts`; do not require the active working directory to be the plugin directory. Keep the active working directory as the user's workspace.

Store persistent state outside the installed plugin. Use `MRI_WECHAT_DATA_DIR` when set; otherwise use `.mri-wechat-publisher/` in the active workspace. Pass `--db <data-dir>/workflow.db` explicitly when coordinating scheduled or concurrent jobs.

## Transactional state

Use `<plugin-root>/scripts/workflow_state_db.py` with `<data-dir>/workflow.db` as the source of truth. Do not edit `<data-dir>/automation-workflow-state.json` or `<data-dir>/publication-registry.json` directly; they are compatibility snapshots generated after each committed database change.

- Read permanent and five-round cooldown exclusions with `recommendation-exclusions`.
- Create a recommendation cycle only with `create-cycle`.
- Record one choice with `select`, or an ordered multi-selection with `select-order --choices 2,3`.
- Acquire scheduled writing atomically with `claim-writing`.
- Record validated sources with `register-source-manifest` and `source-readiness`.
- Record article artifacts only after `QA_PASSED` and `SOURCE_VALIDATED`.
- Require explicit user approval before saving a draft.
- Never store AppID, AppSecret, access tokens, cookies, or other credentials in SQLite, snapshots, manifests, or logs.

## Recommendation stage

Use the maintained `scripts/` workflow, not archived one-off recommendation builders with fixed dates, rounds or paper lists. Development archives are not runtime dependencies.

1. Retrieve exclusions from SQLite before searching.
2. Search recent MRI, cognitive-neuroscience, connectome, neuroimaging-AI, disease, medical, and biological papers.
3. Rank scientific value independently from access status.
4. For the final five candidates, run a metadata-only source check:

```powershell
python "<plugin-root>\scripts\source_availability.py" `
  --input "<data-dir>\recommendations-raw.json" `
  --output "<data-dir>\recommendations-checked.json"
```

The check may query PubMed/PMC, Europe PMC, OpenAlex, and publisher metadata. It must not download or persist a PDF, full-text HTML/XML body, or supplement.

Each final candidate must contain `fulltext_access` with one of:

- `PUBLIC_FULLTEXT_CONFIRMED`
- `PUBLIC_HTML_CONFIRMED`
- `USER_UPLOAD_REQUIRED`
- `ACCESS_UNKNOWN`

`create-cycle` must reject a new recommendation pool whose candidates lack this metadata-only check. Paywalled or unknown-access papers remain eligible for the top five and keep their scientific score.

Display every candidate with title, journal, publication date, scientific score, recommendation reason, method focus, DOI, PubMed link, full-text status, supplement status, and required user action. Do not compress the notification to titles only.

## Selection and source routing

After selection, inspect the returned `source_gate`:

- `PUBLIC_SOURCE_PENDING_FETCH`: wait until the scheduled preparation task, then fetch the confirmed public source.
- `AWAITING_USER_UPLOAD`: create/use the returned `input_dir`, tell the user the exact source deadline, and request the legally obtained main PDF plus any supplements.
- `SOURCE_FILES_READY`: source files and identity manifest exist but evidence sufficiency still needs review.
- `SOURCE_VALIDATED`: full-text evidence is sufficient for writing.
- `EVIDENCE_BLOCKED`: stop and report the missing or mismatched evidence.

Never replace a selected paper silently. If a source is missing at the deadline, preserve its queue position and ask whether to wait, defer it behind the next ready paper, cancel it, or explicitly create a separately labelled abstract-only brief.

## User-uploaded source bundle

Store user files only under:

```text
<data-dir>/<cycle-id>/input/
```

Store publicly fetched files only under:

```text
<data-dir>/<cycle-id>/source/
```

Before registration:

1. Verify the main PDF opens and matches the selected title, DOI, PMID, or publisher record.
2. Verify each supplement belongs to the same paper.
3. Record SHA-256, size, identity signals, and verification evidence.
4. Build the manifest with `scripts/build_source_manifest.py`.
5. Register it with:

```powershell
python "<plugin-root>\scripts\workflow_state_db.py" `
  --db "<data-dir>\workflow.db" register-source-manifest `
  --cycle-id <cycle-id> `
  --manifest <source-manifest.json>
```

Use lowercase `--matched-by doi`, `title`, `pmid`, `publisher_link`, or `filename` when building the manifest.

The raw files remain local and must never be uploaded to WeChat or redistributed.

## Context and deterministic work

Load this orchestration skill at routing, the writing skill/profile when writing, QA at review, formatting at build, and draft-save only after approval. Reuse unchanged instructions within a task; do not reload all five skills per stage. Keep page-aware extraction and a source-bound fact summary under `work/`; read source snippets by locator when needed. Load only the latest five available digest/closing pairs for style comparison, not all history/full articles. Run the deterministic builder once per input/code version and read its compact output; use `--verbose` only for diagnostics. No added model calls or automatic full-article regeneration are required.

The sequence is first-reading facts → early original-figure selection → draft → coverage comparison in existing QA → local repair. Facts, decisions and readability evidence join cache/QA invalidation. Review-only changes reuse intact HTML/image rendering; they never restore stale QA or draft approval. If host usage is unavailable, report model calls/tokens as unmeasured.

## Scheduled preparation

Interpret 09:30 as the delivery target. Use the default preparation sequence:

1. 08:00: lock and preflight the source bundle.
2. 08:10: call `claim-writing`.
3. If the gate is `PUBLIC_SOURCE_PENDING_FETCH`, fetch the public full text now, not during search.
4. If the gate is `SOURCE_FILES_READY`, read the registered user or public bundle.
5. Confirm that Methods and Results are readable and that supplement-dependent claims have the needed supplement.
6. Mark sufficient evidence:

```powershell
python "<plugin-root>\scripts\workflow_state_db.py" `
  --db "<data-dir>\workflow.db" source-readiness `
  --cycle-id <cycle-id> --decision READY `
  --detail "Methods, Results and required supplements verified"
```

7. If evidence is insufficient, use `--decision BLOCKED`; do not draft a full article from the abstract.
8. Invoke `write-mri-paper-method-article` under the single [editorial profile](../../docs/editorial-profile.md). That profile owns section roles, digest/prose, method/evidence maps and original-figure policy; do not duplicate it in this workflow.
9. Run `scripts/prepare_article.py <article.json>`, then perform `qa-wechat-article` including actual 430px inspection. Record completed reviews with `--record-qa`; machine success alone is insufficient. Call `set-artifacts` only after `SOURCE_VALIDATED` and a bundle-bound `QA_PASSED`. Deliver `preview.html`; `article.html` is its lightweight entry and `wechat-upload.html` is upload-only.
10. Present the draft and obtain explicit approval before `save-wechat-draft`. `approve-draft` verifies the registered QA hashes and records `draft-approval.json`; changed content needs new QA and approval.
11. Persist the verified draft receipt with `<plugin-root>/scripts/workflow_state_db.py --db <data-dir>/workflow.db record-draft`; report `next_queued` without fetching its full text early.

## Evidence rules

- A formal article requires a verified main full text.
- Supplements are required only when a central method or result depends on them; otherwise record their absence as a warning and avoid unsupported claims.
- Bind every formal `article.json` to the registered source manifest.
- Support every quantitative result, parameter, anatomical claim, figure, and limitation with a full-text or supplement locator.
- For every mapped analysis, record source-supported data, processing, statistics, importance, and useful outputs in `method_map`. Do not infer missing software versions, parameters, dimensions, thresholds, algorithms, or sample counts. Omit ordinary missing parameters; record only missing information that directly changes interpretation of a principal conclusion or is requested in a method-completeness audit.
- Integrate main text, supplements, appendices, proof, and verified versions before drafting. Do not expose retrieval, verification, or material-comparison language in the public article unless a substantive version difference changes interpretation.
- Classify direct results, author interpretations, editorial explanations, and limited editorial extensions in the internal evidence map; do not expose those QA labels as visible article structure.
- Never turn correlation into causation or infer undisclosed parameters.

## Failure behavior

- Keep the cycle in its last valid state.
- Return `awaiting_source_upload` when user files are required.
- Return `EVIDENCE_BLOCKED` when the source is mismatched, unreadable, or insufficient.
- Report actionable API errors without secrets.
- Never interpret a successful local render as a successful WeChat draft save.
- Never publish, free-publish, mass-send, delete, or overwrite live content.
