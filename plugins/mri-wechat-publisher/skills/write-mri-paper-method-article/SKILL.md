---
name: write-mri-paper-method-article
description: Create or locally revise objective Chinese WeChat interpretations of MRI, cognitive-neuroscience, and related biomedical studies from verified research materials. Use when a selected study must become a source-grounded schema-version-8 article with 研究速览、引言、方法、结果、结果解读、结语, or when an existing article needs a scoped revision that reduces repetition, parameter or statistic dumping, causal overstatement, or formulaic AI prose while preserving claim-level traceability.
---

# Write MRI Paper-and-Method Article

Resolve `<plugin-root>` as the directory two levels above this `SKILL.md`. Resolve schemas and scripts from that root rather than from the active working directory.

## Pass the source gate

1. Require a registered source manifest whose main-paper identity matches the selected record.
2. Require `SOURCE_VALIDATED` before treating the source as sufficient.
3. Treat the main text, supplements, appendices, figure legends, proof, and other verified versions as one internal research-material set. Read every part needed for a central method or result.
4. Prefer the Version of Record, then proof, accepted manuscript, preprint, and other verified versions for conflict resolution. Record provenance internally.
5. Reject unsupported details instead of filling gaps from an abstract, press release, database summary, or general knowledge.
6. Do not generate a formal article when only abstract-level evidence is available.

Set new articles to `schema_version: 8` and set the source gate fields to:

```json
{
  "evidence_level": "FULLTEXT",
  "fulltext_verified": true,
  "source_manifest": "<registered manifest path>"
}
```

Verify the official paper title, journal, DOI and/or PMID, publication date, authorship used in the reference, and source version before drafting.

## Build an internal paper map

Before writing, extract:

- the research background, unresolved question, objective, and any stated hypothesis;
- participants or datasets, modalities, study design, measurements, preprocessing, models, statistical tests, validation, and sensitivity analyses;
- the original Results order, central findings, important negative findings, replication or external-validation results, key numbers, and linked figures or tables;
- the authors' interpretations, stated limitations, and supplement-dependent details.

Use this map to decide emphasis. Do not force a “central conclusion plus three pieces of evidence” template and do not expose the internal map, retrieval path, verification process, or material comparison in the article.

Integrate research materials before drafting. Public prose should state the consolidated method or result, not “补充材料显示”, “proof记录”, “来源材料未说明”, or similar provenance language. Mention a version difference only when it changes a reported method, result, or interpretation; describe the versions and substantive difference directly, without narrating how the difference was discovered.

Before drafting, distinguish the principal answer, the method needed to understand it, the supporting or extension analyses, important null or sensitivity results, and the authors' interpretation. Give these elements different narrative weight instead of presenting every analysis as an equal-sized item.

Write a one- or two-sentence `digest` for the visible grey introduction card. Its job is to answer “why is this paper worth opening?” rather than to miniaturize the study design.

Do not choose a rhetorical format first. Identify the paper-specific entry point first: an empirical contrast, an unresolved ambiguity, a counterintuitive result, a consequential scale or number, a familiar assumption the data revise, or another feature that genuinely earns attention. Then choose the natural form for that content. The digest may be a direct statement, a contrast, an observation, an unanswered question, or a question followed by an answer; these are examples, not a menu to rotate through, and no form is preferred. In particular, a question mark is optional and must not become the default signal for “attractive writing”.

A decisive number may appear when it creates the hook, but do not inventory cohorts, modalities, atlas counts, or pipeline steps. The adjacent 研究速览 owns the compact account of how the study was done and what it found. Do not repeat a sentence or the same sequence of study facts from 研究速览 or 引言.

When drafting more than one article, compare all digests side by side before finalizing them. Revise batch-level sameness such as every card opening with a question, repeated “如果……会……吗”, “究竟是……还是……”, or a fixed “question in sentence one, answer in sentence two” skeleton. Also check declarative cards for repeated sentence architecture. Diversity must follow each paper's content rather than a mechanical alternation rule; do not force a weak statement merely to avoid a question.

