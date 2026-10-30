---
name: write-mri-paper-method-article
description: Create or locally revise objective Chinese WeChat interpretations of MRI, cognitive-neuroscience, and related biomedical studies from verified research materials. Use when a selected study must become a source-grounded schema-version-8 article with 研究速览、引言、方法、结果、结果解读、结语, or when an existing article needs a scoped revision that reduces repetition, parameter or statistic dumping, causal overstatement, or formulaic AI prose while preserving claim-level traceability.
---

# Write MRI Paper-and-Method Article

Resolve the plugin root above `skills/`. Before writing or revising, read [the editorial profile](../../docs/editorial-profile.md) once per task/source version; reuse it until the file changes. It is the single authority for section roles, digest, prose, method/evidence maps, figures and revision scope; do not maintain a second copy here.

## Writing procedure

1. Read the selected cycle and its registered source manifest. Require matching main-paper identity and `SOURCE_VALIDATED`; no abstract-only formal article and no silent paper substitution.
2. Integrate the main text, required supplements, figure legends and verified versions once. Freeze the source-bound `work/research-facts.json` described by the profile before drafting; select only high-value definitions, denominators, interactions/nulls and validation limits, with exact source excerpts/locators. For a key sensitivity analysis, inspect its result panels when prose/captions omit the test values; similar directions do not imply repeated significance. The builder produces its readable Markdown. Do not derive facts from the finished draft or reload all sources at each stage; resolve version conflicts at first reading.
3. Write schema 8 JSON using the editorial profile and `schemas/article.schema.json`. Set `source.evidence_level=FULLTEXT`, `fulltext_verified=true`, and bind the registered manifest. Map every material claim and every principal analysis to source locators; omit unsupported details.
4. Before prose generation, preflight legal original candidates with `prepare_article.py <candidate-JSON> --figures-only`. Inspect at the actual 422px image width in a 430px viewport and record `work/figure-readability.json`, separating core information from genuinely auxiliary labels. Replace unreadable core figures or stop; ND is unchanged. The renderer must not choose, alter or renumber figures.
5. For a scoped revision, preserve unrequested content. Pass `--baseline` to the validator when only Result Interpretation/Closing may change.
6. Compare the digest and ending against the latest five existing completed article JSONs returned in workflow history, excluding this cycle. Revise current template-like repetition only; do not edit history or force rhetorical alternation. Missing history does not block writing.
7. Freeze JSON and original assets. Repair only identified sentences/fields; reuse unchanged evidence and figures. Run `scripts/prepare_article.py <article.json>` (compact by default, identical inputs reuse the frozen build), then follow `qa-wechat-article`. Do not create article-specific renderers or fetch sources again during reproduction.

The standard bundle renders `method-map.md`, `evidence-map.md` and `figure-list.md` from the JSON. Keep these records internal. Successful generation is not completed scientific or visual QA and does not authorize a WeChat write.
