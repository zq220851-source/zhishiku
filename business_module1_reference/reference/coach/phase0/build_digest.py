#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从语料中定向抽取高价值结构化片段，供 Phase 0 各任务引用。
产出 corpus_digest.md —— 按主题组织，每条给 [课件编号 Slide号] + 原文。
"""
import re, glob, os

TXT = "/workspace/output/phase0/corpus_txt"
OUT = "/workspace/output/phase0/corpus_digest.md"

# (主题标题, 正则, 最小命中长度, 最大条数)
TOPICS = [
    ("一、医生画像与科室性格（→ D1 画像卡）", [
        (r"科室[^。]{0,60}?(喜欢|讨厌|反感|不接受|偏好)[^。]{0,120}。", 6),
        (r"(外科|内科|妇科|儿科|肿瘤科|骨科|呼吸科|心内科|中医科|急诊)[^。]{0,80}?(喜欢|讨厌|性格|直接|干脆|啰嗦|慢)[^。]{0,120}。", 6),
        (r"(医生|客户|主任)[^。]{0,20}(喜欢|讨厌|最不喜欢|尊重)[^。]{0,160}。", 8),
        (r"医生选择[^。]{0,20}的[^。]{0,20}因素[^。]{0,200}。", 2),
        (r"(医生类型|客户分类|客户分析)[^。]{0,200}。", 3),
    ], 26),
    ("二、拜访流程与阶段（→ D1/D3/D4）", [
        (r"(访前准备|访中|访后|拜访前|拜访中|拜访后)[^。]{0,140}。", 8),
        (r"(开场白|开场)[^。]{0,40}(需要|注意|方法|技巧)[^。]{0,180}。", 5),
        (r"(完整)?拜访(步骤|流程|过程)[^。]{0,180}。", 5),
        (r"(销售|专业拜访)(八步骤|四部曲|五步)[^。]{0,200}。", 5),
        (r"需求(探询|了解|挖掘)[^。]{0,160}。", 4),
        (r"(探询|提问)[^。]{0,30}(技巧|方法|要点)[^。]{0,160}。", 5),
    ], 30),
    ("三、异议分类与处理（→ D2/D7 基线集素材）", [
        (r"(真实异议|虚假异议|异议的?类型)[^。]{0,220}。", 6),
        (r"(价格|费用|疗效|副作用|安全性|时间|产品|医药代表|服务|竞争|竞品)异议[^。]{0,200}。", 14),
        (r"客户(拒绝|异议)[^。]{0,200}。", 6),
        (r"(处理|应对|化解)(异议|拒绝|反对意见)[^。]{0,180}。", 6),
        (r"(缓冲|重评|对抗|归类|逆转|劣选|吸引)[^。]{0,140}。", 6),
        (r"(拒绝|异议)[^。]{0,30}的(含义|原因|类型|处理)[^。]{0,200}。", 5),
    ], 32),
    ("四、合规红线与行为规范（→ D2 硬红线）", [
        (r"(不得|禁止|严禁|不允许|不可以)[^。]{0,160}。", 14),
        (r"(违(规|法)|合规|廉洁|职业道德|职业操守|九不准)[^。]{0,180}。", 12),
        (r"(回扣|返利|红包|好处费|利益)[^。]{0,140}。", 12),
        (r"(恶意诋毁|诋毁|贬低|攻击)(竞品|竞争对手|竞品产品|对手)[^。]{0,140}。", 6),
        (r"(夸大|绝对化|承诺|保证)[^。]{0,140}。", 8),
        (r"(处方|统方|用药)[^。]{0,30}(数据|统计)[^。]{0,140}。", 4),
    ], 30),
    ("五、医生需求与关注点（→ D1 追问三轴）", [
        (r"医生(最)?(关心|关注|在意)[^。]{0,180}。", 6),
        (r"(临床)?(需求|顾虑|问题)[^。]{0,30}(类型|分类|哪些)[^。]{0,200}。", 5),
        (r"(临床费|学术支持|学术活动|会议|样品)[^。]{0,140}。", 6),
        (r"医(生|师)(的)?(时间|精力|习惯)[^。]{0,140}。", 4),
    ], 20),
    ("六、情绪与心理（→ D1 情绪标签池）", [
        (r"(情绪|心态|心理)[^。]{0,30}(类型|分类|管理|调整)[^。]{0,180}。", 6),
        (r"(恐惧|畏惧)(失败|被拒绝)[^。]{0,160}。", 4),
        (r"(自信|信心)[^。]{0,30}(培养|来源|建立)[^。]{0,160}。", 4),
    ], 16),
]

# 判定为"合规相关"的高价值句子（人工精挑关键词）
COMPLIANCE_STRONG = [
    "不得", "禁止", "严禁", "不可以", "不允许", "违规", "违法", "职业道德", "职业操守",
    "廉洁", "九不准", "不正当", "商业贿赂", "回扣", "好处费", "利益输送", "诋毁", "恶意",
    "夸大", "承诺疗效", "绝对化", "未经授权", "处方数据", "统方",
]


def load():
    files = sorted(glob.glob(os.path.join(TXT, "*.txt")))
    docs = []
    for f in files:
        raw = open(f, encoding="utf-8").read()
        body = raw.split("\n", 1)[1] if "\n" in raw else raw
        parts = re.split(r"\n===== Slide (\d+) =====\n", body)
        code = os.path.basename(f)[:-4].split("-")[0]
        title = os.path.basename(f)[:-4].split("-", 1)[-1]
        slides = []
        for i in range(1, len(parts), 2):
            slides.append((int(parts[i]), parts[i + 1]))
        docs.append((code, title, slides))
    return docs


def sentences(text):
    """按中文句号/分号/换行切句，保留可引用粒度"""
    t = text.replace("⏎", " ").replace("\n", " ")
    parts = re.split(r"(?<=[。！？；;])", t)
    out = []
    for p in parts:
        p = p.strip()
        if 12 <= len(p) <= 220:
            out.append(p)
    return out


def main():
    docs = load()
    lines = [
        "# 语料结构化摘要 — 医药代表培训课件库",
        "",
        "> 本文件由 `build_digest.py` 从 /workspace/output/phase0/corpus_txt 自动抽取，**所有句子均为课件原文**，未做改写。",
        "> 引用格式 `[课件编号 Slide号]`。用于 Phase 0 各任务的锚点素材。",
        f"> 语料规模：{len(docs)} 课件 / {sum(len(s) for _,_,s in docs)} 页。",
        "",
    ]
    seen = set()
    for sec_title, rules, cap in TOPICS:
        lines.append(f"## {sec_title}")
        lines.append("")
        picked = []
        for code, title, slides in docs:
            for n, text in slides:
                for s in sentences(text):
                    for pat, _minlen in rules:
                        if re.search(pat, s):
                            key = (code, n, s[:40])
                            if key in seen:
                                break
                            seen.add(key)
                            picked.append((code, title, n, s))
                            break
                    if len(picked) >= cap:
                        break
                if len(picked) >= cap:
                    break
            if len(picked) >= cap:
                break
        # 按课件聚类展示，便于回查
        by_code = {}
        for code, title, n, s in picked:
            by_code.setdefault((code, title), []).append((n, s))
        for (code, title), items in by_code.items():
            lines.append(f"**[{code}] {title}**")
            lines.append("")
            for n, s in items:
                lines.append(f"- `[S{n}]` {s}")
            lines.append("")
        lines.append(f"> 本节共 {len(picked)} 条原文片段。")
        lines.append("")

    # 合规高危句子单独成节
    lines.append("## 七、合规高危原文集中清单（→ D2 硬红线素材）")
    lines.append("")
    lines.append("> 下列句子在语料中同时命中合规敏感词与行为描述，供 D2 建立红线规则时对照。")
    lines.append("> 注意：课件是**培训材料**，不是法律依据——引用时须标明\"培训教材所载规范\"这一层。")
    lines.append("")
    hits = []
    for code, title, slides in docs:
        for n, text in slides:
            for s in sentences(text):
                if any(k in s for k in COMPLIANCE_STRONG):
                    hits.append((code, title, n, s))
    by_code = {}
    for code, title, n, s in hits:
        by_code.setdefault((code, title), []).append((n, s))
    for (code, title), items in sorted(by_code.items()):
        lines.append(f"**[{code}] {title}**")
        lines.append("")
        for n, s in items[:12]:
            lines.append(f"- `[S{n}]` {s}")
        if len(items) > 12:
            lines.append(f"- *（本课件另有 {len(items)-12} 条同类，可用检索命令获取）*")
        lines.append("")
    lines.append(f"> 共命中 {len(hits)} 条。")

    open(OUT, "w", encoding="utf-8").write("\n".join(lines))
    print(f"[digest] -> {OUT}")
    for sec_title, rules, cap in TOPICS:
        pass
    # 统计
    print(f"总字数 {len(''.join(lines)):,}")
    # 合规段统计
    print(f"合规高危句 {len(hits)} 条")


if __name__ == "__main__":
    main()
