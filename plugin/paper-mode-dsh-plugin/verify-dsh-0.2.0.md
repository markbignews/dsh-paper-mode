# 验收记录：paper-mode-dsh-plugin × DSH 0.2.0-rc.2

本文件记录「随附插件在 DSH 0.2.0-rc.2 上能装、能注册、能跑」的可复现验收流程与实测结果。
验收工具是 `verify-dsh-0.2.0.mjs`（本目录，验收用，不被插件加载、不是插件本体）。

- 目标宿主版本：**0.2.0-rc.2**（桌面版 `runtime/primary-runtime/runtime.json` 的 `desktopVersion`）
- 验收日期与机器：macOS arm64，Node 24.21.0（DSH 运行时自带），Python 3.12.14（DSH 运行时自带）
- 结论：**8/8 工具在真实 0.2.0 组合里注册并执行成功**（严格判定：无抛错、无信号杀死/超时/沙箱拒绝、
  退出码符合声明、关键产物为本轮新产出）

> **独立复核**：本记录由 Lead 编写后，另一名成员用**自建 profile + 自写严格校验器**做了对抗式复核，
> 结论一致（其反例与补充证据见文末「复核补记」）。复核曾发现本文件若干断言不实，已按复核结论修正。

## 前置：为什么仓库根也必须声明 `dsh.bundle`

0.2.0 的插件管理器（桌面版「设置 → 插件」与 `dsh plugin --profile <p> add <目标>`）判定"能不能作为
插件管理"只看**目标目录 `package.json` 里的 `dsh.bundle` 是否为对象**（`dsh-plugin-manager` 的
`inspectionOf` / `not-a-bundle` 分支）。本仓库此前只在 `plugin/paper-mode-dsh-plugin/` 里声明了
`dsh.bundle`，根目录连 `package.json` 都没有，于是：

- 在桌面版插件管理器里安装本仓库 → 被装成"普通依赖"，管理器报**"没有声明组合包，不能作为插件管理"**；
- CLI 侧 `dsh plugin --profile web add <仓库根>` → 依赖被加入但随后抛
  `dsh: cannot resolve profile bundle "dsh-paper-mode"`，exit 1。

修法（已落地）：根目录新增 `package.json`（声明 `dsh.bundle.patch: ./cordis.patch.yml`，另带
`icon.svg` 与 `locale/{zh,en}.json` 供管理器显示）+ `cordis.patch.yml`，patch 用**相对路径**插入
仓库内插件入口 `./plugin/paper-mode-dsh-plugin/lib/index.js`——整仓安装即可用、无需再装子包，
也不依赖包的 exports 自引用。插件子目录仍保留自己的 `package.json`，两种装法都合法。

实测（真实 0.2.0 CLI）：

```
$ dsh plugin --profile web add <仓库根>
dependencies:
+ dsh-paper-mode link:<仓库根>
$ dsh --profile web --dump-config | grep -A2 paper-tools
- id: paper-tools
  name: >-
    file://<profile>/node_modules/dsh-paper-mode/plugin/paper-mode-dsh-plugin/lib/index.js
```

并且用同一套严格验收跑通了两种落地形态：symlink 安装（`link:`）与 pnpm 落盘的真实 copy 安装，
均 **ok=true 8/8**。注意 `skill` 侧不受影响：`package.json` 不参与技能发现（技能名取 SKILL.md
frontmatter 的 `name`），整仓铺进扫描根仍照常被发现。


## 0. 需要先修的问题（适配前的基线）

基线用 git 提交 `9ae8231` 的原始插件文件复跑同一验收链路得到（存档：`accept-before.json`、
`accept-probe.json`）。0.1.x 写法在 0.2.0 上有三处硬失败：

