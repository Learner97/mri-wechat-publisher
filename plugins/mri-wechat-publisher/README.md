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

草稿 API 需要公众号 AppID、AppSecret、相应接口权限和已加入白名单的公网出口 IP。优先使用操作系统环境变量：

```powershell
$env:WECHAT_APP_ID = '<your-app-id>'
$env:WECHAT_APP_SECRET = '<your-app-secret>'
```

也可以复制仓库根目录 `.env.example` 为工作区 `.env`，或使用 `MRI_WECHAT_ENV_FILE` / `--env-file` 指向安全文件。不要把 AppSecret 写入命令行历史、日志、文章、数据库、测试夹具或聊天记录。

浏览器备用通道要求宿主具备浏览器或 Chrome 控制能力，并且用户已经登录微信公众号后台。该能力不是本插件自带连接器；不可用时应停止并报告，而不是请求密码、Cookie 或二维码。

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
