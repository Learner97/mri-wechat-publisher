---
name: qa-wechat-article
description: Validate MRI and cognitive-neuroscience WeChat articles against verified research materials, the schema-version-8 Research Overview structure, low-redundancy natural Chinese prose, importance-ranked internal method maps, decisive statistics, mobile-readable figures, safe typography, and draft-only controls. Use before rendering or saving an article, or when confirming that a scoped local revision changed only the requested content.
---

# QA WeChat Article

Resolve `<plugin-root>` as the directory two levels above this `SKILL.md`. Invoke scripts by absolute path and keep the active working directory as the user's workspace.

## Run deterministic checks

Run `python "<plugin-root>/scripts/validate_article.py" <article.json>`. For a scoped revision, also pass `--baseline <pre-revision-article.json>` so the validator can block any change to protected sections. Treat every error as blocking. Review warnings rather than discarding them automatically.

For a new article, require `schema_version: 8`, a verified `method_map`, and this required order:

1. 研究速览
2. 引言
3. 方法
4. 结果
5. 结果解读
6. 结语

Do not allow a separate 方法启示 section in version 8. Do not require a transferable design or analytical idea to appear in 结语; judge it only when the writer chose to include it because it adds paper-specific information. Accept `schema_version: 1` through `schema_version: 7` only as legacy articles that are being reopened; do not generate new content with a legacy version.

For a scoped revision, compare the input and output before judging prose. Protected sections must remain structurally identical. Treat unrequested polishing of 研究速览或摘要、引言、方法或结果 as blocking when the user asked to revise only the ending.

## Verify source identity and readiness

- Require `source.evidence_level=FULLTEXT`, `source.fulltext_verified=true`, and a source manifest registered in SQLite for every formal article.
- Confirm that the main file matches the selected official title, DOI and/or PMID, journal, publication date, and source version.
- Confirm every used supplement is identity-verified in the same manifest.
- Prefer the Version of Record over proof, accepted manuscript, or preprint when available.
- Reject abstract-only evidence for a formal article.

## Audit scientific accuracy

- Reconcile every quantitative, anatomical, methodological, clinical, predictive, mechanistic, and causal claim with `evidence_map` and its exact locator.
- Confirm that `direct_result`, `author_interpretation`, `editorial_explanation`, and `editorial_extension` are not silently converted into one another.
- Verify sample sizes, group definitions, directions of effect, units, statistical values, anatomical labels, models, validation sets, figure numbers, and supplement references.
- Confirm that correlation is not rewritten as causation and that group-level findings are not rewritten as individual clinical rules.
- Include important null, replication, external-validation, and sensitivity results when omitting them would change interpretation.
- Confirm that general method properties are not inferred from one paper-specific implementation.
- Block unsupported details rather than softening them into vague prose.
- Treat main text, supplements, appendices, proof, and other verified versions as one internal evidence set. Verify conflicts internally, but require public prose to present the integrated research method and result.
- Block public narration of source retrieval, verification, or material comparison, such as “补充材料显示”, “proof记录”, or “来源材料未说明”. Permit a concise version comparison only when the reported difference changes interpretation.

## Audit the article narrative

- **Digest**: require one or two factual sentences that make clear why this particular paper is worth opening. Judge the content before the punctuation: a direct statement, contrast, observation, unanswered question, or question with an answer are all valid, but none is the default. Confirm that the form follows the paper-specific entry point rather than a reusable hook template. Confirm that it does not become a compressed inventory of cohorts, modalities, atlases, and pipeline steps, that the renderer shows it once in the grey card, and that 研究速览 does not repeat the same sequence of factual units.
- **研究速览**: provide a short, flexible map of how the study addressed its question and what it found, with the study object and analytical framework as needed. Do not require labelled fields, a fixed length, or every listed element. Keep detailed t, p, OR, β, confidence intervals, and similar statistics in Results.
- **引言**: give established knowledge, prior findings, and the unresolved gap without repeating the cohort, analytical sequence, or full principal conclusion already stated in 研究速览. Its length is evidence-driven and need not be shorter than Methods or Results.
- **方法**: make the analytical logic, data, key steps, and core parameters clear enough to understand each principal analysis. Keep complete technical provenance in `method_map`, but compress routine software settings, command details, and non-decisive parameters in visible prose.
- **结果**: follow the paper's logic, include as many findings as the source requires, use finding-specific subheadings, and keep interpretation or application claims out. Retain statistics that determine whether a principal conclusion is supported; summarize secondary numerical series and enrichment tables by direction or dominant theme.
- **结果解读**: explain what findings mean, how different findings relate, and which interpretation limit materially changes understanding. Do not reopen paragraphs with the same full result or statistics. Distinguish group from individual, imaging from external molecular or network data, and association from mechanism only where needed; integrate any limit into the relevant explanation instead of appending a disclaimer.
- **结语**: state what knowledge the study adds. A paper-specific analytical idea may be included only when it adds genuine information; it is not required, and a one-paragraph ending is valid. Keep the section concise, concrete, and free of exhaustive result recaps, method pipelines, detailed statistics, evidence ranking, repeated limitations, compulsory future directions, and stock “research-design inspiration” openings.

