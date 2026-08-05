# 第一阶段架构

```text
论文/PDF/DOI
    ↓
SQLite候选、去重与状态事务
    ↓
证据映射与五段式写作
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
- `write-mri-paper-method-article`：证据映射和五段式写作。
- `format-wechat-article`：结构化 JSON 到微信 HTML。
- `qa-wechat-article`：结构、证据、图片和发布安全质检。
- `save-wechat-draft`：API/浏览器双通道，仅保存草稿。

## 状态

主状态库存放于 `MRI_WECHAT_DATA_DIR/workflow.db`；未设置环境变量时使用活动工作区的 `.mri-wechat-publisher/workflow.db`。状态路径为：

`AWAITING_SELECTION → SELECTED → WRITING → AWAITING_DRAFT_APPROVAL → DRAFT_SAVED → PUBLISHED`

`EVIDENCE_BLOCKED` 和 `CANCELLED` 是受控分支。候选论文、推荐轮次、有序处理队列、周期、文章、草稿、发表记录、统计快照和任务运行日志分别持久化；同一时刻只允许一个活动周期。

未选论文按真正的推荐轮次冷却 5 轮，之后可重新进入候选。多选时，首篇进入 `SELECTED`，其余论文进入 `selection_queue`；每次草稿保存成功后事务化推进下一篇，并通过 `available_at` 保持隔日09:30节奏，不下载未到队首或尚未到领取时间论文的全文。

只有 `QA_PASSED` 且用户明确批准的文章可以进入 `DRAFT_SAVED`。插件不调用发表接口；`PUBLISHED` 只记录用户人工发表后的事实。

`automation-workflow-state.json` 和 `publication-registry.json` 由数据库自动导出，仅用于人读、兼容与回滚，不再是写入源。