| # | 0.1.x 写法 | 0.2.0 事实 | 基线现象 |
|---|---|---|---|
| 1 | 脚本候选路径不含 `$DSH_HOME/skills` 等实际安装位置 | 技能扫描根为 `<dshHome>/skills`、`<agentsHome>/skills`、`~/.dsh/skills`、`~/.agents/skills`，另加项目级 `.dsh/skills`、`.agents/skills` | 8/8 报 `找不到脚本 …lib/skills/paper-mode/scripts/ai_signal.py` |
| 2 | `sandboxPolicy.resolve({ session: exec.agent.session })` 直接传任意 session 形态 | 0.2.0 的实现要读 `session.header.cwd`/`session.id`（`dsh-sandbox-policy/lib/index.js:141-148`） | 8/8 报 `TypeError: session.snapshotEvents is not a function` |
| 3 | `ctx.shell.run(spec)` | 0.2.0 的 `ctx.shell` 只有 `resolve()` + `execute()`，结果在 `await handle.result()` | 修掉 #1/#2 后即暴露；反向验证见下 |

反向验证（确认修复是 load-bearing，不是"恒真"）：在**拷贝**上把 `typeof shell.execute === 'function'`
短路（`if (false && …)`），同一 profile 立刻 8/8 报
`宿主 shell 服务既无 execute() 也无 run()`。

## 1. 取得一份 0.2.0 运行时（可选，用于自带运行时的等价复现）

桌面版把运行时封在 `app.asar` 里，可直接读出来跑 CLI（asar 数据段起点是 `18 + headerSize`，
按 header 里的 size/offset 顺序读出即可）：

```bash
NODE="/Applications/DeepSeek Harness.app/Contents/Resources/runtime/primary-runtime/dependencies/node/bin/node"
"$NODE" - <<'EOF'
const fs=require("fs"),path=require("path");
const p="/Applications/DeepSeek Harness.app/Contents/Resources/app.asar";
const fd=fs.openSync(p,"r");const b=Buffer.alloc(16);fs.readSync(fd,b,0,16,0);
const hdrSize=b.readUInt32LE(12);const hb=Buffer.alloc(hdrSize);fs.readSync(fd,hb,0,hdrSize,16);
const json=JSON.parse(hb.toString("utf8").replace(/\0+$/,""));const base=18+hdrSize;
const out=process.argv[2]||"./asar-dsh";let n=0;
(function walk(node,rel){for(const [name,e] of Object.entries(node.files||{})){const r=rel?rel+"/"+name:name;
 if(e.files){walk(e,r);continue} if(!/^dsh\//.test(r))continue;
 try{const d=path.join(out,r.replace(/^dsh\//,""));fs.mkdirSync(path.dirname(d),{recursive:true});
 const buf=Buffer.alloc(Number(e.size));fs.readSync(fd,buf,0,buf.length,base+Number(e.offset));
 fs.writeFileSync(d,buf);n++}catch{}}})(json,"");
console.log("extracted",n);fs.closeSync(fd);
EOF
# 原生插件（sharp/koffi/pty 等）在 app.asar.unpacked 下，覆盖过去：
cp -R "/Applications/DeepSeek Harness.app/Contents/Resources/app.asar.unpacked/dsh/node_modules/." \
      ./asar-dsh/node_modules/
```

> 若只想在桌面版本体里验证，跳过本节：装好插件后重启桌面版，让会话调一次
> `paper_ai_signal`（工具是否可用、是否报错即可判定），**不需要**本节步骤。

## 2. 准备技能资产（插件不复制脚本，必须能找到技能）

```bash
DSH_HOME=/tmp/paper-accept; rm -rf "$DSH_HOME"; mkdir -p "$DSH_HOME/skills"
git clone https://github.com/markbignews/dsh-paper-mode "$DSH_HOME/skills/paper-mode"
```

## 3. 把验收插件装成 bundle，并建最小 host profile

先把 `verify-dsh-0.2.0.mjs` 包成一个小 bundle：

