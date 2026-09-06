// paper-mode-dsh-plugin — 论文模式「原生工具插件」（profile bundle）。
//
// 官方定义的一步到位形态：作为 bundle 装进 profile（package.json 的
// `dsh.profile.bundles` + 本包 `cordis.patch.yml` insert 行，等价于
// `dsh plugin --profile <name> add paper-mode-dsh-plugin`），由 Cordis
// loader 以真实插件行加载并在宿主全局工具层注册模型工具；出现在官方
// 插件清单，可用 `dsh plugin --profile <name> remove` 回退。
//
// 作用：把 paper-mode 技能 scripts/ 下 8 个零依赖 Python/Swift 脚本封装成
// 带 JSON Schema 的模型工具（paper_ai_signal / paper_office_extract /
// paper_docx_extract / paper_docx_write / paper_pdf_to_text /
// paper_pdf_to_images / paper_faith_check / paper_check_sync），模型直接调
// 工具而非手拼 bash。执行统一走 ctx.shell + 会话站立沙箱策略（与 tool-bash
// 同一机制，保持沙箱与审批边界），绝不绕开沙箱自起进程。
//
// 脚本本体不复制进本包：它们是三平台同源资产（真源在技能仓库 scripts/，
// 随「论文模式」预设/技能安装在 ~/.dsh/.agent-presets/<预设>/skills/paper-mode/
// 或任一技能扫描根的 paper-mode/scripts）。插件在 apply 时按候选位置探测，
// 找不到时工具仍注册、执行期给出明确指引（避免本包在无技能环境下把预设
// 挂载搞挂）。
//
// 模块零 @deepseek-ai/* 与第三方依赖，只 import Node 内置模块；工具定义按
// ctx.tools.register 的原始契约手写（等价 defineTool 产出的编译后 JSON Schema
// 形态：parameters 为完整 JSON Schema 对象，output.schema 与 output.render 必填）。
import { existsSync } from 'node:fs'
import { homedir } from 'node:os'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

export const name = 'paper-mode-dsh-plugin'
export const inject = ['tools']

// ── 脚本目录解析 ────────────────────────────────────────────────────────────
// 优先取 config.scriptsDir（预设/宿主组合行里可用 !!js 显式给出）；
// 缺省探测：模块邻近布局 + 常见部署位置（dshHome 的 .agent-presets 预设技能
// 目录、dshHome 的 skills 扫描根、用户级 ~/.agents 变体）。
function dshHomeCandidates() {
  const envHome = typeof process !== 'undefined' && process.env ? process.env : {}
  const dshHome = envHome.DSH_HOME
  const agentsHome = envHome.DSH_AGENTS_HOME
  const userHome = typeof homedir === 'function' ? homedir() : envHome.HOME
  const homes = [...new Set([dshHome, agentsHome, userHome ? join(userHome, '.dsh') : void 0, userHome ? join(userHome, '.agents') : void 0].filter(Boolean))]
  const out = []
  for (const home of homes) {
    out.push(join(home, '.agent-presets', 'paper-mode', 'skills', 'paper-mode', 'scripts'))
    out.push(join(home, 'skills', 'paper-mode', 'scripts'))
  }
  return out
}
function resolveScriptsDir(config) {
  if (config && typeof config.scriptsDir === 'string' && config.scriptsDir.length > 0) {
    return config.scriptsDir
  }
  const here = fileURLToPath(new URL('.', import.meta.url))
  const candidates = [
    join(here, 'skills/paper-mode/scripts'), // 模块紧邻技能（仓库自测/预设捆绑）
    join(here, '../skills/paper-mode/scripts'), // <预设>/plugin/ 布局
    join(here, '../scripts'), // <repo>/plugin/ 布局
    join(here, 'scripts'), // <repo> 根布局
    ...dshHomeCandidates(),
  ]
  for (const p of candidates) {
    if (existsSync(join(p, 'ai_signal.py'))) return p
  }
  return candidates[0] // 缺失留给执行期报错（报错信息含候选清单）
}

