# paper-mode 技能 · 变更日志（三平台同版）

适用版本：`dsh-paper-mode/SKILL.md`（DSH 版）、`cn-thesis-aigc-detector/workbuddy/paper-mode/SKILL.md`（WorkBuddy 版）、`cn-thesis-aigc-detector/generic/paper-mode/SKILL.md`（通用版）——三版 frontmatter 的 `version` 同值；`references/`、`docs/`、`scripts/` 三处同源同一份。

> 角色命名以 2.4.0 为最终口径（A 初审 → B 引述核查 → C 查重自查 → D AI 率检测 → E 改后终审）；历史版本中的字母编号仅用于追溯，不再沿用。

## 2.7.0+DSH-0.2.0 — 适配 DSH 0.2.0-rc.2（插件重写 + 文档按 0.2.0 事实校正）

> 三份 SKILL.md 的 frontmatter `version` **保持 2.7.0 不变**（`scripts/check_sync.py` 要求三平台 version 同值，本次只有 DSH 版仓库可改，故用本轮标记而不抬 version）；`references/`、`docs/`、`scripts/` 未改动，三平台同源门禁仍 PASS。

- **新增 DSH 0.2.0 agent preset「论文模式」**（`presets/paper.patch.yml`，随根 bundle 的第二个 patch 装载；preset id `paper`，官网当前仅 standard/ptc/minimal/cordis 四个内置）：0.2.0 起 preset 不再是 `$DSH_HOME/.agent-presets/<id>/` 目录，而是一条 `@deepseek-ai/dsh-agent-preset` 声明，`config.plugins` 是**完整**子插件列表。本 preset = persona（身份/红线/技能指针）+ agent-instructions + **skill-filesystem** + tool-skill + bash/pwsh + fs/fs-search + jobs + web + 子代理（`subagent`/`subagent_fork`/`workflow`）+ 交互（`ask_user_question`/`todo_write`/`present`）+ 长文档压缩。要点：
  - **preset 必须自己挂 `skill-filesystem`**：`dsh-web-app`（桌面版/Web 必备）在宿主层把 `skill-filesystem`、`tool-skill` 设为 `disabled`（官方注释 "presets own local discovery"），官方三个 preset 也都各自挂。实测对照：桌面版等价组合下缺这一行 → preset 作用域 `skills.list()` 为空、`skill` 工具报 `unknown or no longer available`；加上后返回 `['paper-mode']`。
  - **不重复挂载 `paper-tools`**：仓库根 `cordis.patch.yml` 已在宿主层 insert，工具层 `global ∪ scope 链` 的合并语义下对 preset 可见；重复挂载会报 `paper-tools … never started`（已复现）。
  - **宿主前提**：`tool-subagent` 的 `modelSelectionSettings: true` 需要宿主层 `@deepseek-ai/dsh-tool-subagent/model-selection-settings`（由 `dsh-web-app` 提供）；只有 `dsh-base` 的最小组合需去掉该项或补宿主行，否则带 broken 诊断。
  - 激活验收：`agentPresets.list()` 读到 `paper` 且 `broken` 为空、composition 21 行全启用；base 形态与桌面版等价形态下 preset 作用域都能看到 `paper-mode` 技能。
