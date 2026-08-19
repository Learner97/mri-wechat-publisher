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
8. Invoke `write-mri-paper-method-article` to create a new `schema_version: 8` article in the required order 研究速览、引言、方法、结果、结果解读、结语. Make the grey digest answer why the paper is worth opening while 研究速览 gives the compact method-and-result map; keep the two non-redundant. Select the digest form only after identifying the paper-specific entry point; questions, question-and-answer, contrasts, observations, and direct results are equally optional. When preparing multiple articles, compare all digests side by side and revise repeated interrogative or declarative skeletons before rendering. Compress non-critical technical parameters, retain only decisive statistics, and avoid causal wording for correlation, spatial association, or enrichment results. Do not create a separate 方法启示 section, and do not require method commentary in 结语; include a justified transferable design idea only when it adds paper-specific information. Require a verified, importance-ranked `method_map` whose analyses state data, processing, statistics, optional useful outputs, and research-material locators; require a mobile display strategy for every figure, render `method-map.md`, then invoke `qa-wechat-article` and `format-wechat-article`.
9. Call `set-artifacts` only after both `SOURCE_VALIDATED` and `QA_PASSED`.
10. Present the draft and obtain explicit approval before `save-wechat-draft`.
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
