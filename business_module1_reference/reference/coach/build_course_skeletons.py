#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从临床知识库为每个疾病生成「课程骨架」，供 Agent 填充教学内容。

产出：
  course-skeletons/<condition_id>.json   —— 每门课的骨架（含真实 DB 字段）
  course-skeletons/_index.json           —— 全部课程清单 + 分组（按治疗领域，供并行分工）
  course-skeletons/_areas.json           —— 治疗领域及其核心能力（供 agent 理解领域）
"""
import sqlite3, json, os, re

BASE = "/workspace/output/clinical/medrep-innovent-clinical-knowledge-v0.5"
DB = os.path.join(BASE, "medrep_clinical_knowledge_v0.5.sqlite")
OUT = "/workspace/output/course-skeletons"
os.makedirs(OUT, exist_ok=True)

c = sqlite3.connect(DB)
c.row_factory = sqlite3.Row

areas = {r["area_id"]: dict(r) for r in c.execute("select * from therapeutic_areas")}
conds = {r["condition_id"]: dict(r) for r in c.execute("select * from clinical_conditions")}
srcs = {r["source_id"]: dict(r) for r in c.execute("select * from clinical_sources")}
items = [dict(r) for r in c.execute(
    "select * from competency_items where dimension='disease_foundation'")]
pmap = [dict(r) for r in c.execute(
    "select * from product_condition_map where condition_id is not null")]
prods = {r["product_id"]: dict(r) for r in c.execute("select * from med_products")}
pipe = [dict(r) for r in c.execute("select * from expanded_pipeline")]
pcond = [dict(r) for r in c.execute("select * from pipeline_condition_map")]

# 视觉模式分配：按 scope 关键词自动选择最贴合的交互模式
def pick_visual(scope, keywords):
    s = scope + " " + (keywords or "")
    if any(k in s for k in ["分层", "分型", "标志物", "靶点", "检测", "治疗线次", "分期"]):
        return "comparison"
    if any(k in s for k in ["路径", "流程", "机制", "作用", "评估"]):
        return "process"
    return "concept-map"


index = []
for it in items:
    cid = it["subject_id"]
    cond = conds.get(cid)
    if not cond:
        continue
    area = areas.get(cond["area_id"], {})
    src = srcs.get(it["source_id"], {})
    # 该疾病关联的产品/管线（仅作教学背景，注意 link_type 不是适应症）
    rel_prod = [pm for pm in pmap if pm["condition_id"] == cid]
    prod_names = []
    for pm in rel_prod:
        p = prods.get(pm["product_id"])
        if p:
            prod_names.append({
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
                        "approval_status": pl["approval_status"], "review_status": pl["review_status"],
                    })
    # scope 拆成要点列表
    scope_items = [x.strip() for x in re.split(r"[、，,;；/]", cond["competency_scope"]) if x.strip()]
    checks = [x.strip() for x in re.split(r"[；;。]", it["expected_checks"]) if x.strip()]

    skel = {
        "meta": {
            "title": f"{cond['name']}：基础诊疗背景与沟通边界",
            "subject": f"{area.get('name','医药')}（{area.get('department','')}）",
            "age": "医药代表（入职 0–6 个月）",
            "duration": "15 分钟",
            "language": "zh-CN",
        },
        "condition_id": cid,
        "condition_name": cond["name"],
        "area": {
            "area_id": cond["area_id"], "name": area.get("name"),
            "department": area.get("department"),
            "core_competencies": area.get("core_competencies"),
        },
        "keywords": cond["keywords"],
        "competency_scope": cond["competency_scope"],
        "scope_items": scope_items,
        "relationship_note": cond["relationship_note"],
        "medical_review": cond["medical_review"],
        "original_prompt": it["prompt"],
        "expected_checks": checks,
        "grading_mode": it["grading_mode"],
        "item_id": it["item_id"],
        "source": {
            "source_id": it["source_id"], "title": src.get("title"),
            "source_type": src.get("source_type"), "url": src.get("url"),
            "asof_date": src.get("asof_date"),
        },
        "related_products": prod_names,
        "related_pipeline": rel_pipe,
        "visual_kind": pick_visual(cond["competency_scope"], cond["keywords"]),
        "_fill": {
            "hero_question": "待填：一个该科室医生会真实提出的问题",
            "hero_promise": "待填：学员通过操作能验证什么",
            "goal": "待填：可衡量的学习目标",
            "map_prerequisites": "待填：先修知识 1-3 条",
            "map_unlocks": "待填：掌握后可解锁 1-3 条",
            "hook_title": "待填", "hook_body": "待填", "hook_prompt": "待填",
            "analogy_title": "待填", "analogy_body": "待填", "analogy_limit": "待填",
            "steps": "待填：3-5 步，每步 label/title/body",
            "misconceptions": "待填：2 条，每条 myth/correction/why",
            "checks": "待填：2 道题，每题 question/options(4)/answer/explanation",
            "recall_prompt": "待填", "recall_hint": "待填", "recall_answer": "待填",
            "visual_items_or_stages_or_nodes": "待填：按 visual_kind 给出对应结构",
            "visual_observation": "待填：操作后应观察到什么",
        },
        "_constraints": [
            "禁止 web 搜索；所有临床事实只能来自本骨架给出的字段（condition/area/scope/keywords/related_*）",
            "禁止声称任何产品已获批该疾病适应症——product_condition_map.link_type 是 educational_topic_not_indication",
            "禁止编造具体临床数据（样本量、发生率、p 值）；scope 只给维度不给数值",
            "在研资产（expanded_pipeline）必须与已获批产品严格区分",
            "每门课至少 1 条误区指向『超出证据边界的表述』",
            "每门课至少 1 道检验题的正确答案涉及『承认不确定 + 给出核实路径』",
        ],
    }
    with open(os.path.join(OUT, f"{cid}.json"), "w", encoding="utf-8") as fh:
        json.dump(skel, fh, ensure_ascii=False, indent=2)
    index.append({
        "condition_id": cid, "name": cond["name"], "area_id": cond["area_id"],
        "area_name": area.get("name"), "department": area.get("department"),
        "visual_kind": skel["visual_kind"], "keywords": cond["keywords"],
        "scope": cond["competency_scope"], "n_products": len(prod_names),
        "n_pipeline": len(rel_pipe), "source_id": it["source_id"],
        "source_title": src.get("title"), "source_url": src.get("url"),
        "asof_date": src.get("asof_date"), "area_core": area.get("core_competencies"),
    })

with open(os.path.join(OUT, "_index.json"), "w", encoding="utf-8") as fh:
    json.dump(index, fh, ensure_ascii=False, indent=2)

from collections import defaultdict
by_area = defaultdict(list)
for e in index:
    by_area[e["area_id"]].append(e["condition_id"])

with open(os.path.join(OUT, "_areas.json"), "w", encoding="utf-8") as fh:
    json.dump({a: {"name": areas[a]["name"], "department": areas[a]["department"],
                   "core_competencies": areas[a]["core_competencies"],
                   "conditions": by_area[a]} for a in by_area},
              fh, ensure_ascii=False, indent=2)

print(f"生成 {len(index)} 门课骨架 → {OUT}")
print("\n按治疗领域分组：")
for a, ids in sorted(by_area.items()):
    print(f"  {a} {areas[a]['name']} ({len(ids)}): {', '.join(ids)}")
from collections import Counter
print("\n视觉模式分布:", dict(Counter(e["visual_kind"] for e in index)))