```bash
V="$DSH_HOME/verify-bundle"; mkdir -p "$V"
cp "$REPO/plugin/paper-mode-dsh-plugin/verify-dsh-0.2.0.mjs" "$V/index.js"
cat > "$V/package.json" <<'EOF'
{ "name": "paper-acceptance-bundle", "version": "0.0.0", "private": true, "type": "module",
  "main": "index.js", "dsh": { "bundle": { "patch": "./cordis.patch.yml" } } }
EOF
printf -- '- insert:\n    - id: paper-acceptance\n      name: paper-acceptance-bundle\n' > "$V/cordis.patch.yml"
```

再建一个只挂 `dsh-base` + 两个 bundle 的最小 profile（无 app、无 LLM，不会去连模型）：

```bash
P="$DSH_HOME/profiles/accept"; mkdir -p "$P/node_modules"
ln -sfn "$REPO/plugin/paper-mode-dsh-plugin" "$P/node_modules/paper-mode-dsh-plugin"
ln -sfn "$V" "$P/node_modules/paper-acceptance-bundle"
cat > "$P/package.json" <<EOF
{
  "name": "dsh-profile-accept",
  "private": true,
  "dependencies": {
    "paper-mode-dsh-plugin": "link:$REPO/plugin/paper-mode-dsh-plugin",
    "paper-acceptance-bundle": "link:$V"
  },
  "dsh": { "profile": { "bundles": ["@deepseek-ai/dsh-base", "paper-mode-dsh-plugin", "paper-acceptance-bundle"] } }
}
EOF
printf '# patch\n[]\n' > "$P/cordis.patch.yml"
printf '[]\n' > "$P/cordis.yml"
printf 'packages:\n  - .\n' > "$P/pnpm-workspace.yaml"
```

> `verify-dsh-0.2.0.mjs` 只是仓库里的验收资产：`package.json` 的 `files` 只打包 `lib/` 与
> `cordis.patch.yml`，所以它不会被发布进插件包，也不参与运行时加载。

**严格判定口径**（避免"没抛错就算成功"的假 PASS）：每个工具必须 ① 注册；② `execute` 不抛错；
③ `output.render` 成功且产出非空文本块；④ 输出非空且不含 `[killed by signal:]`、`[timed out after …]`、
`[sandbox: … denied]`、`[aborted]`；⑤ `[exit code: N]` 只在**输出末尾**匹配，且仅允许声明过的工具——
`paper_pdf_to_text` 缺后端 exit 1（必须同时打印安装引导），`paper_faith_check` 由验收显式传
`strict: true`，exit 1 时必须同时打印 `[faith_check] --strict：…`（该文案只在 strict 路径出现，
故异常退出无法冒用）；⑥ `paper_pdf_to_images` 必须**本轮新产** PNG；⑦ `paper_faith_check` 读取
**落盘报告文件**，要求「数字 / 图表公式编号」两节的差异计数 > 0，且报告内容出现在工具输出里。
失败原因会逐条写进报告的 `reasons` 字段。

## 4. 跑验收

