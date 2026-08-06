[中文](#中文) | [English](#english)

<a id="中文"></a>
# MRI 文献公众号助手

`mri-wechat-publisher` 是面向 MRI、认知神经科学及相关医学与生物学论文的 Codex 工作流插件。它将可核验的论文材料转换为“文献解读＋方法解析”中文文章，完成结构、证据、图片许可和发布安全质检，生成微信公众号兼容 HTML，并可在人工批准后保存到公众号草稿箱。

插件只支持保存草稿，不包含自动发表、群发、删除或覆盖线上内容的功能。

## 能力

- 固定五段式中文科学文章规范；
- 结构化文章 JSON 和微信公众号兼容 HTML；
- 事实、引用、图片许可与发布安全检查；
- PubMed、OpenAlex、PMC 和 Nature 文献辅助脚本；
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

## Capabilities

- A fixed five-section Chinese scientific article contract;
- Structured article JSON and WeChat-compatible HTML;
- Evidence, citation, image-license, and publishing-safety checks;
- Helper scripts for PubMed, OpenAlex, PMC, and Nature sources;
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
```

## Safety boundaries

- Articles that do not pass `QA_PASSED` cannot enter the draft box.
- A live API write requires both `--execute` and the exact approval token.
- The plugin contains no API implementation for publishing, mass sending, deleting, or overwriting live content.
- Successful HTML rendering does not guarantee a successful WeChat draft write.
- Every figure must preserve its source, figure identifier, caption, license, and adaptation conditions.

## License

Code and original documentation are released under the MIT License. Papers, publisher pages, supplements, and third-party figures remain governed by their original licenses and copyright terms.
