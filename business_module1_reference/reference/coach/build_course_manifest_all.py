#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成 course_manifest_all.json —— 一期全部课程的机器可读清单。

之前这个文件是空列表 []，且没有任何脚本或文档引用它——是个孤儿文件。
但一期课程清单本身需要一份权威的机器可读版本：
签审工作单、索引页、配置都从各自的脚本生成，容易漂移。
这份清单是「一期到底有哪些课」的唯一事实来源。
"""
import json, os, time, hashlib

from config import BASE, PATHS
A = os.path.join(BASE, "version-A-training-pack")
CFG = json.load(open(os.path.join(A, "phase1-config.json"), encoding="utf-8"))

DIM_LABEL = {
    "df": "疾病基础", "tl": "治疗格局", "ce": "临床证据",
}


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return "sha256:" + h.hexdigest()[:16]


def spec_info(rel):
    p = os.path.join(A, rel)
    if not os.path.exists(p):
        return None
    j = json.load(open(p, encoding="utf-8"))
    meta = j.get("meta", {})
    return {
        "spec": rel,
        "html": rel.replace("specs", "courses").replace(".json", ".html"),
        "title": meta.get("title"),
        "subject": meta.get("subject"),
        "duration": meta.get("duration"),
        "visual": (j.get("visual") or {}).get("kind"),
        "n_steps": len(j.get("steps", [])),
        "n_checks": len(j.get("checks", [])),
        "n_misconceptions": len(j.get("misconceptions", [])),
        "n_sources": len(j.get("sources", [])),
        "content_hash": sha(p),
    }


items = []

# ---- 疾病课：DF / TL / CE ----
for co in CFG["courses"]:
    for dk in ("df", "tl", "ce"):
        d = co.get(dk)
        if not d or d.get("status") != "ready_pending_signoff":
            continue
        info = spec_info(d["spec"])
        if not info:
            continue
        items.append({
            "course_id": f"{co['condition_id']}__{dk.upper()}",
            "condition_id": co["condition_id"],
            "disease": co["disease"],
            "area": co["area"],
            "department": co["department"],
            "keywords": co.get("keywords", ""),
            "dimension": d["dimension"],
            "dimension_label": DIM_LABEL[dk],
            "kind": "disease",
            "status": "ready_pending_signoff",
            "review_status": "pending_medical_review",
            **info,
        })

# ---- 产品 / 管线专项课 ----
for pr in CFG["phase1"]["products"]:
    d = pr.get("course")
    if not d or d.get("status") != "ready_pending_signoff":
        continue
    info = spec_info(d["spec"])
    if not info:
        continue
    items.append({
        "course_id": f"{pr['id']}__{'PB' if pr['status']=='commercialized' else 'PL'}",
        "condition_id": None,
        "disease": None,
        "product_id": pr["id"],
        "product_name": pr["name"],
        "generic_name": pr.get("generic_name"),
        "mechanism_topic": pr.get("mechanism_topic"),
        "product_status": pr["status"],
        "reported_status": pr.get("reported_status"),
        "approval_status": pr.get("approval_status"),
        "link_type": pr.get("link_type"),
        "dimension": d["dimension"],
        "dimension_label": "产品基础" if pr["status"] == "commercialized" else "管线认知",
        "kind": "product",
        "status": "ready_pending_signoff",
        "review_status": "pending_medical_review",
        **info,
    })

out = {
    "version": "A-含课程",
    "generated_at": time.strftime("%Y-%m-%d %H:%M"),
    "phase1_scope": "A-ONCO 实体瘤与肿瘤免疫 · 8 疾病 × 3 维度 + 13 产品/管线专项课",
    "total_courses": len(items),
    "note": "一期全部课程的机器可读清单。全部为候选层，review_status=pending_medical_review，未经 ReviewCase 签审不得进入正式评分。",
    "courses": items,
}

path = os.path.join(A, "course_manifest_all.json")
json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

from collections import Counter
print(f"✅ course_manifest_all.json 已重建：{len(items)} 门")
print(f"   按维度: {dict(Counter(i['dimension_label'] for i in items))}")
print(f"   全部待审: {all(i['review_status']=='pending_medical_review' for i in items)}")
