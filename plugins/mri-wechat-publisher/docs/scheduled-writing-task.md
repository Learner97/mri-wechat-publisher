部署模板：TODO 将 `<workspace>`、`<python>`、`<data-dir>` 和任务ID替换为部署值（工作区示例 `D:\Analysis\MRI-WeChat`）。已有运行优先使用当前任务明确指定的真实路径与状态库，不迁移数据库、不改变既有定时任务。`<CODEX_HOME>` 指当前宿主的Codex用户目录。

本任务采用分批固定聊天。先完整读取并遵守 <workspace>\plugins\mri-wechat-publisher\docs\automation-chat-batches.md。当前lane=writing；任务id=mri-09-30。先按下述业务第1步读取主状态库，再在退出判断前执行所属lane的chat_batch_state.py sync；达到阈值后按该文档创建全新聊天、重新绑定原任务并登记交接。成稿5篇/检索10轮，从首次初始化之后计数。每个批次聊天固定使用gpt-6.1-sol、high。主库和已登记文件是状态/证据依据。

执行“每日09:30 MRI公众号成稿检查”。项目根目录为 <workspace>。主状态库固定为 plugins/mri-wechat-publisher/output/workflow.db；状态工具为 plugins/mri-wechat-publisher/scripts/workflow_state_db.py；来源清单工具为 plugins/mri-wechat-publisher/scripts/build_source_manifest.py；Python 固定使用 <python>。automation-workflow-state.json 与 publication-registry.json 仅为自动导出的兼容快照，禁止直接编辑。

本任务不依赖 Codex 用户级插件安装。每次运行正式分析前，直接读取并遵守工作区内以下本地 Skill：plugins/mri-wechat-publisher/skills/run-mri-wechat-workflow/SKILL.md、write-mri-paper-method-article/SKILL.md、qa-wechat-article/SKILL.md、format-wechat-article/SKILL.md；需要保存草稿且获得明确授权后，再读取 save-wechat-draft/SKILL.md。所有新文章使用 plugins/mri-wechat-publisher 当前源码中的 schema 8 和校验器；schema 1 至 7 只用于兼容历史文章。

每次运行必须按以下顺序：
1. 首先调用 workflow_state_db.py status 和 source-status，读取当前活动周期、队首已选论文及 source_gate；不得自行选文、复用历史论文或处理 selection_queue 中的后续论文。
2. 按 source_gate 做来源预检：
   - 若没有队首已选论文，或状态为 IDLE/AWAITING_SELECTION，报告当前状态后退出。
   - 若为 AWAITING_USER_UPLOAD：只检查数据库返回的当前周期 input_dir。目录为空时报告 awaiting_source_upload 后退出；目录已有文件时，只读取核验身份与可读性所必需的内容，确认主全文与所选题名、DOI或PMID匹配。使用 build_source_manifest.py 生成当前周期 source-manifest.json，再调用 register-source-manifest。无法明确识别主全文、文件损坏、身份不符或证据不足时报告具体问题并退出。
   - 若为 PUBLIC_SOURCE_PENDING_FETCH：继续到领取步骤，只有领取成功后才能获取当前队首论文的公开全文。
   - 若为 SOURCE_FILES_READY 或 SOURCE_VALIDATED：继续到领取步骤。
   - 若为 EVIDENCE_BLOCKED：报告阻断原因后退出。
