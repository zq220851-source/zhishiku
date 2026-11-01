#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
按"一期默认范围"生成聚焦版签审清单。
默认范围：实体瘤与肿瘤免疫领域中 8 门高频疾病（可调整）。
产出：
  version-A-training-pack/signoff/phase1-signoff-focus.md   聚焦签审清单（8 门）
  version-A-training-pack/signoff/phase1-signoff-focus.json 机器可读
"""
import json, os, glob

from config import BASE, PATHS
A = os.path.join(BASE, "version-A-training-pack")
MAN = os.path.join(BASE, "medrep-training-courses-v0.6", "course_manifest.json")
MAP = os.path.join(BASE, "course-mapping", "course-mapping.json")
CLIN = os.path.join(BASE, "clinical/medrep-innovent-clinical-knowledge-v0.5")

manifest = {m["condition_id"]: m for m in json.load(open(MAN, encoding="utf-8"))}
mapping = {m["condition_id"]: m for m in json.load(open(MAP, encoding="utf-8"))}

# 一期默认范围：肿瘤领域 8 门
# 选取依据：课程已就位 + 覆盖"已获批/在研"两类边界场景 + 覆盖主要适应症维度
PHASE1 = [
    "D-NSCLC",   # 非小细胞肺癌 —— 免疫治疗主战场，PD-L1 边界
    "D-BREAST",  # 乳腺癌 —— HR/HER2 双分型
    "D-HCC",     # 肝细胞癌 —— 分期×肝功能双轴
    "D-GC",      # 胃癌 —— CLDN18.2/HER2，ADC 在研场景
    "D-CRC",     # 结直肠癌 —— MSI-H/dMMR 检测口径
    "D-OVARIAN", # 卵巢癌 —— 铂耐药 + ADC 安全性
    "D-GBM",     # 胶质母细胞瘤 —— 功能终点，非肿瘤内科但语言差异大
    "D-CERVICAL",# 宫颈癌 —— 四类谈话场景对照
]

# 对应产品：2–3 已商业化 + 1–2 在研（覆盖边界场景）
PHASE1_PRODUCTS = [
    {"id": "daboshu",   "name": "达伯舒（信迪利单抗）",   "status": "已商业化", "scenario": "免疫治疗适用人群边界"},
    {"id": "dayoutong", "name": "达攸同（贝伐珠单抗）",   "status": "已商业化", "scenario": "联合治疗与安全性表述"},
    {"id": "sulixin",   "name": "苏立信（阿达木单抗）",   "status": "已商业化", "scenario": "自身免疫方向的机制对照"},
    {"id": "IBI343",    "name": "IBI343（CLDN18.2 ADC）", "status": "在研",     "scenario": "在研 vs 已获批的表述边界"},
    {"id": "IBI363",    "name": "IBI363（PD-1/IL-2α 融合蛋白）", "status": "在研", "scenario": "披露状态与审批状态必须分开"},
]

import sqlite3
db = os.path.join(CLIN, "medrep_clinical_knowledge_v0.5.sqlite")
c = sqlite3.connect(db)
c.row_factory = sqlite3.Row
prod_rows = {r["product_id"]: dict(r) for r in c.execute("select * from med_products")}
pipe_rows = {r["asset_id"]: dict(r) for r in c.execute("select * from expanded_pipeline")}

lines = [
    "# 一期签审聚焦清单 —— 8 门（默认范围，可调整）",
    "",
    "> **这是 D01 未拍板前的默认收敛方案。** 若一期范围变更，只需改本文件的疾病列表，",
    "> 签审工作单的完整版（42 门）仍在 `course-signoff-worklist.md`。",
    "",
    "## 一、为什么选这 8 门",
    "",
    "| 考虑 | 说明 |",
    "|---|---|",
    "| 覆盖维度最全 | 8 门覆盖免疫/靶向/ADC/双分型/检测口径/功能终点/决策链全部主要形态 |",
    "| 覆盖已获批与在研 | 前 3 门配已商业化产品，后 2 门配在研资产，边界场景必须覆盖 |",
    "| 语料素材充足 | 这几个疾病在课件中的异议与场景素材密度最高 |",
    "| 签审成本可控 | 8 门 ≈ 4 人日，可在一周内完成 |",
    "",
    "## 二、一期产品范围",
    "",
    "| 产品 | 通用名 / 机制 | 状态 | 本期要覆盖的场景 |",
    "|---|---|---|---|",
]
for p in PHASE1_PRODUCTS:
    if p["id"] in prod_rows:
        r = prod_rows[p["id"]]
        lines.append(f"| {r['brand']} | {r['generic_name']} / {r['mechanism_topic']} | {p['status']} | {p['scenario']} |")
    else:
        r = pipe_rows.get(p["id"], {})
        lines.append(f"| {p['id']} | {r.get('mechanism_topic','—')} | {p['status']} | {p['scenario']} |")

# ★ 按 phase1-config 里的实际课程清单生成，覆盖 DF/TL/CE + 产品/管线专项课。
#   之前硬编码只处理 DF 的 8 门，TL 与 CE 建好后签审工作单没跟上——
#   一期 37 门课里只有 8 门能签审。
_cfg = json.load(open(os.path.join(A, "phase1-config.json"), encoding="utf-8"))
_N_COURSES = _cfg["phase1"]["total_courses"]

lines += [
    "",
    "⚠️ **产品与疾病的关联一律是 `educational_topic_not_indication`（教学主题关联，非获批适应症）。**",
    "签审时若发现任何「该产品适用于该疾病」的表述，直接打回。",
    "",
    f"## 三、{_N_COURSES} 门逐门签审清单",
    "",
    "| 疾病/产品 | 维度 | spec 文件 | 考察点 | 诱导题 | 检验题 | ①医学 | ②边界 | ③数值 | ④适应症 | ⑤核实 | 审核人 | 日期 |",
    "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
]
focus_items = []
_lines = []
for co in _cfg["courses"]:
    for dim_key, dim_label in (("df", "疾病基础"), ("tl", "治疗格局"), ("ce", "临床证据")):
        d = co.get(dim_key)
        if not d or d.get("status") != "ready_pending_signoff":
            continue
        cid = co["condition_id"]
        m = manifest.get(cid, {})
        mp = mapping.get(cid, {})
        n_kp = len(mp.get("knowledge_points", []))
        n_tr = len(mp.get("trap_designs", []))
        n_ck = len(mp.get("check_items", []))
        _lines.append(
            f"| {co['disease'][:12]} | {dim_label} | {d['spec']} | {n_kp} | {n_tr} | {n_ck} | ☐ | ☐ | ☐ | ☐ | ☐ | | |")
        focus_items.append({
            "condition_id": cid,
            "disease": co["disease"],
            "area": co["area"],
            "dimension": dim_key,
            "dimension_label": dim_label,
            "keywords": co.get("keywords", ""),
            "course_file": d.get("html"),
            "spec_file": d.get("spec"),
            "n_knowledge_points": n_kp,
            "n_traps": n_tr,
            "n_checks": n_ck,
            "source": co.get("source"),
            "status": "pending_medical_review",
            "signoff": {k: "☐ 待审" for k in
                        ["medical_accuracy", "boundary_statement", "no_fabricated_numbers",
                         "no_indication_claim", "verify_path_accurate"]},
            "reviewer": "", "date": "", "notes": "",
        })
# 产品 / 管线专项课
for pr in _cfg["phase1"]["products"]:
    d = pr.get("course")
    if not d or d.get("status") != "ready_pending_signoff":
        continue
    _lines.append(
        f"| {pr['name']}（{pr['id']}） | {pr['status']} | {d['spec']} | - | - | 2 | ☐ | ☐ | ☐ | ☐ | ☐ | | |")
    focus_items.append({
        "condition_id": None,
        "disease": pr["name"],
        "product_id": pr["id"],
        "area": "实体瘤与肿瘤免疫",
        "dimension": pr.get("course", {}).get("dimension"),
        "dimension_label": "产品基础" if pr["status"] == "commercialized" else "管线认知",
        "keywords": pr.get("mechanism_topic", ""),
        "course_file": d.get("html"),
        "spec_file": d.get("spec"),
        "reported_status": pr.get("reported_status"),
        "approval_status": pr.get("approval_status"),
        "n_knowledge_points": None,
        "n_traps": None,
        "n_checks": 2,
        "status": "pending_medical_review",
        "signoff": {k: "☐ 待审" for k in
                    ["medical_accuracy", "boundary_statement", "no_fabricated_numbers",
                     "no_indication_claim", "verify_path_accurate"]},
        "reviewer": "", "date": "", "notes": "",
    })
lines += _lines

lines += [
    "",
    "## 四、这 8 门的签审重点（逐门特化）",
    "",
]
FOCUS_NOTES = {
    "D-NSCLC": "重点看：PD-L1 单一指标是否被写成适用标准；五层决策链是否每层都标注了『需临床数据支撑』。",
    "D-BREAST": "重点看：HER2 补充结果未确认时的处理是否明确；是否出现『CDK4/6 抑制剂联合内分泌适用于 HER2 阳性』这类越界。",
    "D-HCC": "重点看：分期×肝功能双轴是否讲清；是否有具体数字（不要）。",
    "D-GC": "重点看：CLDN18.2/HER2 标志物与 ADC 在研边界；『已有 ADC 获批』类表述零容忍。",
    "D-CRC": "重点看：MSI 与 dMMR 两套检测口径是否区分清楚；pMMR 能否承接 dMMR 结论的表述是否说清。",
    "D-OVARIAN": "重点看：铂耐药与 ADC 安全性的表述；HER2 表达未出结果时的处理。",
    "D-GBM": "重点看：解剖指标与功能终点是否区分；『MRI 强化扩大就是进展』这类绝对化判读是否作为误区出现。",
    "D-CERVICAL": "重点看：四类谈话场景（随访/疗效/复发/取数）是否覆盖；决策人识别的表述。",
}
for cid in PHASE1:
    lines.append(f"**{manifest[cid]['condition_name']}**")
    lines.append("")
    lines.append(f"- {FOCUS_NOTES[cid]}")
    lines.append(f"- 出处：`{manifest[cid]['source']['title']}`（{manifest[cid]['source']['url']}）")
    lines.append("")

lines += [
    "## 五、签审完成后（进已审核训练层）",
    "",
    "1. 更新 `phase1-signoff-focus.json` 中该门课的 `status` → `approved`，填 `reviewer` / `date`",
    "2. 同步 `course_manifest.json`：`knowledge_layer` → `approved`，`requires_medical_review` → `false`，"
    "新增 `approved_by` / `approved_at` / `knowledge_pack_version`",
    "3. 课程条目转 KnowledgeCandidate → ReviewCase 签审 → 发布为 KnowledgePackVersion 的一部分",
    "",
    "**只有 `knowledge_layer = approved` 且已绑定 `knowledge_pack_version` 的课程，才能进入正式评分。**",
    "",
    "## 六、工时",
    "",
    "| 项 | 人日 |",
    "|---|---|",
    "| 8 门课签审 | 4 |",
    "| 16 道检验题 rubric 补齐（8 门 × 2 道）| 2.7 |",
    "| 课程 → KnowledgeCandidate 接入（8 门部分）| 2 |",
    "| **一期合计** | **约 9 人日** |",
    "",
    "对照：42 门全签需 21 + 14 = 35 人日。**先签 8 门，一期即可开课。**",
]
open(os.path.join(A, "signoff", "phase1-signoff-focus.md"), "w", encoding="utf-8").write("\n".join(lines))

with open(os.path.join(A, "signoff", "phase1-signoff-focus.json"), "w", encoding="utf-8") as fh:
    json.dump({
        "phase1_scope": "实体瘤与肿瘤免疫 · 8 门",
        "products": PHASE1_PRODUCTS,
        "note": "默认收敛方案，D01 拍板后可调整",
        "items": focus_items,
    }, fh, ensure_ascii=False, indent=2)

print(f"一期聚焦签审清单已生成：{len(PHASE1)} 门")
for cid in PHASE1:
    print(f"  {cid} {manifest[cid]['condition_name']}")