```bash
NODE="<0.2.0 运行时>/dependencies/node/bin/node"          # 步骤 1 解包出来的，或桌面版自带
DSH020="<0.2.0 运行时>/node_modules/@deepseek-ai/dsh/lib/bin.js"
export DSH_HOME=/tmp/paper-accept
export PAPER_ACCEPT_FIXTURES=/tmp/paper-fixtures          # 见下「样例文件」
export PAPER_ACCEPT_OUT=/tmp/paper-accept/report.json
export PAPER_ACCEPT_RUNTIME=dsh-0.2.0-rc.2
export DSH_PERMISSION_MODE=danger-full-access             # 仅验收用：本机嵌套 sandbox-exec 被拒，见 §6.3
"$NODE" "$DSH020" --profile accept
`python3 -c "import json;print(json.load(open('$PAPER_ACCEPT_OUT'))['ok'])"` 打印 `True` 即通过；
失败时报告的每个工具都带 `reasons` 数组说明原因。报告同时记录 `harnessSha256`，可回溯出自哪版判定逻辑。

**负例自检（建议每次验收都跑一次，证明判定不是恒真）**：把 `revised.txt` 换成一版"只改中文措辞、
阿拉伯数字与图号全同"的文本再跑一次 —— 期望 `paper_faith_check` FAIL、
`reasons=['faith report lists no differences in 数字/图表公式编号 sections …']`、整体 `ok=false`。

样例文件（`PAPER_ACCEPT_FIXTURES`）：

- `sample.txt` / `final.txt`：同一份**含阿拉伯数字**的短文（本篇用 2023 年 / 12 所 / 68% / 96.5% / 图 3-1 / [1]）
- `revised.txt`：把其中数字与图号改掉（2024 年 / 15 所 / 72% / 95.5% / 图 3-2），供 `paper_faith_check` 检出差异
  > ⚠️ 注意：`faith_check.py` 的数字正则只认阿拉伯数字（`\d+(?:\.\d+)?`），
  > 若样例只改中文数字（如"百分之六十八"→"百分之七十"），报告会四节全"无"，**测不出**检测能力。
- `sample.docx`：任意 docx（本篇用仓库 `samples/sample_ai_style.docx`）
- `sample.pdf`：带文字层的 PDF；`s1.md`/`s2.md`/`s3.md`：任意 3 份同源 `SKILL.md` 副本

> `--dump-config` 也可单独验证 bundle patch 是否插入组合树：
> `"$NODE" "$DSH020" --profile accept --dump-config | grep -A1 paper-tools`

## 5. 实测结果（本轮，ok=true）

服务契约（`report.json.services`，实测原文）：

```json
{
  "shell": { "methods": ["sandboxMode","resolve","execute","onProcessDone","confine"],
             "sandboxMode": "danger-full-access", "hasExecute": true, "hasRun": false },
  "sandboxPolicy": { "methods": ["resolve","overrideOf"],
                     "defaultMode": "danger-full-access",
                     "workspaceRoot": "<验收工作区>",
                     "resolveEmpty": { "mode": "danger-full-access", "workspaceRoot": "<验收工作区>" } }
}
```

> `sandboxMode` 为 `danger-full-access` 是因为验收显式设了 `DSH_PERMISSION_MODE=danger-full-access`
> （本机真沙箱不可用的规避开关，见 §6.3）。另：把**假 session** 传给 `sandboxPolicy.resolve({ session })`
> 会抛 `TypeError: session.snapshotEvents is not a function`（0.2.0 实现要读会话投影）——这是复核时手工
> 复现的契约细节，本报告不记录该字段；插件据此只在有真实会话时传 session，否则做 agentless 解析。

8 个工具（`report.json.results`，严格判定，全部 ok=true）：

| 工具 | 判定要点 | 实测输出（截断） |
|---|---|---|
| `paper_ai_signal` | 无异常标记 | `=== 论文 AI 痕迹信号扫描（启发式估算，非官方检测）===` / `段落数: 3 总字符(去空白): 185` |
| `paper_office_extract` | 无异常标记 | `已提取 5 行 -> out-office.txt` |
| `paper_docx_extract` | 无异常标记 | `已提取 5 个非空段落 -> out-docx.txt` |
| `paper_docx_write` | 无异常标记 | `已精确保留导出 -> out-final.docx（正文约 185 字，未作任何改写）` |
| `paper_pdf_to_text` | 允许 exit 1，但必须含安装引导文案（本机无 pypdf/pdftotext） | `未找到可用的 PDF 文本提取后端。请任选其一：a) brew install poppler 或 pip3 install pypdf` + `[exit code: 1]` |
| `paper_pdf_to_images` | **本轮新产 PNG**（存在、mtime ≥ 本轮开始、尺寸行匹配） | `wrote png/page-001.png (1600x2264)` / `pages: 1`；产物 **558,986 B** |
| `paper_faith_check` | 报告为本轮新产，且列出**非空**差异 | `报告已写入: out-faith.md` / `### 数字（仅原文 5 处 / 仅改后 5 处）` |
| `paper_check_sync` | 无异常标记 | `check_sync: OK（name/version=2.7.0；角色与控制条款齐全）` / `check_sync: PASS` |