Do not require “three key results”, “three pieces of evidence”, a fixed number of subheadings, equal paragraph lengths, or a fixed paragraph pattern. References follow the final section and are not another main section.

For two or more articles produced in one request or queue, perform a batch-level digest audit after the single-article checks. Compare opening syntax, question-mark placement, sentence count, and the relation between sentence one and sentence two. Flag a run in which every card is interrogative, several cards reuse “如果……吗” or “究竟是……还是……”, or several cards follow the same question-then-answer skeleton. Apply the same test to repeated declarative structures. Do not demand artificial alternation; require only that each retained form is the best fit for that paper and that the batch does not read as one template with substituted nouns.

## Audit the method map

- Require one `method_map` record for every analysis needed to understand a principal result. Do not require records for incidental software operations or background concepts.
- Confirm every record maps to an objective visible Methods subheading and gives an `importance` value, purpose, input data, at least one processing step, at least one statistical item, and precise source locators. Treat `outputs` as optional.
- Verify sample size, source, modality, data split, analysis unit, matrix dimension, software and version, algorithm, parameter, covariate, threshold, correction, resampling count, validation design, and any recorded output against the verified research-material set.
- Block any detail filled from convention, another paper, software defaults, or unstated assumptions. Omit ordinary missing parameters silently. Use `critical_missing_details` only when absence directly changes interpretation of a principal conclusion or the user explicitly requested a method-completeness audit.
- Read Methods together with `method_map`. Confirm that `core` analyses receive the most useful technical detail, `supporting` analyses receive enough detail for interpretation, and `routine` analyses are concise. Do not require visible labels, equal detail, a fixed paragraph count, or a fixed section share.
- Check chapter separation: observed values belong in Results; only necessary interpretation belongs in 结果解读; Methods should contain only the design facts needed to reproduce or understand the analysis.
- Permit at most one or two necessary explanatory sentences for an easily misunderstood concept, then require the prose to return to the actual procedure.
- Reject a generic method tutorial, transfer advice, or methodological praise not required to explain this paper.
- Reject parameter-list prose, unnecessary expansion of a named mature pipeline, and a separate output recap after every method.

## Audit emphasis and prose

- Confirm that results are concrete and distinguish principal findings from extensions, null findings, and sensitivity checks. Treat section statistics as descriptive data only: do not fail, warn, pad, or cut solely because of length or percentage.
- Confirm that the introduction is sufficiently developed for the paper's question without repeating method details. Do not compare its length mechanically with Methods or Results.
- Confirm that the 结语 contains no new claim and does not merely copy Results or 结果解读. It should connect the research question and principal empirical relation; analytical logic is optional and should appear only when it adds a paper-specific insight. Do not require a second paragraph, a fixed word count, a limitation, an outlook, or an elevated conclusion.
- Check continuity across sections and subsections. Merge serial itemization when consecutive analyses answer the same question, and require a factual transition when the analytical purpose changes.
- Review paragraph units by scientific purpose rather than a fixed count or character target. Flag a long run of short paragraphs under one subheading as possible fragmentation, then decide whether the sample, pipeline, model, comparison, or closely linked findings form a single analytical unit.
- Reject standalone transition paragraphs whose only role is to announce the next analysis. Attach the transition to the substantive paragraph it introduces, unless it carries an independently sourced finding.
- Keep only indispensable interpretation limits beside individual results. Do not list analyses, metrics, variables, validation steps, or datasets that the study did not use. Permit an absent measurement only when it prevents a concrete misunderstanding of a central conclusion, is treated as essential in the research materials, or the user requested a limitation or completeness audit.
- Prefer a positive definition of the actual analysis over a negative inventory of alternatives. Flag paragraphs that end by stacking “未测量”“未纳入”“没有检验”“无法回答” or similar disclaimers.
- Review corrective editorial phrases such as “不等同于”“不表示”“不能转换为”“不能覆盖”“不能合并为”“不能用于”. Outside 结果解读, prefer the measured quantity or a factual statement of data source and analysis unit. Inside 结果解读, delete an extra verdict when the factual relationship already makes the scope clear.
- Check every subheading for actual scientific content. Reject headings such as “真正值得带走的是跨尺度分析次序”, “关键证据一”, or “结果的边界”.
- Reject canned expressions flagged by the validator, direct address to “读者”, and visible “证据链” organization.
- Review warning words such as “边界”, “收束”, “链条”, “路径”, “框架”, “范式”, “层级”, “真正”, and “值得”. Keep one only when it is precise source terminology rather than editorial decoration.
- Reduce repeated “不是……而是……” constructions, evaluative adjectives, prescriptive advice, and long compound sentences.
- Check repeated paragraph openings such as “研究……” or “作者……”. Treat repetition as an editorial signal, not a hard quota; revise only when the scientific subject can be stated more directly.
- Reject Methods expressions such as “真正值得关注的是”, “最值得借鉴的是”, “这一结果提醒我们”, “从方法学层面来看”, “对于读者而言”, “意义边界”, or “方法边界”.
- Reject technical-report meta-language such as “该模块”, “本模块”, “该步骤输出”, “分析链”, and “证据链”.
- Prefer “研究”, a concrete data/model/result subject, or an omitted subject. Reserve “作者” mainly for source-attributed interpretations and mechanisms; revise repeated “论文进行了”“论文发现”“论文提出”.
- Flag terminal summaries such as “研究进行了结构连接分析” or “研究进行了PLS分析” when the method map contains concrete inputs, operations, or tests that the prose omitted.
- Require objective attribution such as “结果显示”, “作者认为”, or “图3显示” when the epistemic source matters.