## Preserve claim traceability

- Map every quantitative result, method parameter that affects interpretation, anatomical claim, figure, limitation, and reuse condition to the main text or a verified supplement.
- Use precise locators such as PDF page, section, figure, table, supplement file, and supplement page.
- Assign each evidence record one internal `claim_type`: `direct_result`, `author_interpretation`, `editorial_explanation`, or `editorial_extension`.
- Keep this classification in `evidence_map`; do not label visible prose as “证据” or “证据链”.
- Omit any claim that cannot be located in the registered source bundle.

## Build the internal method map

Before writing Methods, identify every core analysis needed to understand a principal result. Examples include image preprocessing and measurement, normative modeling, connectivity, machine learning, clustering, network analysis, multimodal fusion, spatial transcriptomics, longitudinal modeling, mediation, and external validation. Do not use a fixed method list.

Create one `method_map` record per analysis needed to understand the principal findings. Link it to the exact visible Methods subheading and record:

- `importance`: `core` for the main or innovative analysis, `supporting` for extensions or important validation, and `routine` for standard preparation or secondary checks;

- `data`: sample size and source, modality, training/test/reference groups, analysis unit, and an input dimension when the paper reports it or it follows directly from reported counts;
- `processing_steps`: software and reported version, preprocessing, parcellation, measurement, feature construction, algorithm, model inputs, and important parameters;
- `statistics`: model, covariates, association test, multiple-comparison correction, cross-validation, bootstrap, permutation, spatial null or spin test, threshold, robustness test, and external reference data as applicable;
- `outputs`, when useful: variables, matrices, scores, components, weights, predictions, or statistics that define a later analysis or prevent misunderstanding;
- `source_locators`: a precise main-text or supplement locator supporting every entered detail;
- `critical_missing_details`, only when needed: missing information whose absence directly changes how a principal conclusion can be interpreted, or when the user explicitly requests a method-completeness audit.

Require verified data, processing, statistical, and source-location information for each mapped analysis. Leave optional fields empty when they do not apply. Do not create a list of ordinary missing parameters, and never fill a gap from domain convention, another paper, software defaults, or general knowledge.

Render the internal review file with:

```powershell
python "<plugin-root>/scripts/render_method_map.py" <article.json> --output <method-map.md>
```

Do not expose the field labels or `method_map` itself in the public article.

## Preserve before rewriting

For revision work, treat the user's requested scope as a hard boundary. Keep untouched sections byte-for-byte equivalent in structured content; do not opportunistically polish them while changing a later section.

Apply this edit order:

1. delete redundant wording;
2. retain a natural existing sentence;
3. adjust order or local transitions;
4. add a short explanation where the logic is genuinely incomplete;
5. rewrite a sentence only when the earlier operations cannot fix the problem.

Do not proactively turn serviceable prose into a uniformly polished “AI scientific article”. Preserve differences in paragraph length, syntax, and emphasis when they reflect the paper. Before finishing, compare the protected sections with the input and report any intentional change.

## Write the article sections

Write these required sections in this order:

1. 研究速览
2. 引言
3. 方法
4. 结果
5. 结果解读
6. 结语

Use IDs `overview`, `introduction`, `methods`, `results`, `result_interpretation`, and `closing`. Do not create a separate 方法启示 section. A transferable design or analytical idea is optional in 结语, never a slot that must be filled. References follow 结语 and do not count as a main section.

### 研究速览