// ── 命令构造 ────────────────────────────────────────────────────────────────
// quoteStyle: 'bash'（POSIX 单引号）或 'pwsh'（PowerShell 单引号，内部 '' 转义）。
function shq(arg, style) {
  const s = String(arg)
  if (style === 'pwsh') return `'${s.replaceAll("'", "''")}'`
  return `'${s.replaceAll("'", `'\\''`)}'`
}

function buildCommand(prefixParts, scriptPath, argv, style) {
  const q = (x) => shq(x, style)
  const parts = []
  for (const piece of prefixParts) if (piece) parts.push(piece)
  parts.push(q(scriptPath))
  for (const a of argv) parts.push(q(a))
  return parts.join(' ')
}

// ── 一次脚本执行（复用 tool-bash 的沙箱语义）───────────────────────────────
// 返回 { text }（output.schema 的规范值）；render 原样展示。文本约定与 bash
// 工具一致：stdout 为主文，[stderr] 单独一节，超时/信号/非零退出/沙箱拒绝
// 都有标记行，模型按相同惯例处置。
async function runScript(ctx, exec, command, timeoutMs, stdoutMaxBytes) {
  const shell = ctx.get('shell')
  if (!shell) throw new Error('paper-mode-dsh-plugin: shell 服务不可用（依赖宿主 shell 执行器）')
  const sandboxPolicy = ctx.get('sandboxPolicy')
  const standing = sandboxPolicy && typeof sandboxPolicy.resolve === 'function'
    ? sandboxPolicy.resolve(exec && exec.agent ? { session: exec.agent.session } : {})
    : undefined
  const spec = shell.resolve({
    command,
    timeoutMs,
    stdoutMaxBytes,
    ...(standing ? { workdir: standing.workspaceRoot, sandboxPolicy: standing } : {}),
    ...(exec && exec.signal ? { signal: exec.signal } : {}),
  })
  const result = await shell.run(spec)
  const parts = []
  const out = result.stdout && result.stdout.text ? result.stdout.text : ''
  parts.push(out.length > 0 ? out : '(no output)')
  if (result.stdout && result.stdout.truncated) {
    parts.push(result.stdout.spillPath
      ? `[output truncated; full output: ${result.stdout.spillPath}]`
      : '[output truncated]')
  }
  const err = result.stderr && result.stderr.text ? result.stderr.text : ''
  if (err.length > 0) parts.push(`[stderr]\n${err}`)
  if (result.sandbox && result.sandbox.denied) {
    parts.push(`[sandbox: file access denied under ${result.sandbox.mode} mode]`)
  }
  if (result.timedOut) parts.push(`[timed out after ${result.timeoutMs}ms]`)
  if (result.signal !== null) parts.push(`[killed by signal: ${result.signal}]`)
  else if (result.exitCode !== 0) parts.push(`[exit code: ${result.exitCode}]`)
  return { text: parts.join('\n') }
}

// ── 工具参数 schema 小工具（输出与 defineTool 编译产物同形态）──────────────
// 每个属性可带 required: true（编译进顶层 required 数组后移除）。
function toJsonSchema(spec) {
  const properties = {}
  const required = []
  for (const [key, def] of Object.entries(spec)) {
    const { required: isRequired, ...rest } = def
    properties[key] = rest
    if (isRequired) required.push(key)
  }
  return { type: 'object', properties, ...(required.length ? { required } : {}) }
}

// ── 注册一个脚本封装工具 ────────────────────────────────────────────────────
function register(ctx, scriptsDir, config, def) {
  const style = config.quoteStyle || (process.platform === 'win32' ? 'pwsh' : 'bash')
  // python 解释器：Windows 通常没有 python3（用 python 或 py -3），可经
  // config.pythonCmd 覆盖；pdf_to_images 走 swift，见该 def 的 prefix。
  const pythonCmd = config.pythonCmd || (process.platform === 'win32' ? 'python' : 'python3')
  // prefix 支持带空格串（如 'py -3'），按空白拆成 argv 片段。
  const prefix = def.prefix || String(pythonCmd).split(/\s+/).filter(Boolean)
  const scriptPath = join(scriptsDir, def.script)
  ctx.tools.register({
    name: def.name,
    description: def.description,
    parameters: toJsonSchema(def.parameters),
    timeoutMs: def.timeoutMs,
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        required: ['text'],
        properties: { text: { type: 'string' } },
      },
      render: (_args, value) => [{ type: 'text', text: String(value.text) }],
    },
    async execute(args, exec) {
      if (!existsSync(scriptPath)) {
        throw new Error(`paper-mode-dsh-plugin: 找不到脚本 ${scriptPath}（scriptsDir 配置错误？脚本资产未随技能安装：本插件只在已安装 paper-mode 技能（含 scripts/）的机器上可用）`)
      }
      const argv = def.argsFrom(args)
      return runScript(
        ctx,
        exec,
        buildCommand(prefix, scriptPath, argv, style),
        def.timeoutMs || 120000,
        def.stdoutMaxBytes || 1_000_000,
      )
    },
  })
}

const s = (description, required) => ({ type: 'string', description, ...(required ? { required: true } : {}) })

export function apply(ctx, config = {}) {
  const scriptsDir = resolveScriptsDir(config)

  register(ctx, scriptsDir, config, {
    name: 'paper_ai_signal',
    description:
      '论文 AIGC/AI 信号扫描（估算，非官方检测）：对 .docx/.txt/.md 论文正文运行 ai_signal.py，' +
      '按 references/aigc_signals_zh.md 的信号库输出证据（重复句式/连接词/节奏/模板等），' +
      '供判定风险等级并估算 AI 率。file 为论文文件路径（.docx/.txt/.md）。' +
      '结果仅为语言特征估算，绝非知网/维普/Turnitin 官方结果。',
    script: 'ai_signal.py',
    argsFrom: (a) => [a.file],
    parameters: { file: s('论文文件路径（.docx/.txt/.md），必填', true) },
    timeoutMs: 180000,
  })

  register(ctx, scriptsDir, config, {
    name: 'paper_office_extract',
    description:
      '提取 Office 文件正文为纯文本（office_extract.py，支持 .docx/.pptx/.xlsx）。' +
      'file 必填；out 可选——给出则把提取结果写入该 .txt 并打印摘要，缺省打印到结果文本。',
    script: 'office_extract.py',
    argsFrom: (a) => (a.out ? [a.file, a.out] : [a.file]),
    parameters: {
      file: s('Office 文件路径（.docx/.pptx/.xlsx），必填', true),
      out: s('可选输出 .txt 路径；缺省只打印'),
    },
    timeoutMs: 180000,
  })

  register(ctx, scriptsDir, config, {
    name: 'paper_docx_extract',
    description:
      '提取 .docx 段落原文（docx_extract.py）：按 P0001 编号逐段输出 Word 论文正文。' +
      'file 必填；out 可选——给出则写入该 .txt 并打印摘要，缺省打印到结果文本。',
    script: 'docx_extract.py',
    argsFrom: (a) => (a.out ? [a.file, a.out] : [a.file]),
    parameters: {
      file: s('Word .docx 文件路径，必填', true),
      out: s('可选输出 .txt 路径；缺省只打印'),
    },
    timeoutMs: 180000,
  })

  register(ctx, scriptsDir, config, {
    name: 'paper_docx_write',
    description:
      '精确保留导出定稿文本为 Word（docx_write.py）：把 UTF-8 纯文本原样装进 .docx，' +
      '不做任何改写/排版美化（区别于 doc_generate 的按主题生成，不改数字/术语）。' +
      'src 必填为已定稿 .txt 路径；out 可选，缺省写到 src 同名 .docx。',
    script: 'docx_write.py',
    argsFrom: (a) => (a.out ? [a.src, a.out] : [a.src]),
    parameters: {
      src: s('已定稿 UTF-8 文本（.txt）路径，必填', true),
      out: s('可选输出 .docx 路径；缺省 src 同名 .docx'),
    },
    timeoutMs: 120000,
  })

  register(ctx, scriptsDir, config, {
    name: 'paper_pdf_to_text',
    description:
      'PDF 文字层提取（pdf_to_text.py；后端 pypdf → pdftotext 回退）。pdf 必填；' +
      'out 可选——给出则写入该 .txt（摘要走 stderr），缺省清理连续空行后打印文本' +
      '（可直接送 paper_ai_signal）。扫描件/公式版式无法取字时改用 paper_pdf_to_images（macOS，视觉读图）。',
    script: 'pdf_to_text.py',
    argsFrom: (a) => (a.out ? [a.pdf, a.out] : [a.pdf]),
    parameters: {
      pdf: s('PDF 文件路径，必填', true),
      out: s('可选输出 .txt 路径；缺省只打印'),
    },
    timeoutMs: 300000,
    stdoutMaxBytes: 4_000_000,
  })

  register(ctx, scriptsDir, config, {
    name: 'paper_pdf_to_images',
    description:
      'PDF 逐页转 PNG（pdf_to_images.swift，仅 macOS 且需 swift 运行时）：适合扫描件、' +
      '含公式/图表页；生成后逐页用视觉读图（read_image）审读。pdf 与 outdir 必填。' +
      '非 macOS 平台请改用 paper_pdf_to_text。',
    script: 'pdf_to_images.swift',
    prefix: ['swift'],
    argsFrom: (a) => [a.pdf, a.outdir],
    parameters: {
      pdf: s('PDF 文件路径，必填', true),
      outdir: s('PNG 输出目录路径，必填（应位于工作区内）', true),
    },
    timeoutMs: 300000,
  })

  register(ctx, scriptsDir, config, {
    name: 'paper_faith_check',
    description:
      '改后保真机检（faith_check.py）：逐项对比 原文/改后 的数字、图表公式、引用编号与拉丁术语，' +
      '输出差异清单与 markdown 报告。original、revised 必填（.txt/.md/.docx）；' +
      'report 可选把报告写入该文件；strict 置 true 时差异非空以退出码 1 结束（结果带 [exit code: 1] 标记）。',
    script: 'faith_check.py',
    argsFrom: (a) => {
      const argv = [a.original, a.revised]
      if (a.report) argv.push('--report', a.report)
      if (a.strict) argv.push('--strict')
      return argv
    },
    parameters: {
      original: s('原文文件（.txt/.md/.docx），必填', true),
      revised: s('改后文件（.txt/.md/.docx），必填', true),
      report: s('可选：把 markdown 报告写入该文件'),
      strict: { type: 'boolean', description: '置 true 时数字/编号差异非空退出码为 1' },
    },
    timeoutMs: 120000,
  })

  register(ctx, scriptsDir, config, {
    name: 'paper_check_sync',
    description:
      '三平台 SKILL 同源同步门禁（check_sync.py，维护用）：校验 DSH/WorkBuddy/通用三份 SKILL.md 的 ' +
      'name/version/角色命名/控制条款锚点一致，并可选对资源根做 references/docs/scripts 逐文件 sha256 比对。' +
      'skills 必填为恰好 3 个 SKILL.md 路径（[DSH版, WorkBuddy版, 通用版]）；assetDirs 可选为 ≥2 个资源根目录。',
    script: 'check_sync.py',
    argsFrom: (a) => {
      if (!Array.isArray(a.skills) || a.skills.length !== 3) {
        throw new Error('paper_check_sync: skills 必须恰为 3 个路径（[DSH版, WorkBuddy版, 通用版]）')
      }
      const argv = ['--skills', ...a.skills]
      if (Array.isArray(a.assetDirs)) {
        if (a.assetDirs.length < 2) throw new Error('paper_check_sync: assetDirs 至少需要 2 个目录')
        argv.push('--asset-dirs', ...a.assetDirs)
      }
      if (a.quiet) argv.push('--quiet')
      return argv
    },
    parameters: {
      skills: {
        type: 'array',
        description: '恰好 3 个 SKILL.md 路径：[DSH版, WorkBuddy版, 通用版]',
        items: { type: 'string' },
        required: true,
      },
      assetDirs: {
        type: 'array',
        description: '可选：≥2 个资源根目录（比较 references/docs/scripts 逐字节 sha256）',
        items: { type: 'string' },
      },
      quiet: { type: 'boolean', description: '置 true 时只输出结论' },
    },
    timeoutMs: 120000,
  })
}
