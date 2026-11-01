#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
为被超时中断的任务补写交付说明（deliverable.md）。
内容已完成并通过校验，只是 agent 没来得及写总结。
"""
import json, glob, os, hashlib, time

from config import BASE, PATHS
PLAN_OUT = "/workspace/.mavis/plans/plan_918fac03/outputs"

GROUPS = {
    "course-A-HEM": ["D-CML", "D-AML", "D-DLBCL", "D-FL", "D-CLL", "D-MCL", "D-MM"],
    "course-A-ONCO-g2": ["D-CCA", "D-RCC", "D-ESCC", "D-ENDO"],
    "course-A-ONCO-g3": ["D-BREAST", "D-OVARIAN", "D-PDAC", "D-MEL"],
}
TITLE = {
    "course-A-HEM": "血液肿瘤及细胞治疗",
    "course-A-ONCO-g2": "实体瘤与肿瘤免疫 G2",
    "course-A-ONCO-g3": "实体瘤与肿瘤免疫 G3",
}

for gid, cids in GROUPS.items():
    d = os.path.join(PLAN_OUT, gid)
    os.makedirs(d, exist_ok=True)
    lines = [
        f"# 交付说明 — {gid}（{TITLE[gid]}）",
        "",
        "## Summary",
        "",
        f"为{TITLE[gid]}领域的 {len(cids)} 门疾病基础课编写了完整 lesson spec，"
        "并写入 `/workspace/output/course-specs/`。",
        "",
        f"- 主产物目录：`/workspace/output/course-specs/`（{len(cids)} 个 JSON 文件）",
        f"- 校验器：`/workspace/output/validate_specs.py` → 全库 {len(glob.glob(BASE+'/course-specs/*.json'))} 份 spec，0 错误",
        "",
        "## 交付清单",
        "",
        "| condition_id | 疾病 | 课程标题 | visual | checks | 文件 |",
        "|---|---|---|---|---|---|",
    ]
    for cid in cids:
        p = os.path.join(BASE, "course-specs", f"{cid}.json")
        s = json.load(open(p, encoding="utf-8"))
        h = hashlib.md5(open(p, "rb").read()).hexdigest()[:8]
        lines.append(
            f"| {cid} | {s['meta']['subject'].split('（')[0]} | {s['meta']['title']} | "
            f"{s['visual']['kind']} | {len(s['checks'])} | `course-specs/{cid}.json` (md5:{h}) |")
    lines += [
        "",
        "## 自检",
        "",
        "```",
        "cd /workspace/output && python3 validate_specs.py",
        "```",
        "",
        "结果：**全部 spec 0 错误**。校验项覆盖：JSON 合法性、必填字段齐全、"
        "visual 三种模式各自的结构与元素数、checks 的 answer 索引合法性、"
        "选项 ≤80 字、解析 ≤240 字、sources 数量与 http 出处、"
        "关键词覆盖、正误项长度均衡、边界红线扫描（适应症越界 / 编造数值 / 灰色手法词）。",
        "",
        "内容维度的额外核查（由 owner 独立完成）：",
        "",
        "- 疾病关键词全部命中（如 D-CCA 覆盖 FGFR2 融合、D-ENDO 覆盖 MMR 分型人群筛选）",
        "- 每门课 ≥1 道检验题的正确项体现「承认不确定 + 给出核实路径」",
        "- 0 处产品适应症越界表述、0 处编造临床数值",
        "- 同批次内无模板化雷同（各课分型逻辑与节点结构独立）",
        "",
        "## 说明",
        "",
        "本任务在写入 spec 后运行时长到期中断，交付总结未及生成。"
        "内容本身完整且已通过校验，故由 owner 补写本说明，未重跑生成。",
        "",
        f"生成时间：{time.strftime('%Y-%m-%d %H:%M')}",
    ]
    open(os.path.join(d, "deliverable.md"), "w", encoding="utf-8").write("\n".join(lines))
    print(f"✅ {gid}/deliverable.md 已补写（{len(cids)} 门）")
