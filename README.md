# dsh-paper-mode · paper-mode for DeepSeek Harness（DSH）

面向 **DeepSeek Harness（DSH）** 的 paper-mode 技能包：检测中文学术论文的 AI/AIGC 生成痕迹（按知网 CNKI AIGC 检测的**语言特征**估算 AI 率）、引述可靠性核查先行、给出逐段修改意见，并迭代改写把 AI 率降到用户指定的目标比例（默认 ≤10%）。支持粘贴文本与 Word(.docx)/PowerPoint(.pptx)/Excel(.xlsx)/PDF 文档提取。

本仓库是 paper-mode 技能 **DSH 版的唯一真源**：本技能在多平台的另外两个版本（WorkBuddy 版、通用版）与共享方法论资产（信号库/流程文档/命令行脚本）托管在 [markbignews/cn-thesis-aigc-detector](https://github.com/markbignews/cn-thesis-aigc-detector)。

> ⚠️ **声明（请先阅读）**
>
> 1. **非官方项目**：本仓库是社区独立实现，与杭州深度求索（DeepSeek）及 deepseek-ai 官方团队无隶属、背书或合作关系。
> 2. **估算 ≠ 官方结果**：输出为基于知网 CNKI AIGC 检测**语言特征**的估算，不是知网/维普/Turnitin 官方检测结果；官方检测才是最终标准，每次估算必须附带此声明。
> 3. **仅用于合规自查**：作者在投稿/查重前对 AI 辅助内容做自查与人工润色；不得用于规避学校或期刊的官方检测、掩盖代写、伪造数据。改写不得编造数据、实验、案例与引用。
> 4. **仅适配 DeepSeek Harness**：本版正文依赖 DSH 运行机制（会话技能加载、`subagent` 子代理、会话工作区文件读写、`web_search`/`web_fetch`、可选的上传插件），仅在 DSH 上开发与测试，**未在其他 agent 工具上测试或验证过**。其他平台请用通用版（cn-thesis 仓库 `generic/paper-mode/`）。
> 5. 安装/格式细节以 DeepSeek Harness 官方文档为准（见文末[官方依据](#官方依据)）。

## 功能

| 模块 | 能力 | 入口 |
|---|---|---|
| 信号扫描 | 确定性启发式扫描：句长节奏、连接词堆叠、模板套话、缓和语、引用/数据信号，150–450 字分块输出证据 | `scripts/ai_signal.py` |
| 文本提取 | `.docx/.pptx/.xlsx` 正文提取（纯 stdlib 零依赖）；`.docx` 结构化查看 | `scripts/office_extract.py` / `scripts/docx_extract.py` |
| PDF 解析 | 文字版（可选 pypdf/pdftotext，缺省输出引导）；公式/图表/扫描件视觉版转图 | `scripts/pdf_to_text.py` / `scripts/pdf_to_images.swift` |
| 判定依据 | 五维信号（L1–L5）、8 条预防性写作规则、11 条修复策略、硬约束自检表、噪声预算 | `references/aigc_signals_zh.md` |
| 流程方法 | 引述核查（角色A）→ 独立检测（角色B）→ 修改意见 → 确认改写 → 复查循环 → 精确导出 | `SKILL.md` / `docs/thesis_workflow_zh.md` |
| 精确导出 | 定稿文本**逐字**装回 `.docx`（数字/术语/公式/引号保留，支持 `#` 标题与 `**加粗**`） | `scripts/docx_write.py` |

## 安装

本仓库是一个 DSH skill 目录 bundle（`<name>/SKILL.md` 结构），安装即把仓库克隆到 DSH 的某个技能扫描根目录下，**目录名必须是 `paper-mode`**（DSH 按目录名解析候选 skill，frontmatter `name` 须与之匹配）。

```bash
# 推荐：用户级安装（dshHome 默认 ~/.dsh，rank 400）
git clone https://github.com/markbignews/dsh-paper-mode ~/.dsh/skills/paper-mode

# 或项目级安装（随项目 git 分发，rank 100）
mkdir -p <projectRoot>/.dsh/skills
git clone https://github.com/markbignews/dsh-paper-mode <projectRoot>/.dsh/skills/paper-mode

ls ~/.dsh/skills/paper-mode/SKILL.md   # 验证安装
```

> 若设置了 `$DSH_HOME`/`$DSH_AGENTS_HOME`，请替换为对应目录。不要直接把仓库内容铺进扫描根目录（会因目录名 `dsh-paper-mode` 与 frontmatter `name: paper-mode` 不一致而被拒绝）。

### 发现根目录与优先级（DSH 官方表）

| Rank | 来源 | 路径 |
|---|---|---|
| 100 | 项目级 | `<projectRoot>/.dsh/skills` |
| 200 | 项目级 | `<projectRoot>/.agents/skills` |
| 300 | 自定义 | `Config.customSkillDirs` |
| 400 | 用户级 | `<dshHome>/skills`（`dshHome` = `$DSH_HOME` 或 `~/.dsh`） |
| 500 | 用户级 | `<agentsHome>/skills`（`agentsHome` = `$DSH_AGENTS_HOME` 或 `~/.agents`） |

项目根目录 = 含 `.git` 的最近祖先目录。rank 越小越优先；默认推荐 rank 400（用户级），随项目分发装到 rank 100。SKILL.md 正文按资源基准目录解析相对路径，装在任何扫描根目录下均可直接使用。

## 更新 / 卸载 / 热刷新

```bash
git -C ~/.dsh/skills/paper-mode pull   # 更新
rm -rf ~/.dsh/skills/paper-mode        # 卸载
```

DSH 官方监视行为：`SKILL.md` 正文与 frontmatter 的修改在**下一个模型步骤**刷新目录或影响后续加载，无需重启；`references/`、`scripts/` 等资源子树的变更**不触发**目录刷新，但正文每次加载都会重读文件。

## 使用

- **模型侧**：直接说需求即可触发（description 匹配），例如"检查这篇论文的 AI 率"、"把 AI 率降到 10% 以下"、"这段改得不像 AI 写的"。
- **用户侧**：`/paper-mode`（`user-invocable` 默认开启）。
- **输入**：粘贴文本；或把文档放进**会话工作区**以 `@路径` 引用（本环境无原生文件附件）；若 DSH profile 装有社区上传插件 `dsh-file-upload`，拖入/上传的文档落在 `.dsh-uploads/<sessionId>/`，可用其 `read_document` 工具直接读取。
- **执行闭环**（详见 `SKILL.md`）：引述可靠性核查（角色A 子代理，先行并向用户同步）→ AI 率检测（角色B 全新子代理独立估算）→ 逐段修改意见（确认后才改）→ 复查循环（每轮由新角色B 重测）→ `docx_write.py` 精确保留导出。检测阶段依赖 DSH 的 `subagent`（全新上下文）与 `web_search` 机制，这是 DSH 版与通用版的本质差别。

## 目录结构

```
dsh-paper-mode/                    ← 安装为 <扫描根>/paper-mode/
├── SKILL.md                       # 技能正文（frontmatter: name/description/whenToUse/metadata + DSH 指令）
├── references/
│   ├── aigc_signals_zh.md         # 信号库 v2：判定与改写的唯一依据
│   └── duplicate_check_zh.md      # 查重参考库：机制口径/报告指标/降重策略/与降 AI 率协同（估算非官方）
├── scripts/                       # 六个脚本（python3 ≥3.8 标准库即可运行；swift 需 macOS）
│   ├── ai_signal.py               # 信号扫描（.docx/.txt/.md/stdin）
│   ├── office_extract.py          # docx/pptx/xlsx 统一提取
│   ├── docx_extract.py            # docx 结构化原文提取
│   ├── docx_write.py              # 定稿精确导出 .docx
│   ├── pdf_to_text.py             # PDF 文字版提取（可选装 pypdf/pdftotext）
│   └── pdf_to_images.swift        # PDF 逐页转 PNG（视觉版）
├── samples/                       # 演示样例（sample_ai_style.txt / .docx）
├── docs/
│   └── thesis_workflow_zh.md      # 闭环流程方法论
└── README.md / LICENSE / .gitignore   # 仓库级文件（不影响技能发现）
```

## 脱离 DSH：命令行直接使用

```bash
python3 scripts/ai_signal.py 论文.txt          # 信号扫描
python3 scripts/office_extract.py 论文.docx out.txt   # 提取 Office 文档正文
python3 scripts/pdf_to_text.py paper.pdf out.txt      # PDF 文字版
swift scripts/pdf_to_images.swift paper.pdf outdir 1600  # PDF 视觉版（macOS）
python3 scripts/docx_write.py 定稿.txt 定稿.docx      # 定稿精确导出
python3 scripts/ai_signal.py samples/sample_ai_style.txt  # 试用样例
```

## 官方依据

本仓库的安装路径与格式按 DeepSeek Harness 官方仓库（`deepseek-ai/deepseek-harness`，master）核对：

- [packages/skill/skill-filesystem/README.zh.md — 本地 skill 格式、frontmatter、根目录与监视](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/skill/skill-filesystem/README.zh.md)
- [docs/subsystems/skills.zh.md — skill 命名、发现优先级与目录/工具约定](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/subsystems/skills.zh.md)
- [packages/skill/README.zh.md — skill 能力家族概览（用户 `/name` 调用）](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/skill/README.zh.md)

## 开源许可与致谢

[MIT](LICENSE) © markbignews，2026。

方法论与判定信号在实战中参考并整合了以下 MIT 开源项目的经验（详见 `references/aigc_signals_zh.md` 第十节）：

- [qingshanliuci/cnki-aigc---skill](https://github.com/qingshanliuci/cnki-aigc---skill)
- [redbaronyyyyy-eng/humanizer-zh-academic](https://github.com/redbaronyyyyy-eng/humanizer-zh-academic)
- [ChHsiching/chhsich-thesis-aigc-skills](https://github.com/ChHsiching/chhsich-thesis-aigc-skills)
