#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
office_extract.py — 从 Word(.docx) / PowerPoint(.pptx) / Excel(.xlsx) 提取文本（零依赖：仅 zipfile + re）。
输出为纯文本，便于后续交给 ai_signal.py 或直接阅读。

用法:
    python3 office_extract.py <docx|pptx|xlsx>            # 打印文本
    python3 office_extract.py <docx|pptx|xlsx> out.txt    # 写入文本文件
"""
import re
import sys
import zipfile

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
SP = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_ENTITY = {"&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"', "&apos;": "'"}


def _unescape(s: str) -> str:
    for k, v in _ENTITY.items():
        s = s.replace(k, v)
    return s


# ---------- docx ----------

def extract_docx(path: str) -> list[str]:
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8", errors="replace")
    xml = re.sub(r"<w:tab\s*/>", " ", xml)
    xml = re.sub(r"<w:br\s*/>", " ", xml)
    paras = re.findall(r"<w:p\b[^>]*>.*?</w:p>", xml, flags=re.S)
    out = []
    for p in paras:
        texts = re.findall(r"<w:t\b[^>]*>(.*?)</w:t>", p, flags=re.S)
        t = _unescape("".join(texts))
        t = re.sub(r"\s+", " ", t).strip()
        if t:
            out.append(t)
    return out


# ---------- pptx ----------

def extract_pptx(path: str) -> list[str]:
    lines: list[str] = []
    with zipfile.ZipFile(path) as z:
        names = [n for n in z.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", n)]
    names.sort(key=lambda n: int(re.search(r"(\d+)", n).group(1)))
    with zipfile.ZipFile(path) as z:
        for i, n in enumerate(names, 1):
            xml = z.read(n).decode("utf-8", errors="replace")
            texts = re.findall(r"<a:t\b[^>]*>(.*?)</a:t>", xml, flags=re.S)
            seg = [_unescape(t) for t in texts]
            seg = [_ for _ in seg if _.strip()]
            lines.append(f"--- 幻灯片 {i} ---")
            lines.extend(" ".join(p.strip().split()) for p in seg if p.strip())
            lines.append("")
    return lines


# ---------- xlsx ----------

def extract_xlsx(path: str) -> list[str]:
    lines: list[str] = []
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        # 共享字符串表（索引 → 文本）
        shared: list[str] = []
        if "xl/sharedStrings.xml" in names:
            sxml = z.read("xl/sharedStrings.xml").decode("utf-8", errors="replace")
            for si in re.findall(r"<si\b[^>]*>.*?</si>", sxml, flags=re.S):
                ts = re.findall(r"<t\b[^>]*>(.*?)</t>", si, flags=re.S)
                shared.append(_unescape("".join(ts)))
        # sheet 顺序与名称
        sheet_names: list[str] = []
        if "xl/workbook.xml" in names:
            wxml = z.read("xl/workbook.xml").decode("utf-8", errors="replace")
            for s in re.findall(r"<sheet\b[^>]*/>", wxml):
                m = re.search(r'name="([^"]*)"', s)
                if m:
                    sheet_names.append(_unescape(m.group(1)))
        # 逐个 sheet
        sheets = sorted(
            [n for n in names if re.match(r"xl/worksheets/sheet\d+\.xml$", n)],
            key=lambda n: int(re.search(r"(\d+)", n).group(1)),
        )
        for idx, n in enumerate(sheets):
            title = sheet_names[idx] if idx < len(sheet_names) else n
            lines.append(f"=== 工作表: {title} ===")
            xml = z.read(n).decode("utf-8", errors="replace")
            for row in re.findall(r"<row\b[^>]*>.*?</row>", xml, flags=re.S):
                cells = []
                for c in re.findall(r"<c\b[^>]*>.*?</c>", row, flags=re.S):
                    t = re.search(r't="([^"]*)"', c)
                    v = re.search(r"<v\b[^>]*>(.*?)</v>", c, flags=re.S)
                    val = ""
                    if v:
                        raw = _unescape(v.group(1))
                        if t and t.group(1) == "s":
                            try:
                                val = shared[int(raw)] if int(raw) < len(shared) else raw
                            except Exception:
                                val = raw
                        else:
                            val = raw
                    cells.append(val)
                if any(c.strip() for c in cells):
                    lines.append("\t".join(cells))
            lines.append("")
    return lines


# ---------- 分发 ----------

def extract(path: str) -> list[str]:
    lower = path.lower()
    if lower.endswith(".docx"):
        return extract_docx(path)
    if lower.endswith(".pptx"):
        return extract_pptx(path)
    if lower.endswith(".xlsx"):
        return extract_xlsx(path)
    raise ValueError("仅支持 .docx / .pptx / .xlsx")


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0 if argv and argv[0] in ("-h", "--help") else 1
    src = argv[0]
    try:
        lines = extract(src)
    except Exception as e:
        print(f"提取失败: {e}", file=sys.stderr)
        return 1
    if len(argv) > 1:
        with open(argv[1], "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        print(f"已提取 {len(lines)} 行 -> {argv[1]}", file=sys.stderr)
    else:
        print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
