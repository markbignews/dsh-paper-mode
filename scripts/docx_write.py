#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
docx_write.py — 精确保留地把“给定文本”写进 .docx（零依赖：仅 zipfile + re）。

用途：把已定稿的论文/报告**原样**装进 Word，不经过任何 AI 改写。
这是和 walioffice `doc_generate` 的区别：doc_generate 会按主题“重写”一篇新文，
本脚本只把传入的文本逐字装进 .docx，数字、术语、标点完全保留。

支持简单的 Markdown 结构（用于标题/强调）：
  # 一级标题   ## 二级标题   ### 三级标题   **加粗**
其它内容一律按普通段落原样写入；空行跳过。

用法:
    python3 docx_write.py <输入.txt|.md> [输出.docx]   # 输出默认“同名.docx”
    cat 定稿.txt | python3 docx_write.py - 输出.docx   # 从 stdin
"""
import re
import sys
import zipfile
from pathlib import Path

NS_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

_ENTITY = {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&apos;"}


def esc(s: str) -> str:
    for k, v in _ENTITY.items():
        s = s.replace(k, v)
    return s


def _runs(text: str) -> str:
    """把一行文本转成 <w:r> 序列（处理 **bold**）。"""
    parts = re.split(r"(\*\*.+?\*\*)", text)
    out = []
    for p in parts:
        if not p:
            continue
        if p.startswith("**") and p.endswith("**"):
            out.append(f"<w:r><w:rPr><w:b/></w:rPr><w:t xml:space=\"preserve\">{esc(p[2:-2])}</w:t></w:r>")
        else:
            out.append(f"<w:r><w:t xml:space=\"preserve\">{esc(p)}</w:t></w:r>")
    return "".join(out)


def _para(line: str) -> str:
    m = re.match(r"^(#{1,6})\s+(.*)$", line)
    if m:
        level = len(m.group(1))
        text = m.group(2).strip()
        return (f'<w:p><w:pPr><w:pStyle w:val="Heading{min(level,3)}"/></w:pPr>'
                f'{_runs(text)}</w:p>')
    return f"<w:p>{_runs(line.strip())}</w:p>"


def build_document(text: str) -> str:
    lines = text.splitlines()
    paras = "".join(_para(l) for l in lines if l.strip())
    body = (paras
            + '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
              '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:gutter="0"/></w:sectPr>')
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="' + NS_W + '"><w:body>' + body + '</w:body></w:document>')


def build_styles() -> str:
    base = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:styles xmlns:w="' + NS_W + '">'
            '<w:docDefaults><w:rPrDefault><w:rPr>'
            '<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:eastAsia="宋体"/>'
            '<w:sz w:val="24"/><w:szCs w:val="24"/></w:rPr></w:rPrDefault></w:docDefaults>'
            '<w:style w:type="paragraph" w:styleId="Normal">'
            '<w:pPr><w:spacing w:after="120" w:line="360" w:lineRule="auto"/></w:pPr>'
            '<w:rPr><w:rFonts w:eastAsia="宋体"/><w:sz w:val="24"/></w:rPr></w:style>'
            '<w:style w:type="paragraph" w:styleId="Heading1">'
            '<w:pPr><w:spacing w:before="240" w:after="120"/></w:pPr>'
            '<w:rPr><w:b/><w:sz w:val="32"/><w:rFonts w:eastAsia="黑体"/></w:rPr></w:style>'
            '<w:style w:type="paragraph" w:styleId="Heading2">'
            '<w:pPr><w:spacing w:before="200" w:after="120"/></w:pPr>'
            '<w:rPr><w:b/><w:sz w:val="28"/><w:rFonts w:eastAsia="黑体"/></w:rPr></w:style>'
            '<w:style w:type="paragraph" w:styleId="Heading3">'
            '<w:pPr><w:spacing w:before="160" w:after="120"/></w:pPr>'
            '<w:rPr><w:b/><w:sz w:val="26"/><w:rFonts w:eastAsia="黑体"/></w:rPr></w:style>'
            '</w:styles>')
    return base


def write_docx(text: str, out: Path) -> None:
    content_types = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                     '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                     '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                     '<Default Extension="xml" ContentType="application/xml"/>'
                     '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
                     '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/></Types>')
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>')
    drels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
             '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
             '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>')
    doc = build_document(text)
    styles = build_styles()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", rels)
        z.writestr("word/document.xml", doc)
        z.writestr("word/styles.xml", styles)
        z.writestr("word/_rels/document.xml.rels", drels)


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0 if argv and argv[0] in ("-h", "--help") else 1
    src = argv[0]
    out = Path(argv[1]) if len(argv) > 1 else None
    if src == "-":
        text = sys.stdin.read()
        if out is None:
            print("从 stdin 输入时必须指定输出文件（第二个参数）。", file=sys.stderr)
            return 1
    else:
        p = Path(src)
        if out is None:
            out = p.with_suffix(".docx")
        try:
            text = p.read_text(encoding="utf-8")
        except Exception as e:
            print(f"读取失败: {e}", file=sys.stderr)
            return 1
    try:
        write_docx(text, out)
    except Exception as e:
        print(f"写入失败: {e}", file=sys.stderr)
        return 1
    n_chars = len(re.sub(r"\s", "", text))
    print(f"已精确保留导出 -> {out}（正文约 {n_chars} 字，未作任何改写）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
