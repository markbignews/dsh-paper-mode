#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_sync.py — 三平台 SKILL 同源同步校验（零第三方依赖）。

用法:
    python3 check_sync.py --skills <dsh版SKILL.md> <workbuddy版SKILL.md> <通用版SKILL.md>
                          [--asset-dirs <DSH根> <cn根> ...]     # 比较各根的 references/docs/scripts 逐文件 sha256
                          [--quiet]

论文模式在三个平台（DSH / WorkBuddy / 通用）各有一份 SKILL.md，正文允许平台差异，
但 version、角色命名与关键控制条款必须一致。本脚本做可机检的一致性门禁：
  1) frontmatter 的 name / version 三者相等；
  2) 五个角色（角色A…角色E）都在正文出现；
  3) 关键控制条款锚点词都在正文出现（迭代上限/返修上限/官方实测回传/faith_check/
     例外与跳过记账/判定锚点）；
  4) --asset-dirs 给出的根目录（可多个，须 >=2）之间 references/ docs/ scripts/
     的相对文件逐字节（sha256）一致——这三类是"同源同一份"资产。

任一检查失败打印 FAIL 并以退出码 1 结束（可作 CI/手动门禁）。
"""
import argparse
import hashlib
import os
import re
import sys

ASSET_SUBDIRS = ("references", "docs", "scripts")
ANCHORS = [
    "迭代上限", "返修上限", "官方实测回传", "faith_check",
    "例外与跳过记账", "判定锚点",
]


def frontmatter_field(text, key):
    m = re.search(r"^---\s*\n(.*?)\n---", text, re.S | re.M)
    if not m:
        return None
    fm = m.group(1)
    mm = re.search(r"^%s:\s*(.+?)\s*$" % re.escape(key), fm, re.M)
    return mm.group(1) if mm else None


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def rel_files(root):
    out = {}
    for sub in ASSET_SUBDIRS:
        base = os.path.join(root, sub)
        if not os.path.isdir(base):
            continue
        for dp, _, fns in os.walk(base):
            for fn in fns:
                full = os.path.join(dp, fn)
                rel = os.path.relpath(full, root)
                out[rel] = full
    return out


def main():
    ap = argparse.ArgumentParser(description="三平台 SKILL 同源同步校验")
    ap.add_argument("--skills", nargs=3, required=True,
                    metavar=("DSH", "WORKBUDDY", "GENERIC"),
                    help="三份 SKILL.md 的路径（顺序：DSH/WorkBuddy/通用）")
    ap.add_argument("--asset-dirs", nargs="+", help=">=2 个资源根目录，比较 references/docs/scripts")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    fails = []
    texts = [open(p, encoding="utf-8").read() for p in args.skills]
    names = [frontmatter_field(t, "name") for t in texts]
    vers = [frontmatter_field(t, "version") for t in texts]

    if len(set(names)) != 1 or names[0] != "paper-mode":
        fails.append("name 不一致: %s" % names)
    if len(set(vers)) != 1 or not vers[0]:
        fails.append("version 不一致或缺失: %s" % vers)

    for i, label in enumerate(("DSH", "WorkBuddy", "通用")):
        for ch in ("角色A", "角色B", "角色C", "角色D", "角色E"):
            if ch not in texts[i]:
                fails.append("%s 版缺少 %s" % (label, ch))
        for anchor in ANCHORS:
            if anchor not in texts[i]:
                fails.append("%s 版缺少控制条款锚点: %s" % (label, anchor))

    if args.asset_dirs:
        if len(args.asset_dirs) < 2:
            fails.append("--asset-dirs 至少需要 2 个目录")
        else:
            filesets = [rel_files(d) for d in args.asset_dirs]
            base = filesets[0]
            for d, fs in zip(args.asset_dirs[1:], filesets[1:]):
                if set(base) != set(fs):
                    missing = sorted(set(base) - set(fs))
                    extra = sorted(set(fs) - set(base))
                    if missing:
                        fails.append("%s 缺少资产: %s" % (d, missing))
                    if extra:
                        fails.append("%s 多出资产: %s" % (d, extra))
                for rel in sorted(set(base) & set(fs)):
                    if sha(base[rel]) != sha(fs[rel]):
                        fails.append("资产不一致: %s vs %s (%s)" % (args.asset_dirs[0], d, rel))

    if fails:
        if not args.quiet:
            for f in fails:
                print("FAIL:", f)
        print("check_sync: %d 项不一致" % len(fails))
        sys.exit(1)
    if not args.quiet:
        print("check_sync: OK（name/version=%s；角色与控制条款齐全；%d 组资源一致）"
              % (vers[0], max(len(args.asset_dirs or []) - 1, 0)))
    print("check_sync: PASS")


if __name__ == "__main__":
    main()