- **插件按 0.2.0 契约重写** `plugin/paper-mode-dsh-plugin/lib/index.js`：
  - 执行路径由 0.1.x 的 `ctx.shell.run(spec)` 改为 0.2.0 的 `ctx.shell.execute(ctx.shell.resolve(req))` + `await handle.result()`（`ShellRunResult`），并保留 `run()` 特性探测分支用于 0.1.x 尽力兼容（0.1.5 实测受该环境自身 sharp 签名问题阻断，未验证）。
  - `inject` 保持最小硬依赖 `['tools']`：`shell`/`sandboxPolicy` 在执行期用 `ctx.get` 取并按调用兜底报错——这样在尚未挂 bash/sandbox 的组合里插件仍会加载、8 个工具仍注册（缺服务时执行期给出明确错误）；若把它们写进 `inject`，缺任一服务时整条插件行会一直 pending、工具全部消失。
  - 站立沙箱策略按 0.2.0 语义解析：仅当执行器声明 confining（`shell.sandboxMode` 存在）时传 `sandboxPolicy`，且**无真实 Session 时只做 agentless 解析**——0.2.0 的实现要读 `session.header.cwd`/`session.id`，传任意形态会抛 `session.snapshotEvents is not a function`；另新增 `result.aborted` 标记行。
  - 脚本目录探测对齐 0.2.0 技能扫描根（`<dshHome>/skills`、`<agentsHome>/skills`、`~/.dsh/skills`、`~/.agents/skills`），并新增**项目级根探测**（从进程 cwd 向上找 `<projectRoot>/.dsh/skills`、`<projectRoot>/.agents/skills`，对应 README 推荐的项目级安装），保留 0.1.x `.agent-presets` 旧布局探测（标注为兼容路径）；找不到脚本时报错列出全部已尝试候选。
  - Python 解释器优先级改为：`config.pythonCmd` → 随 DSH 运行时捆绑的 `…/runtime/primary-runtime/dependencies/python/bin/python3`（桌面版自带，含 python-docx/pptx/openpyxl/Pillow）→ PATH 上的 `python3`（Windows `python`）。
  - `paper_pdf_to_images` 自动追加 `-Xcc -fmodules-cache-path=<会话工作区>/.paper-mode-swift-cache`（无工作区身份时退回本机临时目录同名子目录）：沙箱下 clang 默认模块缓存目录常被拒写，且缓存路径冲突会导致 `module '_DarwinFoundation1' is defined in both …` 编译失败；改指唯一可写目录后正常出图（本机实测 1600×2264 PNG，558,986 B）。
- **SKILL.md 按 0.2.0 事实校正**（只改 DSH 版正文表述，不动 frontmatter version / 角色锚点 / 控制条款）：
  - 删除"本环境无原生文件附件（附件仅支持图片）"：0.2.0 原生支持**任意类型文件附件**，通用文件为内容寻址只读对象（`<DSH_HOME>/attachments/v1/files/<摘要前缀>/<摘要>/<文件名>`），模型收到一行句柄文本，用 `read`/脚本按该路径读取。
  - 删除对 `dsh-file-upload` 插件、`.dsh-uploads/<sessionId>/` 目录与 `read_document` 工具的依赖：0.2.0 运行时**均不存在**（社区机制，非官方；该插件 peer 依赖亦与 0.2.0 不匹配）。
  - `read_image` 补"需当前会话模型声明图片输入"的条件（0.2.0 有路由门禁）。
  - walioffice 引用改为"第三方、非官方、0.2.0 peer 不匹配"，工具名更正为 `doc_generate`/`sheet_generate`/`ppt_generate`。
  - frontmatter `metadata` 增 `dshCompatibility: dsh-0.2.0-rc.2`（0.2.0 解析 metadata；未知字段安全）。
- **README 增「与 DSH 0.2.0-rc.2 的核对清单」**，并修正：`.agent-presets` 旧预设布局在 0.2.0 已不被读取；"目录名须等于 frontmatter name"的结论错误（0.2.0 只取 frontmatter name）；桌面版 profile 只能由桌面版插件管理器/carrier CLI 操作；安装插件必须指向 `plugin/paper-mode-dsh-plugin/` 子目录（仓库根不是 bundle，误装只会成普通依赖且不生效）；角色编号与 SKILL.md 统一（A 初审→B 引述→C 查重→D 检测→E 终审，统一轮）。
- **仓库根成为合法组合包（可被插件管理器识别）**：此前根目录没有 `package.json`，桌面版插件管理器安装本仓库时会报"没有声明组合包，不能作为插件管理"（CLI 侧 `cannot resolve profile bundle`，exit 1）——因为 0.2.0 只看**目标目录** `package.json` 里的 `dsh.bundle`。现新增根 `package.json`（`dsh.bundle.patch: ./cordis.patch.yml`，另带 `icon.svg`、`locale/{zh,en}.json` 供管理器显示图标与显示名）+ 根 `cordis.patch.yml`，patch 用**相对路径** insert 仓库内插件入口 `./plugin/paper-mode-dsh-plugin/lib/index.js`：整仓安装即可用、无需再装子包，也不依赖包的 exports 自引用；插件子目录仍保留自己的 `package.json`，两种装法都合法（README 已按此改写安装步骤）。实测：根 bundle 下 symlink 安装与真实 copy 安装两种形态的严格验收均 8/8；`skill` 侧不受影响（`package.json` 不参与技能发现）。
- **新增组合包自检** `plugin/paper-mode-dsh-plugin/verify-plugin-manifest.mjs`（零依赖）：校验根与插件子目录的 `dsh.bundle` 是否为对象、声明的 patch 文件是否存在且为合法 patch 列表、`insert` 入口能否解析到真实文件、`icon`/`locale` 是否合法、`files` 是否带上 patch；负例（抽掉 `dsh.bundle`）确认会 FAIL。放在 `plugin/` 下而非 `scripts/`，避免影响三平台同源资产门禁。
- **验收证据**：`plugin/paper-mode-dsh-plugin/verify-dsh-0.2.0.md` 记录了可复现的验收流程与**严格判定**结果（注册 + 不抛错 + render 成功 + 无信号杀死/超时/沙箱拒绝 + 退出码符合声明 + 关键产物为本轮新产出 + 保真差异计数 > 0），并附负例自检（弱样例必须 FAIL）与 `harnessSha256` 回溯字段——在真实 DSH 0.2.0-rc.2 组合里 8 个 `paper_*` 工具全部执行成功（含 `paper_pdf_to_images` 真实出图 1600×2264），最小组合、桌面版等价组合、项目级安装、整仓根 bundle 四种场景均通过。文件另附独立复核补记（复核者自建 profile 复现 8/8，并发现、促成本条的基线证据、`inject` 理由、`pdf_to_text` 退出码、swift 缓存路径，以及 harness 两条假 PASS 通道共六处更正）。