- Give the reader a compact map of the study. Depending on the paper, include the research question, study object, analytical framework, and principal result, but do not force these into labelled fields or a fixed checklist.
- Keep the section concise enough to orient rather than duplicate the article. Let the paper determine its exact length and emphasis; do not impose a word count.
- State the principal result broadly. Reserve t, p, OR, β, confidence intervals, and other detailed test statistics for Results.
- Do not repeat the same core conclusion in full again in 引言, 结果解读, or 结语. Later sections should add background, evidence, interpretation, or implications rather than replay the overview.
- Do not use fixed labels such as “30秒读懂”, “最重要的结论”, or “一句话收束”.
- Do not duplicate the digest or translate the paper abstract sentence by sentence. After drafting, list the factual units in the digest and opening paragraph mentally; if the same sample scale, data types, analytical sequence, and principal result appear in both, keep the reading motive in the digest and move the compact method-and-result map to 研究速览. For a batch, inspect the cards together and confirm that their rhetorical forms and sentence relations are not being generated from one shared template.

### 引言

- Follow the paper's scientific logic: what is known, what remains unknown, why prior work is insufficient, what this study asks, and the broad approach used.
- Give the background, prior findings, unresolved gap, and study objective enough space to make the research question understandable on its own.
- Include only background needed to understand the research question. Let the paper's conceptual difficulty determine the introduction length; do not force it below Methods or Results.
- Do not repeat the cohort, analytical sequence, or complete principal result already given in 研究速览. End with the unresolved problem when the overview has already stated the study design.
- Do not turn the introduction into a field tutorial or introduce clinical implications and limitations before the results.

### 方法

- Follow the study's actual method organization; do not impose a fixed number of subsections.
- Use short, objective, paper-specific subheadings such as “数据与预处理”, “规范模型”, “结构连接分析”, “PLS分析”, or “外部验证”. Derive them from the paper; do not force these examples onto every article.
- Group consecutive procedures that answer the same scientific question. Start a new subsection only when the data source, analytical purpose, or output changes materially.
- For every core analysis, make the prose sufficient to reconstruct what data entered, how it was processed, and how it was tested. State an output only when it defines a later input, matrix, variable, score, component, or otherwise improves understanding.
- State sample and source, modality, training/test/reference roles, ROI or spatial unit, and a matrix dimension when source-supported.
- State the data, analytical idea, key steps, and core parameters that affect interpretation. Keep full software and parameter provenance in `method_map`; visible prose does not need every reported command, version, tracking setting, threshold, or routine pipeline option.
- State the statistical model, covariates, association method, correction, validation, bootstrap, permutation, spin or spatial null, threshold, robustness test, and external reference when used.
- Name an output explicitly when it is needed later, for example a per-subject score, connectivity matrix, nodal metric, component, gene weight, prediction, or test statistic. Do not end every analysis with a separate output summary.
- Distinguish a general method principle from this paper's implementation without visible meta-labels.
- Allocate detail by `importance`. Explain `core` analyses and innovative methods in detail, summarize `supporting` analyses enough to interpret their results, and compress `routine` preprocessing, standard database enrichment, and secondary sensitivity checks.
- Retain only parameters that define the core analysis, materially change its output, or are needed to understand the result. After naming a mature standard pipeline, compress routine internal operations into one clause unless the study changed them. For tractography, preprocessing, registration, feature extraction, and similar pipelines, do not serially list software, algorithm names, step size, streamline length, count, and defaults when those details are not central to the paper's claim.
- Explain the method used in this paper; do not expand it into a prescriptive tutorial for unrelated studies.
- Permit one or two direct explanatory sentences only when an output or cross-dataset design is easy to misunderstand. Define the concept, then return immediately to the paper's procedure.
- Omit ordinary missing parameters without comment. State a missing detail only when it directly affects interpretation of a principal conclusion or when the user explicitly requests a method-completeness audit.
- Keep methodological praise, transfer advice, field commentary, observed results, and study limitations out of Methods. Methods states what the authors did; Results states what they found; 结果解读 explains only what needs interpretation.
- Treat one paragraph as one complete analytical unit. Keep the sample, preprocessing, and measurement together when they form one input pipeline; keep model fitting, output definition, and closely linked inference together when they answer one question.
- Do not start a new paragraph for every parameter, software step, threshold, or explanatory sentence. Do not impose a paragraph count: split only when the data source, analytical purpose, or inferential stage changes.
- Attach a transition to the substantive paragraph that follows it. Do not leave a short sentence whose only function is to announce the next analysis as a standalone paragraph.
- Do not write vague terminal statements such as “研究进行了结构连接分析” or “研究进行了PLS分析” when the materials support the input, algorithm, or statistical test.
- Avoid parameter-list prose. Connect parameters to the operation they define, and omit routine defaults after a standard pipeline is named.
- Give `core` methods the clearest analytical logic. Compress `supporting` and `routine` methods more aggressively while preserving the data source, purpose, decisive operation, and inferential test.
- Do not use technical-report meta-language such as “该模块”, “本模块”, “该步骤输出”, “分析链”, or “证据链”. State the research procedure directly.

