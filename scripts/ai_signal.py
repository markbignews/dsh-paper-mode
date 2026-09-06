#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ai_signal.py — 论文 AI 写作痕迹信号扫描（启发式、确定性，零依赖）。
输入 .docx / .txt / .md 或 stdin 文本；把短段合并为 150–450 字分析块，
对每块输出句长节奏 / 连接词 / 模板套话 / 缓和语 / 引用数据等信号。

⚠️ 本脚本只输出"证据"，不做最终判定：AI 率估算与风险等级由调用方(模型)
结合原文按 references/aigc_signals_zh.md 判定，并如实告知用户这只是估算。

用法:
    python3 ai_signal.py <论文.docx|.txt|.md>      # 按输入文件分析
    python3 ai_signal.py -                          # 从 stdin 读全文
"""
import re
import sys

# ---------- 文本获取 ----------

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_ENTITY = {"&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"', "&apos;": "'"}


def _read_docx(path: str) -> list[str]:
    import zipfile

    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8", errors="replace")
    xml = re.sub(r"<w:tab\s*/>", " ", xml)
    xml = re.sub(r"<w:br\s*/>", " ", xml)
    paras = re.findall(r"<w:p\b[^>]*>.*?</w:p>", xml, flags=re.S)
    out = []
    for p in paras:
        texts = re.findall(r"<w:t\b[^>]*>(.*?)</w:t>", p, flags=re.S)
        t = "".join(texts)
        for k, v in _ENTITY.items():
            t = t.replace(k, v)
        t = re.sub(r"\s+", " ", t).strip()
        if t:
            out.append(t)
    return out


def load_text(src: str) -> tuple[list[str], str]:
    """返回 (段落列表, 来源描述)。"""
    if src == "-":
        return [l.strip() for l in sys.stdin if l.strip()], "stdin"
    if src.lower().endswith(".docx"):
        paras = _read_docx(src)
        return paras, src
    with open(src, encoding="utf-8", errors="replace") as f:
        raw = f.read()
    if src.lower().endswith((".md", ".txt")):
        raw = re.sub(r"^#{1,6}\s*", "", raw, flags=re.M)  # 去掉 markdown 标题井号
    paras = [p.strip() for p in raw.splitlines() if p.strip()]
    return paras, src


# ---------- 切块 ----------

def make_chunks(paras: list[str], min_len: int = 150, max_len: int = 450) -> list[dict]:
    """把段落合并为块。返回 [{'start','end','text'}]，start/end 为段落下标（含两端）。"""
    chunks, cur, cur_idx, cur_len = [], [], [], 0
    for i, p in enumerate(paras):
        L = len(p)
        if cur and cur_len + L > max_len and cur_len >= min_len:
            chunks.append({"start": cur_idx[0], "end": cur_idx[-1], "text": "".join(cur)})
            cur, cur_idx, cur_len = [p], [i], L
        else:
            cur.append(p)
            cur_idx.append(i)
            cur_len += L
    if cur:
        chunks.append({"start": cur_idx[0], "end": cur_idx[-1], "text": "".join(cur)})
    # 兜底：超长单段(如被整体粘贴)按句子再拆
    final = []
    for c in chunks:
        if len(c["text"]) > max_len * 2 and c["start"] == c["end"]:
            sents = split_sentences(c["text"])
            buf, bl = [], 0
            for s in sents:
                if buf and bl + len(s) > max_len and bl >= min_len:
                    final.append({"start": c["start"], "end": c["end"], "text": "".join(buf)})
                    buf, bl = [], 0
                buf.append(s)
                bl += len(s)
            if buf:
                final.append({"start": c["start"], "end": c["end"], "text": "".join(buf)})
        else:
            final.append(c)
    return final


# ---------- 句子与统计 ----------

def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[。！？!?；;])", text)
    return [p for p in parts if p.strip()]


def count_any(text: str, patterns: list[str]) -> dict[str, int]:
    hits = {}
    for pat in patterns:
        n = len(re.findall(re.escape(pat), text))
        if n:
            hits[pat] = n
    return hits


def stats_sentences(sents: list[str]) -> dict:
    lens = [len(s) for s in sents if s.strip()]
    n = len(lens)
    if n == 0:
        return {"n": 0, "avg": 0.0, "sd": 0.0, "mid20_35": 0.0, "short_le15": 0.0, "long_ge45": 0.0}
    avg = sum(lens) / n
    var = sum((x - avg) ** 2 for x in lens) / n
    return {
        "n": n,
        "avg": round(avg, 1),
        "sd": round(var ** 0.5, 1),
        "mid20_35": round(sum(1 for x in lens if 20 <= x <= 35) / n, 2),
        "short_le15": round(sum(1 for x in lens if x <= 15) / n, 2),
        "long_ge45": round(sum(1 for x in lens if x >= 45) / n, 2),
    }


# ---------- 特征词典 ----------

# L4 连接词（按功能分组，组内同现即为"功能重叠"）
CONNECTORS = {
    "因果": ["因此", "从而", "进而", "由此", "基于此", "据此", "由此可见", "因而", "故"],
    "递进": ["此外", "与此同时", "不仅", "而且", "更为重要的是", "进一步"],
    "转折": ["然而", "但是", "不过", "却", "反之"],
    "总结": ["综上所述", "总而言之", "综上", "总体而言", "总的来看"],
    "时序": ["首先", "其次", "再次", "最后", "随后", "继而"],
    "条件/让步": ["虽然", "尽管", "即便", "除非", "一旦"],
}

# L5 模板/泛化套话
TEMPLATES = [
    "随着" , "在当今", "在当今日益", "日益", "备受关注", "越来越受到",
    "具有重要的理论意义和现实意义", "具有重要的理论意义", "现实意义",
    "发挥着重要作用", "扮演着重要角色", "不可忽视", "毋庸置疑", "毫无疑问",
    "值得注意的是", "需要指出的是", "总的来说", "综上所述", "由此可见",
    "在一定程度上", "一定程度上", "具有重要影响", "产生了深远影响",
    "提供了新的视角", "为……提供了", "以期", "有望", "助力", "赋能",
    "不难发现", "显而易见", "可以说", "所谓", "众所周知", "深入研究",
    "系统分析", "全面探讨", "本文旨在", "本研究旨在", "文章结构安排如下",
]

# 缓和语（人写特征，属正面信号；注意仅作参考项，不直接降风险）
HEDGES = ["较为", "相对", "通常", "往往", "一般说来", "可能", "或许", "有待", "尚需", "尝试", "初步"]

# 引用/数据类（缓和信号）
CITE_RE = re.compile(r"\[\d+(?:[-,，]\d+)*\]|（\d{4}）|\((\d{4})\)|等（\d{4}）|等\((\d{4})\)|图\s*\d+[—\-–]?\d*|表\s*\d+")
NUM_RE = re.compile(r"\d+(?:\.\d+)?%?")


def analyze(text: str) -> dict:
    sents = split_sentences(text)
    st = stats_sentences(sents)
    conn = {}
    for group, pats in CONNECTORS.items():
        hits = count_any(text, pats)
        if hits:
            conn[group] = hits
    tmpl = count_any(text, TEMPLATES)
    hedge = count_any(text, HEDGES)
    cites = len(CITE_RE.findall(text))
    nums = len(NUM_RE.findall(text))
    chars = len(re.sub(r"\s", "", text))
    return {
        "chars": chars,
        "sent": st,
        "connectors": conn,
        "templates": tmpl,
        "hedges": hedge,
        "cite_marks": cites,
        "numbers": nums,
    }


def fmt_hits(hits: dict[str, int], top: int = 6) -> str:
    if not hits:
        return "-"
    items = sorted(hits.items(), key=lambda kv: -kv[1])[:top]
    return " ".join(f"{k}x{v}" for k, v in items)


def fmt_conn(conn: dict[str, dict[str, int]]) -> str:
    if not conn:
        return "-"
    parts = []
    for group, hits in conn.items():
        parts.append(f"{group}(" + ", ".join(f"{k}x{v}" for k, v in hits.items()) + ")")
    return " ".join(parts)


# ---------- 主流程 ----------

def run(src: str) -> None:
    paras, source = load_text(src)
    if not paras:
        print("未提取到任何文本。")
        return
    total_chars = sum(len(re.sub(r"\s", "", p)) for p in paras)
    chunks = make_chunks(paras)

    print(f"=== 论文 AI 痕迹信号扫描（启发式估算，非官方检测）===")
    print(f"来源: {source}")
    print(f"段落数: {len(paras)}    总字符(去空白): {total_chars}    分析块数: {len(chunks)}")

    # 全文句长总览（L1 全文层面）
    all_sents = []
    for p in paras:
        all_sents += split_sentences(p)
    full = stats_sentences(all_sents)
    lens = [len(s) for s in all_sents if s.strip()]
    import statistics as _st
    blens = [c["text"] for c in chunks]
    print("\n--- 全文概览 ---")
    print(f"总句数: {full['n']}   平均句长: {full['avg']}   句长标准差: {full['sd']}")
    print(f"句长20-35字占比: {full['mid20_35']:.0%}   ≤15字短句占比: {full['short_le15']:.0%}   ≥45字长句占比: {full['long_ge45']:.0%}")
    if len(blens) >= 3:
        clens = [len(b) for b in blens]
        print(f"块长度均值: {sum(clens)/len(clens):.0f}   块长度标准差: {_st.pstdev(clens):.0f}  （越小说明段落密度越均匀，AI 化风险越高）")

    print("\n--- 逐块信号 ---")
    for ci, c in enumerate(chunks, 1):
        a = analyze(c["text"])
        s = a["sent"]
        print(f"\n[块{ci}] 段P{c['start']+1:03d}-P{c['end']+1:03d}  字数{a['chars']}  句数{s['n']}")
        print(f"  句长: 平均{s['avg']} 标准差{s['sd']}  20-35字占{s['mid20_35']:.0%}  ≤15字占{s['short_le15']:.0%}  ≥45字占{s['long_ge45']:.0%}")
        print(f"  连接词: {fmt_conn(a['connectors'])}")
        print(f"  模板/套话: {fmt_hits(a['templates'])}")
        print(f"  缓和语(人写特征): {fmt_hits(a['hedges'])}")
        print(f"  引用/图表标记: {a['cite_marks']}   数字: {a['numbers']}")
        # 同功能连接词重叠提示
        overlap = [g for g, h in a["connectors"].items() if len(h) >= 2]
        if overlap:
            print(f"  ⚠ 同功能连接词重叠组: {'、'.join(overlap)}  → L4 风险线索")
        mid = s["mid20_35"]
        if s["n"] >= 8 and mid >= 0.6 and s["sd"] and s["sd"] < 9:
            print(f"  ⚠ 长句分布集中(20-35字占{mid:.0%}且标准差{s['sd']}<9)  → L1 节奏均匀风险线索")
        if a["templates"]:
            print(f"  ⚠ 命中模板/套话  → L5 风险线索（需结合上下文判断是否为泛化空话）")
    print("\n=== 结束：以上仅为信号证据，请结合原文与信号库判定风险等级并估算 AI 率 ===")


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0 if argv and argv[0] in ("-h", "--help") else 1
    run(argv[0])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
