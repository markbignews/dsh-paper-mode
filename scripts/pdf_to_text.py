#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pdf_to_text.py — PDF 提取纯文本（多后端回退，尽量零依赖）。
后端顺序:
  1) pypdf         (pip install pypdf)         — 最稳
  2) pdftotext     (brew install poppler)      — 版面更准
  3) 以上都缺失时，打印引导语并提示"视觉方案"（pdf_to_images.swift -> read_image）。
用法:
    python3 pdf_to_text.py <paper.pdf>         # 打印全文
    python3 pdf_to_text.py <paper.pdf> out.txt # 写入文本文件
"""
import re
import subprocess
import sys


def try_pypdf(path: str) -> str | None:
    try:
        from pypdf import PdfReader  # noqa
    except Exception:
        try:
            from PyPDF2 import PdfReader  # noqa
        except Exception:
            return None
    reader = PdfReader(path)
    pages = [p.extract_text() or "" for p in reader.pages]
    return "\n\n".join(pages).strip()


def try_pdftotext(path: str) -> str | None:
    exe = "pdftotext"
    try:
        subprocess.run([exe, "-v"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        return None
    r = subprocess.run([exe, "-layout", path, "-"], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0 if argv and argv[0] in ("-h", "--help") else 1
    src = argv[0]
    text = None
    for name, fn in (("pypdf", try_pypdf), ("pdftotext", try_pdftotext)):
        text = fn(src)
        if text:
            print(f"[使用后端: {name}]", file=sys.stderr)
            break
    if not text:
        print(
            "未找到可用的 PDF 文本提取后端。请任选其一：\n"
            "  a) 安装文本后端:  brew install poppler   或   pip3 install pypdf\n"
            "  b) 用视觉方案（零安装）:  swift <pdf_to_images.swift 路径> <pdf> <outdir>，"
            "然后用 read_image 逐页读生成的 PNG。",
            file=sys.stderr,
        )
        return 1

    if len(argv) > 1:
        with open(argv[1], "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print(f"已写入 {argv[1]}（{len(text)} 字符）", file=sys.stderr)
    else:
        # 清理连续空行，便于送进 ai_signal 扫描
        clean = re.sub(r"\n{3,}", "\n\n", text)
        print(clean)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
