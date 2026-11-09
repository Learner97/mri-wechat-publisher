[中文](#中文) | [English](#english)

<a id="中文"></a>
# MRI 文献公众号助手

`mri-wechat-publisher` 是面向 MRI、认知神经科学及相关医学与生物学论文的 Codex 工作流插件。它将可核验的论文材料转换为“文献解读＋方法解析”中文文章，完成结构、证据、图片许可和发布安全质检，生成微信公众号兼容 HTML，并可在人工批准后保存到公众号草稿箱。

插件只支持保存草稿，不包含自动发表、群发、删除或覆盖线上内容的功能。

当前稳定版本：[v0.8.2](https://github.com/Learner97/mri-wechat-publisher/releases/tag/v0.8.2)。

版本8重点减少批量文章中的模板痕迹：灰框根据论文内容动态选择陈述、反差、开放问题或自问自答，问句不作为默认格式；研究速览再说明研究怎样开展及主要发现。结语首先收束论文增加的认识，MRI 或研究设计启示只有在带来论文特异的新信息时才自然写入，第二段不是必选项。

## 能力

- “研究速览—引言—方法—结果—结果解读—结语”中文科学文章规范；灰框动态提供论文特异的阅读动机，研究速览交代方法与发现，结语不强制附加方法启示；
- 结构化文章 JSON 和微信公众号兼容 HTML；
- 核心结果图优先，组合图可裁切或拆分；正文仅显示简洁图注，来源、许可和移动端策略保留在内部质检记录；
- HTML调用设备系统字体，插件生成的封面使用已登记的开源字体；
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

图片的来源、许可和 `mobile_display` 策略保存在 JSON、图片清单和 QA 记录中，公开 HTML 只显示简洁图注。信息过密的组合图使用裁切、拆分或关键面板选择，同时保留原图号和面板。总字数、章节占比和配图数量不设硬性目标；系统只报告各章节统计，不根据比例阻断、警告、补写或删减正文。

`schema_version: 1` 至 `schema_version: 7` 仅用于兼容已有文章。旧文章仍可校验、渲染和进入原有草稿流程；新文章必须使用版本8。此次兼容不会修改历史 JSON、已生成 HTML、SQLite 记录或公众号草稿。

HTML恢复原始设备字体栈：`-apple-system`、`BlinkMacSystemFont`、`Segoe UI`、`PingFang SC`、`Hiragino Sans GB`、`Microsoft YaHei` 和通用无衬线回退。这里只调用用户设备已经安装的字体，不复制、打包、嵌入、下载或再分发这些系统字体文件。插件生成封面继续使用随插件登记的 Noto Sans SC 及 SIL Open Font License 1.1；合法复用的论文原始栅格图不修改数据和图内文字。`digest` 同时作为公众号草稿元数据，并在作者行与“研究速览”之间以浅灰色导读卡显示一次。

正文按科学问题组织段落，不固定各节篇幅或段落数。连续步骤或结果若回答同一问题，应合并为完整的分析单元；只负责报幕的短过渡句不单独成段。群体推断、外部图谱、横断面设计和临床适用范围只在确实影响理解时进入结果解读，并直接陈述数据关系。默认不列举研究未测量、未纳入或未检验的内容；必要范围说明与其限定的主张放在一起，不在段尾连续追加免责声明。


## Python 环境

在用户工作区创建独立环境，并从插件根目录的依赖清单安装完整工作流依赖；不要在 Codex 的插件缓存目录中创建虚拟环境：

```powershell
py -3.12 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r <plugin-root>\requirements.txt
```

将 `<plugin-root>` 替换为 Codex 安装后的插件根目录。Linux/macOS 可以使用等价的 `python3 -m venv .venv`。封面生成 PowerShell 脚本依赖 Windows `System.Drawing`，但普通使用不需要重新生成内置封面。

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
python <plugin-root>\scripts\wechat_draft_api.py article.json article.html --check-token-only
```

普通调用默认是 dry-run，不访问微信接口，但必须能够解析一个实际存在的封面文件。封面可以写在文章 JSON 的 `cover.path` 中，也可以传入 `--cover`；相对路径以文章 JSON 所在目录为基准：

```powershell
python <plugin-root>\scripts\wechat_draft_api.py article.json article.html --cover cover.png
```

缺少封面或封面文件不存在时，dry-run 返回 `DRAFT_SAVE_BLOCKED`，不会误报 `DRY_RUN_READY`。只有用户明确同意保存草稿后，才可以同时加入以下两个参数：

```text
--execute --approval-token USER_APPROVED_DRAFT_ONLY
```

## 离线验证

以下检查不访问网络，也不会写入真实微信草稿：

```powershell
python scripts\self_test.py
python scripts\test_source_availability.py
python scripts\test_workflow_state_db.py
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

Current stable release: [v0.8.2](https://github.com/Learner97/mri-wechat-publisher/releases/tag/v0.8.2).

Version 8 specifically reduces template artifacts across article batches. The grey digest selects a statement, contrast, open question, or question with an answer from the paper itself, with no default question form; Research Overview then explains how the study was conducted and what it found. Closing first states what the study adds. MRI or study-design implications appear only when they contribute paper-specific information, and a second paragraph is never mandatory.

## Capabilities

- A Chinese scientific article contract with Research Overview, Introduction, Methods, Results, Result Interpretation, and Closing, including a paper-specific digest and an optional method-implication paragraph;
- Structured article JSON and WeChat-compatible HTML;
- Concise public figure captions with provenance and licensing retained in internal QA records;
- Open-source-preferred HTML typography and an OFL-licensed bundled font for generated covers;
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

Total length and figure count are evidence-driven. Section shares are reported as descriptive statistics only and never trigger validation decisions by themselves. Figures prioritize core findings; dense composite figures are cropped, split, or reduced to selected panels for mobile reading while preserving source provenance. Public HTML shows only concise figure captions; provenance and licensing remain mandatory internal metadata. HTML references the original device-system font stack without distributing font files, while generated covers continue to use the bundled OFL-licensed Noto Sans SC. The digest appears once in the grey card above the Research Overview. Existing `schema_version: 1` through `schema_version: 7` articles remain valid for reading, rendering, and the established draft workflow, but new writing must use version 8. No migration rewrites historical JSON, HTML, SQLite records, or WeChat drafts.

## Python environment

Create an isolated environment in the user's workspace, not inside the Codex plugin cache:

```powershell
py -3.12 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r <plugin-root>\requirements.txt
```

Replace `<plugin-root>` with the installed plugin directory. On Linux or macOS, use the equivalent `python3 -m venv .venv` commands. The PowerShell cover-generation helpers depend on Windows `System.Drawing`; ordinary use does not require regenerating the bundled test covers.

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
python <plugin-root>\scripts\wechat_draft_api.py article.json article.html --check-token-only
```

The normal command is a dry-run and makes no WeChat request, but it must resolve a real cover image. Configure `cover.path` in the article JSON or pass `--cover`; relative paths are resolved from the article JSON directory:

```powershell
python <plugin-root>\scripts\wechat_draft_api.py article.json article.html --cover cover.png
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
python scripts\test_source_availability.py
python scripts\test_workflow_state_db.py
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
