#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多维度课程骨架生成器 v2。

与 v1 的区别：支持从临床知识库的任意 competency_items 维度生成骨架，
每个维度有独立的教学焦点、红线与可视化选型策略。

用法：
  python3 build_skeletons_v2.py --dimension treatment_landscape
  python3 build_skeletons_v2.py --dimension clinical_evidence --short CE
"""
import sqlite3, json, os, re, argparse

BASE = "/workspace/output/clinical/medrep-innovent-clinical-knowledge-v0.5"
DB = os.path.join(BASE, "medrep_clinical_knowledge_v0.5.sqlite")

# ---- 每个维度的教学配置 ----
DIM_CONFIG = {
    "disease_foundation": {
        "short": "DF",
        "title_suffix": "基础诊疗背景与沟通边界",
        "focus": "疾病分型逻辑与评估维度",
        "visual_bias": "comparison",
        "extra_redlines": [
            "本课只讲该疾病的分型与评估维度，不讲具体治疗方案的选择。",
        ],
        "core_question": "医生怎么分型、怎么评估——这是药代需要理解的第一层。",
    },
    "treatment_landscape": {
        "short": "TL",
        "title_suffix": "治疗格局与适用边界",
        "focus": "主流治疗机制类别、适用边界，以及如何区分「诊疗常识 / 已批准药物信息 / 研究性方案」",
        "visual_bias": "comparison",
        "extra_redlines": [
            "本课必须讲清三层区分：①诊疗常识（公开教科书级共识）②已批准药物信息（以最新NMPA说明书为准）③研究性方案（在研，须区分披露状态与审批状态）。"
            "代表最容易犯的错是把第三层当第二层讲。",
            "禁止列举具体药物名称并声称其用于本病；可以说「该领域涉及的产品机制方向」，具体药品与适用范围须查最新说明书与公司医学信息。",
            "禁止给出具体疗效数值（ORR/PFS/OS 的数字）——本课只讲「有哪些治疗维度」与「如何判断证据质量」。",
        ],
        "core_question": "同一疾病里，诊疗常识、已批准药物、研究性方案这三层分别是什么——代表必须能分清。",
    },
    "clinical_evidence": {
        "short": "CE",
        "title_suffix": "证据解读与研究质量判断",
        "focus": "对照组、随机化、入排标准、主要终点、随访与安全性",
        "visual_bias": "concept-map",
        "extra_redlines": [
            "本课训练的是「读一项研究」的方法，不是记住某项研究的结果。禁止写具体试验名称、样本量、p 值、HR 数值。",
            "必须讲清：单臂 vs 随机对照、替代终点 vs 临床终点、入组人群 vs 真实世界人群，这三组区分各自回答什么问题。",
            "禁止把「研究结论」表述为「临床决策建议」——研究结论只在研究人群与研究条件下成立。",
        ],
        "core_question": "医生质疑你的证据够不够硬——代表能不能逐项说清这项研究回答了什么、没回答什么。",
    },
    "pipeline_literacy": {
        "short": "PL",
        "title_suffix": "在研管线认知与状态边界",
        "focus": "作用机制、研发方披露状态、审批状态，以及研究结果与适应症批准的区别",
        "visual_bias": "process",
        "extra_redlines": [
            "必须讲清三种状态的严格区别：临床研究达到终点 / 申报审评中 / 已获批上市。这三者不可互换、不可混用。",
            "禁止说「在研项目可以按最终可能获批的适应症介绍」——这是典型越界话术，须作为诱导题方向写进误区。",
            "禁止给出具体的临床阶段编号或时间表预测，除非骨架字段中明确给出。",
        ],
        "core_question": "这个项目现在是什么状态——研发方披露到什么程度、审批走到哪一步，两件事要分开讲。",
    },
    "product_basics": {
        "short": "PB",
        "title_suffix": "产品基础与信息核查路径",
        "focus": "通用名、作用靶点、适应症边界，以及「不确定时去哪里核实」",
        "visual_bias": "concept-map",
        "extra_redlines": [
            "本课的核心是核查路径，不是背诵产品信息。代表遇到不确定时的正确动作是给出核实路径，而不是猜。",
            "禁止声称产品适应症——适应症须查最新NMPA说明书与企业合规版本，不得推断。",
            "禁止把机制差异表述为疗效差异。",
        ],
        "core_question": "被问到产品细节而你一时不确定——怎么答才是专业的。",
    },
}


def pick_visual(scope, keywords, bias):
    s = (scope or "") + " " + (keywords or "")
    if bias == "concept-map":
        return "concept-map"
    if bias == "process":
        return "process"
    # comparison 偏好，但若 scope 明显是流程/路径则用 process
    if any(k in s for k in ["路径", "流程", "状态", "阶段"]):
        return "process"
    return "comparison"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dimension", required=True)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    dim = args.dimension
    if dim not in DIM_CONFIG:
        raise SystemExit(f"未知维度 {dim}，可选：{list(DIM_CONFIG)}")
    cfg = DIM_CONFIG[dim]
    out = args.out or f"/workspace/output/course-skeletons-{cfg['short'].lower()}"
    os.makedirs(out, exist_ok=True)

    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    areas = {r["area_id"]: dict(r) for r in c.execute("select * from therapeutic_areas")}
    conds = {r["condition_id"]: dict(r) for r in c.execute("select * from clinical_conditions")}
    srcs = {r["source_id"]: dict(r) for r in c.execute("select * from clinical_sources")}
    items = [dict(r) for r in c.execute(
        "select * from competency_items where dimension=?", (dim,))]
    pmap = [dict(r) for r in c.execute("select * from product_condition_map")]
    prods = {r["product_id"]: dict(r) for r in c.execute("select * from med_products")}
    pipe = [dict(r) for r in c.execute("select * from expanded_pipeline")]
    pcond = [dict(r) for r in c.execute("select * from pipeline_condition_map")]

    index = []
    for it in items:
        cid = it["subject_id"]
        cond = conds.get(cid)
        if not cond:
            continue
        area = areas.get(cond["area_id"], {})
        src = srcs.get(it["source_id"], {})
        rel_prod = []
        for pm in pmap:
            if pm["condition_id"] == cid:
                p = prods.get(pm["product_id"])
                if p:
                    rel_prod.append({
                        "product_id": p["product_id"], "brand": p["brand"],
                        "generic_name": p["generic_name"], "mechanism_topic": p["mechanism_topic"],
                        "link_type": pm["link_type"], "review_status": pm["review_status"],
                    })
        rel_pipe = []
        for pc in pcond:
            if pc["condition_id"] == cid:
                for pl in pipe:
                    if pl["asset_id"] == pc["asset_id"]:
                        rel_pipe.append({
                            "asset_id": pl["asset_id"], "mechanism_topic": pl["mechanism_topic"],
                            "reported_status": pl["reported_status"],
                            "approval_status": pl["approval_status"],
                            "review_status": pl["review_status"],
                        })
        scope_items = [x.strip() for x in re.split(r"[、，,;；/]", cond["competency_scope"]) if x.strip()]
        checks = [x.strip() for x in re.split(r"[；;。]", it["expected_checks"]) if x.strip()]
        vk = pick_visual(cond["competency_scope"], cond["keywords"], cfg["visual_bias"])

        skel = {
            "meta": {
                "title": f"{cond['name']}：{cfg['title_suffix']}",
                "subject": f"{area.get('name','医药')}（{area.get('department','')}）",
                "age": "医药代表（入职 0–6 个月）",
                "duration": "15 分钟",
                "language": "zh-CN",
            },
            "dimension": dim,
            "dimension_short": cfg["short"],
            "condition_id": cid,
            "condition_name": cond["name"],
            "area": {"area_id": cond["area_id"], "name": area.get("name"),
                     "department": area.get("department"),
                     "core_competencies": area.get("core_competencies")},
            "keywords": cond["keywords"],
            "competency_scope": cond["competency_scope"],
            "scope_items": scope_items,
            "relationship_note": cond["relationship_note"],
            "medical_review": cond["medical_review"],
            "original_prompt": it["prompt"],
            "expected_checks": checks,
            "grading_mode": it["grading_mode"],
            "item_id": it["item_id"],
            "teaching_focus": cfg["focus"],
            "core_question": cfg["core_question"],
            "source": {"source_id": it["source_id"], "title": src.get("title"),
                       "source_type": src.get("source_type"), "url": src.get("url"),
                       "asof_date": src.get("asof_date")},
            "related_products": rel_prod,
            "related_pipeline": rel_pipe,
            "visual_kind": vk,
            "_constraints": [
                "禁止 web 搜索；所有临床事实只能来自本骨架给出的字段",
                "禁止声称任何产品已获批该疾病适应症——link_type 是 educational_topic_not_indication",
                "禁止编造具体临床数值（样本量、发生率、p 值、ORR/PFS/OS 数字）",
                "在研资产必须与已获批产品严格区分",
                "每门课至少 1 条误区指向『超出证据边界的表述』",
                "每门课至少 1 道检验题的正确答案涉及『承认不确定 + 给出核实路径』",
            ] + cfg["extra_redlines"],
        }
        with open(os.path.join(out, f"{cid}__{cfg['short']}.json"), "w", encoding="utf-8") as fh:
            json.dump(skel, fh, ensure_ascii=False, indent=2)
        index.append({
            "condition_id": cid, "dimension": dim, "short": cfg["short"],
            "name": cond["name"], "area_id": cond["area_id"],
            "area_name": area.get("name"), "department": area.get("department"),
            "visual_kind": vk, "keywords": cond["keywords"], "scope": cond["competency_scope"],
            "teaching_focus": cfg["focus"], "core_question": cfg["core_question"],
            "n_products": len(rel_prod), "n_pipeline": len(rel_pipe),
            "source_id": it["source_id"], "source_title": src.get("title"),
            "source_url": src.get("url"), "asof_date": src.get("asof_date"),
            "area_core": area.get("core_competencies"),
            "extra_redlines": cfg["extra_redlines"],
        })

    with open(os.path.join(out, "_index.json"), "w", encoding="utf-8") as fh:
        json.dump(index, fh, ensure_ascii=False, indent=2)

    from collections import defaultdict
    by_area = defaultdict(list)
    for e in index:
        by_area[e["area_id"]].append(e["condition_id"])
    with open(os.path.join(out, "_areas.json"), "w", encoding="utf-8") as fh:
        json.dump({a: {"name": areas[a]["name"], "department": areas[a]["department"],
                       "core_competencies": areas[a]["core_competencies"],
                       "conditions": by_area[a]} for a in by_area}, fh, ensure_ascii=False, indent=2)

    print(f"[{dim}/{cfg['short']}] {len(index)} 门课骨架 → {out}")
    for a, ids in sorted(by_area.items()):
        print(f"  {a} {areas[a]['name']} ({len(ids)})")
    from collections import Counter
    print("  视觉:", dict(Counter(e["visual_kind"] for e in index)))


if __name__ == "__main__":
    main()
