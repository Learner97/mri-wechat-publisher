---
name: write-mri-paper-method-article
description: Create Chinese WeChat articles that combine MRI or cognitive-neuroscience paper interpretation with a deeper transferable-method explanation. Use when source papers, PDFs, supplements, figures, DOI records, or verified notes must become the fixed five-section article JSON with an evidence map and traceable references.
---

# Write MRI Paper-and-Method Article

Resolve `<plugin-root>` as the directory two levels above this `SKILL.md`. Resolve bundled schemas and scripts from that root rather than from the active working directory.

## Evidence gate

1. Read the full source sections needed for the abstract, design, method, results, figure legends, discussion, limitations, and supplement-dependent claims.
2. Separate research topic, analysis family, transferable method, and paper-specific implementation.
3. Build an evidence map for every quantitative result, method choice, interpretation, figure, DOI, and reuse condition.
4. Reject unsupported details rather than filling gaps.

## Fixed structure

Write exactly these five main sections:

1. 摘要解读
2. 研究设计与数据
3. 核心方法解析
4. 关键结果与证据链
5. 方法启示与总结

Place references after the fifth section without numbering them as a sixth section. Integrate cautions where they affect method interpretation or application. Do not create a standalone “最容易误解或做错的地方” or generic limitations section.

## Focus-first synthesis

- Before drafting, state the article's single most important takeaway in one sentence. Use it to decide which findings are primary and which analyses are supporting evidence.
- Near the beginning of “摘要解读”, include a visually distinct, concise synthesis of the scientific question, principal finding, and why it matters. Its label, subheading, format, and number of points must follow the paper naturally; never force stock wording such as “30秒读懂”.
- Keep the principal findings prominent across the article. Design details, parameters, secondary outcomes, and sensitivity analyses should support the main evidence chain rather than compete with it as equal-weight conclusions.
- At the end of “方法启示与总结”, naturally gather the most important conclusions again. Use prose, a callout, or a short list as appropriate, with a content-specific or omitted heading; never force stock wording or a fixed number of takeaways.
- The opening synthesis and closing recap must add navigation and emphasis, not repeat identical sentences or turn the article into a formulaic template.

## Title contract

- For an article centered on one paper, use the fixed shape `<journal name or recognized abbreviation> | <short content-specific hook>` so the source venue is visible at a glance.
- Count only the content hook after ` | `. It must not exceed 20 characters; the journal label and separator are excluded from this limit.
- Prefer the journal's conventional abbreviation when its full name would make the title too long; for example, use `Nat Neurosci` for *Nature Neuroscience*.
- Keep the hook faithful to the paper's central question, method, or finding. Use the available 20 characters when they improve specificity, but do not copy the full paper title, stack subtitles, or use a generic slogan.
- Verify the journal label against the publisher or bibliographic record before drafting the title.

## Editorial profile

- Target 8,000–11,000 Chinese characters when the evidence supports it.
- Allocate roughly 55%–60% to background, design, and results; 30%–35% to method; 10%–15% to implications and summary.
- Select 5–7 non-duplicative figures when usable and legally supportable.
- Explain general method logic before the paper-specific implementation.
- Use cautious language for clinical, predictive, mechanistic, and causal claims.
- Never invent sample sizes, parameters, regions, statistics, software versions, references, DOIs, or licenses.

## Output

Produce JSON conforming to `<plugin-root>/schemas/article.schema.json`. Preserve a separate evidence map during drafting and require `qa-wechat-article` before draft delivery.