## 2.7.0 — 省 token 大瘦身 + 统一轮（查重&AIGC 检测并出报告后一次统一改写）

- 三份 SKILL.md frontmatter `version` 升至 **2.7.0**；docs 同步。
- **A1 · Persona 瘦身**（DSH 预设）：角色 A–E 全流程细节从 persona 移除，只保留身份/触发/先问服务范围/红线/技能指针（约 1845 → 842 字符），每条消息固定开销约省 60%。
- **A2 · 子代理任务书外置**：角色 A–E 完整任务书从三份 SKILL 正文移到共享资产 `references/subagent_prompts/`（5 个平台中立文件）；SKILL 只留"任务书路径 + 让子代理先 read 再执行"，主 agent 不再把模板全文转述进对话（读不到文件的宿主再贴全文）。三份 SKILL 合计瘦身约 3–5k 字符，每次触发即省。
- **A3 · 报告落盘默认**：长报告/逐块清单默认写 `02_报告/`、改写稿写 `03_改写稿/`，聊天只给"结论摘要 + 最高优先级项（≤5 条）+ 路径"，改写对照给代表段 ≤3 处；无文件系统宿主给精简摘要。
- **统一轮（默认轮次编排，v2.7.0 起）**：两者都做时不再拆"查重轮改完达标→再 AIGC 轮改"两轮；改为——角色C 查重自查 + 角色D AIGC 检测**并出报告（只查不改）** → 两份报告合并成一份**统一修改意见** → 确认后**一次统一改写**（同段两类问题一次按两套规则改到位）→ **新角色C 与新角色D 并行复查同一稿** → 两项都达标才进角色E 终审；只做单项则只跑对应检测/复查；用户明确要求分先后两轮（默认先查重后 AIGC）时从其指定。省约一整轮"意见→确认→改写→复查"。
- 角色总览表、需求参数确认轮次编排、初审触发、工作流各阶段、终审触发、官方回传、验证清单、docs 闭环图与流程方法论同步改统一轮表述。
- DSH 交付层同步：论文模式预设 persona（瘦身 + 统一轮）与 `preset.yml` 描述更新（本条目不涉及插件代码）。

## 2.6.0 — 服务范围确认（先问清再检测：一条龙全流程 / 只做某个环节 / 自定义）

