#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从信达临床库为剩余 3 个维度建课程骨架：
  CE clinical_evidence  → 按疾病（42 门）
  PL pipeline_literacy  → 按在研资产（29 门）
  PB product_basics     → 按已商业化产品（20 门）

这三类课程形态不同：CE 是疾病视角，PL/PB 是资产视角。
"""
import sqlite3, json, os, re

from config import BASE, PATHS
CLIN = os.path.join(BASE, "clinical/medrep-innovent-clinical-knowledge-v0.5")
DB = os.path.join(CLIN, "medrep_clinical_knowledge_v0.5.sqlite")
OUT = os.path.join(BASE, "course-skeletons-ce")
os.makedirs(OUT, exist_ok=True)

c = sqlite3.connect(DB)
c.row_factory = sqlite3.Row

areas = {r["area_id"]: dict(r) for r in c.execute("select * from therapeutic_areas")}
conds = {r["condition_id"]: dict(r) for r in c.execute("select * from clinical_conditions")}
csrcs = {r["source_id"]: dict(r) for r in c.execute("select * from clinical_sources")}
prods = {r["product_id"]: dict(r) for r in c.execute("select * from med_products")}
pipes = {r["asset_id"]: dict(r) for r in c.execute("select * from expanded_pipeline")}
pcond = [dict(r) for r in c.execute("select * from pipeline_condition_map")]

items = [dict(r) for r in c.execute("select * from competency_items")]

# ---------- 视觉模式选择 ----------
def pick_visual(dim, scope):
    s = (scope or "")
    if dim == "clinical_evidence":
        return "comparison"      # 对照组/随机化/终点/随访 的对照
    if dim == "pipeline_literacy":
        return "process"         # 披露状态 → 审批状态 的流程
    return "concept-map"         # 产品：机制 → 疾病 → 适应症边界


EXTRA_RULES = {
    "clinical_evidence": [
        "本课训练的是「读一项研究」的方法，不是记住某项研究的结果。",
        "必须覆盖三组区分：①单臂 vs 随机对照 ②替代终点 vs 临床终点 ③入组人群 vs 真实门诊人群。",
        "禁止写具体试验名称、样本量、p 值、HR 数值——本课只讲方法，不讲某项研究的数据。",
        "禁止把研究结论表述为临床决策建议——结论只在研究人群与研究条件下成立。",
    ],
    "pipeline_literacy": [
        "本课的核心是「披露状态 ≠ 审批状态」。两者必须分别讲、分别标注。",
        "课程中提到的具体资产，其 reported_status（研发方披露口径）与 approval_status（审批状态）都要给出，但必须说明前者是披露口径、后者是审批状态。",
        "禁止把在研资产的机制方向说成已获批适应症；禁止预测审批时间表。",
        "资产与疾病的关联一律是 educational_topic_not_indication（教学主题关联，非获批适应症），课程里提到时必须体现这一层。",
    ],
    "product_basics": [
        "本课的核心是「核查路径」，不是背诵产品信息。",
        "必须讲清：通用名与靶点可核实；**适应症必须查最新 NMPA 说明书与企业合规版本，不得推断**。",
        "禁止列举具体适应症、用法用量、疗程天数等需说明书支撑的内容。",
        "产品与疾病的关联一律是 educational_topic_not_indication（教学主题关联，非获批适应症）。",
    ],
}

TITLES = {
    "clinical_evidence": "证据解读：怎么读一项研究",
    "pipeline_literacy": "管线认知：披露状态与审批状态的分离",
    "product_basics": "产品基础与核查路径",
}

index = []
for it in items:
    dim = it["dimension"]
    if dim not in ("clinical_evidence", "pipeline_literacy", "product_basics"):
        continue
    st, sid = it["subject_type"], it["subject_id"]
    src = csrcs.get(it["source_id"], {})

    if st == "clinical_condition":
        cond = conds.get(sid)
        if not cond:
            continue
        area = areas.get(cond["area_id"], {})
        title = f"{cond['name']}：{TITLES[dim]}"
        scope_items = [x.strip() for x in re.split(r"[、，,;；/]", cond["competency_scope"]) if x.strip()]
        scope = cond["competency_scope"]
        keywords = cond["keywords"]
        name = cond["name"]
        dept = area.get("department")
        area_name = area.get("name")
        area_id = cond["area_id"]
        rel_prod = []
        for pm in c.execute("select m.product_id,m.link_type,p.brand,p.mechanism_topic from product_condition_map m join med_products p on p.product_id=m.product_id where m.condition_id=?", (sid,)):
            rel_prod.append(dict(pm))
        rel_pipe = []
        for pc in pcond:
            if pc["condition_id"] == sid:
                pl = pipes.get(pc["asset_id"])
                if pl:
                    rel_pipe.append({
                        "asset_id": pl["asset_id"], "mechanism_topic": pl["mechanism_topic"],
                        "reported_status": pl["reported_status"],
                        "approval_status": pl["approval_status"],
                        "review_status": pl["review_status"],
                    })
        subj_kind = "clinical_condition"
    elif st == "commercial_product":
        p = prods.get(sid)
        if not p:
            continue
        title = f"{p['brand']}（{p['generic_name']}）：{TITLES[dim]}"
        scope = p["mechanism_topic"] or ""
        scope_items = [x for x in [p["domain"], p["mechanism_topic"]] if x]
        keywords = p["mechanism_topic"]
        name = f"{p['brand']}（{p['generic_name']}）"
        dept = "肿瘤学" if p["domain"] == "肿瘤" else ("血液科" if "血液" in p["domain"] else "其他")
        area_name = "产品与管线"
        area_id = "ASSET"
        rel_prod = [dict(p)]
        rel_pipe = []
        subj_kind = "commercial_product"
    else:  # research_asset
        p = pipes.get(sid)
        if not p:
            continue
        title = f"{sid}（{p['mechanism_topic']}）：{TITLES[dim]}"
        scope = p["mechanism_topic"] or ""
        scope_items = [x for x in [p["mechanism_topic"]] if x]
        keywords = p["mechanism_topic"]
        name = f"{sid}（{p['mechanism_topic']}）"
        dept = "肿瘤学"
        area_name = "产品与管线"
        area_id = "ASSET"
        rel_prod = []
        rel_pipe = [dict(p)]
        subj_kind = "research_asset"

    short = {"clinical_evidence": "CE", "pipeline_literacy": "PL", "product_basics": "PB"}[dim]
    skel = {
        "meta": {
            "title": title,
            "subject": f"{area_name}（{dept}）",
            "age": "医药代表（入职 0–6 个月）",
            "duration": "15 分钟",
            "language": "zh-CN",
        },
        "dimension": dim,
        "dimension_short": short,
        "condition_id": sid,
        "condition_name": name,
        "subject_kind": subj_kind,
        "area": {"area_id": area_id, "name": area_name, "department": dept,
                 "core_competencies": areas.get(area_id, {}).get("core_competencies")},
        "keywords": keywords,
        "competency_scope": scope,
        "scope_items": scope_items,
        "teaching_focus": TITLES[dim],
        "core_question": it["prompt"],
        "expected_checks": [x.strip() for x in re.split(r"[；;。]", it["expected_checks"]) if x.strip()],
        "original_prompt": it["prompt"],
        "grading_mode": it["grading_mode"],
        "medical_review": it["review_status"],
        "item_id": it["item_id"],
        "source": {"source_id": it["source_id"], "title": src.get("title"),
                   "source_type": src.get("source_type"), "url": src.get("url"),
                   "asof_date": src.get("asof_date")},
        "related_products": rel_prod,
        "related_pipeline": rel_pipe,
        "visual_kind": pick_visual(dim, scope),
        "_constraints": [
            "禁止 web 搜索；临床事实只能来自信达临床库的字段（source_id + 表名 + 记录 ID）",
            "禁止声称任何产品已获批该疾病适应症——link_type 是 educational_topic_not_indication",
            "禁止编造临床数值（样本量、发生率、p 值、生存期数字）",
            "禁止把研究结论表述为临床决策建议",
            "在研资产必须区分 reported_status（披露口径）与 approval_status（审批状态）",
            "每门课至少 1 条误区指向『超出证据边界的表述』",
            "每门课至少 1 道检验题的正确答案是『承认不确定 + 给出核实路径』——核实路径必须在正确项文本本身",
            "每门课至少 1 道检验题的干扰项包含绝对化或越界表述",
            "steps 3–5 步；checks 2 道；misconceptions 2 条；sources 2–3 条（必须含骨架的 source_url）",
            "医生提问必须用该疾病/资产的具体标志物或维度",
            "选项 ≤80 字，解析 ≤240 字；正确项与错误项长度量级要相当",
        ] + EXTRA_RULES[dim],
    }
    with open(os.path.join(OUT, f"{sid}__{short}.json"), "w", encoding="utf-8") as fh:
        json.dump(skel, fh, ensure_ascii=False, indent=2)
    index.append({
        "condition_id": sid, "dimension": dim, "short": short, "name": name,
        "area_id": area_id, "area_name": area_name, "department": dept,
        "visual_kind": skel["visual_kind"], "keywords": keywords, "scope": scope,
        "teaching_focus": TITLES[dim], "n_products": len(rel_prod), "n_pipeline": len(rel_pipe),
        "source_id": it["source_id"], "source_title": src.get("title"),
        "source_url": src.get("url"), "asof_date": src.get("asof_date"),
    })

with open(os.path.join(OUT, "_index.json"), "w", encoding="utf-8") as fh:
    json.dump(index, fh, ensure_ascii=False, indent=2)
from collections import defaultdict, Counter
by_area = defaultdict(list)
for e in index:
    by_area[e["area_id"]].append(e["condition_id"])
with open(os.path.join(OUT, "_areas.json"), "w", encoding="utf-8") as fh:
    json.dump({a: {"name": (areas.get(a) or {}).get("name", a),
                   "department": (areas.get(a) or {}).get("department", ""),
                   "core_competencies": (areas.get(a) or {}).get("core_competencies", ""),
                   "conditions": ids} for a, ids in by_area.items()},
              fh, ensure_ascii=False, indent=2)
print(f"✅ {len(index)} 门骨架 → {OUT}")
print("  按维度:", dict(Counter(e["dimension"] for e in index)))
print("  按领域:")
for a, ids in sorted(by_area.items(), key=lambda kv: -len(kv[1])):
    print(f"    {a}: {len(ids)}")
print("  视觉:", dict(Counter(e["visual_kind"] for e in index)))