### 结果

- Follow the original Results order by default. Reorder only when it improves readability without changing the paper's logic.
- Include all results needed to answer the research question and support the paper's central conclusion. Include important null results, replication, external validation, and sensitivity analyses when they materially affect interpretation.
- Do not limit the number of results and do not organize them as “三条证据”, “第一层”, or another preset count.
- Use content-specific subheadings that state the actual comparison or finding. Avoid generic labels such as “关键结果”, “核心发现”, and “证据一”.
- Merge consecutive findings that answer the same question. Use fewer, broader subheadings when a paper contains many related analyses, so the principal result, extensions, null findings, and sensitivity checks do not receive identical visual weight.
- For each result, state what was analyzed, what was found, the decisive numbers or figure when available, and its direct meaning. Keep mechanistic speculation, clinical extrapolation, and future work out of this section.
- Keep only statistics that determine whether a principal conclusion is supported. Do not serially report every p value, OR, β, confidence interval, enrichment term, or sensitivity statistic when their direction and corrected significance can be summarized accurately.
- For enrichment results, name the dominant biological themes and retain a representative or decision-critical corrected statistic only when it materially supports the conclusion.
- Report the observed result before any interpretation limit. Replace corrective editorial phrasing such as “不能转换为”“不等同于”“不能覆盖” with the directly observed quantity or a factual description of the data relationship whenever that preserves accuracy.
- Keep a result-specific qualification here only when omitting it would change the numerical or statistical meaning of that result. Move necessary explanation about group-level inference, external atlases, cross-sectional design, causality, or clinical use to 结果解读, and state each recurring point once.
- Merge adjacent result paragraphs when they use the same dataset to answer the same question. Let figures and genuine analytical changes create paragraph boundaries; do not turn each database, enrichment term, sensitivity check, or transition into a separate paragraph.

### 结果解读

