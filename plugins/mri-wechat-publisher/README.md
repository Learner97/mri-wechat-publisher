# MRI 文献公众号助手

这是 MRI 公众号工作流插件，用于把 MRI、认知神经科学及相关医学与生物学论文转换为“文献解读＋方法解析”微信公众号文章，并在人工审核后保存到公众号草稿箱。定时选题、成稿、去重、草稿/发表历史和人工统计快照由本地 SQLite 状态库协调。

## 第一阶段范围

- 五段式中文科学文章规范；
- 结构化文章 JSON 与微信公众号兼容 HTML；
- 事实、引用、图片与发布安全检查；
- 微信草稿 API 连接器；
- 已登录浏览器备用通道；
- 仅保存草稿，禁止自动发表。

定时文献推荐、次日推送、自动发表和运营数据看板不在第一阶段范围内。

## 工作流状态库

主状态库为 `output/workflow.db`，通过 `scripts/workflow_state_db.py` 访问。旧的两个 JSON 状态文件保留为自动导出的兼容快照，禁止直接编辑。

未选候选默认进入 5 个推荐轮次的冷却期，第 6 个间隔轮次结束后可再次参与筛选；已选择、已排队、已成稿或已发表的论文永久排除。用户可按顺序选择多篇，例如 `2,3` 表示先处理第 2 篇，其草稿保存成功后自动把第 3 篇交给后续成稿任务。队列会保留隔日节奏：下一篇最早在间隔一个完整自然日后的 09:30 才能领取。

```powershell
$python = 'C:\Users\Solel\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $python scripts\workflow_state_db.py status
& $python scripts\workflow_state_db.py check
& $python scripts\workflow_state_db.py recommendation-exclusions
& $python scripts\workflow_state_db.py select-order --choices 2,3
& $python scripts\workflow_state_db.py queue-status
```

数据库只保存非敏感工作流元数据；公众号凭据仍只存放在工作区根目录 `.env`。

## 快速验证

```powershell
$python = 'C:\Users\Solel\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $python scripts\validate_article.py examples\phase1-test-article.json
& $python scripts\render_wechat_html.py examples\phase1-test-article.json --output output\phase1-test-article.html
& $python scripts\test_workflow_state_db.py
```

API 凭据必须保存在工作区根目录 `.env` 中；不要把 AppSecret 写入命令行、日志、文章文件或聊天记录。