- 三份 SKILL.md frontmatter `version` 升至 **2.6.0**；`docs/thesis_workflow_zh.md` 同步（0. 服务范围确认为硬性第一步，原 0 三条底线顺延为 0.1、论文初审顺延为 0.2）。
- **新增硬性首步「服务范围确认」**：用户提出论文处理需求（检测/改写/查重/引述核查/导出等）后，主 agent **先主动问清本次要哪种服务**——① **一条龙全流程**（默认完整闭环：初审→参数确认→引述核查→查重/AIGC 轮→改写→复查→终审→导出交付）；② **只做某个环节**（只测 AI 率、只查重自查、只引述核查、只改写降率、只导出 Word 等，只执行该环节及其硬性前置，不自动扩展成完整闭环）；③ **自定义**（按用户现场指定执行）。**问清之前不对论文运行任何检测/自查/改写**；上下文已明确范围则不重复问。
- 角色A 论文初审、需求参数确认等环节的启用条件随之限定为**一条龙全流程/整篇处理范围**；单环节服务不自动触发初审/终审，只问该环节所需参数。红线（估算非官方声明、不编造、保真、引述疑点明示）不因范围缩小而豁免。
- 角色总览表、验证清单（WorkBuddy/通用版）、docs 闭环图同步更新；三平台继续同方法论同源。
- DSH 交付层同步：论文模式预设 persona 与 `preset.yml` 描述加入"先问服务范围再检测"约束（本条目不涉及插件代码）。

## 2.5.2 — DSH 交付层升级：官方 profile bundle（取代 2.5.1 的预设代码行方案）

> 仍只落在 DSH 版仓库交付层；三份 SKILL.md version 保持 2.5.0，三平台资产未动。

- 把 2.5.1 的 `plugin/paper-tools.mjs`（预设内代码行）升级为**官方形态 profile bundle**：`plugin/paper-mode-dsh-plugin/`（`package.json` 声明 `dsh.bundle.patch: ./cordis.patch.yml`，patch `insert` 一行 `name: paper-mode-dsh-plugin`）。
- 安装即官方路径：`dsh plugin --profile web add ./plugin/paper-mode-dsh-plugin`（或 profile `package.json` 的 `dsh.profile.bundles` 注册），重启 `dsh web` 生效；插件出现在官方插件清单，`dsh plugin --profile web remove paper-mode-dsh-plugin` 可回退。
- 工具注册在宿主全局工具层（任何模式会话可见 8 个 `paper_*` 工具）；2.5.1 的预设代码行已从论文模式预设中移除（避免双份注册）。
- 脚本本体不复制进插件包（保持三平台同源）：插件按 `$DSH_HOME`/`~/.dsh` 技能扫描根与 `.agent-presets` 预设目录自动探测 `scripts/`，找不到时工具仍注册、执行期报错指引。
- 其余行为不变：8 工具一一对应脚本、走 `ctx.shell`+会话沙箱、零 `@deepseek-ai` 依赖、Windows 自动 `python`、`paper_pdf_to_images` 仅 macOS。

## 2.5.1 — DSH 版附加：预设内代码行插件（三平台 SKILL 内容未变）

> 本条目只落在 DSH 版仓库的交付层；**三份 SKILL.md 的 version 仍是 2.5.0 未随本条目改动**，`references/`/`docs/`/`scripts/` 三平台资产也未改动，check_sync 门禁不受影响。

- 新增 `plugin/paper-tools.mjs`：一个**预设内代码行插件**（随论文模式 Agent 预设挂载，不装进 profile、无需重启宿主，新会话即生效）。
- 作用：把 `scripts/` 下 8 个脚本封装成注册在工具目录里的原生模型工具——`paper_ai_signal` / `paper_office_extract` / `paper_docx_extract` / `paper_docx_write` / `paper_pdf_to_text` / `paper_pdf_to_images`（macOS/swift）/ `paper_faith_check` / `paper_check_sync`——带 JSON Schema 参数化调用，替代"手拼 python3 命令"。
- 安全边界：工具执行统一经 `ctx.shell` + 会话站立沙箱策略（与 tool-bash 同机制），不绕开沙箱与审批；模块零 `@deepseek-ai` 依赖（只 import Node 内置模块），可整体复制分发。
- 挂载：`agent.cordis.yml` 加一行 `- id: paper-tools` + `name: './plugin/paper-tools.mjs'`（相对预设目录解析），插件文件置于预设 `plugin/` 目录下（详见仓库 README「可选：装成论文模式预设并挂代码行插件」）。
- 平台：Windows 自动取 `python` 解释器（可用 `config.pythonCmd` 覆盖）；`paper_pdf_to_images` 仅 macOS。

## 2.5.0 — 控制条款（迭代上限 / 终审返修上限 / 保真机检 / 官方实测回传节点 / 初审锚点与复核 / 例外记账）

