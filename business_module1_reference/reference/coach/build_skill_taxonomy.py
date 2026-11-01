#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SkillTaxonomy 构建器 —— V1.3 列为"共同地基"的实体，我们此前缺失。

产出两棵树（对应 V1.3 的双轨）：
  A. 知识技能树 —— 临床知识库来源
     治疗领域 → 疾病/主题 → 知识能力点（按 competency_items 的 5 个维度）
  B. 沟通技能树 —— 课件语料来源（D0 提取）
     拜访阶段 → 异议类型 → 抗拒形态 → 行为能力点

每条 skill 有稳定 ID（SK-...），可被 GapCandidate / CoverageMap / EmployeeSkillState 引用。

产出：
  skill-taxonomy.json          完整能力树（机器可读）
  skill-taxonomy.md            人读版
"""
import sqlite3, json, os, re, glob
from collections import defaultdict

from config import BASE, PATHS
CLIN = os.path.join(BASE, "clinical/medrep-innovent-clinical-knowledge-v0.5")
DB = os.path.join(CLIN, "medrep_clinical_knowledge_v0.5.sqlite")
PHASE0 = os.path.join(BASE, "phase0")
OUT = os.path.join(BASE, "skill-taxonomy")
os.makedirs(OUT, exist_ok=True)

# ============ A. 知识技能树 ============
c = sqlite3.connect(DB)
c.row_factory = sqlite3.Row
areas = {r["area_id"]: dict(r) for r in c.execute("select * from therapeutic_areas")}
conds = {r["condition_id"]: dict(r) for r in c.execute("select * from clinical_conditions")}
srcs = {r["source_id"]: dict(r) for r in c.execute("select * from clinical_sources")}
items = [dict(r) for r in c.execute("select * from competency_items")]

# V1.3 的两套轨道归属
DIM_TRACK = {
    "disease_foundation":   {"track": "medical", "v13_item": "知识准确性",   "axis": "疾病分型与评估维度"},
    "treatment_landscape":  {"track": "medical", "v13_item": "适用边界",     "axis": "治疗机制类别与适用边界"},
    "clinical_evidence":    {"track": "medical", "v13_item": "证据运用",     "axis": "研究设计与证据质量判断"},
    "product_basics":       {"track": "medical", "v13_item": "知识准确性",   "axis": "产品基础信息与核查路径"},
    "pipeline_literacy":    {"track": "medical", "v13_item": "专业与合规要求", "axis": "在研与获批的状态边界"},
}

def slug(s):
    return re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").upper()[:14]

knowledge_skills = []
# 同一疾病的同一 scope 在多个维度下重复出现 —— 知识能力点应唯一，维度作为属性集合
_scope_index = {}   # (condition_id, scope) -> skill 记录


def _add_scope_skill(cond, scope_text, dim, cfg, it):
    key = (cond["condition_id"], scope_text)
    if key in _scope_index:
        sk = _scope_index[key]
        if dim not in sk["dimensions"]:
            sk["dimensions"].append(dim)
            sk["v13_evaluation_items"].append(cfg.get("v13_item"))
            sk["axes"].append(cfg.get("axis"))
        return sk
    area = areas.get(cond["area_id"], {})
    sid = f"SK-K-{slug(cond['condition_id'])}-{len(_scope_index)+1:03d}"
    sk = {
        "skill_id": sid,
        "tree": "knowledge",
        "track": cfg.get("track", "medical"),
        "name": scope_text,
        "parent_id": cond["condition_id"],
        "grandparent_id": cond["area_id"],
        "area_name": area.get("name"),
        "department": area.get("department"),
        "condition_name": cond["name"],
        "keywords": cond["keywords"],
        "dimensions": [dim],
        "v13_evaluation_items": [cfg.get("v13_item")],
        "axes": [cfg.get("axis")],
        "source": {"source_id": it["source_id"], "item_id": it["item_id"],
                   "title": (srcs.get(it["source_id"]) or {}).get("title"),
                   "url": (srcs.get(it["source_id"]) or {}).get("url"),
                   "asof_date": (srcs.get(it["source_id"]) or {}).get("asof_date")},
        "medical_review": cond.get("medical_review"),
        "grading_mode": it.get("grading_mode"),
    }
    _scope_index[key] = sk
    knowledge_skills.append(sk)
    return sk


for it in items:
    dim = it["dimension"]
    st = it["subject_type"]
    sid = it["subject_id"]
    cfg = DIM_TRACK.get(dim, {})
    if st == "clinical_condition":
        cond = conds.get(sid)
        if not cond:
            continue
        scope = [x.strip() for x in re.split(r"[、，,;；/]", cond["competency_scope"]) if x.strip()]
        for sp in scope:
            _add_scope_skill(cond, sp, dim, cfg, it)
    elif st in ("commercial_product", "research_asset"):
        # 产品/管线视角：单独成一族（每个资产每个维度各一条）
        label, mechanism = sid, ""
        if st == "commercial_product":
            r = c.execute("select * from med_products where product_id=?", (sid,)).fetchone()
            mechanism = (r["mechanism_topic"] if r else "") or ""
            label = f"{r['brand']}（{r['generic_name']}）" if r else sid
        else:
            r = c.execute("select * from expanded_pipeline where asset_id=?", (sid,)).fetchone()
            mechanism = (r["mechanism_topic"] if r else "") or ""
            label = f"{sid}（{mechanism}）" if r else sid
        knowledge_skills.append({
            "skill_id": f"SK-K-{slug(sid)}-{slug(dim)[:4]}-01",
            "tree": "knowledge",
            "track": cfg.get("track", "medical"),
            "name": f"{label}：{cfg.get('axis','')}",
            "parent_id": f"ASSET-{sid}",
            "grandparent_id": f"ASSET-{st}",
            "area_name": "产品与管线",
            "condition_name": label,
            "keywords": mechanism,
            "subject_type": st,
            "dimensions": [dim],
            "v13_evaluation_items": [cfg.get("v13_item")],
            "axes": [cfg.get("axis")],
            "source": {"source_id": it["source_id"], "item_id": it["item_id"],
                       "title": (srcs.get(it["source_id"]) or {}).get("title"),
                       "url": (srcs.get(it["source_id"]) or {}).get("url"),
                       "asof_date": (srcs.get(it["source_id"]) or {}).get("asof_date")},
            "medical_review": it.get("review_status"),
            "grading_mode": it.get("grading_mode"),
        })

# ============ B. 沟通技能树（从 D0 提取） ============
d0_path = os.path.join(PHASE0, "D0-语料资产库.md")
communication_skills = []
if os.path.exists(d0_path):
    d0 = open(d0_path, encoding="utf-8").read()
    # 2.1 异议类型体系表的 7 类实质类型（列表格式：- **价格异议** `[A36 S162]`：...）
    m = re.search(r"####\s*A\.\s*实质类型.*?\n(.*?)(?=\n####|\n###)", d0, re.S)
    seg = m.group(1) if m else ""
    objection_types = []
    for line in seg.split("\n"):
        mm = re.match(r"^\s*-\s*\*\*(.+?)\*\*\s*`\[([A-Z]\d+)\s*S(\d+)\]`", line)
        if mm:
            objection_types.append((mm.group(1).strip(), mm.group(2), int(mm.group(3))))
    # 拜访阶段：产品侧 5 阶段（V1.3 与任务拆解一致）+ 语料侧 7 阶段
    stages = []
    m_p = re.search(r"产品侧 5 阶段[^\n]*\n`([^`\n]+)`", d0)
    if m_p:
        stages += [x.strip() for x in m_p.group(1).split("→") if x.strip()]
    m_c = re.search(r"语料侧 7 阶段[^\n]*\n`([^`\n]+)`", d0)
    corpus_stages = [x.strip() for x in m_c.group(1).split("→") if x.strip()] if m_c else []
    # 抗拒形态（从语料直接抽）
    resist = [
        ("拖延的抗拒", "A71", 56), ("假借理由的抗拒", "A71", 56), ("沉默的抗拒", "A71", 56),
        ("转换话题的抗拒", "A71", 56), ("反对层出不穷", "A71", 56), ("倦态的抗拒", "A71", 56),
    ]
    for i, (name, code, sl) in enumerate(resist, 1):
        communication_skills.append({
            "skill_id": f"SK-C-STAGE-RESIST-{i:02d}",
            "tree": "communication", "track": "communication",
            "v13_evaluation_items": ["情境适应"],
            "axes": ["抗拒形态下的临场应变"],
            "name": f"应对「{name}」",
            "parent_id": "STAGE-04-异议处理",
            "grandparent_id": "STAGE",
            "source": {"course": code, "slide": sl, "cite": f"[{code} S{sl}]"},
        })
    for i, (name, code, sl) in enumerate(objection_types, 1):
        communication_skills.append({
            "skill_id": f"SK-C-OBJ-{i:02d}",
            "tree": "communication", "track": "communication",
            "v13_evaluation_items": ["临场应变"],
            "axes": [f"{name}类异议的处理"],
            "name": f"处理「{name}」",
            "parent_id": "STAGE-04-异议处理",
            "grandparent_id": "STAGE",
            "source": {"course": code, "slide": sl, "cite": f"[{code} S{sl}]"},
        })
    # 语料侧 7 阶段 → 7 个能力点
    for i, stg in enumerate(corpus_stages, 1):
        communication_skills.append({
            "skill_id": f"SK-C-CSTAGE-{i:02d}",
            "tree": "communication", "track": "communication",
            "v13_evaluation_items": ["情境适应"],
            "axes": ["拜访阶段推进"],
            "name": f"{stg}（语料侧阶段）",
            "parent_id": f"CSTAGE-{i:02d}",
            "grandparent_id": "CSTAGE",
            "source": {"course": "A42", "slide": 4, "cite": "[A42 S4]"},
        })

    # 五个通用沟通能力（对应 V1.3 五维）
    generic = [
        ("问题理解", "准确识别医生真正在问什么（含转问、追问、质疑）", "问题理解"),
        ("回答结构", "给出可跟随的回答结构（结论先行、分层、留核查口）", "回答结构"),
        ("表达清晰", "口语可懂、无黑话、术语即时解释", "表达清晰"),
        ("临场应变", "被拒绝/被打断/被质疑时的即时调整", "临场应变"),
        ("情境适应", "同一知识在不同医生风格与场合下的表达适配", "情境适应"),
    ]
    for i, (name, desc, v13) in enumerate(generic, 1):
        communication_skills.append({
            "skill_id": f"SK-C-GEN-{i:02d}",
            "tree": "communication", "track": "communication",
            "v13_evaluation_items": [v13],
            "axes": [v13],
            "name": name, "description": desc,
            "parent_id": "GEN-COMM", "grandparent_id": "STAGE",
            "source": {"course": "V1.3", "slide": None, "cite": "V1.3 §1.5"},
        })

# ============ 组装 ============
all_skills = knowledge_skills + communication_skills
tree = {
    "version": "v1.3-aligned",
    "generated_for": "MedRep Coach V1.3",
    "note": "两棵树对应 V1.3 的双轨：knowledge 树归入 medical 轨道（V1.3 的四项：知识准确性/证据运用/适用边界/专业与合规要求），communication 树归入 communication 轨道（V1.3 的五维）",
    "trees": {
        "knowledge": {
            "description": "知识技能树 —— 临床知识库来源",
            "roots": [
                {"area_id": aid, "name": a["name"], "department": a["department"],
                 "core_competencies": a["core_competencies"],
                 "children": sorted({s["condition_name"] for s in knowledge_skills
                                     if s.get("grandparent_id") == aid})}
                for aid, a in sorted(areas.items())
            ],
            "asset_roots": sorted({s["grandparent_id"] for s in knowledge_skills
                                   if s.get("grandparent_id", "").startswith("ASSET-")}),
        },
        "communication": {
            "description": "沟通技能树 —— 课件语料来源（D0 提取）",
            "product_stages": stages,
            "corpus_stages": corpus_stages,
            "objections": sorted({s["name"] for s in communication_skills
                                  if s["skill_id"].startswith("SK-C-OBJ-")}),
            "generic": sorted({s["name"] for s in communication_skills
                               if s["skill_id"].startswith("SK-C-GEN-")}),
        },
    },
    "skills": all_skills,
}
with open(os.path.join(OUT, "skill-taxonomy.json"), "w", encoding="utf-8") as fh:
    json.dump(tree, fh, ensure_ascii=False, indent=2)

# ---- 人读版 ----
L = ["# SkillTaxonomy 能力树（V1.3 对齐）", "",
     "> V1.3 把 SkillTaxonomy 列为**共同地基**与核心实体。此前项目产出中该实体缺失，",
     "> 导致知识考察点只是切分出来的短语、没有稳定标识——而 V1.3 §2.3 的差异分析（CoverageMap）",
     "> 恰恰要求按能力点比对。本文件补齐这个地基。", "",
     f"知识技能点 **{len(knowledge_skills)}** 个 ｜ 沟通技能点 **{len(communication_skills)}** 个 ｜ 合计 **{len(all_skills)}**", "",
     "## 一、两棵树与 V1.3 双轨的对应", "",
     "| 树 | 来源 | 对应 V1.3 轨道 | V1.3 评价项 |", "|---|---|---|---|",
     "| knowledge | 临床知识库 `competency_items`（5 维度 × 疾病/产品）| 专业知识运用 | 知识准确性 / 证据运用 / 适用边界 / 专业与合规要求 |",
     "| communication | 课件语料（D0 提取）| 沟通与应变 | 问题理解 / 回答结构 / 表达清晰 / 临场应变 / 情境适应 |", "",
     "## 二、知识技能树", ""]
by_area = defaultdict(list)
for s in knowledge_skills:
    by_area[s["grandparent_id"]].append(s)
for aid, a in sorted(areas.items()):
    ss = by_area.get(aid, [])
    if not ss:
        continue
    L.append(f"### {a['name']}（{a['department']}）— {len(ss)} 个能力点")
    L.append("")
    L.append(f"> 领域核心能力：{a['core_competencies']}")
    L.append("")
    by_cond = defaultdict(list)
    for s in ss:
        by_cond[s["parent_id"]].append(s)
    for cid, group in sorted(by_cond.items(), key=lambda kv: kv[1][0]["condition_name"]):
        L.append(f"**{group[0]['condition_name']}** `{cid}`")
        L.append("")
        for s in group:
            dims = "/".join(s.get("dimensions", []))
            v13 = "/".join(sorted(set(x for x in s.get("v13_evaluation_items", []) if x)))
            L.append(f"- `{s['skill_id']}` **{s['name']}** — 维度：{dims} ｜ V1.3 评价项：{v13}")
        L.append("")

asset_sk = [s for s in knowledge_skills if s.get("grandparent_id", "").startswith("ASSET-")]
if asset_sk:
    L += ["### 产品与管线视角", ""]
    by_st = defaultdict(list)
    for s in asset_sk:
        by_st[s["grandparent_id"]].append(s)
    for st, group in sorted(by_st.items()):
        L.append(f"**{st}**（{len(group)} 项）")
        L.append("")
        for s in group:
            dims = "/".join(s.get("dimensions", []))
            L.append(f"- `{s['skill_id']}` {s['condition_name']} — {dims}")
        L.append("")

L += ["## 三、沟通技能树", "",
      "### 3.1 五个通用沟通能力（V1.3 §1.5 五维）", ""]
for s in sorted(communication_skills, key=lambda x: x["skill_id"]):
    if s["skill_id"].startswith("SK-C-GEN-"):
        L.append(f"- `{s['skill_id']}` **{s['name']}** — {s.get('description','')} ｜ V1.3 评价项：{'/'.join(s.get('v13_evaluation_items',[]))}")
L += ["", "### 3.2 拜访阶段能力点", ""]
for s in sorted(communication_skills, key=lambda x: x["skill_id"]):
    if s["skill_id"].startswith("SK-C-STAGE-") and not s["skill_id"].startswith("SK-C-STAGE-RESIST"):
        L.append(f"- `{s['skill_id']}` {s['name']}  `{s['source']['cite']}`  ｜ {'/'.join(s.get('axes',[]))}")
L += ["", "### 3.3 异议类型能力点（7 类实质类型）", ""]
for s in sorted(communication_skills, key=lambda x: x["skill_id"]):
    if s["skill_id"].startswith("SK-C-OBJ-"):
        L.append(f"- `{s['skill_id']}` {s['name']}  `{s['source']['cite']}`  ｜ {'/'.join(s.get('axes',[]))}")
L += ["", "### 3.4 抗拒形态能力点", ""]
for s in sorted(communication_skills, key=lambda x: x["skill_id"]):
    if s["skill_id"].startswith("SK-C-STAGE-RESIST"):
        L.append(f"- `{s['skill_id']}` {s['name']}  `{s['source']['cite']}`  ｜ {'/'.join(s.get('axes',[]))}")
L += ["", "## 四、这份能力树解锁了什么", "",
      "| V1.3 需求 | 本文件如何满足 |", "|---|---|",
      "| §2.3 CoverageMap 按能力点比对 | 每个 skill 有稳定 ID，预测考点与复盘问题都映射到同一 ID |",
      "| §2.5 EmployeeSkillState 按 skill 记录 | skill_id 可直接作为 EmployeeSkillState.skill_id |",
      "| §1.3 QuestionCandidate 必须关联 skill_ids[] | 每门课的 148 个知识考察点已有稳定 ID 形态 |",
      "| §1.5 Rubric 跨情境比较 | 沟通树与知识树分离，两轨各用自己的 skill 空间 |",
      "", "**仍缺的**：SkillTaxonomy 目前覆盖 42 个疾病 + 49 个产品/管线 + 沟通树。",
      "V1.3 §1.2 要求的 `ExpertRef`/`TopicAffinity`（真实专家的公开学术线索）尚未建——",
      "那部分必须来自公开可核验来源，不能从课件语料推断。", ""]
open(os.path.join(OUT, "skill-taxonomy.md"), "w", encoding="utf-8").write("\n".join(L))

# 统计
from collections import Counter
print(f"SkillTaxonomy 已生成 → {OUT}")
print(f"  知识技能点: {len(knowledge_skills)}")
print(f"  沟通技能点: {len(communication_skills)}")
print(f"  合计: {len(all_skills)}")
print("  按 V1.3 评价项分布:",
      dict(Counter(x for s in all_skills for x in s.get("v13_evaluation_items", []) if x)))