- Help explain the reported results rather than imitate a journal Discussion. Select only the questions this paper needs: what a main result means for the research question, why a finding needs explanation, how group and individual or imaging and molecular analyses relate, which result is easily overread, and how a null result or design property changes its interpretation.
- Start from the existing Results and the source-grounded interpretations in the research materials. Prefer the authors' concrete explanation of the main findings; add editorial explanation only when it clarifies an actual relation among analyses. Do not restate each finding in new words. Repeat a statistic, sample size, p value, or effect only when it is necessary for the explanation.
- Focus on what a result means, how it relates to other findings, and which level of analysis it describes. Do not reopen a paragraph by reproducing the full result or its statistics.
- Require interpretive gain. Each paragraph must add at least one useful relation, distinction, or clarification beyond Results: connect two findings, explain what a spatial/statistical relation means, distinguish analysis levels, develop a source-grounded mechanism, or resolve a likely misreading. A paragraph made only of repeated results or limitations has no interpretive gain.
- Let depth come from explaining relationships among findings. Where relevant, connect widespread and regionally heterogeneous effects, group and individual patterns, network position and morphology, imaging and molecular maps, or a phenotype and a related structural measure. Do not create depth by listing more caveats.
- Do not force “main finding → mechanism → limitations → outlook”, a fixed subheading count, or equal paragraph lengths. A clear result may receive no additional paragraph.
- State cross-dataset and inferential facts directly. For example, say that MRI and gene-expression maps come from different samples and are compared at the regional level. Do not append another sentence that merely judges the evidence after the fact is already clear.
- Keep association as association, spatial correspondence as spatial correspondence, cross-sectional age effects separate from disease progression, and group patterns separate from individual diagnosis. Do not invent a mechanism.
- For correlations, spatial associations, normative-reference comparisons, PLS maps, and gene-set enrichment, do not call the result a causal effect, direct mechanism, or mechanism evidence unless the study design independently supports that claim.
- Default to describing what the study measured and analyzed. Do not list analyses, metrics, variables, validation steps, or datasets that the study did not use. Mention an absent measurement only when omitting it would create a concrete misunderstanding of a central conclusion, the research materials treat it as essential to that interpretation, or the user explicitly requests a limitation or method-completeness audit.
- When a scope statement is necessary, integrate it beside the claim it qualifies and state it once. Prefer a positive definition such as “研究以加权度表示总体连接强度” over an inventory such as “未纳入介数中心性、参与系数和个体连接”.
- Add an interpretation limit only when it changes how a central result should be read. Integrate it into the relevant sentence; do not append a generic disclaimer or make every paragraph end with a boundary statement.
- Do not end successive paragraphs with “未测量”“未纳入”“没有检验”“无法回答” or similar disclaimers. If deleting a limitation leaves the scientific meaning intact, delete it. A null result that the study actually tested may be discussed when it changes interpretation.
- Use a few direct topic subheadings only when they separate genuinely different result themes. Do not fragment the section for visual symmetry.
- Do not require a summary sentence at the end of a paragraph. If the final sentence only recaps, ranks, elevates, limits, or adds a generic future direction, delete it when the paragraph remains complete.

### 结语

- State the main knowledge added by the study and why it matters for the relevant MRI or neuroimaging problem. Use concrete objects, measures, and relations as sentence subjects. Do not recap every result, sample size, statistic, limitation, or future direction.
- Keep 结语 concise. Do not repeat the method pipeline, all findings, or detailed statistics.
- Decide first whether a method-level sentence adds information that is not already obvious from Methods. If not, end with the study-level synthesis; one paragraph is sufficient. Do not create a second paragraph by default.
- When the paper does contain a genuinely transferable design choice or analytical logic, explain the paper-specific reason the analyses were ordered or combined and the ambiguity this resolved. Integrate it wherever it fits; it may be one sentence in the main paragraph or a second paragraph. Do not repeat software, parameters, or a step-by-step tutorial.
- Do not introduce that optional point with a reusable signpost such as “研究设计上的启发在于”, “方法学上的启发在于”, “对MRI研究，较有用的是”, or “对计算神经影像研究”. Start from the concrete contrast, dataset, model, region, or inferential problem instead.
- A concrete next measurement may be mentioned only when it follows directly from the study and clarifies the remaining question. Do not turn the ending into generic advice or praise.
- When no method insight is justified, do not create an empty method comment or a separate 总结 section merely to satisfy a template.
- Avoid a two-sentence compressed copy of Results. The section should connect the research question, the main empirical relation, and—when present—the analytical logic, while remaining shorter than the substantive Results and Result Interpretation.
- Do not rank evidence or value with “最稳定的发现”, “最重要的结果”, “最可靠的证据”, “核心价值在于”, or similar phrases.
- Do not require a limitation, future direction, or uplifting final sentence. End when the necessary information is complete.
- Do not add a callout, bullets, a fixed takeaway count, or new claim.

## Control emphasis and length

