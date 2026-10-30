[中文](#中文) | [English](#english)

<a id="中文"></a>
# MRI 文献公众号助手

`mri-wechat-publisher` 是面向 MRI、认知神经科学及相关医学与生物学论文的 Codex 工作流插件。它将可核验的论文材料转换为“文献解读＋方法解析”中文文章，完成结构、证据、图片许可和发布安全质检，生成微信公众号兼容 HTML，并可在人工批准后保存到公众号草稿箱。

插件只支持保存草稿，不包含自动发表、群发、删除或覆盖线上内容的功能。

当前稳定版本：[v0.9.0](https://github.com/Learner97/mri-wechat-publisher/releases/tag/v0.9.0)。

版本8重点减少批量文章中的模板痕迹：灰框根据论文内容动态选择陈述、反差、开放问题或自问自答，问句不作为默认格式；研究速览再说明研究怎样开展及主要发现。结语首先收束论文增加的认识，MRI 或研究设计启示只有在带来论文特异的新信息时才自然写入，第二段不是必选项。

## v0.9.0：来源事实覆盖与手机选图

本版将首次来源阅读、正文生成和既有科学审校连接起来：先冻结高价值事实，再检查正文是否准确覆盖、合理省略、重要遗漏、错误/过度解释或来源不足。Python负责来源字节、摘录、定位和确定性检查；语义审校判断来源是否真正支持解释。未完成的覆盖核查不能登记正式QA，普通细节不因此全部加入正文。

选图提前到正文生成前。检查430px视口/422px图宽下必要坐标、图例和比较标签，区分核心信息与不影响当前结论的辅助标签；核心失败不能以正常加载替代通过。ND原图不裁剪，找不到合法可读整图时阻断。缓存只复用未变化的确定性结果，不继承失效的QA或批准。当前无法从宿主获得逐篇模型usage时记录“未测量”。

## 能力

- “研究速览—引言—方法—结果—结果解读—结语”中文科学文章规范；灰框动态提供论文特异的阅读动机，研究速览交代方法与发现，结语不强制附加方法启示；
- 结构化文章 JSON 和微信公众号兼容 HTML；
- 核心结果高清原图整图优先，仅在过密或过高且确有必要时按原面板最小拆分，保留共享色条、坐标、图例和标签；
- HTML只调用设备系统字体，不携带字体文件；正式封面只取自当前论文原图；
- 事实、引用、图片许可与发布安全检查；
- PubMed、OpenAlex、PMC 和 Nature 文献辅助脚本；
- 五篇候选的元数据级全文与补充材料可用性检查，推荐阶段不下载正文；
- 付费墙或状态未知论文仍可入选，全文状态不改变科学评分；
- 公开来源或用户上传文件的哈希清单、身份核验与全文证据门控；
- SQLite 推荐、去重、排队和草稿状态管理；
- 微信公众号草稿 API；
- 可选的已登录浏览器备用通道。

文章生成质量取决于 Agent 能否读取并核验论文全文、补充材料、图注和许可信息。插件不会用猜测填补缺失证据。

## Codex 安装

需要支持插件的 Codex CLI 或桌面端，以及 Git 和 Python 3.11–3.12。

```powershell
codex plugin marketplace add Learner97/mri-wechat-publisher
codex plugin add mri-wechat-publisher@solel-mri-plugins
```

安装或升级后，请新建一个 Codex 任务，使新 Skill 生效。

## 全文来源门控

推荐检索根据 PMCID、Europe PMC 和 OpenAlex 元数据检查公开可用性，但不请求或缓存 PDF、全文 HTML/XML 正文和补充材料。状态分为：

- `PUBLIC_FULLTEXT_CONFIRMED` / `PUBLIC_HTML_CONFIRMED`：选择后再获取并核验合法公开全文；
- `USER_UPLOAD_REQUIRED`：等待用户提供其合法取得的主论文 PDF，可附补充材料；
- `ACCESS_UNKNOWN`：元数据不足，选择后重新核验，必要时请求用户上传。

全文状态不参与科学评分，也不阻止付费墙论文进入五篇候选。选择后，来源文件必须位于工作区数据目录，生成 SHA-256 清单，并通过题名、DOI/PMID 或出版商记录核验。正式成稿必须达到 `SOURCE_VALIDATED`；摘要、新闻稿和数据库简介不能冒充全文证据。

```powershell
python scripts\build_source_manifest.py --cycle-id <cycle-id> --source-kind USER_UPLOAD --main <data-dir>\<cycle-id>\input\paper.pdf --title "<paper title>" --doi "<doi>" --matched-by doi --matched-by title --verification-evidence "DOI and title verified" --output <data-dir>\<cycle-id>\source-manifest.json
python scripts\workflow_state_db.py --db <data-dir>\workflow.db register-source-manifest --cycle-id <cycle-id> --manifest <data-dir>\<cycle-id>\source-manifest.json
python scripts\workflow_state_db.py --db <data-dir>\workflow.db source-readiness --cycle-id <cycle-id> --decision READY --detail "Identity and full text verified"
```

## 文章结构与版本兼容

新生成的文章使用 `schema_version: 8`，正文一级结构为：

1. 研究速览；
2. 引言；
3. 方法；
4. 结果；
5. 结果解读；
6. 结语。

版本8以“研究速览”取代摘要。浅灰色 digest 先找到每篇论文最有辨识度的阅读入口，再决定采用直接陈述、现象反差、观察、开放问题或自问自答；问句不是默认形式，这些形式也不是轮换模板。批量写作还要横向检查开头语法、问号位置和两句之间的关系。研究速览再用灵活的短篇幅交代研究怎样开展及主要发现，但不写死字段或字数，也不提前罗列 t、p、OR、β 等详细统计量。

结果解读说明结果意味着什么、不同结果之间如何联系及确实影响理解的解释范围，不模仿 SCI Discussion，也不把结果换一种说法重写。相关分析、空间对应、PLS 和基因富集保持关联性措辞，不写成直接因果或机制证据。版本8不单独设置“方法启示”；结语首先说明研究增加的认识，只有当具体分析逻辑带来额外信息时才自然写入，不默认生成第二段。

修改旧稿时，未在用户范围内的研究速览或摘要、引言、方法和结果保持不变。编辑优先级为“删除多余表达—保留自然原句—调整句序和衔接—局部补充解释—必要时重写”，不主动把原文统一润色成过度工整的 AI 科研文风。

写作与 QA 会区分研究直接结果、作者解释和编辑说明。版本5至版本8要求分析进入内部 `method_map`，按 `core`、`supporting`、`routine` 标记重要性，记录数据、处理步骤、统计检验、必要输出和研究材料定位，并生成 `method-map.md` 供人工核查。内部字段不会显示在正文中；正文整合主文、补充材料、附录和已核验版本，不暴露检索、核查或材料比较过程。

方法部分突出数据、分析思路、关键步骤和核心参数。完整软件、命令和参数来源保留在 `method_map`；公开正文不连续罗列软件版本、算法、步长、流线长度、流线数量和常规阈值。结果部分只保留决定主要结论成立与否的统计量，次要数值和富集条目按方向、范围或主要主题概括。

常规未报告参数默认省略，也不主动写“未报告”“未进一步说明”或“来源材料未提供”。只有缺失信息直接影响主要结论解释，或用户明确要求审查方法完整性时才指出。正文优先使用“研究”、具体数据/模型主语或省略主语；“作者”主要用于讨论观点和机制解释，并避免“该模块”“该步骤输出”“分析链”等技术报告式元语言。

图片的来源、许可和 `mobile_display` 策略保存在 JSON、图片清单和 QA 记录中，公开 HTML 只显示简洁图注。可读原图必须优先整图保留；只有过密组合图或正文高宽比达到约1.8时才考虑必要的面板裁剪，不能为版式统一裁图。不得丢失共享色条、坐标、图例和必要标签，也不得把原文图3重编号为推文图2。封面同样只用本篇原图。总字数、章节占比和配图数量不设硬性目标。

## 新版QA的内部记录

在现有写作/QA流程中维护以下内部文件，结构及短示例见[验收文档](docs/acceptance-tests.md#来源事实覆盖与选图预检第二轮)：

- `work/research-facts.json`：正文前冻结的来源事实、实际分析分母、关键定义及定位；构建器生成同源的可读Markdown。
- `work/fact-coverage-review.json`：现有语义审校对所选事实的判断，绑定当前事实及文章哈希，不以布尔标志代替来源核验。
- `work/figure-readability.json`及真实截图：核心/辅助标签、具体可读性结论、当前图片与截图哈希。

写作前可用现有 `figures` 结构保存候选JSON，执行 `python <plugin-root>/scripts/prepare_article.py <figure-candidates.json> --figures-only`。它只生成原图检查页，不生成正文、不批准QA。未知或失败状态保留阻断；确认问题后只修正对应段落。修改事实、正文、图片、截图或审查决定后，旧QA和用户批准失效。

## 固定输入，一键复现

写作完成后冻结 schema 8 的 `article.json` 与论文原图，统一执行：

```powershell
python <plugin-root>\scripts\prepare_article.py <article.json>
```

同一份输入和插件代码会输出字节一致的 `article.html`、`preview.html`、`wechat-upload.html`、`figure-review.html`、内部证据/方法/图片清单及 `bundle-manifest.json`。仅 `preview.html` 内嵌真实图片；`article.html` 为轻量跳转入口，图片检查页引用同一份本地原图，避免重复保存大图片。上传版含占位地址，仅供获得授权后的草稿接口使用。清单保存输入、渲染器和输出SHA-256；代码升级或任何输入变化会反映在哈希中。这里复现的是固定稿件和资产的成品，不保证重新调用模型写作仍得到逐字相同的文案。

新 schema 8 正式稿的封面和配图须登记 `image_provenance`（`original_path`、`original_sha256`、`source_locator`），以及 `mobile_display` 的原图号、面板与复核说明。整图逐像素核对；必要裁图还须记录 `crop_reason`、`crop_box` 与实际核查后的 `annotations_preserved=true`，并无损保存。历史schema 8重新交付时需补齐来源记录；schema 1–7按历史规范兼容。

`LOCAL_CHECKS_PASSED` 只表示结构与文件核查通过。科学证据、实际许可和430px手机端可读性仍需人工复核，全部完成后才能登记最终 `QA_PASSED`。图片不可读时应寻找高清源或其他原图，不能用生成图替代。

全部实际复核完成后，用同一入口的 `--record-qa --scientific-review "实际科学复核说明" --license-review "实际许可复核说明" --visual-review "实际430px检查说明"` 记录 `qa-review.json`。该操作记录已完成的复核，并不代替复核。`set-artifacts` 校验当前版本并登记哈希；获得用户明确授权后，`approve-draft` 才生成 `draft-approval.json`。保存接口会核对整份标准HTML及JSON、原图、成稿清单和复核/批准记录，任何变化均使旧版本记录失效。

写作规则统一维护于 [编辑规范](docs/editorial-profile.md)；各Skill只保留自身流程与检查职责。JSON Schema负责结构，Python校验器负责来源、科学写作和图片等业务约束。

待审稿修订后可以重新执行 `set-artifacts` 登记新的已复核版本；内容或QA记录变化会清除旧批准，完全相同版本的重复登记保留已有批准。已保存周期不因此重开或改动队列。

`schema_version: 1` 至 `schema_version: 7` 仅用于兼容已有文章。旧文章仍可校验、渲染和进入原有草稿流程；新文章必须使用版本8。此次兼容不会修改历史 JSON、已生成 HTML、SQLite 记录或公众号草稿。

HTML恢复原始设备字体栈：`-apple-system`、`BlinkMacSystemFont`、`Segoe UI`、`PingFang SC`、`Hiragino Sans GB`、`Microsoft YaHei` 和通用无衬线回退。这里只调用用户设备已经安装的字体，不复制、打包、嵌入、下载或再分发字体文件。正式封面只使用当前论文原图，合法复用的论文原始栅格图不修改数据和图内文字。两张已有测试封面只用于离线夹具，schema 8正式稿会拒绝将它们作为原图，即使复制或改名。`digest` 同时作为公众号草稿元数据，并在作者行与“研究速览”之间以浅灰色导读卡显示一次。

正文按科学问题组织段落，不固定各节篇幅或段落数。连续步骤或结果若回答同一问题，应合并为完整的分析单元；只负责报幕的短过渡句不单独成段。群体推断、外部图谱、横断面设计和临床适用范围只在确实影响理解时进入结果解读，并直接陈述数据关系。默认不列举研究未测量、未纳入或未检验的内容；必要范围说明与其限定的主张放在一起，不在段尾连续追加免责声明。


## Python 环境

在用户工作区创建独立环境，并从插件根目录的依赖清单安装完整工作流依赖；不要在 Codex 的插件缓存目录中创建虚拟环境：

```powershell
py -3.12 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r <plugin-root>\requirements.txt
```

将 `<plugin-root>` 替换为 Codex 安装后的插件根目录。Linux/macOS 可以使用等价的 `python3 -m venv .venv`。正式成稿不需要封面生成器、Windows `System.Drawing` 或字体文件。

正式发行包已移除旧封面生成器、字体和写死历史轮次的一次性推荐脚本；它们不再是运行依赖。日常推荐统一走状态库排除、检索、来源检查和 `create-cycle`。通用 `tools/render_jats_evidence_pdf.py` 保留为可选内部证据阅读工具，额外需要 ReportLab，其 `--font` 由调用者提供合法字体，不生成公众号图片。

## 工作区配置

插件代码和用户数据分离。默认在当前工作区创建：

```text
.mri-wechat-publisher/
├── workflow.db
├── automation-workflow-state.json
├── publication-registry.json
└── draft-receipt.json
```

可以通过环境变量指定持久数据目录：

```powershell
$env:MRI_WECHAT_DATA_DIR = 'D:\Analysis\mri-wechat-data'
```

为兼容早期本地版本，如果插件自己的 `output/workflow.db` 已存在且工作区尚无数据库，程序会继续使用该旧库。新安装不会在插件目录创建状态库；设置 `MRI_WECHAT_DATA_DIR` 可始终覆盖自动选择。

数据库只保存非敏感工作流元数据。不要把数据库或文章输出写入插件安装目录。

## 微信草稿凭据

草稿 API 需要使用者自己的公众号 AppID、AppSecret、草稿箱与素材接口权限，以及公众号后台接受的公网出口 IP 白名单。请先在[微信公众平台](https://mp.weixin.qq.com/)确认账号接口权限，并参考微信官方的[新增草稿](https://developers.weixin.qq.com/doc/offiaccount/Draft_Box/Add_draft.html)与[稳定版接口调用凭据](https://developers.weixin.qq.com/doc/offiaccount/Basic_Information/getStableAccessToken.html)文档。优先使用操作系统环境变量：

```powershell
$env:WECHAT_APP_ID = '<your-app-id>'
$env:WECHAT_APP_SECRET = '<your-app-secret>'
```

也可以复制仓库根目录 `.env.example` 为工作区 `.env`，或使用 `MRI_WECHAT_ENV_FILE` / `--env-file` 指向安全文件。不要把 AppSecret 写入命令行历史、日志、文章、数据库、测试夹具或聊天记录。

浏览器备用通道要求宿主具备浏览器或 Chrome 控制能力，并且用户已经登录微信公众号后台。该能力不是本插件自带连接器；不可用时应停止并报告，而不是请求密码、Cookie 或二维码。

写入前可以先检查凭据；命令不会打印 access token：

```powershell
python <plugin-root>\scripts\wechat_draft_api.py article.json wechat-upload.html --check-token-only
```

普通调用默认是 dry-run，不访问微信接口，但必须能够解析一个实际存在的封面文件。封面可以写在文章 JSON 的 `cover.path` 中，也可以传入 `--cover`；相对路径以文章 JSON 所在目录为基准：

```powershell
python <plugin-root>\scripts\wechat_draft_api.py article.json wechat-upload.html
```

缺少封面或封面文件不存在时，dry-run 返回 `DRAFT_SAVE_BLOCKED`，不会误报 `DRY_RUN_READY`。只有用户明确同意保存草稿后，才可以同时加入以下两个参数：

```text
--execute --approval-token USER_APPROVED_DRAFT_ONLY
```

## 离线验证

以下检查不访问网络，也不会写入真实微信草稿：

```powershell
python scripts\self_test.py
python scripts\check_font_policy.py
python -m unittest discover -s scripts -p "test_*.py"
python scripts\validate_article.py examples\phase1-test-article.json
```

状态库默认使用 `MRI_WECHAT_DATA_DIR`，否则使用当前工作区的 `.mri-wechat-publisher/`：

```powershell
python scripts\workflow_state_db.py init
python scripts\workflow_state_db.py status
python scripts\workflow_state_db.py check
python scripts\workflow_state_db.py recommendation-exclusions
python scripts\workflow_state_db.py select-order --choices 2,3
python scripts\workflow_state_db.py queue-status
python scripts\workflow_state_db.py source-status --cycle-id <cycle-id>
```

## 安全边界

- 未通过 `QA_PASSED` 的文章不能进入草稿箱；
- 实时 API 写入同时需要 `--execute` 和精确人工批准标记；
- 本插件没有发表、群发、删除或覆盖线上内容的 API 实现；
- HTML 渲染成功不代表微信草稿保存成功；
- 所有图片必须记录来源、图号、图注、许可和改编条件。

## 许可

代码和原创文档以 MIT License 发布。论文全文、出版商页面、补充材料和第三方图片仍受各自许可证及版权条款约束，不因本插件的许可证而改变。

---

<a id="english"></a>
# MRI WeChat Publisher

`mri-wechat-publisher` is a Codex workflow plugin for MRI, cognitive neuroscience, and related biomedical papers. It converts verified source material into Chinese paper-and-method articles, validates structure, evidence, figure licensing, and publishing safety, renders WeChat-compatible HTML, and can save an explicitly approved draft.

The plugin is draft-only. It does not implement automatic publishing, mass sending, deletion, or overwriting of live content.

Current stable release: [v0.9.0](https://github.com/Learner97/mri-wechat-publisher/releases/tag/v0.9.0).

Version 8 specifically reduces template artifacts across article batches. The grey digest selects a statement, contrast, open question, or question with an answer from the paper itself, with no default question form; Research Overview then explains how the study was conducted and what it found. Closing first states what the study adds. MRI or study-design implications appear only when they contribute paper-specific information, and a second paragraph is never mandatory.

## v0.9.0: source-fact coverage and phone-first figure selection

This release connects the first source reading to the existing scientific review: freeze high-value source facts, then assess accurate coverage, reasonable omission, important omission, misinterpretation or insufficient evidence. Python verifies source bytes, excerpts, locations and deterministic constraints; semantic review determines whether the evidence supports the claim. Incomplete coverage prevents formal QA without forcing every ordinary detail into the article.

Inspect essential coordinates, legends and comparison labels at a 430px viewport/422px figure width before writing. Separate genuinely auxiliary labels from essential information; successful loading is not readability. Do not crop ND figures to fix legibility; block if no suitable legal original is available. Caching reuses unchanged deterministic results, never stale QA or approval. Per-article model usage is marked unmeasured when the host does not expose it.

## Capabilities

- A Chinese scientific article contract with Research Overview, Introduction, Methods, Results, Result Interpretation, and Closing, including a paper-specific digest and an optional method-implication paragraph;
- Structured article JSON and WeChat-compatible HTML;
- Concise public figure captions with provenance and licensing retained in internal QA records;
- Device-native HTML typography without bundled fonts, and covers sourced only from the selected paper;
- Evidence, citation, image-license, and publishing-safety checks;
- Helper scripts for PubMed, OpenAlex, PMC, and Nature sources;
- Metadata-only full-text and supplement availability checks for the final five candidates, with no source download during recommendation;
- Scientific ranking that remains independent from access status, so paywalled and unknown-access papers stay eligible;
- Hashed source manifests, paper-identity verification, and evidence gates for public or user-provided files;
- SQLite-based recommendation, deduplication, queue, and draft-state tracking;
- WeChat Official Account draft API integration;
- An optional fallback through an already signed-in browser.

Output quality depends on the host Agent's access to the full paper, supplements, figure legends, and licensing evidence. Missing evidence is blocked rather than guessed.

## Install in Codex

The plugin requires a plugin-capable Codex CLI or desktop app, Git, and Python 3.11–3.12.

```powershell
codex plugin marketplace add Learner97/mri-wechat-publisher
codex plugin add mri-wechat-publisher@solel-mri-plugins
```

Start a new Codex task after installation or upgrade so that new Skills are loaded.

## Full-text source gate

Recommendation checks use PMCID, Europe PMC, and OpenAlex metadata without requesting or caching PDFs, full-text HTML/XML bodies, or supplements. `PUBLIC_FULLTEXT_CONFIRMED` and `PUBLIC_HTML_CONFIRMED` sources are fetched only after selection. `USER_UPLOAD_REQUIRED` and `ACCESS_UNKNOWN` preserve a path for the user to provide a legally obtained main PDF and any supplements.

Access status does not affect scientific ranking. Selected files stay in the workspace data directory, receive a SHA-256 manifest, and must match the selected title, DOI/PMID, or publisher record. Formal writing requires `SOURCE_VALIDATED`; abstracts, press releases, and database summaries cannot substitute for full-text evidence.

## Article structure and compatibility

New articles use `schema_version: 8` with Research Overview, Introduction, Methods, Results, Result Interpretation, and Closing. The grey digest starts from the paper-specific reason to read, then adopts the natural form: direct statement, contrast, observation, open question, or question with an answer. No form is preferred, and batch writing includes a side-by-side audit for repeated syntax and question patterns. Research Overview then gives the compact method-and-result map without previewing detailed statistics. The internal `method_map` ranks analyses as `core`, `supporting`, or `routine` and records data, processing, statistics, useful outputs, and research-material locators.

Core and innovative analyses receive the most detail; software command chains, noncritical acquisition or tracking settings, standard preprocessing, routine database enrichment, and secondary sensitivity checks are compressed. Methods foreground the analytical logic, key steps, and parameters that materially affect interpretation. Ordinary unreported parameters are omitted silently. A missing detail is stated only when it directly changes interpretation of a principal conclusion or the user explicitly requests a method-completeness audit. Outputs are described only when they define a later variable, matrix, score, or component.

Relative section length and subsection count are determined by the paper. Results retain only the statistics needed to establish the main conclusions instead of listing every p value, odds ratio, coefficient, or enrichment term. Result Interpretation explains meaning, relationships among findings, and only the boundaries that materially affect interpretation; it does not restate the result paragraphs. Correlations, spatial correspondence, PLS weights, and gene-set enrichment are not written as direct causal or mechanistic evidence. Closing states what the study adds without replaying the full workflow or every result. A neuroimaging or study-design implication is included only when it adds paper-specific information and may be omitted entirely. When revising an existing draft, the workflow preserves sections outside the requested scope and prefers deletion or local adjustment over wholesale rewriting.

Total length and figure count are evidence-driven. Section shares are descriptive only. Prefer complete, high-resolution original figures from the selected paper, including the cover. Crop only a genuinely unreadable dense composite or an excessively tall body figure, preserve shared color bars, axes, legends and original numbering, and record provenance and the exact lossless crop. Public HTML shows concise captions. Keep the established system font stack, spacing, blue headings and grey digest card.

Run `python <plugin-root>/scripts/prepare_article.py <article.json>` to reproduce a frozen article bundle. `preview.html` embeds images once; `article.html` is a lightweight entry, `figure-review.html` references the local originals, and `wechat-upload.html` is the separate upload fragment. Input, renderer and output SHA-256 hashes are recorded in `bundle-manifest.json`. `LOCAL_CHECKS_PASSED` does not replace scientific, reuse-license or phone-readability review. Record completed reviews with `--record-qa` and all three review notes; SQLite registration, user approval and API execution check the exact reviewed artifacts. The editorial profile is the single writing authority; the JSON Schema owns structure. New schema 8 production assets require provenance and inspection notes; schema 1–7 retain their legacy validation. Rerendering frozen inputs is reproducible; a new model-generated draft is not promised to be verbatim identical.

## Internal records for formal QA

The existing writing/QA stages maintain `work/research-facts.json` before drafting, source-supported decisions in `work/fact-coverage-review.json`, and `work/figure-readability.json` with real phone-width screenshots. Formats are documented in [acceptance tests](docs/acceptance-tests.md). The builder derives readable fact notes from the same JSON; internal review fields never appear in public HTML.

Run `python <plugin-root>/scripts/prepare_article.py <figure-candidates.json> --figures-only` before prose generation using the existing `figures` structure. It produces an original-figure inspection page, without a draft or QA approval. Keep unresolved facts/readability blocked and repair only affected paragraphs. Changes to facts, body, assets, screenshots or review decisions invalidate prior QA and approval.

## Python environment

Create an isolated environment in the user's workspace, not inside the Codex plugin cache:

```powershell
py -3.12 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r <plugin-root>\requirements.txt
```

Replace `<plugin-root>` with the installed plugin directory. On Linux or macOS, use the equivalent `python3 -m venv .venv` commands. Production articles need no cover generator, Windows `System.Drawing`, or bundled font file.

Legacy cover generators, fonts and hard-coded recommendation-round scripts are excluded from the stable distribution and are not runtime dependencies or workflow entry points. Retain existing PNGs only as offline fixtures; schema 8 production image checks reject these exact fixture images even if renamed or copied. Normal recommendations use database exclusions, source checks and `create-cycle`. The reusable `tools/render_jats_evidence_pdf.py` remains an optional internal reader requiring ReportLab and an explicitly supplied, legally usable `--font`; it does not generate WeChat images.

## Workspace data

Code and user data are separated. By default, runtime state is stored under the active workspace:

```text
.mri-wechat-publisher/
├── workflow.db
├── automation-workflow-state.json
├── publication-registry.json
└── draft-receipt.json
```

Override the location when needed:

```powershell
$env:MRI_WECHAT_DATA_DIR = 'D:\Analysis\mri-wechat-data'
```

For backward compatibility, an existing legacy `output/workflow.db` inside the plugin is reused only when the workspace has no database. New installations do not create runtime state inside the plugin, and `MRI_WECHAT_DATA_DIR` always overrides automatic selection.

The database stores non-secret workflow metadata only. Do not write databases or article output into the installed plugin directory.

## WeChat draft credentials

Draft API access requires the user's own Official Account `AppID`, `AppSecret`, draft and permanent-material API permissions, and a public egress IP accepted by the account's allowlist configuration. Check access in the [WeChat Official Account platform](https://mp.weixin.qq.com/) and consult the official [Add draft](https://developers.weixin.qq.com/doc/offiaccount/Draft_Box/Add_draft.html) and [stable access token](https://developers.weixin.qq.com/doc/offiaccount/Basic_Information/getStableAccessToken.html) documentation.

Prefer operating-system environment variables:

```powershell
$env:WECHAT_APP_ID = '<your-app-id>'
$env:WECHAT_APP_SECRET = '<your-app-secret>'
```

Alternatively, copy the repository's `.env.example` to `.env` in the user's workspace, or point `MRI_WECHAT_ENV_FILE` / `--env-file` to a protected file. Never place an AppSecret in shell history, logs, article data, databases, test fixtures, or chat messages.

Check credentials without printing the token or writing a draft:

```powershell
python <plugin-root>\scripts\wechat_draft_api.py article.json wechat-upload.html --check-token-only
```

The normal command is a dry-run and makes no WeChat request, but it must resolve a real cover image. Configure `cover.path` in the article JSON or pass `--cover`; relative paths are resolved from the article JSON directory:

```powershell
python <plugin-root>\scripts\wechat_draft_api.py article.json wechat-upload.html
```

Missing or nonexistent cover images return `DRAFT_SAVE_BLOCKED`, never `DRY_RUN_READY`. Only after explicit user approval may a caller add both:

```text
--execute --approval-token USER_APPROVED_DRAFT_ONLY
```

The optional browser fallback requires browser or Chrome control in the host Agent and an existing user-managed login. It is not a connector bundled with this plugin. If unavailable, stop and report the limitation; never request passwords, cookies, or QR codes.

## Offline validation

These commands make no network request and do not write a live WeChat draft:

```powershell
python scripts\self_test.py
python scripts\check_font_policy.py
python -m unittest discover -s scripts -p "test_*.py"
python scripts\validate_article.py examples\phase1-test-article.json
```

Workflow-state commands use `MRI_WECHAT_DATA_DIR` or the active workspace's `.mri-wechat-publisher/` directory:

```powershell
python scripts\workflow_state_db.py init
python scripts\workflow_state_db.py status
python scripts\workflow_state_db.py check
python scripts\workflow_state_db.py recommendation-exclusions
python scripts\workflow_state_db.py select-order --choices 2,3
python scripts\workflow_state_db.py queue-status
python scripts\workflow_state_db.py source-status --cycle-id <cycle-id>
```

## Safety boundaries

- Articles that do not pass `QA_PASSED` cannot enter the draft box.
- A live API write requires both `--execute` and the exact approval token.
- The plugin contains no API implementation for publishing, mass sending, deleting, or overwriting live content.
- Successful HTML rendering does not guarantee a successful WeChat draft write.
- Every figure must preserve its source, figure identifier, caption, license, and adaptation conditions.

## License

Code and original documentation are released under the MIT License. Papers, publisher pages, supplements, and third-party figures remain governed by their original licenses and copyright terms.