- **迭代上限**：每轮"改写→复查"定点迭代最多 3 次，第 4 轮起需用户逐轮明示"继续"，否则停在决策点（继续 / 接受现状并记账 / 调整目标或顺序）。
- **终审返修上限**：角色E 返修最多 2 轮，之后交由用户决策。
- **保真机检**：新增 `scripts/faith_check.py`（数字/图表公式/引用编号/拉丁术语的确定性差异，零依赖，支持 .txt/.md/.docx，`--strict` 可作门禁）；终审前必跑，角色E 须逐条解释或修正差异。
- **官方实测回传节点**：交付后回传官方报告/标红段 → 如实解读指标 → 按类型重开对应轮（角色C 查重 / 角色D AIGC）→ 定点改写（版本续增标注）→ 复查（≤3 次）→ 涉及全文再过角色E。
- **初审校准**：新增 ✅/⚠️/❌ 判定锚点示例（题目-内容脱节、拼凑抄袭、数据与结论互斥、空壳套话等）；作者不服时再开全新初审子代理对照复核。
- **例外与跳过记账**：跳过/override/接受未达标一律入账（`02_报告/决策与例外记录.md` 或交付总结「例外与跳过」节），交付末尾固定输出清单。
- **同步校验脚本**：新增 `scripts/check_sync.py`（三平台 SKILL 的 name/version/角色/控制条款锚点一致性 + 共享资产逐字节比对，可作 CI 门禁）。

## 2.4.0 — 命名排序规范 + DSH 目录保存要求

- 子代理命名与排序统一为默认执行序：**角色A 论文初审 → 角色B 引述核查 → 角色C 查重自查 → 角色D AI 率检测 → 角色E 改后终审**（需求参数指定"先降 AIGC"时仅 C/D 互换，A/B/E 位置固定）；三个 SKILL 开头新增「子代理角色总览」，分工表/角色卡/模板块按执行序重排。
- frontmatter 新增 `version` 字段。
- DSH 版新增 §1.1 目录与保存要求：每篇论文任务独立目录（`00_原文 / 01_文本 / 02_报告 / 03_改写稿 / 04_交付`）、版本只增不覆盖、临时中间件用后即清，保持工作区整洁。

## 2.3.0 — 论文初审（值不值得改）

- 新增论文初审（即现行角色A）：**先于一切流程**执行，由全新上下文子代理评审立意/结构/前后矛盾/内容质量与可改性，输出四维评级与结论 ✅ 值得改 / ⚠️ 有条件 / ❌ 不值得改；❌ 说明硬理由并**退出流程**（不进入参数确认与任何改写）；单段局部精修按"片段自洽性"轻量执行，用户明确要求可跳过。

## 2.2.0 — 默认顺序改为先降查重率

- 两者都做时，默认处理顺序从"先降 AIGC 率"改为"**先降查重率、后降 AIGC 率**"（先处理与语料重合的段落可顺带消减大量 AI 特征，之后 AIGC 轮只需定点句法微调）；「需求参数确认」仍允许用户临时指定其他顺序。

## 2.1.0 — 查重能力 + 需求参数确认

- 新增 `references/duplicate_check_zh.md`：查重机制经验口径、报告指标（总复制比/去除引用/去除本人/单篇最大）解读、降重策略与无效做法、与降 AI 率改写的协同与冲突、合规红线；明示"估算非官方、以官方平台实测为准"。
- 查重风险自查/复查由**全新上下文子代理**（即现行角色C）执行，与 AI 率检测（即现行角色D）同构：独立自查 → 降重意见 → 确认 → 改写 → 新角色C 复查。
- 新增「需求参数确认」：每次开始先问/复用——目标优先级（只降 AIGC / 只降查重 / 两者都做）、学历级别、论文级别（类型）、目标比例；上下文已明确给出则不重复问。
- DSH 版 description 补充查重触发词。

## 2.0.0 — v2 基线（引述核查前置 + 独立子代理机制）

- 引述/引用可靠性核查先于 AI 率检测（角色分离，先向用户同步 ✅/⚠️/❌ 清单与处理建议，不得为降率掩盖捏造引述）。
- 任何 AI 率估算——首次检测与每轮复查重测——都由**不带本会话对话历史**的全新子代理独立执行，避免"改写着自测"的乐观偏差与前序结论锚定。
- `references/aigc_signals_zh.md` 信号库 v2（五维信号 L1–L5、8 条预防性写作规则、11 条修复策略、硬约束自检表、噪声预算）与 `docs/thesis_workflow_zh.md` 流程文档同步修订。
