# 第三阶段：隔日选题与成稿工作流

## 节奏

- 第一天 17:00：生成五篇候选论文，同时执行不下载正文的公开全文/补充材料元数据检查，等待用户明确选择一篇，或按处理顺序选择多篇。
- 选择后至第二天 08:00：公开来源论文准备合法公开全文；需上传或状态未知的论文等待用户放入周期专属 `input` 目录。系统核验文件哈希、DOI/标题身份和补充材料归属。
- 第二天 08:10：来源锁定检查。只有 `SOURCE_VALIDATED` 才允许领取写作任务；证据不足则进入 `EVIDENCE_BLOCKED` 并说明缺什么。
- 第二天 09:30：独立本地任务读取共享状态并生成成稿与预览，不静默换成其他论文。
- 此后每两天重复一次，以北京时间为准。

## 状态交接

唯一主状态库：`MRI_WECHAT_DATA_DIR/workflow.db`。未设置环境变量时使用定时任务活动工作区下的 `.mri-wechat-publisher/workflow.db`；所有相关任务必须显式使用同一个持久数据目录。

`automation-workflow-state.json` 与 `publication-registry.json` 仅是数据库事务提交后自动生成的兼容快照，不得由任务直接编辑。

17:00任务先使用 `recommendation-exclusions` 获取永久排除项和 5 轮冷却项；检索脚本再为每个候选写入 `fulltext_access`，最后使用 `create-cycle` 原子创建候选周期。该可用性字段只决定选中后的来源路径，不参与科学评分，也不能成为排除付费墙论文的理由。用户回复单个序号时可继续使用 `select`；回复有序序号（例如 `2,3`）时使用 `select-order --choices 2,3`。

选文后使用 `source-status` 读取来源路径。合法公开文件或用户上传文件由 `build_source_manifest.py` 生成哈希清单，通过 `register-source-manifest` 登记；核验完成后使用 `source-readiness --decision READY` 进入 `SOURCE_VALIDATED`。09:30任务使用 `claim-writing` 原子领取队首论文，只有 `claimed=true` 才能成稿；完成QA后使用 `set-artifacts` 保存文章与预览路径。

当队首论文成功保存到草稿箱并执行 `record-draft` 后，数据库将其标记为完成，并自动把下一篇排队论文创建为 `SELECTED` 活动周期，同时设置 `available_at`。下一次17:00任务看到已有 `SELECTED` 周期时不重新检索；每日09:30检查在 `available_at` 之前返回 `queued_not_ready`，从而保证下一篇最早在间隔一个完整自然日后的09:30领取。队列耗尽后才恢复新一轮五篇推荐。

## 批量本地待审模式

用户要求把排队论文一次性生成、逐篇确认后再上传时，不把四篇同时伪装成活动周期。每篇 QA 通过后使用 `register-prepared` 登记到 `prepared_drafts`，状态为 `PENDING`；确认或退回分别使用 `review-prepared --decision APPROVED|REJECTED`。全部开放队列项均已登记后，使用 `retire-selection-batch` 一次性退役旧 `ACTIVE/QUEUED` 项，数据库恢复 `IDLE`，但待审稿仍保留永久去重身份。

17:00心跳每天检查一次 `recommendation_schedule.next_recommendation_at`，只有到期且活动周期为 `IDLE` 时才检索。`set-recommendation-due` 可为特殊日期指定下一次检索时间；`create-cycle` 成功后按照 `cadence_days` 自动推进下一次到期时间。这样可以让批量待审稿与新的隔日推荐并存，又不会让旧队列占用下一次09:30。

用户明确同意保存草稿后，先执行 `approve-draft`，草稿验证成功后执行 `record-draft`。人工发表和后台统计导出分别写入 `publications` 与 `stats_snapshots`。

## 安全门

1. 未选择论文：不成稿。
2. 未获得身份匹配、可合法使用且经过哈希登记的全文：停止在证据阶段；补充材料缺失时禁止生成依赖它的结论。
3. `QA_PASSED` 之前：不交付草稿候选。
4. 用户未明确确认：不调用微信公众号草稿API。
5. 所有定时任务禁止发表、群发、删除或覆盖现有内容。

## 推荐展示

五篇候选必须完整展示标题、期刊、日期、DOI/PMID、官方链接、科学评分、推荐理由、适合讲解的方法，以及“全文可用性”和“补充材料可用性”。`ACCESS_UNKNOWN` 必须表述为“尚未确认”，不能表述为“没有全文”。用户即使选择付费墙论文，也保留上传本人合法取得 PDF 和补充材料继续解读的路径。

## 去重

每轮检索必须通过 `recommendation-exclusions` 同时执行：

- 已选择、已排队、已成稿、已入草稿箱或已发表论文：永久排除；
- 未选择论文：从其最近一次出现后冷却 5 个完整推荐轮次；
- 冷却期结束的未选论文：允许根据最新评分再次进入候选；
- 当前活动论文：始终排除。

`recommendation_rounds` 只记录真正生成五篇候选的推荐轮次；队列内部推进不会消耗冷却轮次。数据库对候选论文标识、队列位置、单个活动周期和任务运行键设置唯一约束；状态转换使用事务，避免17:00、09:30或重试任务重复创建周期和重复成稿。