- Let evidence density and paper complexity determine total length; do not target a fixed character range.
- Report section lengths for review, but never block, warn, pad, or cut an article solely because a section falls outside a percentage range or is longer than another section.
- If an editor requests a rough planning guide, describe ranges as non-validating and let the source determine the actual balance. Do not assign a fixed share to 结果解读或结语.
- Ensure the paper's results receive more space and specificity than generic commentary.
- Use as many figures as the explanation needs, provided each figure is relevant, mobile-readable, identity-verified, and legally reusable. Do not target a fixed figure count.
- Describe each figure objectively: what is compared, what changes, and which reported result it supports.

## Use objective Chinese

- Prefer “研究”, a concrete dataset/model/result, or an omitted subject. Reserve “作者” mainly for source-attributed interpretations and proposed mechanisms in 结果解读. Reduce “论文进行了”“论文发现”“论文提出”等以“论文”为动作主语的表达。
- Use evaluative adjectives only when the source supplies a comparison or criterion.
- Avoid addressing “读者” or telling the audience what it should think.
- Avoid formulaic expressions including “真正值得带走的是”, “一句话收束”, “全文可以收束为”, “本文只需记住”, and repeated “不是……而是……”.
- Treat words such as “边界”, “收束”, “链条”, “路径”, “框架”, “范式”, “层级”, “真正”, and “值得” as warning signs; use them only when they are precise source terminology.
- Split long compound sentences when a single sentence exceeds roughly 60 Chinese characters and contains multiple logical turns.
- Write subheadings that name the actual topic or finding, not the act of interpreting it.
- Add transitions at genuine analytical changes: say why an analysis follows, which preceding question it uses, or what new aspect it tests. Avoid generic sequencing phrases and do not repeat the same transition pattern.
- Avoid an editor-like sequence of prohibitions in visible prose, including repeated “不等同于”“不表示”“不能转换为”“不能覆盖”“不能合并为”“不能用于”. Preserve the scientific limitation by describing the actual data, analysis unit, and measured outcome, then explain the inferential scope once in 结果解读 when it matters.
- In Methods, also avoid “真正值得关注的是”, “关键证据”, “意义边界”, “方法边界”, “重新理解”, “这一结果提醒我们”, “最值得借鉴的是”, “从方法学层面来看”, and any address to the reader. Replace each with the concrete data, operation, statistic, or output when possible.
- Vary paragraph subjects only when the scientific subject changes. Prefer the dataset, model, comparison, or measured outcome over repetitive paragraph openings such as “研究……” and “作者……”.
- Across the article, avoid repeated AI-style transitions and verdicts such as “这些结果共同表明”, “这一发现进一步说明”, “值得注意的是”, “更重要的是”, “总体而言”, “综合来看”, “这一发现提示我们”, “提供了新的视角”, “核心价值在于”, “尚待检验的是”, and “未来研究需要进一步”. These expressions are not a thesaurus problem: delete them when a concrete scientific subject can carry the sentence.
- Inspect the last sentence of every paragraph in the final two sections. Prefer deletion when it only repeats, evaluates, elevates, limits, lists an unperformed analysis, or adds generic outlook after the paragraph is already complete.

## Title and output contract

- Use `<journal name or recognized abbreviation> | <content-specific hook>`.
- Count only the hook after ` | `; it must not exceed 20 characters.
- Verify the journal label against the source record and prefer a specific finding over a slogan or copied paper title.
- For every figure, prefer a principal result and declare `mobile_display.strategy` as `native`, `cropped`, `split_panel`, or `selected_panels`. When cropping, splitting, or selecting panels, retain `source_figure_id`, panel labels, provenance, and licence metadata. Do not shrink an unreadable composite figure into a phone-width image.
- Produce JSON conforming to `<plugin-root>/schemas/article.schema.json` with `schema_version: 8`, a verified importance-ranked `method_map`, and a mobile display strategy for every figure.
- Bind the article to the registered source manifest, preserve the internal evidence map, and require `qa-wechat-article` before rendering or draft delivery.
- Never invent sample sizes, parameters, regions, statistics, software versions, references, identifiers, licenses, or unavailable supplement results.
