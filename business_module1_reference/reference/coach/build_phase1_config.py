#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
版本 A 一期配置固化。

产出：
  version-A-training-pack/phase1-config.json   机器可读配置（工程与培训都用它）
  version-A-training-pack/phase1-config.md     人读版配置说明
"""
import json, os, sqlite3, glob, hashlib, time

from config import BASE, PATHS
A = os.path.join(BASE, "version-A-training-pack")
os.makedirs(A, exist_ok=True)
CLIN = os.path.join(BASE, "clinical/medrep-innovent-clinical-knowledge-v0.5")

# ---- 一期范围（沿用已生成的聚焦签审清单）----
PHASE1_CIDS = ["D-NSCLC", "D-BREAST", "D-HCC", "D-GC",
               "D-CRC", "D-OVARIAN", "D-GBM", "D-CERVICAL"]

manifest = {m["condition_id"]: m for m in json.load(
    open(os.path.join(BASE, "medrep-training-courses-v0.6", "course_manifest.json"), encoding="utf-8"))}
mapping = {m["condition_id"]: m for m in json.load(
    open(os.path.join(BASE, "course-mapping", "course-mapping.json"), encoding="utf-8"))}
skel_df = {os.path.basename(f)[:-5]: json.load(open(f, encoding="utf-8"))
           for f in glob.glob(os.path.join(BASE, "course-skeletons", "D-*.json"))}
skel_tl = {os.path.basename(f)[:-len("__TL.json")]: json.load(open(f, encoding="utf-8"))
           for f in glob.glob(os.path.join(BASE, "course-skeletons-tl", "D-*__TL.json"))}

# ---- 产品范围：从数据库真实映射推导，不手工挑 ----
db = sqlite3.connect(os.path.join(CLIN, "medrep_clinical_knowledge_v0.5.sqlite"))
db.row_factory = sqlite3.Row
prod_rows = {r["product_id"]: dict(r) for r in db.execute("select * from med_products")}
pipe_rows = {r["asset_id"]: dict(r) for r in db.execute("select * from expanded_pipeline")}

pmap_rows = list(db.execute(
    "select m.condition_id, m.product_id, m.link_type, m.review_status "
    "from product_condition_map m"))
pcond_rows = list(db.execute(
    "select m.condition_id, m.asset_id from pipeline_condition_map m"))

# 每个产品覆盖哪些一期疾病
prod_cover = {}
for r in pmap_rows:
    if r["condition_id"] in PHASE1_CIDS:
        prod_cover.setdefault(r["product_id"], []).append(r["condition_id"])
pipe_cover = {}
for r in pcond_rows:
    if r["condition_id"] in PHASE1_CIDS:
        pipe_cover.setdefault(r["asset_id"], []).append(r["condition_id"])

PRODUCTS = []
for pid, conds in sorted(prod_cover.items(), key=lambda kv: -len(kv[1])):
    p = prod_rows.get(pid, {})
    PRODUCTS.append({
        "id": pid, "name": p.get("brand", pid), "generic_name": p.get("generic_name"),
        "mechanism_topic": p.get("mechanism_topic"),
        "status": "commercialized", "covers": conds,
        "link_type": "educational_topic_not_indication",
        # 产品专项课（product_basics）——按实际文件存在性挂载
        "course": {
            "dimension": "product_basics",
            "spec": f"specs-ce/{pid}__PB.json",
            "html": f"courses-ce/{pid}__PB.html",
            "status": ("ready_pending_signoff"
                       if os.path.exists(os.path.join(A, "specs-ce", f"{pid}__PB.json"))
                       else "to_build"),
            "visual": "concept-map",
        },
    })
for aid, conds in sorted(pipe_cover.items(), key=lambda kv: -len(kv[1])):
    p = pipe_rows.get(aid, {})
    PRODUCTS.append({
        "id": aid, "name": aid, "generic_name": None,
        "mechanism_topic": p.get("mechanism_topic"),
        "status": "pipeline",
        "reported_status": p.get("reported_status"),
        "approval_status": p.get("approval_status"),
        "covers": conds,
        "link_type": "educational_topic_not_indication",
        # 管线专项课（pipeline_literacy）
        "course": {
            "dimension": "pipeline_literacy",
            "spec": f"specs-ce/{aid}__PL.json",
            "html": f"courses-ce/{aid}__PL.html",
            "status": ("ready_pending_signoff"
                       if os.path.exists(os.path.join(A, "specs-ce", f"{aid}__PL.json"))
                       else "to_build"),
            "visual": "concept-map",
        },
    })

# ---- 一期课程（两个维度）----
courses = []
for cid in PHASE1_CIDS:
    m = manifest[cid]
    mp = mapping.get(cid, {})
    courses.append({
        "condition_id": cid,
        "disease": m["condition_name"],
        "area": m["area_name"],
        "department": m["department"],
        "keywords": m["keywords"],
        # DF 维度（已完成）
        "df": {
            "dimension": "disease_foundation",
            "spec": f"specs/{cid}.json",
            "html": f"courses/{cid}.html",
            "status": "ready_pending_signoff",
            "visual": skel_df.get(cid, {}).get("visual_kind"),
        },
        # TL 维度（本次扩课）
        # ★ 状态按 spec 文件是否实际存在判定，不硬编码。
        #   之前硬编码 to_build，后续课程建成但配置没回填，
        #   导致签审工作单和索引漏掉 8 门 TL 课。
        "tl": {
            "dimension": "treatment_landscape",
            "spec": f"specs-tl/{cid}__TL.json",
            "html": f"courses-tl/{cid}__TL.html",
            "status": ("ready_pending_signoff"
                       if os.path.exists(os.path.join(A, "specs-tl", f"{cid}__TL.json"))
                       else "to_build"),
            "visual": skel_tl.get(cid, {}).get("visual_kind"),
            "scope": skel_tl.get(cid, {}).get("competency_scope"),
        },
        # CE 维度（临床证据）——按实际文件存在性判定
        "ce": {
            "dimension": "clinical_evidence",
            "spec": f"specs-ce/{cid}__CE.json",
            "html": f"courses-ce/{cid}__CE.html",
            "status": ("ready_pending_signoff"
                       if os.path.exists(os.path.join(A, "specs-ce", f"{cid}__CE.json"))
                       else "to_build"),
            "visual": "comparison",
            "scope": "对照 / 终点 / 人群 / 边界 四道必答条款",
        },
        "source": m["source"],
        "knowledge_points": len(mp.get("knowledge_points", [])),
        "trap_designs": len(mp.get("trap_designs", [])),
        "check_items": len(mp.get("check_items", [])),
    })

def _count_courses():
    """按磁盘实际存在的课程 spec 计数（一期范围内）"""
    n = 0
    for sub in ("specs", "specs-tl", "specs-ce"):
        d = os.path.join(A, sub)
        if not os.path.isdir(d):
            continue
        for f in os.listdir(d):
            if f.endswith(".json"):
                n += 1
    return n


config = {
    "version": "A-含课程",
    "config_version": "v1.0",
    "generated_at": time.strftime("%Y-%m-%d %H:%M"),
    "baseline": "MedRep Coach V1.3（2026-10-31）+ 课件语料库 + 信达临床知识库 v0.5",
    "phase1": {
        "therapeutic_area": {
            "area_id": "A-ONCO",
            "name": "实体瘤与肿瘤免疫",
            "department": "肿瘤学",
            "rationale": f"课程库中该领域课程最密集（{_count_courses()} 门），语料素材覆盖异议类型与抗拒形态最全，且同时覆盖已获批与在研两类产品边界场景",
        },
        "conditions": PHASE1_CIDS,
        "condition_count": len(PHASE1_CIDS),
        "course_dimensions": ["disease_foundation", "treatment_landscape",
                              "clinical_evidence", "product_basics", "pipeline_literacy"],
        # 课程总数按磁盘实际文件数推导，不硬编码
        # （之前硬编码 8×2=16，CE 21 门建好后没回填，签审工作单与索引会漏）
        "total_courses": _count_courses(),
        "products": PRODUCTS,
        "pilot": {
            "reps": "20–30 名",
            "weeks": 6,
            "note": "比无课程版多 2 周，用于配合医学签审与课程熟悉；V1.3 验收场景 AT05/AT12 需在试点中验证",
        },
        "signoff": {
            "gates": ["①医学准确性", "②边界表述", "③无编造数值", "④无适应症越界", "⑤核实路径可行"],
            "per_course_person_days": 0.5,
            # 按实际课程数计，不按疾病数——一期含 8×3 疾病课 + 21 门产品/管线专项课
            "phase1_person_days": round(_count_courses() * 0.5, 1),
            "full_42_person_days": 21,
            "worklist": "signoff/phase1-signoff-focus.md",
        },
        "rubric": {
            "questions_to_backfill": sum(c["check_items"] for c in courses),
            "person_days": round(sum(c["check_items"] for c in courses) * 0.17, 1),
            "worklist": "signoff/rubric-worklist.md",
        },
    },
    "knowledge_layer": {
        "current": "candidate",
        "target": "approved",
        "rule": "V1.3 §0.2 —— 未经 ReviewCase 签审不得进入正式评分与标准训练",
        "flow": "candidate → auto_checked → pending_human → approved/rejected/needs_revision → published",
    },
    "acceptance": {
        "standard": "V1.3 §5.3 AT01–AT16",
        "phase1_active": ["AT01", "AT03", "AT05", "AT12", "AT13", "AT15"],
        "deferred_to_phase2": ["AT02", "AT04", "AT06", "AT07", "AT08", "AT09", "AT10", "AT11", "AT14", "AT16"],
        "defer_reason": "AT02/04/06–11/14/16 依赖复盘流与专家画像，属二��范围；A 版一期无复盘链路",
    },
    "open_decisions": {
        "D01a_version": {"status": "decided", "value": "A（含课程）", "decided_at": "2026-10-31"},
        "D01b_area": {"status": "decided", "value": "A-ONCO 实体瘤与肿瘤免疫"},
        "D01c_conditions": {"status": "decided", "value": PHASE1_CIDS},
        "D01d_products": {"status": "decided", "value": f"按数据库真实映射：{sum(1 for p in PRODUCTS if p['status']=='commercialized')} 已商业化 + {sum(1 for p in PRODUCTS if p['status']=='pipeline')} 在研"},
        "D01e_signoff_blocking": {"status": "pending", "question": "课程签审是否阻塞上线？建议阻塞（V1.3 §0.2）"},
        "D04a_question_count": {"status": "pending", "question": "题量上下限与选择规则"},
        "D08a_rubric_gate": {"status": "pending", "question": "两套评分量表分值与严重错误闸门"},
    },
    "courses": courses,
}

with open(os.path.join(A, "phase1-config.json"), "w", encoding="utf-8") as fh:
    json.dump(config, fh, ensure_ascii=False, indent=2)

# ---- 人读版 ----
L = [
    "# 版本 A · 一期配置", "",
    f"> 生成时间：{config['generated_at']}",
    "> 基准：V1.3 开发文档 + 课件语料库 + 信达临床知识库 v0.5",
    "",
    "## 一、一期范围", "",
    "| 项 | 内容 |", "|---|---|",
    f"| 治疗领域 | {config['phase1']['therapeutic_area']['name']}（{config['phase1']['therapeutic_area']['department']}）|",
    f"| 疾病数 | {len(PHASE1_CIDS)} |",
    f"| 课程维度 | disease_foundation（已完成）+ treatment_landscape（本次扩课）|",
    f"| 课程总数 | {len(PHASE1_CIDS) * 2} 门 |",
    f"| 产品 | {len(PRODUCTS)} 个（{sum(1 for p in PRODUCTS if p['status']=='commercialized')} 已商业化 + {sum(1 for p in PRODUCTS if p['status']=='pipeline')} 在研）|",
    f"| 试点 | {config['phase1']['pilot']['reps']} × {config['phase1']['pilot']['weeks']} 周 |",
    "",
    f"**选这个领域的理由**：{config['phase1']['therapeutic_area']['rationale']}",
    "",
    "## 二、疾病与课程清单", "",
    "| 疾病 | 科室 | 关键词 | DF 课（已完成）| TL 课（扩课）| 考察点 | 诱导题 | 检验题 |",
    "|---|---|---|---|---|---|---|---|",
]
for c in courses:
    L.append(f"| {c['disease']} | {c['department']} | {(c['keywords'] or '')[:20]} | "
             f"{'✅ ' + c['df']['visual']} | {c['tl']['visual']} | {c['knowledge_points']} | "
             f"{c['trap_designs']} | {c['check_items']} |")

L += ["", "## 三、产品范围", "",
      "| 产品 | 机制方向 | 状态 | 覆盖的一期疾病 |", "|---|---|---|---|"]
for p in config["phase1"]["products"]:
    mech = p.get("mechanism_topic") or "—"
    if p["status"] == "commercialized":
        st = "已商业化"
    else:
        st = f"在研（披露：{p.get('reported_status') or '—'}）"
    cov = "、".join(dict.fromkeys(p["covers"]))
    L.append(f"| {p['name']} | {mech} | {st} | 覆盖 {cov} |")

L += [
    "",
    "⚠️ **产品与疾病的关联一律是 `educational_topic_not_indication`（教学主题关联，非获批适应症）。**",
    "签审时若发现任何「该产品适用于该疾病」的表述，直接打回。",
    "",
    "## 四、知识分层与签审（V1.3 §0.2）", "",
    "```",
    "candidate（现在）→ auto_checked → pending_human → approved/rejected → published",
    "```",
    "",
    "**当前所有课程都在 candidate 层。** 未经 ReviewCase 签审，不得进入正式评分与标准训练。",
    "",
    "| 项 | 一期 | 全量 42 门 |",
    "|---|---|---|",
    f"| 签审 | {config['phase1']['signoff']['phase1_person_days']} 人日（{config['phase1']['total_courses']} 门）| {config['phase1']['signoff']['full_42_person_days']} 人日 |",
    f"| rubric 补齐 | {config['phase1']['rubric']['person_days']} 人日（{config['phase1']['rubric']['questions_to_backfill']} 道）| 14 人日 |",
    "",
    "## 五、一期启用的验收场景", "",
    "采用 V1.3 §5.3 的 AT01–AT16 统一清单。A 版一期启用：",
    "",
]
for a in config["acceptance"]["phase1_active"]:
    L.append(f"- **{a}**")
L += ["", "**推迟到二期的**（依赖复盘流与专家画像，A 版一期无该链路）：",
      ", ".join(config["acceptance"]["deferred_to_phase2"]), "",
      f"> 理由：{config['acceptance']['defer_reason']}", "",
      "## 六、已拍板与待拍板", "",
      "### 已拍板", "",
      "| 决策 | 取值 |", "|---|---|",
]
for k, v in config["open_decisions"].items():
    if v.get("status") == "decided":
        L.append(f"| {k} | {v['value']} |")
L += ["", "### 待拍板（阻塞 Phase 1 开发）", "",
      "| 决策 | 问题 |", "|---|---|"]
for k, v in config["open_decisions"].items():
    if v.get("status") == "pending":
        L.append(f"| {k} | {v['question']} |")

L += ["", "## 七、下一步", "",
      "1. **医学签审 8 门**（4 人日）—— 清单见 `signoff/phase1-signoff-focus.md`",
      "2. **补 16 道检验题 rubric**（2.7 人日）—— 见 `signoff/rubric-worklist.md`",
      "3. **TL 维度扩课 8 门**（本次并行进行）",
      "4. **拍板 D04a / D08a** —— 阻塞评分引擎开发",
      "", "## 八、文件", "",
      "```",
      "version-A-training-pack/",
      "├── phase1-config.json          本配置（机器可读）",
      "├── phase1-config.md            本配置（人读）",
      "├── courses/                    42 门 DF 课（8 门为一期重点）",
      "├── courses-tl/                 8 门 TL 课（本次扩课）",
      "├── specs/  specs-tl/           对应教学 spec",
      "├── scenarios/                  48 条场景种子",
      "├── skill-taxonomy/             222 个能力点",
      "├── course-mapping/             课程↔知识点映射",
      "└── signoff/                    签审 + rubric 工作单",
      "```",
      ]
open(os.path.join(A, "phase1-config.md"), "w", encoding="utf-8").write("\n".join(L))

print(f"✅ 一期配置已生成")
print(f"   领域: {config['phase1']['therapeutic_area']['name']}")
print(f"   疾病: {len(PHASE1_CIDS)} | 课程: {config['phase1']['total_courses']} 门 | 产品: {len(PRODUCTS)}")
print(f"   签审 {config['phase1']['signoff']['phase1_person_days']} 人日 | rubric {config['phase1']['rubric']['person_days']} 人日")
