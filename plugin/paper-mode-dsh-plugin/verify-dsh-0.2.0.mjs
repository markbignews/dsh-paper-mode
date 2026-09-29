// verify-dsh-0.2.0.mjs — paper-mode-dsh-plugin 的 DSH 0.2.0 验收插件（原样可用）。
//
// 作用：在**真实** DSH 组合（真 shell / 真沙箱策略 / 真工具注册表）里加载
// paper-mode-dsh-plugin 注册的 8 个 paper_* 工具，对样例文件各跑一次，逐项做**严格判定**
// 并把结果写进 JSON。用来把「插件在 0.2.0 上能不能装、能不能跑」变成可复现命令。
//
// 判定不是"execute 没抛错就算过"（那会把渲染崩溃、信号杀死、超时、退出码非 0 都当成功）：
//   · 每个工具：必须注册；execute 不抛错；`output.render` 不得抛错且必须产出非空 text block；
//     输出不得为空；不得出现 [killed by signal:] / [timed out after Nms] / [sandbox: ... denied] / [aborted]。
//   · [exit code: N] **只在输出末尾**匹配（插件在末尾追加标记，避免误判脚本自身输出里的同字样），
//     且只允许出现在显式声明 ALLOWED_EXIT 的工具上，并对该工具校验必须出现的文案：
//     - paper_pdf_to_text：无 pypdf/pdftotext 后端时脚本按设计以退出码 1 结束，必须打印安装引导；
//       若没出现退出码标记，则要求产出 out-pdf.txt。
//     - paper_faith_check：验收显式传 `strict: true`，检出差异时脚本按设计退出 1（并在退出前打印
//       `[faith_check] --strict：…`，该文案只在 strict 路径出现，故不会被异常退出冒用）。
//   · paper_pdf_to_images：要求 PNG **本轮新产出**（存在且 mtime 不早于本轮开始）+ 尺寸行匹配。
//   · paper_faith_check：要求报告本轮新产出，且从**落盘报告文件**里数出「数字 / 图表公式编号」两节
//     的**非零**差异条目（样例故意含阿拉伯数字与图号差异；只有中文数字差异数不出来，故样例不可那样造），
//     并核对报告内容出现在工具输出里。payload 还记录 harness 自身 sha256，便于回溯判定版本。
//
// 这是**验收工具**，不是插件本体：它作为第二个 profile bundle 加载，本身不注册模型工具；
// 除 PAPER_ACCEPT_OUT 外，只写 PAPER_ACCEPT_FIXTURES 下的 out-* / png/ 产物。
//
// 用法见 verify-dsh-0.2.0.md「步骤 4」。
import { createHash } from 'node:crypto'
import { existsSync, mkdirSync, readFileSync, statSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

export const name = 'paper-acceptance'
export const inject = ['tools', 'shell', 'sandboxPolicy']

const TOOL_NAMES = [
  'paper_ai_signal',
  'paper_office_extract',
  'paper_docx_extract',
  'paper_docx_write',
  'paper_pdf_to_text',
  'paper_pdf_to_images',
  'paper_faith_check',
  'paper_check_sync',
]

// 允许出现非 0 退出码的工具（环境缺失或设计如此），并把必须出现的文案一并声明。
// marker 必须只在该工具**真正走那次非 0 退出**时才出现，否则该许可会吸收异常退出
// （例如"报告写完后才崩"）。因此：
//   · paper_faith_check：验收显式传 strict:true，脚本在退出前打印 `[faith_check] --strict：…`。
//   · paper_pdf_to_text：无 pypdf/pdftotext 后端时按设计退出 1，并打印安装引导。
const ALLOWED_EXIT = {
  paper_faith_check: { codes: [1], marker: /\[faith_check\] --strict/ },
  paper_pdf_to_text: { codes: [1], marker: /未找到可用的 PDF 文本提取后端/ },
}

function buildArgs(name, fx) {
  switch (name) {
    case 'paper_ai_signal':
      return { file: join(fx, 'sample.txt') }
    case 'paper_office_extract':
      return { file: join(fx, 'sample.docx'), out: join(fx, 'out-office.txt') }
    case 'paper_docx_extract':
      return { file: join(fx, 'sample.docx'), out: join(fx, 'out-docx.txt') }
    case 'paper_docx_write':
      return { src: join(fx, 'final.txt'), out: join(fx, 'out-final.docx') }
    case 'paper_pdf_to_text':
      return { pdf: join(fx, 'sample.pdf'), out: join(fx, 'out-pdf.txt') }
    case 'paper_pdf_to_images':
      return { pdf: join(fx, 'sample.pdf'), outdir: join(fx, 'png') }
    case 'paper_faith_check':
      // 显式开 --strict：既验收"门禁能拦住保真差异"，也让 exit 1 成为预期路径（见 ALLOWED_EXIT）。
      return {
        original: join(fx, 'sample.txt'),
        revised: join(fx, 'revised.txt'),
        report: join(fx, 'out-faith.md'),
        strict: true,
      }
    case 'paper_check_sync':
      return { skills: [join(fx, 's1.md'), join(fx, 's2.md'), join(fx, 's3.md')] }
    default:
      throw new Error(`paper-acceptance: unknown tool ${name}`)
  }
}

/** 探测宿主服务契约（方法名 / 沙箱模式 / 策略解析），把「0.2.0 暴露什么」写成证据。 */
function probeServices(ctx) {
  const out = { shell: {}, sandboxPolicy: {} }
  const shell = ctx.get('shell')
  if (shell) {
    out.shell.methods = Object.getOwnPropertyNames(Object.getPrototypeOf(shell)).filter((k) => k !== 'constructor')
    out.shell.sandboxMode = shell.sandboxMode
    out.shell.hasExecute = typeof shell.execute === 'function'
    out.shell.hasRun = typeof shell.run === 'function'
  } else out.shell.missing = true
  const sp = ctx.get('sandboxPolicy')
  if (sp) {
    out.sandboxPolicy.methods = Object.getOwnPropertyNames(Object.getPrototypeOf(sp)).filter((k) => k !== 'constructor')
    out.sandboxPolicy.defaultMode = sp.defaultMode
    out.sandboxPolicy.workspaceRoot = sp.workspaceRoot
    try {
      out.sandboxPolicy.resolveEmpty = sp.resolve()
    } catch (error) {
      out.sandboxPolicy.resolveEmptyError = String(error)
    }
  } else out.sandboxPolicy.missing = true
  return out
}

/** 取结果文本。render 失败要显式上报，绝不当作成功（否则"未抛错"会掩盖渲染崩溃）。 */
function textOf(definition, args, value) {
  let blocks
  try {
    blocks = definition.output.render(args, value)
  } catch (error) {
    return { text: `[render failed: ${String(error)}]`, renderError: String(error) }
  }
  const text = Array.isArray(blocks)
    ? blocks.filter((b) => b && b.type === 'text' && typeof b.text === 'string').map((b) => b.text).join('\n')
    : ''
  if (text.trim().length === 0) return { text: JSON.stringify(value, null, 2), renderError: 'render returned no text block' }
  return { text, renderError: undefined }
}

/**
 * 读 faith_check 报告里的差异计数，**只统计"数字"与"图表公式编号"两节**
 * （这两类才是脚本可确定性机检、也是保真门禁真正拦的对象；只改拉丁术语不该算过验收）。
 * 标题形如 `### 数字（仅原文 5 处 / 仅改后 5 处）`。
 */
function faithDiffTotal(reportText) {
  let total = 0
  // 捕获范围必须**含标题行本身**（"仅原文 N 处"就写在标题括号里）。
  const sections = /^###\s*(数字|图表公式编号)[^\n]*\n[\s\S]*?(?=^###|^##|$)/gm
  let sec
  while ((sec = sections.exec(reportText)) !== null) {
    const re = /仅原文\s*([0-9]+)\s*处[\s\S]{0,40}?仅改后\s*([0-9]+)\s*处/g
    let m
    while ((m = re.exec(sec[0])) !== null) total += Number(m[1]) + Number(m[2])
  }
  return total
}

/** 插件在输出末尾追加的标记行（只在行尾匹配，避免误判脚本自身输出里的同字样）。 */
function exitMarker(text) {
  return text.match(/\[exit code: (\d+)\]\s*$/)
}

/** 本验收脚本自身的 sha256：写进报告，让每份 out*.json 自证出自哪一版判定逻辑。 */
function harnessSha256() {
  try {
    return createHash('sha256').update(readFileSync(fileURLToPath(import.meta.url))).digest('hex')
  } catch {
    return undefined
  }
}

/** 产物新鲜度：文件存在且 mtime 不早于本轮开始。 */
function freshFile(path, sinceMs) {
  try {
    const st = statSync(path)
    return { ok: st.isFile() && st.mtimeMs >= sinceMs, path, bytes: st.size, mtimeMs: Math.round(st.mtimeMs) }
  } catch (error) {
    return { ok: false, path, error: String(error) }
  }
}

/** 逐工具执行并做严格判定。 */
async function runAll(ctx, startedAt) {
  const registry = ctx.get('tools')
  const fx = process.env.PAPER_ACCEPT_FIXTURES
  if (!fx) throw new Error('paper-acceptance: PAPER_ACCEPT_FIXTURES is required')
  const services = probeServices(ctx)
  const results = []
  for (const name of TOOL_NAMES) {
    const definition = registry.get(name)
    const record = { name, registered: definition !== undefined, ok: false, reasons: [], artifacts: [] }
    if (!definition) {
      record.reasons.push('TOOL NOT REGISTERED')
      results.push(record)
      continue
    }
    const args = buildArgs(name, fx)
    const exec = {
      callId: 'paper-acceptance',
      name,
      arguments: args,
      // 0.2.0 的沙箱服务要求真实 Session（要有 snapshotEvents 等方法）；验收没有会话，
      // 故这里只给 agentless 形态，sandboxPolicy.resolve() 不传 session。
      agent: undefined,
      signal: new AbortController().signal,
    }
    let rendered
    try {
      rendered = textOf(definition, args, await definition.execute(args, exec))
    } catch (error) {
      record.reasons.push(`THREW: ${error && error.message ? error.message : String(error)}`)
      record.output = `THREW: ${error && error.stack ? error.stack : String(error)}`
      results.push(record)
      continue
    }
    record.output = rendered.text
    const out = record.output
    if (rendered.renderError) record.reasons.push(`render failed: ${rendered.renderError}`)
    if (out.trim().length === 0) record.reasons.push('empty tool output')
    if (/\[killed by signal:/.test(out)) record.reasons.push('killed by signal')
    if (/\[timed out after/.test(out)) record.reasons.push('timed out')
    if (/\[sandbox: .*denied/.test(out)) record.reasons.push('sandbox denied')
    if (/\[aborted\]/.test(out)) record.reasons.push('aborted')
    // 标记行只认末尾（插件在输出最后一行追加），避免脚本自身输出里的同字样被误判。
    const exitMatch = exitMarker(out)
    if (exitMatch) {
      const allowed = ALLOWED_EXIT[name]
      if (allowed && allowed.codes.includes(Number(exitMatch[1]))) {
        const marker = allowed.marker instanceof RegExp ? allowed.marker : new RegExp(String(allowed.marker))
        if (!marker.test(out)) record.reasons.push(`exit ${exitMatch[1]} but missing expected marker ${marker}`)
      } else {
        record.reasons.push(`unexpected exit code ${exitMatch[1]}`)
      }
    }
    if (name === 'paper_pdf_to_images') {
      const png = freshFile(join(fx, 'png', 'page-001.png'), startedAt)
      record.artifacts.push(png)
      if (!png.ok) record.reasons.push(`PNG not produced this run (${JSON.stringify(png)})`)
      else if (!out.includes('1600x2264')) record.reasons.push('PNG produced but dimensions line missing')
    }
    if (name === 'paper_pdf_to_text' && !exitMatch) {
      const txt = freshFile(join(fx, 'out-pdf.txt'), startedAt)
      record.artifacts.push(txt)
      if (!txt.ok) record.reasons.push(`expected out-pdf.txt when a backend is present (${JSON.stringify(txt)})`)
    }
    if (name === 'paper_faith_check') {
      // 必须是**非空**差异报告：样例在数字与图号上确有差异。判定读**落盘报告文件**
      // （交付物本身），而不是 stdout 回显。
      const rep = freshFile(join(fx, 'out-faith.md'), startedAt)
      record.artifacts.push(rep)
      if (!rep.ok) record.reasons.push(`faith report missing/stale (${JSON.stringify(rep)})`)
      else {
        let reportText = ''
        try {
          reportText = readFileSync(rep.path, 'utf8')
        } catch (error) {
          record.reasons.push(`faith report unreadable: ${String(error)}`)
        }
        const diffTotal = faithDiffTotal(reportText)
        record.faithDiffTotal = diffTotal
        if (diffTotal === 0) record.reasons.push('faith report lists no differences in 数字/图表公式编号 sections (样例必须含可检出的差异)')
        // 落盘报告应与 stdout 里打印的报告一致（脚本两份都输出，不一致说明捕获/落盘有偏差）
        if (reportText.trim().length > 0 && !out.includes(reportText.trim().slice(0, 80))) {
          record.reasons.push('report file content not reflected in tool output')
        }
      }
    }
    record.ok = record.reasons.length === 0
    results.push(record)
  }
  return { services, results }
}

export function apply(ctx) {
  const out = process.env.PAPER_ACCEPT_OUT
  if (!out) return
  ctx.effect(() => {
    let cancelled = false
    ;(async () => {
      const startedAt = Date.now()
      let payload
      try {
        const { services, results } = await runAll(ctx, startedAt)
        payload = {
          runtime: process.env.PAPER_ACCEPT_RUNTIME ?? 'unknown',
          node: process.version,
          permissionMode: process.env.DSH_PERMISSION_MODE ?? '(unset)',
          harnessSha256: harnessSha256(),
          startedAt,
          ok: results.every((r) => r.ok),
          services,
          results,
        }
      } catch (error) {
        payload = { ok: false, fatal: String(error && error.stack ? error.stack : error) }
      }
      if (cancelled) return
      mkdirSync(dirname(out), { recursive: true })
      writeFileSync(out, `${JSON.stringify(payload, null, 2)}\n`)
      const failed = (payload.results ?? []).filter((r) => !r.ok).map((r) => `${r.name}: ${r.reasons.join('; ')}`)
      process.stderr.write(`paper-acceptance: wrote ${out} (ok=${payload.ok}${failed.length ? `; failed=[${failed.join(' | ')}]` : ''})\n`)
      // 验收完成即退出（本 profile 没有交互式 app，不需要常驻）。
      setTimeout(() => process.exit(payload.ok ? 0 : 1), 50)
    })()
    return () => {
      cancelled = true
    }
  })
}
