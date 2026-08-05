---
name: qa-wechat-article
description: Validate an MRI WeChat article for fixed structure, source traceability, method-versus-implementation distinctions, references, figures, copyright notes, formatting safety, and publication controls. Use before rendering or saving any generated article to the Official Account draft box.
---

# QA WeChat Article

Resolve `<plugin-root>` as the directory two levels above this `SKILL.md`. Invoke scripts by absolute path and keep the active working directory as the user's workspace.

## Run deterministic checks

Run `python "<plugin-root>/scripts/validate_article.py" <article.json>`. Treat any error as blocking.

## Review scientific evidence

- Reconcile each quantitative or anatomical claim with the evidence map.
- Verify bibliographic metadata through the supplied paper, DOI landing page, PubMed, Crossref, or publisher.
- Confirm that general method properties are not inferred from one implementation.
- Check that clinical, predictive, and causal claims do not exceed the design.
- Confirm that each figure has a distinct role, source, figure identifier, and reuse note.
- Confirm that the article has one identifiable central takeaway and that primary findings are not buried beneath equal-weight design details, parameters, or sensitivity analyses.
- Confirm that “摘要解读” opens with a concise, content-specific synthesis and that “方法启示与总结” naturally recaps the main conclusions. Their headings and point counts must remain flexible rather than using mandatory slogans.
- Reject opening and closing summaries that merely duplicate the same sentences or add formulaic labels without improving emphasis.

## Review publishing safety

- Require `publication_mode` to equal `draft_only`.
- Reject instructions or configuration containing `publish`, `freepublish`, `mass_send`, or automatic deletion as requested actions.
- Verify that no token, AppSecret, cookie, QR code, or account credential appears in article content, logs, or fixtures.

## Decision

Return exactly one gate status: `QA_PASSED` or `QA_BLOCKED`. Include blocking findings, warnings, article statistics, and the evidence records inspected.
