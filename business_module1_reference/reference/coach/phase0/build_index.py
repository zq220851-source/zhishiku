#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
对已抽取的语料建立检索索引 + 主题分类。
产出：
  corpus_index.md   —— 人工可读的课件清单 + 主题标签 + 规模统计
  corpus_search.py  —— 关键词检索工具（供专家 agent 用 bash 调用）
  topic_map.json    —— 课件 -> 主题标签映射
"""
import os, json, re, glob

TXT = "/workspace/output/phase0/corpus_txt"
OUT = "/workspace/output/phase0"

# 主题判定规则：关键词 -> 主题标签。顺序即优先级
TOPIC_RULES = [
    ("行为规范与合规", ["行为规范", "廉洁", "合规", "九不准", "反商业贿赂", "职业道德", "职业操守",
                        "禁止", "不得", "违规", "条例", "法规", "法律", "廉洁从业"]),
    ("拜访流程与步骤", ["拜访步骤", "拜访流程", "工作流程", "销售八步骤", "四部曲", "专业拜访步骤",
                        "完整流程", "销售流程", "步骤", "流程"]),
    ("开场与破冰", ["顺利开场", "开场", "破冰", "引入", "自我介绍", "寒暄", "开场白"]),
    ("需求探询与提问", ["需求", "探询", "提问", "问诊", "了解需求", "痛点", "诊断"]),
    ("异议处理与拒绝", ["异议", "拒绝", "拒绝处理", "应对异议", "反对意见", "处理拒绝", "异议处理",
                        "如何应对", "说服", "促单", "成交", "获得承诺"]),
    ("医生画像与客户分类", ["客户", "医生类型", "客户分析", "潜力分析", "客户细分", "性格",
                            "沟通技巧", "与医生沟通", "处方", "影响力", "决策人", "学术推广"]),
    ("学术呈现与内容", ["学术", "循证", "循证医学", "证据", "指南", "适应症", "机制", "作用机制",
                        "产品介绍", "药品知识", "医学", "常见病", "适应症", "临床", "学术活动", "科室会"]),
    ("心理与情绪管理", ["心理", "情绪", "压力", "心态", "自信", "挫折", "拒绝后", "信心", "礼仪", "形象"]),
    ("时间与行程管理", ["时间管理", "拜访管理", "行程", "日程", "效率", "一天", "计划"]),
    ("职业发展与自我管理", ["职业生涯", "职业规划", "目标管理", "晋升", "职业", "收入", "待遇"]),
    ("渠道与终端运营", ["终端", "进药", "渠道", "窜货", "招标", "挂网", "扣率", "商业", "代理",
                        "经销商", "大包", "小包", "走医院", "走市场", "价格"]),
    ("医院开发与准入", ["医院开发", "开发医院", "民营医院", "准入", "进院", "药事", "科室",
                        "医院分级", "客户资源", "新医院", "目标医院"]),
    ("销售技巧与实战", ["销售技巧", "实战", "技巧", "销售", "签单", "铺货", "动销", "上量",
                        "客情", "维护", "关系"]),
    ("团队与客户关系管理", ["团队", "主管", "区域", "市场管理", "大区", "汇报", "客户关系", "CRM"]),
]

STOP = set("的了和与及或在是有为对从到这那我们你们他们一个这个那个之其以所不很也都还就要会能可")


def classify(text):
    hits = {}
    for topic, kws in TOPIC_RULES:
        c = sum(text.count(k) for k in kws)
        if c:
            hits[topic] = c
    if not hits:
        return []
    ranked = sorted(hits.items(), key=lambda kv: -kv[1])
    # 只保留占比显著的，最多 3 个
    total = sum(hits.values())
    out = [(t, c, c / total) for t, c in ranked[:4] if c / total >= 0.12 or c >= 8]
    return [(t, c) for t, c, _ in out]


def build():
    files = sorted(glob.glob(os.path.join(TXT, "*.txt")))
    entries = []
    for f in files:
        raw = open(f, encoding="utf-8").read()
        stem = os.path.basename(f)[:-4]
        body = raw.split("\n", 1)[1] if "\n" in raw else raw
        slides = body.count("===== Slide ")
        # 逐 slide 拆分，用于 slide 级索引
        slide_map = []
        parts = re.split(r"\n===== Slide (\d+) =====\n", body)
        for i in range(1, len(parts), 2):
            n = int(parts[i])
            content = parts[i + 1] if i + 1 < len(parts) else ""
            slide_map.append({"n": n, "text": content.strip(), "len": len(content)})
        topics = classify(body)
        entries.append({
            "stem": stem,
            "title": stem.split("-", 1)[1] if "-" in stem else stem,
            "code": stem.split("-")[0],
            "slides": slides,
            "chars": len(body),
            "topics": [t for t, _ in topics],
            "slide_map": slide_map,
        })

    entries.sort(key=lambda e: e["code"])
    with open(os.path.join(OUT, "topic_map.json"), "w", encoding="utf-8") as fh:
        json.dump([{k: v for k, v in e.items() if k != "slide_map"} for e in entries],
                  fh, ensure_ascii=False, indent=2)

    # 索引 md
    lines = ["# 语料索引 — 医药代表培训课件库", "",
             f"课件总数 **{len(entries)}**，Slide 总数 **{sum(e['slides'] for e in entries)}**，"
             f"正文字符 **{sum(e['chars'] for e in entries):,}**", "",
             "> 检索脚本：`python3 /workspace/output/phase0/corpus_search.py <关键词> [关键词2 ...]`",
             "> 检索脚本默认返回命中课件 + slide 号 + 原文片段，支持 `--full` 看完整 slide 文本。",
             "> 所有 slide 文本已按 slide 切分并保留原文，未做改写。", "",
             "## 课件清单", "",
             "| 编号 | 标题 | Slide | 字符 | 主题标签 |",
             "|---|---|---|---|---|"]
    for e in entries:
        lines.append(f"| {e['code']} | {e['title']} | {e['slides']} | {e['chars']:,} | "
                     f"{'、'.join(e['topics']) if e['topics'] else '—'} |")

    # 主题聚合
    lines += ["", "## 按主题聚合", ""]
    agg = {}
    for e in entries:
        for t in e["topics"]:
            agg.setdefault(t, []).append(e["code"])
    for t, codes in sorted(agg.items(), key=lambda kv: -len(kv[1])):
        lines.append(f"**{t}**（{len(codes)} 个课件）：{', '.join(codes)}")

    open(os.path.join(OUT, "corpus_index.md"), "w", encoding="utf-8").write("\n".join(lines))
    print(f"[index] {len(entries)} 课件, {sum(e['slides'] for e in entries)} slides")
    for t, codes in sorted(agg.items(), key=lambda kv: -len(kv[1])):
        print(f"  {t}: {len(codes)}")


if __name__ == "__main__":
    build()
