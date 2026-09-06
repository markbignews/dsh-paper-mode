#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
faith_check.py — 定稿保真机检（确定性 token 差异，零第三方依赖）。

用法:
    python3 faith_check.py <原文文件> <改后文件> [--report out.md] [--strict]

用途（论文模式 v2.5.0 流程）：终审（角色E）前先运行本脚本，把"可机检的保真差异"
交给终审/复查子代理逐条解释或修正，把"内容保真"从纯主观断言变成 机检证据 + 判定。

检查项（确定性证据，非判定）：
  1) 数字类：整数/小数/百分比（10%、12.5）的多重集差异；
  2) 编号类：图表/公式编号（图3-1、表2、式(1)…）与引用编号（[1]、[3,5]…）差异；
  3) 拉丁术语：全大写或首字母大写的英文/缩写串（CRM、SPSS、K-means 等）差异；
  4) 全文统计：总字符（去空白）与段落数变化。

支持 .txt/.md/.docx（docx 用 zipfile + 正则抽取正文，零依赖）。
⚠️ 边界（如实说明）：中文术语与句式语义的保真不在本脚本能力内，
   仍由终审员结合本输出与原文判断；本脚本只输出证据，不替代判定。
--strict 时：数字类或编号类出现差异即返回退出码 1（供流程/CI 门禁使用）。
"""
import argparse
import re
import sys
import zipfile
from collections import Counter

NUM = re.compile(r"\d+(?:\.\d+)?")
FIG = re.compile(r"(?:图|表|式)\s*\d+(?:[—-]\d+)*")
CIT = re.compile(r"\[\d+(?:\s*,\s*\d+)*\]")
LATIN = re.compile(r"[A-Za-z][A-Za-z0-9]*(?:[.\-_][A-Za-z0-9]+)*")
LATIN_STOP = {"the", "of", "and", "for", "with", "from", "that", "this", "are", "was", "were", "is", "in", "on", "to", "as", "by", "at", "an"}


def read_text(path):
    low = path.lower()
    if low.endswith(".docx"):
        with zipfile.ZipFile(path) as z:
            xml = z.read("word/document.xml").decode("utf-8", "ignore")
        return "".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", xml, re.S))
    with open(path, encoding="utf-8", errors="ignore") as f:
        return f.read()


def norm(t):
    return re.sub(r"\s+", "", t)


def latin_tokens(t):
    out = []
    for tok in LATIN.findall(t):
        if len(tok) < 2 or len(tok) > 32:
            continue
        if tok[0].isupper() or tok.isupper():
            if tok.lower() not in LATIN_STOP:
                out.append(tok)
    return out


def collect(t):
    return {
        "数字": NUM.findall(t),
        "图表公式编号": FIG.findall(t),
        "引用编号": CIT.findall(t),
        "拉丁术语": latin_tokens(t),
    }


def diff_lists(name, orig, new):
    only_o = list((Counter(orig) - Counter(new)).elements())
    only_n = list((Counter(new) - Counter(orig)).elements())
    return name, sorted(only_o), sorted(only_n)


def main():
    ap = argparse.ArgumentParser(description="定稿保真机检（论文模式 v2.5.0）")
    ap.add_argument("original", help="原文文件（.txt/.md/.docx）")
    ap.add_argument("revised", help="改后文件（.txt/.md/.docx）")
    ap.add_argument("--report", help="把 markdown 报告写入该文件")
    ap.add_argument("--strict", action="store_true", help="数字/编号差异非空时退出码 1")
    args = ap.parse_args()

    a, b = read_text(args.original), read_text(args.revised)
    stats = {
        "字符数(去空白)": (len(norm(a)), len(norm(b))),
        "段落数": (len([p for p in a.splitlines() if p.strip()]), len([p for p in b.splitlines() if p.strip()])),
    }

    lines = []
    hard_diff = False
    for name in ("数字", "图表公式编号", "引用编号", "拉丁术语"):
        cat, only_o, only_n = diff_lists(name, collect(a)[name], collect(b)[name])
        if name in ("数字", "图表公式编号", "引用编号") and (only_o or only_n):
            hard_diff = True
        lines.append("### {0}（仅原文 {1} 处 / 仅改后 {2} 处）".format(
            cat, len(only_o), len(only_n)))
        lines.append("- 仅原文: " + ("、".join(only_o[:60]) if only_o else "无"))
        lines.append("- 仅改后: " + ("、".join(only_n[:60]) if only_n else "无"))

    lines.insert(0, "# faith_check：定稿保真机检报告（确定性证据）")
    lines.append("## 统计")
    for k, (x, y) in stats.items():
        lines.append("- {0}: 原文 {1} → 改后 {2}".format(k, x, y))
    lines.append("")
    lines.append("> 说明：本报告只列可机检的 token 差异（中文术语/语义保真由终审员判定）；")
    lines.append("> 数字/编号类存在差异时，终审报告中必须逐条解释或修正，不得跳过。")
    text = "\n".join(lines)

    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print("报告已写入:", args.report)
    print(text)
    if args.strict and hard_diff:
        print("[faith_check] --strict：数字/编号类存在差异 → 退出码 1")
        sys.exit(1)


if __name__ == "__main__":
    main()