3. 完成预检后调用 workflow_state_db.py claim-writing --automation-id mri-09-30 --run-key <北京时间YYYY-MM-DD>。只有返回 claimed=true 才继续；其他 claimed=false 状态报告后退出。保存 job_run_id 与 cycle_id。
4. 领取成功后，以数据库返回的队首已选论文作为唯一输入。公开全文只在允许的时点获取并核验；SOURCE_FILES_READY 或 SOURCE_VALIDATED 只读取已登记来源。不得提前处理队列中的后续论文。不得在数据库、快照、清单或日志中写入 AppID、AppSecret、access token、cookie或其他凭据。
5. 通过 PubMed、OpenAlex、Crossref和出版商官方页面核验题名、期刊、日期、DOI、摘要与访问状态；读取当前论文全文的 Abstract、Methods、Results、Discussion、相关图注、补充材料与图片许可。证据不足时调用 source-readiness BLOCKED 并结束任务；证据充分时按状态工具要求登记 READY。
6. 按本地 Skill 写作 schema 8 文章，固定章节为：研究速览、引言、方法、结果、结果解读、结语。先识别每篇论文最有辨识度的阅读入口，再决定浅灰 digest 采用直接陈述、现象反差、观察、开放问题或自问自答；问句不是默认形式，各形式也不是轮换模板。digest 负责说明“为什么值得看”，研究速览再灵活交代研究怎样开展及主要发现；两者不得重复同一串样本、模态、步骤和结果事实。研究速览不提前堆叠 t、p、OR、β 等详细统计量。
7. 方法部分保留研究对象、分析逻辑、关键步骤和会改变解释的核心参数；压缩非关键软件命令、常规预处理、追踪细节和技术参数，完整可追溯信息放入内部 method_map，不把参数清单写进公开正文。
8. 结果部分只保留能够支撑主要结论的统计量；结果解读重点解释结果意味着什么、不同结果之间的关系和必要的解释边界，不重复整段结果。相关分析、空间关联、PLS和基因富集只能写成关联或空间对应，不写成直接因果关系或机制证据。结语先简洁说明研究增加的认识；MRI、脑影像或研究设计层面的评论是可选项，只在能增加论文特异的新信息时自然写入，一段结语完全合格，不默认生成第二段，也不得使用“研究设计上的启发在于”“方法学上的启发在于”“对MRI研究，较有用的是”“对计算神经影像研究”等固定开头。完成当前初稿后，使用第1步 status 返回的 history，排除当前 cycle_id，只读加载最近5篇仍存在的已完成 article_json_path；按实际可用数量横向比较 digest 的开头语法、问号位置、句数与两句关系，以及结语是否反复出现固定第二段或相同启示开头。只修改当前稿中的模板化重复，不改历史稿，也不为追求形式轮换而牺牲当前论文最合适的表达；历史文件不足时不阻断成稿。
9. 所有封面与正文图片，无论文章来源、公开访问状态或许可类型，均只能使用当前所选论文正文或补充材料中实际出现的原文图片；禁止生成、重绘、仿制、信息图化或使用图库、装饰图。图表优先展示核心结果。原图在手机端文字、数据和图例清楚，且不构成纵向长图时，必须整图保留，非必要不得裁剪；不得为了视觉统一、版面偏好或凑图而裁掉原始内容。只有原图为信息过密的组合图，或单图在公众号正文宽度下高度明显妨碍连续阅读时，才可按最小必要原则裁剪、拆分面板或只保留关键面板。裁剪或拆分必须沿原文可辨识的面板边界进行，优先保留完整面板、完整坐标轴、图例和必要标签；不得改变图内数据、标签、颜色含义或新增元素。不得使用单张纵向长图：若原文整图在手机端呈现的高度约为宽度的1.8倍以上，优先选择同一原图中的完整横向或近方形关键面板；若核心信息分布于多个独立面板，可按原文面板顺序拆成多张较短图片；若无法在不破坏原图信息的前提下做到可读，应改选该论文其他原文图，不得缩放成影响阅读的长图。每张 schema 8 图必须保留原 figure_id、panel label、source、license_note 和 mobile_display，并在 figure-list.md 说明是否保留整图、最小裁剪或按原图面板拆分。若原文图片无法合法复用、无法取得可读图像或许可证据不足，不得以生成图替代；必须报告具体的许可或来源阻断并停止交付。封面也必须取自原文图片；优先整图使用，仅在适配封面比例确有必要时做最小裁剪，不得重新设计。建立独立 evidence-map.md、method-map.md 和 figure-list.md。
10. 运行当前本地 validate_article.py、科学证据复核、图片许可核查、凭据扫描、微信HTML渲染和本地预览。只有 QA_PASSED 才可继续。调用 workflow_state_db.py set-artifacts --cycle-id <cycle_id> --article-json <文章JSON绝对路径> --preview <预览绝对路径> --qa-status QA_PASSED；随后调用 finish-job --job-run-id <job_run_id> --status SUCCEEDED。只有数据库返回 AWAITING_DRAFT_APPROVAL 才能交付。
11. 输出标题、研究速览、章节清单、图表清单、QA结果、文章JSON、HTML、预览和内部方法映射的绝对路径，并明确请求用户回复“确认保存到公众号草稿箱，仅保存草稿，不发表”。
12. 未获得上述明确确认时，禁止调用 approve-draft、wechat_draft_api.py 或 record-draft。获得确认后，先 approve-draft，再通过当前本地 save-wechat-draft 流程保存并验证草稿，最后 record-draft。任何情况下禁止发表、freepublish、群发、删除或覆盖已有内容。
