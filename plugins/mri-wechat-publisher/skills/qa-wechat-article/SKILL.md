---
name: qa-wechat-article
description: Validate an MRI WeChat article for verified full-text source readiness, claim-level traceability, fixed structure, method-versus-implementation distinctions, references, figures, copyright notes, formatting safety, and publication controls. Use before rendering or saving any generated article to the Official Account draft box.
---

# QA WeChat Article

Resolve `<plugin-root>` as the directory two levels above this `SKILL.md`. Invoke scripts by absolute path and keep the active working directory as the user's workspace.

## Run deterministic checks

Run `python "<plugin-root>/scripts/validate_article.py" <article.json>`. Treat any error as blocking.

## Verify the source gate

- Require `source.evidence_level=FULLTEXT` and `source.fulltext_verified=true` for formal articles.
- Confirm `source.source_manifest` exists and equals the manifest registered in SQLite.
- Confirm the main file identity matches the selected DOI, title, PMID, or publisher record.
- Confirm every used supplement is listed and identity-verified in the same manifest.
- Reject abstract-only evidence for a formal article.

## Review scientific evidence

- Reconcile each quantitative, anatomical, methodological, clinical, predictive, mechanistic, and causal claim with the evidence map.
- Require source locators to identify the main text or a specific supplement location.
- Verify bibliographic metadata through the supplied paper, DOI landing page, PubMed, Crossref, or publisher.
- Confirm that general method properties are not inferred from one implementation.
- Confirm that correlation is not rewritten as causation.
- Confirm that each figure has a distinct role, source, figure identifier, and reuse note.
- Confirm one identifiable central takeaway and keep primary findings more prominent than secondary parameters.
- Confirm the opening synthesis and closing recap are content-specific and non-formulaic.

## Review publishing safety

- Require `publication_mode=draft_only`.
- Reject publish, free-publish, mass-send, deletion, or replacement actions.
- Verify that no token, AppSecret, cookie, QR code, account credential, raw source PDF, or supplement is included in the WeChat payload.

## Decision

Return exactly `QA_PASSED` or `QA_BLOCKED`, including blocking findings, warnings, article statistics, source-manifest status, and the evidence records inspected.
