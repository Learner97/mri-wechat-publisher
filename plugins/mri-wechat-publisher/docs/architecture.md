# 第一阶段架构

```text
PubMed/OpenAlex 候选元数据
    ↓
科学评分（与全文可用性独立）＋元数据级全文检查（不下载正文）
    ↓
SQLite候选、去重、选择队列与状态事务
    ↓
公开来源获取或用户上传主论文/补充材料
    ↓
文件哈希、论文身份与证据充分性门控
    ↓
证据映射、核心分析 method_map 与结果解读式写作
    ↓
结构化 article.json
    ↓
事实、引用、图片与安全质检
    ↓
微信公众号兼容 HTML
    ↓
人工确认进入草稿箱
    ↓
API 草稿通道 ──失败──→ 已登录浏览器备用通道
    ↓
公众号草稿箱
    ↓
用户人工预览和发表
```

## 子 Skill

- `run-mri-wechat-workflow`：状态编排和人工确认门。
- `write-mri-paper-method-article`：证据映射、核心分析方法映射和“研究速览—引言—方法—结果—结果解读—结语”写作；压缩非关键技术参数与重复统计数字，并控制空间关联和基因富集的结论强度。
- `format-wechat-article`：结构化 JSON 到调用设备系统字体且使用简洁公开图注的微信 HTML；不分发系统字体文件，来源与许可继续内部留档。
- `qa-wechat-article`：结构、证据、图片和发布安全质检。
- `save-wechat-draft`：API/浏览器双通道，仅保存草稿。

## 状态

主状态库存放于 `MRI_WECHAT_DATA_DIR/workflow.db`；未设置环境变量时使用活动工作区的 `.mri-wechat-publisher/workflow.db`。状态路径为：

`AWAITING_SELECTION → SELECTED → SOURCE_VALIDATED → WRITING → AWAITING_DRAFT_APPROVAL → DRAFT_SAVED → PUBLISHED`

来源门控使用 `PUBLIC_SOURCE_PENDING_FETCH`、`AWAITING_USER_UPLOAD`、`SOURCE_FILES_READY`、`SOURCE_VALIDATED` 和 `EVIDENCE_BLOCKED`。候选论文、推荐轮次、有序处理队列、周期、来源清单、文章、草稿、发表记录、统计快照和任务运行日志分别持久化；同一时刻只允许一个活动周期。

未选论文按真正的推荐轮次冷却 5 轮，之后可重新进入候选。多选时，首篇进入 `SELECTED`，其余论文进入 `selection_queue`；每次草稿保存成功后事务化推进下一篇，并通过 `available_at` 保持隔日09:30节奏，不下载未到队首或尚未到领取时间论文的全文。

检索阶段只读取可用性元数据，不下载候选全文。论文被选择后才准备正文；需要用户上传时写入独立周期目录，文件由 SHA-256 和 DOI/标题身份信息登记。只有 `SOURCE_VALIDATED` 才允许正式成稿，只有 `QA_PASSED` 且用户明确批准的文章可以进入 `DRAFT_SAVED`。插件不调用发表接口；`PUBLISHED` 只记录用户人工发表后的事实。

`automation-workflow-state.json` 和 `publication-registry.json` 由数据库自动导出，仅用于人读、兼容与回滚，不再是写入源。