Apply the “说了一堆，啥也没说” check: read only the title, 研究速览, result subheadings, and 结语. A scientifically literate reader must be able to state what the paper studied, which core method it used, and what it found. If not, return `QA_BLOCKED` with the missing information.

## Audit natural revision style

- Apply this correction priority: delete redundant wording; preserve a natural sentence; adjust order or connection; add a local explanation; rewrite only as a last resort.
- Compare Results and 结果解读 sentence by sentence. Block direct sentence duplication unless a repeated value is indispensable to the interpretation.
- Do not demand the same number of paragraphs, similar paragraph lengths, or an identical “finding → meaning → limitation → future” pattern across subheadings.
- Review “这些结果共同表明”, “这一发现进一步说明”, “值得注意的是”, “更重要的是”, “总体而言”, “综合来看”, “这一发现提示我们”, “提供了新的视角”, “研究由此表明”, “核心价值在于”, “尚待检验的是”, and similar expressions as possible AI scaffolding. Prefer deletion when the following fact stands on its own; do not merely replace them with synonyms.
- Inspect the final sentence of every paragraph in 结果解读和结语. If it only recaps, ranks, elevates, limits, lists an unperformed analysis, or adds a generic outlook, remove it when the paragraph remains complete.
- Block evidence/value ranking in 结语, including “最稳定的发现”, “最重要的结果”, “最可靠的证据”, “核心价值在于”, and “最大的价值在于”.
- Reject a separate 方法启示 section in version 8. Treat method-level commentary in 结语 as optional. When it is present, confirm that it explains a concrete design decision naturally rather than occupying a standard second-paragraph slot or opening with “研究设计上的启发在于”, “方法学上的启发在于”, “对MRI研究，较有用的是”, or “对计算神经影像研究”.

## Verify figures and safety

- Confirm that every figure has a distinct explanatory role, source figure identifier, caption, source, license note, alt text, permitted adaptation status, and `mobile_display.strategy`.
- Prefer figures that directly support principal results. For dense composites, require a cropped, split-panel, or selected-panel asset that remains legible on a phone while preserving the original figure ID and panel label. Reject a whole composite that is merely shrunk until its labels are unreadable.
- Keep figure source and license metadata in article JSON, the figure list, and QA records. Confirm that the visible HTML shows only the concise caption and does not append a public “来源：” line.
- Confirm that HTML uses the approved system-native font stack without embedding or distributing system font files. Confirm that plugin-generated cover assets use the bundled OFL-licensed Noto Sans SC. Treat unmodified, legally reused raster figures as source works rather than plugin-generated typography.
- Confirm that HTML renders the digest exactly once in the light-grey card between the author line and the 研究速览 heading.
- Require `publication_mode=draft_only`.
- Reject publish, free-publish, mass-send, deletion, replacement, or overwrite actions.
- Verify that no token, AppSecret, cookie, QR code, account credential, raw source PDF, or supplement is included in the WeChat payload.

## Decision

Return `QA_PASSED` or `QA_BLOCKED` first, followed by blocking findings, warnings, article and section statistics, source-manifest status, the method records inspected, and the evidence records inspected.
