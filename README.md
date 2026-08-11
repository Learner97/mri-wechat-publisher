# MRI WeChat Publisher / MRI 文献公众号助手

[中文](#中文) | [English](#english)

<a id="中文"></a>
## 中文

`mri-wechat-publisher` 是通过 `solel-mri-plugins` Marketplace 分发的 Codex 插件，用于把经过核验的 MRI、认知神经科学及相关论文转换成中文“文献解读＋方法解析”文章，完成证据与发布安全检查，并生成微信公众号兼容 HTML。

插件只支持在用户明确批准后保存到公众号草稿箱，不包含自动发表、群发、删除或覆盖线上内容的功能。

当前稳定版本：[v0.2.0](https://github.com/Learner97/mri-wechat-publisher/releases/tag/v0.2.0)。

### 全文来源与证据门控

- 推荐阶段只通过 PMCID、Europe PMC、OpenAlex 等元数据检查最终五篇候选的全文与补充材料可用性，不下载或缓存正文；
- 付费墙或状态未知的论文仍可进入候选，全文可访问性不改变科学评分；
- 选文后才获取合法公开全文，或等待用户上传其合法取得的 PDF 及补充材料；
- 来源文件必须通过论文身份、SHA-256 清单和证据充分性核验。正式文章只有达到 `SOURCE_VALIDATED` 才能生成，摘要或新闻稿不能冒充全文证据。

具体状态、上传目录和命令见[完整插件文档](plugins/mri-wechat-publisher/README.md#全文来源门控)。

### 谁可以直接使用

- 安装 Codex、Git 和 Python 3.11–3.12 后，任何人都可以使用文章写作、结构化 JSON、证据核查、HTML 排版和离线 QA；这些功能不需要微信公众号凭据。
- 保存到微信公众号草稿箱需要使用者自己的公众号 `AppID`、`AppSecret`、草稿/素材接口权限，以及符合公众号后台要求的公网出口 IP 白名单。
- 浏览器备用通道需要宿主 Agent 提供浏览器控制能力，并由用户自己保持微信公众号后台登录；本仓库不提供账号、Cookie 或二维码。
- Codex 以外的 Agent 可以复用脚本和 `SKILL.md` 工作流，但 Codex Marketplace 安装命令仅适用于 Codex。

### Codex 安装

```powershell
codex plugin marketplace add Learner97/mri-wechat-publisher
codex plugin add mri-wechat-publisher@solel-mri-plugins
```

安装后请在用户工作区创建 Python 虚拟环境，并从插件根目录安装依赖：

```powershell
py -3.12 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r <plugin-root>\requirements.txt
```

### 微信公众号配置

把 [.env.example](.env.example) 复制到用户工作区的 `.env`，填写使用者自己的凭据；不要提交 `.env`：

```dotenv
WECHAT_APP_ID=<your-app-id>
WECHAT_APP_SECRET=<your-app-secret>
```

草稿 dry-run 必须能够找到有效封面，可在文章 JSON 的 `cover.path` 中配置，或显式传入 `--cover <image>`。完整命令和安全边界见[插件文档](plugins/mri-wechat-publisher/README.md)。

运行数据库、凭据、论文全文、图片素材和生成稿件均被排除在仓库之外。

### 许可证

插件代码和原创文档采用 [MIT License](LICENSE)。论文、出版商页面、补充材料和第三方图片继续适用其原始许可证和版权条款。

<a id="english"></a>
## English

`mri-wechat-publisher` is a Codex plugin distributed through the `solel-mri-plugins` marketplace. It turns verified MRI, cognitive-neuroscience, and related papers into Chinese paper-and-method articles, checks evidence and publishing safety, and renders WeChat Official Account-compatible HTML.

The plugin can save an explicitly approved draft, but it does not implement automatic publishing, mass sending, deletion, or overwriting of live content.

Current stable release: [v0.2.0](https://github.com/Learner97/mri-wechat-publisher/releases/tag/v0.2.0).

### Full-text source and evidence gate

- Recommendation performs metadata-only availability checks for the final five candidates through PMCID, Europe PMC, OpenAlex, and related records; it does not download or cache article bodies;
- Paywalled and unknown-access papers remain eligible, and access status does not alter scientific ranking;
- Legal public full text is fetched only after selection, or the workflow waits for a legally obtained user PDF and any supplements;
- Source identity, SHA-256 manifests, and evidence sufficiency must be verified. Formal writing requires `SOURCE_VALIDATED`; abstracts and press releases cannot substitute for full-text evidence.

See the [full plugin documentation](plugins/mri-wechat-publisher/README.md#full-text-source-gate) for states, source locations, and commands.

### Who can use it

- Anyone with Codex, Git, and Python 3.11–3.12 can use writing, structured JSON, evidence review, HTML rendering, and offline QA without WeChat credentials.
- Saving to a WeChat Official Account draft box requires the user's own `AppID`, `AppSecret`, draft/material API permissions, and a public egress IP accepted by the account's IP allowlist settings.
- The optional browser fallback requires browser-control capability in the host Agent and an existing user-managed login. This repository never supplies accounts, cookies, passwords, or QR codes.
- Non-Codex agents may reuse the scripts and `SKILL.md` workflows, but the Marketplace installation commands below are Codex-specific.

### Install in Codex

```powershell
codex plugin marketplace add Learner97/mri-wechat-publisher
codex plugin add mri-wechat-publisher@solel-mri-plugins
```

Create a Python environment in the user's workspace and install dependencies from the installed plugin root:

```powershell
py -3.12 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r <plugin-root>\requirements.txt
```

### WeChat configuration

Copy [.env.example](.env.example) to `.env` in the user's workspace and provide that user's own credentials. Never commit `.env`:

```dotenv
WECHAT_APP_ID=<your-app-id>
WECHAT_APP_SECRET=<your-app-secret>
```

A draft dry-run must resolve a valid cover image through `cover.path` in the article JSON or an explicit `--cover <image>` argument. See the [full plugin documentation](plugins/mri-wechat-publisher/README.md) for commands and safety boundaries.

Runtime databases, credentials, source papers, figures, and generated drafts are intentionally excluded from this repository.

### License

Plugin code and original documentation are released under the [MIT License](LICENSE). Papers, publisher pages, supplements, and third-party figures retain their original licenses and copyright terms.
