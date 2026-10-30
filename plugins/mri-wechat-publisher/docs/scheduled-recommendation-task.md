部署模板：TODO 将 `<workspace>`、`<python>`、`<data-dir>` 和任务ID替换为部署值（工作区示例 `D:\Analysis\MRI-WeChat`）。已有运行优先使用当前任务明确指定的真实路径与状态库，不迁移数据库、不改变既有定时任务。`<CODEX_HOME>` 指当前宿主的Codex用户目录。

本任务采用分批固定聊天。先完整读取并遵守 <workspace>\plugins\mri-wechat-publisher\docs\automation-chat-batches.md。当前lane=recommendation；任务id=mri。先按下述业务第1步读取主状态库，再在退出判断前执行所属lane的chat_batch_state.py sync；达到阈值后按该文档创建全新聊天、重新绑定原任务并登记交接。成稿5篇/检索10轮，从首次初始化之后计数。每个批次聊天固定使用gpt-6.1-sol、high。主库和已登记文件是状态/证据依据。

在当前任务中执行“MRI公众号隔日选题推荐”。工作目录固定为 <workspace>。主状态库固定为 plugins\mri-wechat-publisher\output\workflow.db；状态工具为 plugins\mri-wechat-publisher\scripts\workflow_state_db.py；来源可得性工具为 plugins\mri-wechat-publisher\scripts\source_availability.py；Python 固定使用 <python>。automation-workflow-state.json 与 publication-registry.json 仅为自动导出的兼容快照，禁止直接编辑。

每次运行：
1. 先调用 workflow_state_db.py status --compact 读取数据库。若 current_cycle.status 不是 IDLE，报告当前状态，不创建重复周期。prepared_drafts 中的 PENDING/APPROVED 本地待审稿与新推荐周期互不占用，不得因它们存在而恢复旧 selection_queue。
2. current_cycle.status 为 IDLE 时，检查 recommendation_schedule.next_recommendation_at。只有当前北京时间已达到或超过该时间才启动检索；未到时间则安静报告尚未到期，不创建周期。首次指定到期时间为 2026-08-10 17:00（北京时间），新周期成功创建后由 create-cycle 按 cadence_days=2 自动推进下一次到期时间。
3. 到期后调用 workflow_state_db.py recommendation-exclusions，获取 permanent_exclusions 和 cooldown_exclusions。永久排除已选择、曾排队、已成稿、已入草稿箱、已发表以及已登记为 prepared_drafts 的论文；未选论文只在最近5个完整推荐轮次内排除。禁止自行恢复永久排除论文。
4. 通过 PubMed 与 OpenAlex 只读检索近两年论文，主题覆盖 MRI、认知神经科学、脑连接组、神经影像机器学习、涉及MRI分析的疾病/医学/生物学。优先 Nature、Science、Cell 体系及本领域顶级期刊，但不以“越新越好”为目标。
5. 对候选执行“正式版成熟期”筛选。以北京时间运行日为基准，首次在线发表或正式发布日期在最近15天内的论文原则上不进入最终5篇。只有出版商官方页面已明确提供最终 Version of Record，且可确认存在无水印的正式排版全文、正文原图及研究所需补充材料时，才可例外纳入。仅有 accepted manuscript、proof、pre-proof、Journal Pre-proof、Early View/Online Ahead of Print 的不稳定排版，或当前只能取得带水印 PDF、无法确认正式原图与补充材料的论文，必须排除并用更成熟论文替换。不得把预印本或作者稿冒充正式排版版本。
6. 先按领域相关性、期刊质量、方法创新和科学价值形成备选，再将来源成熟度作为最终入围门槛。最终5篇应优先选择已稳定上线约15天以上、题名/DOI/PMID/日期可核验、正式排版全文与原图可获得的论文；不需要追求最近几天或最近半个月的新论文。
7. 将拟入围候选池保存为 plugins\mri-wechat-publisher\output 下的 UTF-8 JSON，文件名包含周期日期，结构包含 generated_at 和 candidates 数组；每个候选必须含 choice、title，尽可能含 doi、pmid、journal、publication_date、score、topic_tags 与 pilot_reason。先运行 source_availability.py 生成 checked JSON；检查只允许查询 PubMed/PMC、Europe PMC、OpenAlex、Crossref和出版商元数据，不得下载或持久化全文、PDF、HTML正文或补充材料。每篇必须包含 fulltext_access、supplement_status、成熟期判断、正式版本状态和用户所需动作。
8. 使用检查后的候选JSON调用 workflow_state_db.py create-cycle --cycle-id <唯一周期ID> --recommendations-json <检查后候选JSON绝对路径>。只有返回 status=AWAITING_SELECTION 才能展示候选；如数据库报告永久排除、5轮冷却、来源不成熟或正式版状态不明确，替换候选后重新核验，禁止绕过约束。不得在数据库、快照或日志中写入凭据。
9. 展示每篇候选的标题、期刊、正式发表日期、距今时间、DOI/PMID、官方链接、科学价值、推荐理由、适合讲解的方法、正式版本状态、全文状态、补充材料状态和所需用户动作。说明最近15天论文是否因明确的正式版例外而入选。
10. 请求用户回复单个序号，或用逗号给出有序多选。例如“2”表示只处理第2篇；“2,3”表示按顺序处理。不要自行选文、写作、上传草稿、发表或群发。
11. 用户明确回复单个序号时调用 workflow_state_db.py select --choice <序号>；回复有序多选时调用 workflow_state_db.py select-order --choices <逗号序列>。只有返回 status=SELECTED 才确认选择。禁止直接编辑SQLite或JSON。
