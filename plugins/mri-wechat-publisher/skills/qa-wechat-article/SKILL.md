---
name: qa-wechat-article
description: Validate MRI and cognitive-neuroscience WeChat articles against verified research materials, the schema-version-8 Research Overview structure, low-redundancy natural Chinese prose, importance-ranked internal method maps, decisive statistics, mobile-readable figures, safe typography, and draft-only controls. Use before rendering or saving an article, or when confirming that a scoped local revision changed only the requested content.
---

# QA WeChat Article

Resolve the plugin root above `skills/`. Use the already-read [editorial profile](../../docs/editorial-profile.md); read it only if not loaded or changed; it is the authority for scientific prose, chapter roles, figures and revision scope. This skill defines the review procedure, not another writing specification.

## Deterministic checks

Run `scripts/prepare_article.py <article.json>`. The shared validator executes the JSON Schema first, then content, file and image checks. Treat errors as blocking and review warnings in context. For an ending-only revision, also run `validate_article.py <article.json> --baseline <original.json>`.

`LOCAL_CHECKS_PASSED` means only automated checks passed. It cannot establish scientific truth, permission or phone readability.

## Manual review

- Reconcile the official paper identity, source version, registered manifest and required supplements with the selected cycle.
- Reuse the first-reading fact summary and evidence/method maps. Inspect `scientific-review.json`; only flagged/changed or otherwise high-risk claims need targeted source re-reading, not a second full draft. The rules cannot establish truth or detect every paraphrase. Check each material claim against its evidence locator: sample, groups, effect direction, numbers/units, anatomy, statistics, model and validation. Preserve direct result versus author/editorial interpretation; include consequential null and sensitivity findings.
- Complete `scientific-review.json.fact_coverage` in this same review, using the already-verified first-reading facts and body candidates. Record all selected facts as accurate, reasonable omission, important omission, misinterpreted or source insufficient in `work/fact-coverage-review.json` with current article/facts hashes, actual body excerpt and source-supported reason. Missing terms are candidates, not truth; resolve paraphrases without synonym substitutions. Do not add a new full-paper/model pass. Ordinary omitted details do not require expanding the draft; unresolved consequential facts prevent QA recording. Formats are in the acceptance tests.
- Inspect every core `method_map` record against source materials and the visible Methods subheading. Confirm inputs, principal operation and inferential test; reject invented details and visible parameter inventories.
- Apply the editorial profile's narrative standards. Compare Results and Result Interpretation for duplication, inspect paragraph endings and digest/overview overlap, and check that title/overview/result subheadings/closing communicate the actual study. Do not impose fixed section lengths, figure counts or rhetorical patterns.
- For revisions, compare protected sections with the baseline. For queued articles, compare the latest five available completed digests/endings, excluding the current cycle.
- Apply the profile’s five image decisions: whole-image inspection first, full split before omission, larger complete panel groups before single panels, before/after evidence, and separate necessity/integrity review. Check the original panels against the declared omissions; machine checks cannot judge their scientific importance. Visually compare every used image with its original. Pixel checks do not detect whether a scientifically necessary shared legend was omitted from the selected region. Confirm complete axes, color bars, legends and panel labels, and verify the exact license/use condition.
- Inspect `preview.html` and `figure-review.html` at 430 CSS pixels. Record the actual method and findings. If visual review is unavailable or fails, leave it incomplete; do not infer legibility from dimensions or successful rendering.
- Reuse valid selection-stage readability records, then confirm the final layout. Core coordinates/legends/comparisons must be readable. Small auxiliary labels may be nonessential only with a specific explanation tied to the current claims; unknown importance stays blocked. Failed core readability cannot be cured by cropping an ND original.
- Check the final payload for sensitive credentials and raw paper/supplement files. Only draft creation may follow explicit user approval.

## Record the reviewed version

Only after all reviews above pass, record factual review notes:

```powershell
python "<plugin-root>/scripts/prepare_article.py" <article.json> --record-qa --scientific-review "<completed evidence review>" --license-review "<actual license and use review>" --visual-review "<actual 430px inspection method and result>"
```

For detected scientific risks, pass `--risk-review <resolutions.json>` with an array of `{id, decision:"supported", source_path, pages, source_locator, source_excerpt, reason}`. The source must be in the registered manifest; PDF pages are 1-based. Fixing a false claim locally may remove the risk instead. Uncertain facts remain unresolved; a `verified` label alone cannot resolve them. See the acceptance tests for record formats.

This records `qa-review.json` against the exact bundle hash; it does not perform or invent the reviews. Any change to JSON, sources, images, output files or the review invalidates the bound version. Register artifacts in SQLite only after this step.

Return `QA_PASSED` or `QA_BLOCKED`, blockers, reviewed warnings, section statistics, source status and actual manual-review results. An old report must not be reused for revised files.
