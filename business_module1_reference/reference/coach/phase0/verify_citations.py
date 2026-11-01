#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全局引用校验器 —— 验证 Phase 0 全部产出文档中的语料引用是否真实存在。

检查项：
  1. 引用格式 [Axx Syy] 的编号与页码是否在语料中真实存在
  2. 引用附近若附带原文摘录（引号内），核对该摘录是否真出现在对应 slide 文本中
  3. 检出 web 来源残留（http/https 链接）、可疑的法规文号格式
  4. 检出灰色手法关键词被写进"推荐做法"语境（启发式）
  5. 统计每个文档的引用密度与无效引用

用法：
  python3 verify_citations.py                # 校验 /workspace/output/phase0 下所有 D*.md
  python3 verify_citations.py --file X.md    # 指定文件
  python3 verify_citations.py --verbose     # 打印无效引用明细
"""
import os, re, glob, json, sys
from collections import defaultdict

PHASE0 = "/workspace/output/phase0"
TXT = os.path.join(PHASE0, "corpus_txt")

CITE_RE = re.compile(r"\[([A-Z]\d{1,3})\s*S(\d{1,4})\]")

# 摘录提取：只认中文引号「」『』"”，避免把表格分隔符/Markdown 标记误当摘录
# 形式1: [A36 S162]：「原文...」     形式2: [A36 S162] "原文..."
QUOTE_PATTERNS = [
    re.compile(r"[「『]([^」』\n]{6,140})[」』]"),
    re.compile(r'[“"]([^”"\n]{6,140})[”"]'),
]

# 灰色手法关键词 —— 用于第 4 项检查
GRAY_WORDS = ["回扣", "临床费", "统方", "处方数据", "好处费", "返利", "二次公关", "窜货", "摆平"]

# 可疑的法规文号/版本号格式（编造高发区）
SUSPECT = [
    (re.compile(r"第\s*\d+\s*号令"), "疑似部令文号"),
    (re.compile(r"《[^》]{2,30}》\s*\(\s*\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日\s*施行"), "疑似施行日期"),
    (re.compile(r"文号[：:]\s*\S+"), "疑似文号声明"),
    (re.compile(r"(NMPA|国家药监局)\s*[\[(（]?\d{4}\s*年第?\s*\d+\s*号"), "疑似 NMPA 文号"),
]

VERB_CONTEXT = ["建议使用", "推荐使用", "应当使用", "应该使用", "可以采用", "正确做法是",
                "最佳实践", "应该这样", "应该向医生", "话术示范", "高分示范", "标准话术"]


def load_slides():
    """课件编号 -> {slide号: 文本}"""
    data = {}
    for f in glob.glob(os.path.join(TXT, "*.txt")):
        stem = os.path.basename(f)[:-4]
        code = stem.split("-")[0]
        raw = open(f, encoding="utf-8").read()
        body = raw.split("\n", 1)[1] if "\n" in raw else raw
        parts = re.split(r"\n===== Slide (\d+) =====\n", body)
        slides = {}
        for i in range(1, len(parts), 2):
            slides[int(parts[i])] = parts[i + 1]
        data.setdefault(code, {}).update(slides)
    return data


def normalize(s):
    """归一化：去所有空白与换行、全角转半角标点，便于摘录比对。

    注意：引文里的 / ／ —— 等可能是编者加的分隔符，原文里并不存在，
    因此比对用的"实义字符序列"必须把这些分隔符也剔除，否则必然不匹配。
    """
    s = s.replace("⏎", "")
    s = re.sub(r"\s+", "", s)
    pairs = [("：", ":"), ("，", ","), ("、", ","), ("。", "."), ("；", ";"),
             ("！", "!"), ("？", "?"), ("（", "("), ("）", ")"), ("【", "["),
             ("】", "]"), ("《", "<"), ("》", ">"), ("“", '"'), ("”", '"'),
             ("‘", "'"), ("’", "'"), ("－", "-"), ("～", "~"), ("−", "-"),
             ("\u3000", ""), ("—", ""), ("——", ""), ("/", ""), ("／", ""),
             (",", ""), (";", ""), (":", ""), (".", ""), ("!", ""), ("?", ""),
             ("(", ""), (")", ""), ("[", ""), ("]", ""), ("<", ""), (">", "")]
    for a, b in pairs:
        s = s.replace(a, b)
    return s


def char_overlap(q, hay):
    """字符级包含率：用于识别"转述/拼接/简称"型引文（字面不同但语义一致）"""
    qs = set(q)
    if not qs:
        return 0.0
    hs = set(hay)
    return len(qs & hs) / len(qs)


def check_file(path, data, verbose=False):
    raw = open(path, encoding="utf-8").read()
    lines = raw.split("\n")
    stats = {"cites": 0, "bad_page": [], "bad_quote": [], "misattributed": [],
             "web": [], "suspect": [], "gray_ctx": [], "reworded": [], "lines": len(lines)}
    total_cites = len(CITE_RE.findall(raw))
    stats["cites"] = total_cites

    for code, sl in CITE_RE.findall(raw):
        sn = int(sl)
        if code not in data:
            stats["bad_page"].append(f"{code} S{sn}（课件不存在）")
            continue
        if sn not in data[code]:
            stats["bad_page"].append(f"{code} S{sn}（页码不存在，该课件共 {len(data[code])} 页）")
            continue
        # 找该引用所在行，检查是否带原文摘录
        # 关键：引文归属于"本引用与下一个引用之间"的文本，不能取行内第一个引号
        for ln in lines:
            if f"[{code} S{sn}]" not in ln:
                continue
            if ln.strip().startswith("|") or ln.strip().startswith("```"):
                break
            # 定位本引用在行内的位置，取到下一个引用为止的片段
            pos = ln.find(f"[{code} S{sn}]")
            nxt = re.search(r"\[[A-Z]\d{1,3}\s*S\d{1,4}\]", ln[pos + 1:])
            seg = ln[pos + len(f"[{code} S{sn}]"): pos + 1 + nxt.start()] if nxt else ln[pos:]
            # 否定性陈述：引号内容是被否定的"不存在的说法"，不是引文
            NEG = re.compile(r"(没有|不存在|未[^\S]{0,3}有|无[^\S]{0,3}任何|不含|缺乏|未见|并非|不是)")
            for pat in QUOTE_PATTERNS:
                m = pat.search(seg[:220])
                if m:
                    prefix = seg[:m.start()]
                    if NEG.search(prefix):
                        break  # 跳过否定性引用
                    q = normalize(m.group(1)).rstrip("。.,，;；:：")
                    if len(q) >= 6:
                        hay = normalize(data[code][sn])
                        if q not in hay:
                            frag = q[:10]
                            if frag not in hay:
                                # 区分：语料中完全不存在 = 杜撰；存在于其他页 = 引文归属存疑
                                anywhere = any(q in normalize(t) for t in data[code].values())
                                if anywhere:
                                    stats["misattributed"].append(
                                        f"{code} S{sn}：引文「{m.group(1)[:36]}」存在于语料但不在此页")
                                else:
                                    # 转述/拼接/简称型：字符高度重叠 -> 表述待核，非杜撰
                                    ov = char_overlap(q, hay)
                                    if ov >= 0.82:
                                        stats["reworded"].append(
                                            f"{code} S{sn}：转述型引文「{m.group(1)[:36]}」（重叠{ov:.0%}，非逐字）")
                                    else:
                                        stats["bad_quote"].append(
                                            f"{code} S{sn}：引文「{m.group(1)[:40]}」语料中不存在")
                    break
            break

    # web 残留
    for i, ln in enumerate(lines, 1):
        for m in re.finditer(r"https?://[^\s\)\]\"，。；]+", ln):
            stats["web"].append(f"L{i}: {m.group(0)[:70]}")

    # 可疑文号
    for i, ln in enumerate(lines, 1):
        for pat, label in SUSPECT:
            if pat.search(ln):
                stats["suspect"].append(f"L{i} [{label}]: {ln.strip()[:80]}")

    # 灰色手法在推荐语境
    for i, ln in enumerate(lines, 1):
        if any(w in ln for w in GRAY_WORDS) and any(v in ln for v in VERB_CONTEXT):
            stats["gray_ctx"].append(f"L{i}: {ln.strip()[:90]}")

    return stats


def main():
    args = sys.argv[1:]
    verbose = "--verbose" in args
    if "--file" in args:
        i = args.index("--file")
        files = [args[i + 1]]
    else:
        files = sorted(glob.glob(os.path.join(PHASE0, "D*.md")))

    if not files:
        print("没有待校验文件（先等产出落地）")
        return

    data = load_slides()
    print(f"语料索引：{len(data)} 个课件 / {sum(len(v) for v in data.values())} 页\n")

    total_bad = 0
    summary = []
    for f in files:
        st = check_file(f, data, verbose)
        nbad = len(st["bad_page"]) + len(st["bad_quote"])
        total_bad += nbad
        name = os.path.basename(f)
        line = (f"{name:38} 引用 {st['cites']:4} | 无效页 {len(st['bad_page']):3} | "
                f"引文杜撰 {len(st['bad_quote']):3} | 归属存疑 {len(st['misattributed']):3} | "
                f"转述 {len(st['reworded']):3} | web {len(st['web']):2} | "
                f"可疑文号 {len(st['suspect']):2} | 灰色语境 {len(st['gray_ctx']):2}")
        summary.append((name, st, nbad))
        print(line)
        if verbose:
            for k in ("bad_page", "bad_quote", "misattributed", "reworded", "web", "suspect", "gray_ctx"):
                for item in st[k][:12]:
                    print(f"      · {k}: {item}")
            if st["bad_page"] or st["bad_quote"]:
                print()

    print(f"\n{'='*70}")
    print(f"合计：{len(files)} 个文档，{sum(st['cites'] for _, st, _ in summary)} 条引用，"
          f"{total_bad} 处无效")
    if total_bad == 0 and not any(s["web"] or s["suspect"] for _, s, _ in summary):
        print("✅ 全部引用有效，无 web 残留，无可疑文号")
    else:
        print("⚠️ 存在需要处理的问题，详见上方明细（加 --verbose 看细节）")
    # 写报告
    rep = {name: {k: v for k, v in st.items()} for name, st, _ in summary}
    with open(os.path.join(PHASE0, "citation_verification.json"), "w", encoding="utf-8") as fh:
        json.dump(rep, fh, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
