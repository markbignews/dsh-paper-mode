// verify-plugin-manifest.mjs — 校验本仓库的「组合包声明」是否合法（零依赖，仅 Node 内置模块）。
//
// 背景：DSH 0.2.0 的插件管理器只用**目标目录** package.json 里的 `dsh.bundle` 是否为对象来判定
// "能不能作为插件管理"（`dsh-plugin-manager` 的 `inspectionOf` / `not-a-bundle` 分支）；判定通过后
// 由 `dsh-app-boot` 的 `bundlePatchPaths()` 把 `dsh.bundle.patch` 拼成绝对路径直接读文件
// （**不走包 exports、不做 npm 解析**）。因此最容易踩的坑是：manifest 写了、但 patch 文件没进
// 发布物/路径写错/内容不是合法 patch 数组——装载期才炸。
//
// 本脚本把这两个失败点在提交前拦下来，覆盖两个组合包：
//   1) 仓库根            ./package.json + ./cordis.patch.yml
//   2) 插件子目录        ./plugin/paper-mode-dsh-plugin/package.json + 其 cordis.patch.yml
//
// 用法：
//   node verify-plugin-manifest.mjs            # 以脚本所在目录为仓库根
//   node verify-plugin-manifest.mjs <repoDir>  # 指定仓库根
// 退出码 0 = 全部通过；1 = 有 FAIL。
import { existsSync, readFileSync, statSync } from 'node:fs'
import { dirname, isAbsolute, join, relative, resolve, sep } from 'node:path'
import { fileURLToPath } from 'node:url'

const MAX_ICON_BYTES = 256 * 1024
const ICON_EXT = new Set(['.svg', '.png', '.jpg', '.jpeg', '.webp'])

/** 从本脚本位置向上找仓库根：同时含根 package.json 与插件包 manifest 的那一级。 */
function findRepoRoot(from) {
  let dir = from
  for (let i = 0; i < 6; i++) {
    if (existsSync(join(dir, 'package.json')) && existsSync(join(dir, 'plugin', 'paper-mode-dsh-plugin', 'package.json'))) return dir
    const parent = dirname(dir)
    if (parent === dir) break
    dir = parent
  }
  return from
}

const packageRoot = dirname(fileURLToPath(import.meta.url))
const root = resolve(process.argv[2] ?? findRepoRoot(resolve(packageRoot, '..')))
const fails = []
const notes = []

const readJson = (file) => JSON.parse(readFileSync(file, 'utf8'))