说明：

- **桌面版等价验证（另一轮）**：把 profile 的 bundle 列表换成桌面版的同一组（`dsh-base` +
  `dsh-web-app` + `dsh-experimental-agent-team-profile` + `dsh-experimental-auto-review` + 本插件 +
  验收 bundle；profile 名不能用保留名 `desktop`，故用 `desklike`），严格判定同样 **ok=true（8/8）**，
  `--dump-config` 里 `paper-tools` 只出现 1 次、无插件兼容性 warning——说明本插件与桌面版完整插件集合
  并存无冲突。插件 `package.json` 无 `peerDependencies`，因此 0.2.0 的兼容闸门（只校验
  `@deepseek-ai/dsh*` 的 peer 范围）不会拦它，**无需版本豁免**。
- **项目级安装也覆盖**：在 `<projectRoot>/.dsh/skills/paper-mode` 下装技能、进程 cwd 设为该项目根，
  严格判定同样 8/8（插件会从 cwd 向上探测项目级扫描根）。
- **整仓安装（根 bundle）也覆盖**：以仓库根为 bundle（`dsh-paper-mode` → 根 `cordis.patch.yml`
  → 相对路径插入插件入口）跑严格验收，**symlink 安装与真实 copy 安装两种形态均 8/8**；
  `--dump-config` 中 `paper-tools` 的 `name` 解析为 `<profile>/node_modules/dsh-paper-mode/plugin/…`。
- `paper_pdf_to_images` 只在 macOS 可用；沙箱下 clang 默认模块缓存目录常被拒写，插件会自动
  追加 `-Xcc -fmodules-cache-path=<会话工作区>/.paper-mode-swift-cache`（没有工作区身份时退回
  本机临时目录的同名子目录），缓存落在工作区/临时目录，不污染技能目录。

## 6. 未覆盖 / 已知限制

1. **0.1.5 未能实测**：插件保留 `ctx.shell.run()` 兼容分支（用桩验证可达：只有 `run()` 的假 shell
   能正常注册并执行），但本机 0.1.5 命令行因其自身 `sharp`/`koffi` 原生模块签名问题
   （`ERR_DLOPEN_FAILED`，Team ID 不匹配）无法启动任何 profile，与本插件无关。
   故 0.1.x 兼容性只是"桩测试 + 源码契约核对"，**不是真机验证**。
2. **未在桌面版 live profile 内实测**：桌面版 `desktop` profile 只能由桌面版插件管理器或桌面版
   自带 carrier CLI 操作（普通 `dsh` 会拒绝：*profile "desktop" is managed exclusively by the
   Electron application*）。第 5 节已用**与桌面版完全相同的 bundle 列表**在同版本运行时上跑通，
   但它仍是独立进程、不等于桌面版进程内实测；桌面版内验证请在应用内插件管理器安装后重启，
   再让会话调一次 `paper_ai_signal`。
3. **真沙箱模式未跑通（宿主环境限制）**：0.2.0 的 `dsh-bash-sandbox` 在没有可用后端时按设计拒绝执行
   （`SandboxUnavailableError`）。本机验收进程本身已在沙箱内，嵌套 `sandbox-exec` 被系统拒绝，
   因此 workspace-write 下 8/8 都会失败——**同一环境下 `tool-bash` 也一样失败**，不是插件缺陷。
   验收用 `DSH_PERMISSION_MODE=danger-full-access` 绕过；沙箱行为本身由宿主负责，插件只是把站立
   策略透传给 `ctx.shell`（与 `tool-bash` 同一边界）。
4. **`paper_check_sync` 的 `--asset-dirs` 分支**未在验收里跑（需要 cn-thesis 仓库的另一份同源资产）；
   `--skills` 分支已 PASS。
