#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
docx_extract.py — 从 .docx 提取正文段落文本（零依赖：仅 zipfile + re）。
把整段 XML 文本拼接后按段落输出，兼容正文与表格中的段落；忽略页眉页脚。

用法:
    python3 docx_extract.py <论文.docx>              # 打印 "段号<TAB>文本"
    python3 docx_extract.py <论文.docx> out.txt      # 写入纯文本文件（每段一行）
"""
import re
import sys
import zipfile

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

_ENTITY = {
    "&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"', "&apos;": "'",
}


def unescape(s: str) -> str:
    for k, v in _ENTITY.items():
        s = s.replace(k, v)
    return s


def read_docx_paragraphs(docx_path: str) -> list[str]:
    """返回正文段落文本列表（含表格内段落，忽略空段）。"""
    with zipfile.ZipFile(docx_path) as z:
        xml = z.read("word/document.xml").decode("utf-8", errors="replace")
    # 为 w:tab / w:br / w:cr 补空格，避免词被拼死
    xml = re.sub(r"<w:tab\s*/>", " ", xml)
    xml = re.sub(r"<w:br\s*/>", " ", xml)
    xml = re.sub(r"<w:cr\s*/>", " ", xml)
    paras = re.findall(r"<w:p\b[^>]*>.*?</w:p>", xml, flags=re.S)
    out = []
    for p in paras:
        texts = re.findall(r"<w:t\b[^>]*>(.*?)</w:t>", p, flags=re.S)
        t = unescape("".join(texts)).strip()
        t = re.sub(r"\s+", " ", t)
        if t:
            out.append(t)
    return out


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 1
    src = argv[0]
    paras = read_docx_paragraphs(src)
    if len(argv) > 1:
        with open(argv[1], "w", encoding="utf-8") as f:
            f.write("\n".join(paras))
            f.write("\n")
        print(f"已提取 {len(paras)} 个非空段落 -> {argv[1]}")
    else:
        for i, t in enumerate(paras, 1):
            print(f"P{i:04d}\t{t}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