/** 极简 YAML 顶层列表解析：只认本仓库 patch 文件用到的 `- key:` / `  - key:` 结构。 */
function parsePatchList(text, file) {
  const lines = text.split(/\r?\n/)
  const topLevel = []
  const insertNames = []
  let inInsert = false
  let insertIndent = 0
  for (const raw of lines) {
    if (/^\s*#/.test(raw) || raw.trim() === '') continue
    const indent = raw.length - raw.trimStart().length
    const line = raw.trim()
    if (indent === 0) {
      inInsert = false
      if (!line.startsWith('-')) {
        fails.push(`${file}: 顶层必须是 YAML 列表项（以 "-" 开头），实际: ${line}`)
        return undefined
      }
      topLevel.push(line.slice(1).trim())
      continue
    }
    if (topLevel.at(-1) === 'insert:') {
      if (!inInsert) {
        inInsert = true
        insertIndent = indent
      }
      if (indent < insertIndent) inInsert = false
      // 只收 insert 列表**直接子项**（缩进与首项相同）的 name；preset 等嵌套列表里的
      // 子插件（更深缩进）不是顶层 insert 目标，不能算作"裸包名"。
      else if (indent === insertIndent) {
        const m = line.match(/^-?\s*name:\s*(.+?)\s*$/)
        if (m) insertNames.push(m[1].replace(/^['"]|['"]$/g, ''))
      }
    }
  }
  return { topLevel, insertNames }
}

/** 校验一个组合包声明：manifest 有 dsh.bundle、patch 可读且是合法 patch 列表、相对入口文件存在。 */
function checkBundle(label, manifestPath) {
  const dir = dirname(manifestPath)
  if (!existsSync(manifestPath)) {
    fails.push(`${label}: 缺少 ${relative(root, manifestPath)} —— 插件管理器会判"没有声明组合包"`)
    return
  }
  let manifest
  try {
    manifest = readJson(manifestPath)
  } catch (error) {
    fails.push(`${label}: ${relative(root, manifestPath)} 不是合法 JSON: ${error.message}`)
    return
  }
  const name = manifest.name
  if (typeof name !== 'string' || name.length === 0) fails.push(`${label}: package.json 缺少 name`)
  const bundle = manifest.dsh && typeof manifest.dsh === 'object' ? manifest.dsh.bundle : undefined
  if (bundle === null || typeof bundle !== 'object') {
    fails.push(`${label}: package.json 的 dsh.bundle 不是对象 → 插件管理器判 not-a-bundle`)
    return
  }
  const declared = Array.isArray(bundle.patch) ? bundle.patch : [bundle.patch]
  if (declared.some((p) => typeof p !== 'string' || p.length === 0)) {
    fails.push(`${label}: dsh.bundle.patch 必须是字符串或字符串数组`)
    return
  }
  for (const patchRel of declared) {
    const patchPath = join(dir, patchRel) // 与 dsh-app-boot 的 bundlePatchPaths() 同语义
    if (!existsSync(patchPath)) {
      fails.push(`${label}: 声明的 patch 文件不存在: ${patchRel}（装载期会直接报错）`)
      continue
    }
    const parsed = parsePatchList(readFileSync(patchPath, 'utf8'), relative(root, patchPath))
    if (parsed === undefined) continue
    if (parsed.topLevel.length === 0) fails.push(`${label}: patch 文件 ${patchRel} 没有任何顶层条目`)
    if (!parsed.topLevel.includes('insert:')) notes.push(`${label}: patch 无 insert 行（仅做覆盖/禁用也合法）`)
    for (const target of parsed.insertNames) {
      if (!target.startsWith('.') && !isAbsolute(target)) {
        notes.push(`${label}: insert ${target} 是裸包名，需能从 profile 解析；当前用相对路径可免依赖`)
        continue
      }
      const entry = resolve(dir, target)
      if (!entry.startsWith(resolve(root) + sep) && resolve(root) !== dirname(entry)) {
        fails.push(`${label}: insert 入口越出仓库: ${target}`)
        continue
      }
      if (!existsSync(entry)) fails.push(`${label}: insert 入口不存在: ${target} → ${entry}`)
      else notes.push(`${label}: insert 入口可解析 → ${relative(root, entry)}`)
    }
  }
  // 显示元数据：缺失只影响 UI 显示，但既然声明了就校验合法性。
  if (manifest.icon !== undefined) {
    if (typeof manifest.icon !== 'string' || isAbsolute(manifest.icon)) fails.push(`${label}: icon 必须是相对路径`)
    else {
      const iconPath = join(dir, manifest.icon)
      if (!existsSync(iconPath)) fails.push(`${label}: icon 文件不存在: ${manifest.icon}`)
      else if (!ICON_EXT.has(manifest.icon.slice(manifest.icon.lastIndexOf('.')).toLowerCase())) fails.push(`${label}: icon 必须是 svg/png/jpg/webp`)
      else if (statSync(iconPath).size > MAX_ICON_BYTES) fails.push(`${label}: icon 超过 256 KiB`)
    }
  }
  for (const lang of ['en', 'zh']) {
    const loc = join(dir, 'locale', `${lang}.json`)
    if (!existsSync(loc)) notes.push(`${label}: 无 locale/${lang}.json（显示回退到 package.json）`)
    else {
      try {
        const dict = readJson(loc)
        if (!dict?.meta?.title) notes.push(`${label}: locale/${lang}.json 缺少 meta.title`)
      } catch (error) {
        fails.push(`${label}: locale/${lang}.json 不是合法 JSON: ${error.message}`)
      }
    }
  }
}

checkBundle('root', join(root, 'package.json'))
checkBundle('plugin', join(root, 'plugin', 'paper-mode-dsh-plugin', 'package.json'))

// 发布物自检：files 里必须带上 patch 文件与本地入口，否则 npm 安装后 patch 读不到。
for (const [label, manifestPath] of [['root', join(root, 'package.json')], ['plugin', join(root, 'plugin', 'paper-mode-dsh-plugin', 'package.json')]]) {
  if (!existsSync(manifestPath)) continue
  const manifest = readJson(manifestPath)
  const files = manifest.files
  if (!Array.isArray(files)) {
    notes.push(`${label}: 未声明 files（本地目录安装不受影响；发布 npm 时建议声明）`)
    continue
  }
  const hasPatch = files.some((f) => f.includes('cordis.patch.yml'))
  if (!hasPatch) fails.push(`${label}: files 未包含 cordis.patch.yml —— 发布后 bundle patch 会缺失`)
}

for (const note of notes) console.log(`note: ${note}`)
if (fails.length > 0) {
  for (const fail of fails) console.log(`FAIL: ${fail}`)
  console.log(`verify-plugin-manifest: ${fails.length} 项不通过`)
  process.exit(1)
}
console.log('verify-plugin-manifest: PASS（根组合包与插件子目录的 dsh.bundle / patch / 入口 / 显示元数据均合法）')
