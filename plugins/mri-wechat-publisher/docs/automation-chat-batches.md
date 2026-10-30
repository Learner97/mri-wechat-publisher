部署模板：TODO 将 `<workspace>`、`<python>`、`<data-dir>` 和任务ID替换为部署值（工作区示例 `D:\Analysis\MRI-WeChat`）。已有运行优先使用当前任务明确指定的真实路径与状态库，不迁移数据库、不改变既有定时任务。`<CODEX_HOME>` 指当前宿主的Codex用户目录。

# MRI公众号定时任务的分批聊天

此策略仅在用户明确授权创建聊天、发送业务交接及重新绑定既有定时任务后启用；文档本身不授予这些权限。检索默认每10轮、成稿每5篇切换全新聊天，模型和推理强度使用已授权部署配置（示例：`gpt-6.1-sol`、`high`）。不得把两项任务合并到同一聊天。

## 固定路径与任务

- 工作区：`<workspace>`
- Python：`<python>`
- 主状态库：`<data-dir>/workflow.db`
- 批次工具：`<workspace>\plugins\mri-wechat-publisher\scripts\chat_batch_state.py`
- 业务状态工具：同一 `scripts` 目录的 `workflow_state_db.py`
- `recommendation`：既有任务 `mri`，每天北京时间17:00检查到期状态；只有数据库允许时才产生隔日推荐，10个成功登记的新推荐轮次一批。
- `writing`：既有任务 `mri-09-30`，每天北京时间09:30检查，5篇新成稿一批。

两项任务均使用 heartbeat，沿用绑定聊天的模型与推理强度。heartbeat更新接口不接受 `model`、`reasoningEffort`；在创建每个批次聊天时明确传入 `model="gpt-6.1-sol"`、`thinking="high"`，并保持该聊天设置。

## 计数与执行

先按业务任务第1步读取 `status`；成稿还须读取 `source-status`。在空闲/等待分支退出前执行批次维护，然后执行其余业务步骤。不得为了批次计数提前选文、获取全文、领取写作或推进队列。

调用固定Python和批次工具：

```text
chat_batch_state.py --db <主状态库绝对路径> sync --lane recommendation
chat_batch_state.py --db <主状态库绝对路径> sync --lane writing
```

只执行当前任务所属的lane。工具仅在主库 `metadata` 的 `chat_batch:*` 键内保存计数与聊天绑定；不编辑兼容JSON快照，不更改论文或周期状态。首次初始化前已完成的论文、已登记推荐轮次均作为基线排除，从本次调整后开始计数。

- 成稿以 `articles` 或 `prepared_drafts` 登记的 `QA_PASSED` 为准，同一论文仅计一次；修订、重跑、失败和等待不增加计数。
- 检索以 `recommendation_rounds` 成功登记的新周期为准；候选篇数、日期检查、失败、等待和队列推进不计数。
- 业务成功登记推荐、QA成稿、用户选文、取消或保存草稿后，再运行一次所属lane的 `sync`。
- `rotation_due=true` 但 `rotation_ready=false` 时继续在原聊天处理当前待办。检索等待当前推荐的用户选择后换聊；成稿等待当前文章的草稿审批/保存或用户明确取消后换聊。批次阈值不是新的草稿保存授权。
- `rotation_due=true` 时不启动本lane的下一轮新业务；到安全边界先换聊。

## 自动换聊交接

只能使用Codex提供的聊天和定时任务管理工具，不得通过命令行或直接修改 `automation.toml`、应用数据库来重新绑定。

1. 读取 `sync` 返回的 `thread_id`、`batch_number`、`current_cycle`，确认 `rotation_ready=true`。只维护自己的lane。若旧聊天收到过期定时消息，先只读核对实际任务目标；已转移的任务不得再在旧聊天继续运行。
2. 调用 `list_projects`，按确切路径找到 `<workspace>` 的本地项目。调用 `create_thread` 创建一个**全新**本地项目聊天，不用fork、不创建worktree。模型固定 `gpt-6.1-sol`，thinking固定 `high`。标题为 `MRI公众号检索 · 第N批（10轮）` 或 `MRI公众号成稿 · 第N批（5篇）`。
3. 新聊天初始消息只包含本lane、批次号、工作区/主库路径、本文与对应业务任务Markdown的绝对路径，以及 `current_cycle` 的简短交接；明确“现在仅确认接收并结束；不要执行业务、创建任务或修改批次状态；等待绑定完成后的后续消息”。不复制旧聊天历史、论文全文或凭据。调用一次 `wait_threads` 确认初始化结束；不要轮询。
4. 读取 `<CODEX_HOME>\automations\<automation_id>\automation.toml`，通过 `automation_update` 的 `mode=update` 更新**同一个id**，kind为heartbeat，`targetThreadId`设为新聊天id。完整保留原name、prompt、rrule、status及已有通知设置。不要创建第二个定时任务，不改变检查时间，不给heartbeat传不支持的模型参数。
5. 回读该配置，确认唯一原任务已指向新聊天。随后执行：

```text
chat_batch_state.py --db <主状态库绝对路径> rotate --lane <当前lane> --from-thread <旧聊天id> --thread-id <新聊天id>
```

   工具会检查阈值、安全边界与旧绑定，再推进批次；同一交接重试不会重复递增。只有实际任务绑定已核验才登记新绑定。
6. 若工具或配置更新失败，停止该次交接，不新建更多聊天、不执行下一项业务；保留已创建的目标聊天id，修复时复用它。若配置已指向新聊天而工具仍登记旧聊天，先完成第5步；不要再次创建新聊天。
7. 若换聊发生在本次定时业务开始前，绑定成功后通过 `send_message_to_thread` 将本次定时任务交给新聊天（固定模型/推理强度），让其重新从主库和业务任务第1步判断是否该执行；旧聊天结束。若换聊发生在本轮业务已完成后，只交接等待下一次定时运行，不补跑或重复业务。必要时通过 `wait_threads` 获取一次状态；等待结果不得替代人工选文或草稿审批。
8. 在旧聊天交付新聊天链接，按工具要求输出 `created-thread` 指令。保留旧聊天，不删除、不自动归档；用户后续仍可回看或处理明确指向旧文章的请求。

新聊天收到首次定时消息时，先确认自身与实际配置及批次工具的绑定一致；如存在第6步描述的未完成交接，先修复本地绑定再执行业务。

## 上下文与交付

主库、已登记来源、文章JSON和证据/方法/图片映射是状态和科学事实依据。聊天摘要只用于定位，不代替原文核验。每篇论文读取自己的来源，最近5篇风格比较按业务任务从本地文件读取。

成稿正文保留在文章JSON与HTML/预览文件；聊天交付标题、短研究速览、章节/图片清单、QA、关键链接和草稿确认语，不把全文再次粘贴进聊天。候选推荐仍完整展示每篇所需元数据和选择动作，不为缩短消息删掉选文依据。状态无变化时不重复发送旧文章或旧候选；仅在新候选、新成稿、来源/接口失败或需要人工选择/授权时提醒。

每次草稿保存仍需针对具体文章和审核版本获得用户明确确认；任何情况下禁止发表、freepublish、群发、删除或覆盖已有内容。