5. **`inject` 只保留 `['tools']`**：`shell`/`sandboxPolicy` 在执行期用 `ctx.get` 取并按调用兜底报错。
   这样在尚未挂 bash/sandbox 的组合里插件仍会加载、8 个工具仍注册（执行期报明确错误），
   与"无技能环境也不把预设挂挂"的设计一致。若把两者写进 `inject`，缺任一服务时整条插件行会一直
   pending、工具全部消失——这是复核发现后改掉的写法。
6. **项目级根探测的作用域**：`resolveScriptsDir` 在 **apply 期**用 `process.cwd()` 向上探测
   `<projectRoot>/.dsh/skills` 等，因此"项目级安装 + 只用插件"这条路只在**宿主进程 cwd 落在该项目内**
   时生效（§5 的项目级场景就是在这个前提下跑通的）。桌面版宿主进程的 cwd 通常不是会话工作区，
   此时要么把技能也放到用户级扫描根，要么在组合行 `config.scriptsDir` 显式指定。已实测：
   诱饵目录（有 `.dsh/skills/paper-mode` 但**没有** `ai_signal.py`）不会被误采纳。

## 复核补记（独立复核结论摘要）

- 复核者用**自建 profile + 自写严格校验器**独立复现 8/8，并额外验证：PNG 真实产出
  （`file` 确认 `PNG image data, 1600 x 2264, RGBA`）、`faith_check --strict` 退出码 1、
  `docx_write` 往返文本完全一致（800 字符），`check_sync` 负例（改掉锚点）确实 FAIL。
- 复核发现并已修正的本文档问题：§0 基线证据与存档不符（已按存档改写）、§5 服务契约片段与存档
  不一致（已换成实测原文）、`pdf_to_text` 被写成"以 0 退出"（实际 `return 1`，已改）、
  `inject` 的因果理由不成立（实测 `inject=['tools']` 也能取到 shell，已删除该理由并改为
  `['tools']` 的健壮性取舍）。
- 复核又指出**本验收 harness 自身**有两条"假 PASS"通道并复现：① `paper_faith_check` 的"非空差异"
  断言因 `&& !/图表/` 恒假（死代码）；② `output.render` 抛错被 `textOf` 吞成普通文本、只靠产物断言
  兜底（5/8 工具会误判成功）。两者均已修：faith 断言改为读取**落盘报告**并解析「数字 / 图表公式编号」
  两节的差异计数（要求 > 0）；render 失败显式计入失败原因，并要求输出非空、退出码标记只在末尾匹配。
- 第三轮复核又指出一处低危：`paper_faith_check` 的 exit 1 许可当时"永不合法触发"（验收没传 strict），
  会把"报告写完后才崩"也放行。已修：验收显式传 `strict: true`，许可 marker 换成只在 strict 路径打印的
  `[faith_check] --strict`；并按复核建议把差异计数改为只统计两节、改为读落盘报告、在报告里记录
  `harnessSha256`。
- 反例验证（用当前仓库文件重跑）：`render` 必抛的假插件 → 8/8 FAIL 且每条含 `render failed: …`；
  只有中文措辞差异的样例 → `faithDiffTotal=0` → FAIL；仅"拉丁术语"有差异的报告 → 计数为 0（不计入两节）；
  正常样例 → `faithDiffTotal=12`、8/8 PASS。
- 复核还核实并促成两处文档更正：`paper_faith_check` 样例必须含**阿拉伯数字/图号**差异（`faith_check.py`
  的正则只认 `\d+`，只改中文数字会四节全"无"）；README 的"仓库根 add"失败模式应为
  "依赖被加入但命令抛错、exit 1"，不是"只打印一句 warning"。
- 更早一轮的**弱判定**验收（"execute 未抛错即成功"）曾把 `paper_pdf_to_images` 的 swift 模块缓存
  冲突误判为成功；现已把判定改为"注册 + 不抛错 + render 成功 + 异常标记 + 退出码声明 + 产物新鲜度"，
  并据此重跑出上表结果。
