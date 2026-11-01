#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从语料中资产化抽取：把课件原文里的可训练资产结构化。
产出：
  corpus_assets.jsonl   —— 结构化资产（异议类型/拒绝话术/科室性格/医生画像/拜访阶段/合规红线）
  corpus_assets.md      —— 人工可读资产清单
这是 Phase 0 各任务的素材底座，也是 Phase 1「真实场景库」的预置种子。
"""
import re, glob, os, json

TXT = "/workspace/output/phase0/corpus_txt"
OUT = "/workspace/output/phase0"


def load():
    docs = []
    for f in sorted(glob.glob(os.path.join(TXT, "*.txt"))):
        raw = open(f, encoding="utf-8").read()
        body = raw.split("\n", 1)[1] if "\n" in raw else raw
        parts = re.split(r"\n===== Slide (\d+) =====\n", body)
        code = os.path.basename(f)[:-4].split("-")[0]
        title = os.path.basename(f)[:-4].split("-", 1)[-1]
        slides = []
        for i in range(1, len(parts), 2):
            slides.append((int(parts[i]), parts[i + 1]))
        docs.append({"code": code, "title": title, "slides": slides})
    return docs


def sents(text):
    t = text.replace("⏎", " ").replace("\n", " ")
    return [p.strip() for p in re.split(r"(?<=[。！？；;])", t) if 12 <= len(p.strip()) <= 240]


# 资产类型识别规则
ASSET_RULES = [
    # (asset_type, 正则, 需含上下文关键词之一)
    ("异议类型", r"(价格|费用|疗效|副作用|安全性|时间|产品|医药代表|服务|竞争|竞品|决策|资金)异议", None),
    ("拒绝理由", r"(拒绝|不同意|不接受|没兴趣|没时间|不用|不需要|考虑一下|再说|资料先放|研究研究)[^。]{0,40}", None),
    ("科室性格", r"(外科|内科|妇科|儿科|肿瘤|骨科|呼吸|心内|中医|急诊|影像|检验)[^。]{0,70}?(喜欢|讨厌|反感|不接受|偏好|干脆|啰嗦|直接|慢|性格)", None),
    ("医生画像", r"(医生|客户|主任)[^。]{0,25}(喜欢|讨厌|最不喜欢|尊重|反感|看重|关注|关心)[^。]{0,120}", None),
    ("拜访阶段", r"(访前准备|访中|访后|拜访前|拜访中|拜访后|开场|破冰|需求|呈现|异议处理|推进|成交|承诺|会后分析|访后分析)[^。]{0,90}", None),
    ("情绪心理", r"(恐惧|畏惧|焦虑|压力|自信|信心|情绪|心态|挫折|拒绝后)[^。]{0,90}", None),
    ("合规红线", r"(不得|禁止|严禁|不允许|不可以|违规|违法|职业道德|职业操守|廉洁|不正当|商业贿赂|恶意诋毁|夸大不实|诋毁竞争对手)[^。]{0,120}", None),
    ("灰色手法", r"(回扣|返利|红包|好处费|临床费|统方|处方数据|客情费|赞助个人|二次公关|摆平|窜货)[^。]{0,110}", None),
    ("商务术语", r"(扣率|挂网|招标|进药|代理|大包|小包|走医院|走市场|窜货|药事管理委员会|确标)[^。]{0,110}", None),
]

# 灰色手法：这些是"教材里存在但违规/不可推荐"的内容，单独标记
GRAY = {"回扣", "返利", "红包", "好处费", "临床费", "统方", "处方数据", "客情费", "赞助个人", "二次公关", "摆平", "窜货"}


def classify(s):
    for atype, pat, _ in ASSET_RULES:
        if re.search(pat, s):
            return atype
    return None


def main():
    docs = load()
    assets = []
    seen = set()
    for d in docs:
        for n, text in d["slides"]:
            for s in sents(text):
                atype = classify(s)
                if not atype:
                    continue
                key = (d["code"], n, s[:50])
                if key in seen:
                    continue
                seen.add(key)
                gray = atype == "灰色手法" or any(g in s for g in GRAY)
                assets.append({
                    "asset_id": f"{atype}-{len(assets)+1:04d}",
                    "type": atype,
                    "text": s,
                    "source": f"[{d['code']} S{n}]",
                    "course": d["code"],
                    "course_title": d["title"],
                    "slide": n,
                    "gray_area": gray,
                })

    with open(os.path.join(OUT, "corpus_assets.jsonl"), "w", encoding="utf-8") as fh:
        for a in assets:
            fh.write(json.dumps(a, ensure_ascii=False) + "\n")

    # md 清单
    from collections import defaultdict
    by_type = defaultdict(list)
    for a in assets:
        by_type[a["type"]].append(a)

    lines = ["# 语料资产清单 — 从课件库结构化抽取的可训练素材", "",
             "> 由 `build_assets.py` 自动抽取，**所有 text 字段均为课件原文**，未改写。",
             f"> 资产总数 **{len(assets)}**，来源 {len(docs)} 个课件。",
             "",
             "> ⚠️ **灰色手法区**：`gray_area=true` 的条目是课件中存在但**不可作为推荐做法**的内容",
             "> （回扣/临床费/统方/二次公关等）。它们只用于两件事：",
             "> ① 作为 D2 合规红线的**识别对象**；② 作为 D7 基线集的**违规正例素材**。",
             "> 任何任务都不得把它们写成推荐行为。",
             ""]
    order = ["异议类型", "拒绝理由", "医生画像", "科室性格", "拜访阶段",
             "情绪心理", "合规红线", "灰色手法", "商务术语"]
    for atype in order:
        items = by_type.get(atype, [])
        if not items:
            continue
        lines.append(f"## {atype}（{len(items)} 条）")
        lines.append("")
        by_course = defaultdict(list)
        for it in items:
            by_course[(it["course"], it["course_title"])].append(it)
        for (code, title), group in sorted(by_course.items()):
            lines.append(f"**[{code}] {title}**")
            lines.append("")
            for it in group[:10]:
                mark = " ⚠️灰色" if it["gray_area"] else ""
                lines.append(f"- `{it['source']}`{mark} {it['text']}")
            if len(group) > 10:
                lines.append(f"- *（本课件另有 {len(group)-10} 条）*")
            lines.append("")
    open(os.path.join(OUT, "corpus_assets.md"), "w", encoding="utf-8").write("\n".join(lines))

    print(f"[assets] {len(assets)} 条 -> corpus_assets.jsonl / corpus_assets.md")
    for atype in order:
        print(f"  {atype}: {len(by_type.get(atype, []))}")
    print(f"  其中灰色手法标记: {sum(1 for a in assets if a['gray_area'])}")


if __name__ == "__main__":
    main()
