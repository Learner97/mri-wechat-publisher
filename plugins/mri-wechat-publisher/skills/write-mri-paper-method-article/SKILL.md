---
name: write-mri-paper-method-article
description: Create Chinese WeChat articles that combine MRI or cognitive-neuroscience paper interpretation with a deeper transferable-method explanation. Use when a verified full-text source manifest, main paper, supplements, figures, DOI records, and evidence notes must become the fixed five-section article JSON with claim-level traceability.
---

# Write MRI Paper-and-Method Article

Resolve `<plugin-root>` as the directory two levels above this `SKILL.md`. Resolve bundled schemas and scripts from that root rather than from the active working directory.

## Evidence gate

1. Require a registered source manifest whose main paper identity matches the selected record.
2. Require `SOURCE_VALIDATED` before treating the source as sufficient.
3. Read the full sections needed for the abstract, design, methods, results, figure legends, discussion, limitations, and supplement-dependent claims.
4. Reject unsupported details instead of filling gaps from the abstract or general knowledge.
5. Do not generate the formal article when only an abstract is available.

Set the article source fields to:

```json
{
  "evidence_level": "FULLTEXT",
  "fulltext_verified": true,
  "source_manifest": "<registered manifest path>"
}
```

## Evidence mapping

- Map every quantitative result, method parameter, anatomical claim, figure, DOI, limitation, and reuse condition to the main text or a verified supplement.
- Use precise locators such as PDF page, section, figure, table, supplement file, and supplement page.
- Mark author conclusions, direct observations, and editorial interpretation separately.
- Omit claims that cannot be located in the registered source bundle.

## Fixed structure

Write exactly these five main sections:

1. 摘要解读
2. 研究设计与数据
3. 核心方法解析
4. 关键结果与证据链
5. 方法启示与总结

Place references after the fifth section without numbering them as a sixth section. Integrate cautions where they affect interpretation. Do not create a standalone generic “最容易误解或做错的地方” section.

## Focus-first synthesis

- State the single most important takeaway before drafting and use it to prioritize evidence.
- Open “摘要解读” with a concise, content-specific synthesis of the question, principal finding, and importance. Do not force labels such as“30秒读懂”。
- Keep primary findings visually and logically prominent; parameters and sensitivity analyses should support the main evidence chain.
- Close naturally with the most important conclusions. Do not force a fixed heading or a fixed number of takeaways.
- Avoid repeating identical opening and closing sentences.

## Title contract

- Use `<journal name or recognized abbreviation> | <short content-specific hook>`.
- Count only the hook after ` | `; it must not exceed 20 Chinese characters.
- Verify the journal label against the source record.
- Prefer a specific hook over a generic slogan or copied paper title.

## Editorial profile

- Target 8,000–11,000 Chinese characters when evidence supports that length.
- Allocate roughly 55%–60% to background, design, and results; 30%–35% to method; 10%–15% to implications and summary.
- Select 5–8 non-duplicative figures only when their source and reuse status are verified.
- Explain general method logic before the paper-specific implementation.
- Use cautious language for clinical, predictive, mechanistic, and causal claims.
- Never invent sample sizes, parameters, regions, statistics, software versions, references, DOIs, licenses, or unavailable supplement results.

## Output

Produce JSON conforming to `<plugin-root>/schemas/article.schema.json`. Bind it to the registered source manifest, preserve a separate evidence map, and require `qa-wechat-article` before draft delivery.
