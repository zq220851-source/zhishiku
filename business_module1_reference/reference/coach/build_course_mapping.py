#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成「课程 ↔ 陪练 Agent 知识点」映射表。

目的：把 42 门课的教学元素对接到陪练 Agent 的知识轨道与诱导题设计，
让 D3 门控规则冻结后可以直接接入，不用返工。

产出：
  course-mapping.md      映射表（人读）
  course-mapping.json    机器可读（给 D7 基线集 / D1 画像卡用）
"""
import json, glob, os, re
from collections import defaultdict

from config import BASE, PATHS
SPECS = os.path.join(BASE, "course-specs")
SKELS = os.path.join(BASE, "course-skeletons")
PHASE0 = os.path.join(BASE, "phase0")
OUT = os.path.join(BASE, "course-mapping")

os.makedirs(OUT, exist_ok=True)

# 维度映射：课程 competency_items 维度 ↔ 陪练知识轨道三项
# V1.3 §1.5 的两套轨道与四项医学评价项
DIM_MAP = {
    "disease_foundation": {"track": "专业知识运用", "v13_item": "知识准确性",
                           "axis": "疾病基础分型逻辑",
                           "coach_role": "AI医生以分型/标志物提问，考察药代能否讲清该疾病的评估维度"},
    "treatment_landscape": {"track": "专业知识运用", "v13_item": "适用边界",
                            "axis": "治疗机制类别与适用边界",
                            "coach_role": "AI医生追问机制方向与适用人群的对应关系"},
    "clinical_evidence": {"track": "专业知识运用", "v13_item": "证据运用",
                           "axis": "研究设计、对照与终点层级",
                           "coach_role": "AI医生质疑证据强度，考察药代能否识别局限而非硬推"},
    "product_basics": {"track": "专业知识运用", "v13_item": "知识准确性",
                       "axis": "产品基础信息与状态",
                       "coach_role": "AI医生核对通用名/机制/上市状态"},
    "pipeline_literacy": {"track": "专业知识运用", "v13_item": "专业与合规要求",
                          "axis": "在研与获批的边界",
                          "coach_role": "AI医生试探是否把在研当获批介绍"},
}

# 从三个 spec 目录统一重建映射（覆盖 DF / TL / CE 三维度）
import glob as _glob
_rows = []
_SPEC_DIRS = [("course-specs", "DF", "courses", "course-skeletons"),
              ("course-specs-tl", "TL", "courses-tl", "course-skeletons-tl"),
              ("course-specs-ce", "CE", "courses-ce", "course-skeletons-ce")]
for _sd, _short, _hd, _kd in _SPEC_DIRS:
    for _f in sorted(_glob.glob(os.path.join(BASE, _sd, "*.json"))):
        _cid = os.path.basename(_f)[:-5]
        _sp = json.load(open(_f, encoding="utf-8"))
        _base, _sh = (_cid.split("__") + [_short])[:2] if "__" in _cid else (_cid, _short)
        _skp = os.path.join(BASE, _kd, f"{_base}__{_short}.json")
        if not os.path.exists(_skp):
            _cands = sorted(_glob.glob(os.path.join(BASE, _kd, f"{_base}__*.json")))
            _skp = _cands[0] if _cands else os.path.join(BASE, _kd, f"{_base}.json")
        _sk = json.load(open(_skp, encoding="utf-8"))
        _kp = [{"kp_id": f"{_cid}.{i+1}", "skill_id": None, "condition": _sk["condition_name"],
                "dimension": _sp_ if False else _d, "source": "clinical_conditions.competency_scope"}
               for i, _sp_ in enumerate(_sk["scope_items"])
               for _d in [_sk["scope_items"][i]]]
        _traps = [{"trap_id": f"{_cid}.T{i+1}", "myth": m["myth"], "correction": m["correction"],
                   "why": m["why"], "type": "证据边界越界"} for i, m in enumerate(_sp.get("misconceptions", []))]
        _checks = []
        for i, c in enumerate(_sp.get("checks", [])):
            _a = c["answer"]; _o = c["options"]; _ans = str(_o[_a])
            _checks.append({"check_id": f"{_cid}.C{i+1}", "question": c["question"], "answer": _ans,
              "explanation": c["explanation"],
              "question_type": "边界判断题" if re.search(r"(产品|资产|适应症|获批|能不能|可不可以|状态|数据|研究|证据|疗效|安全性|人群|用在哪|怎么用|上市)", c["question"]) else "知识辨析题",
              "has_verify_path": bool(re.search(r"(核实|确认|查证|不确定|需按|需要按|须按|按最新|说明书|医学信息|医学团队|为准|核对|口径)", _ans)),
              "verify_path_required": bool(re.search(r"(产品|资产|适应症|获批|能不能|可不可以|状态|数据|研究|证据|疗效|安全性|人群|用在哪|怎么用|上市)", c["question"])),
              "distractors_are_boundary_violations": any(
                  re.search(r"(所有|全部|肯定|一定|必然|绝对|获批|适用于|比竞品)", x)
                  for j, x in enumerate(_o) if j != _a)})
        _rows.append({"condition_id": _base, "dimension": _sk.get("dimension", "disease_foundation"),
                      "condition_name": _sk["condition_name"],
          "area_id": _sk["area"]["area_id"], "area_name": _sk["area"]["name"], "department": _sk["area"]["department"],
          "course_title": _sp["meta"]["title"], "course_file": f"{_hd}/{_cid}.html",
          "spec_file": f"{_sd}/{_cid}.json", "hero_question": _sp["hero"]["question"], "goal": _sp["goal"],
          "visual_kind": _sp["visual"]["kind"], "knowledge_points": _kp, "trap_designs": _traps,
          "check_items": _checks, "clinical_source": _sk["source"], "medical_review": _sk["medical_review"],
          "related_products": _sk.get("related_products", []), "related_pipeline": _sk.get("related_pipeline", [])})
rows = _rows

# 始终写出（生成器已统一覆盖 DF/TL/CE 三维度）
_json_out = os.path.join(OUT, "course-mapping.json")
with open(_json_out, "w", encoding="utf-8") as fh:
    json.dump(rows, fh, ensure_ascii=False, indent=2)

# ---- 人读版 ----
area_groups = defaultdict(list)
for r in rows:
    area_groups[(r["area_id"], r["area_name"], r["department"])].append(r)

n_kp = sum(len(r["knowledge_points"]) for r in rows)
n_trap = sum(len(r["trap_designs"]) for r in rows)
n_chk = sum(len(r["check_items"]) for r in rows)
n_verify = sum(1 for r in rows for c in r["check_items"] if c["has_verify_path"])
n_viol = sum(1 for r in rows for c in r["check_items"] if c["distractors_are_boundary_violations"])
n_bnd = sum(1 for r in rows for c in r["check_items"] if c["verify_path_required"])
n_bnd_ok = sum(1 for r in rows for c in r["check_items"] if c["verify_path_required"] and c["has_verify_path"])
n_bnd_bad = [(r["condition_id"], c["check_id"]) for r in rows for c in r["check_items"]
             if c["verify_path_required"] and not c["has_verify_path"]]

lines = [
    "# 课程 ↔ 陪练 Agent 知识点映射表",
    "",
    "> 目的：把 42 门疾病基础课的教学元素，对接到陪练 Agent 的**知识轨道**与**诱导题设计**。",
    "> D3 门控规则冻结后可直接接入，无需返工。",
    "",
    "## 一、映射总览",
    "",
    "| 课程 | 知识考察点 | 诱导题（挖坑方向） | 检验项 | 边界判断题 | 其中含核实路径 | 其中含越界干扰项 |",
    "|---|---|---|---|---|---|---|",
]
for (aid, aname, dept), ms in sorted(area_groups.items(), key=lambda kv: -len(kv[1])):
    k = sum(len(r["knowledge_points"]) for r in ms)
    t = sum(len(r["trap_designs"]) for r in ms)
    c = sum(len(r["check_items"]) for r in ms)
    b = sum(1 for r in ms for x in r["check_items"] if x["verify_path_required"])
    v = sum(1 for r in ms for x in r["check_items"] if x["has_verify_path"])
    d = sum(1 for r in ms for x in r["check_items"] if x["distractors_are_boundary_violations"])
    lines.append(f"| {aname}（{len(ms)} 门）| {k} | {t} | {c} | {b} | {v} | {d} |")
lines += [
    f"| **合计** | **{n_kp}** | **{n_trap}** | **{n_chk}** | **{n_bnd}** | **{n_verify}** | **{n_viol}** |",
    "",
    "## 二、三类对接物分别接到哪里",
    "",
    "| 课程元素 | 对接位置 | 说明 |",
    "|---|---|---|",
    "| `knowledge_points`（疾病分型/标志物维度）| **知识轨道 · 事实准确性 + 场景适配性** | 这是一个药代**应该知道**的维度。AI 医生就这些维度提问，考察药代能否讲清 |",
    "| `trap_designs`（每门 2 条误区）| **合规诱导题设计依据** | 每条误区对应一个「药代如果踩坑就会被抓」的表述方向。AI 医生可据此主动挖坑 |",
    "| `check_items`（每门 2 道检验题）| **知识轨道评分题库** | 补齐 rubric 与分值后可直接做机器评分 |",
    "| `hero_question`（真实医生提问）| **AI 医生话术模板** | 每门课开头那个问题，就是 AI 医生开场会问的话 |",
    "| `course_file` 的 `recall` 环节 | **陪练 Agent 的一次知识轨道练习** | 闭卷复述 = 知识轨道的检验形式 |",
    "",
    "## 三、维度映射：课程 competency_items ↔ 知识轨道三项",
    "",
    "| 课程维度 | V1.3 轨道 | V1.3 评价项 | 考察轴 | AI 医生如何出题 |",
    "|---|---|---|---|---|",
]
for d, v in DIM_MAP.items():
    lines.append(f"| `{d}` | {v['track']} | **{v['v13_item']}** | {v['axis']} | {v['coach_role']} |")

lines += [
    "",
    "> **两类检验题的分工**：知识辨析题问的是纯知识区别（如 CLL 与 SLL 的区分、FISH 与 PCR 的差异），",
    "> 考的是知识准确性，不要求核实路径；边界判断题涉及产品状态、适应症、证据边界或具体数据，",
    "> **必须**体现「承认不确定 + 给出核实路径」。",
    "",
    "> **注意**：42 门课只覆盖 `disease_foundation` 一个维度（知识库 42 条恰好全是这个维度）。",
    "> 课程库**不覆盖** `treatment_landscape`(42) / `clinical_evidence`(42) / `pipeline_literacy`(29) / `product_basics`(20)。",
    "> 这四个维度是后续扩课方向，见第五节。",
    "",
    "## 四、逐课程映射明细",
    "",
]
for (aid, aname, dept), ms in sorted(area_groups.items(), key=lambda kv: -len(kv[1])):
    lines.append(f"### {aname}（{dept}）")
    lines.append("")
    for r in sorted(ms, key=lambda x: x["condition_name"]):
        lines.append(f"#### {r['condition_id']} · {r['condition_name']}")
        lines.append("")
        lines.append(f"- **课程**：[{r['condition_title'] if 'condition_title' in r else r['course_title']}]({r['course_file']}) ｜ visual={r['visual_kind']} ｜ 医学状态={r['medical_review']}")
        lines.append(f"- **AI 医生开场会问**：{r['hero_question'][:110]}")
        lines.append(f"- **知识考察点**（{len(r['knowledge_points'])} 个）：")
        for kp in r["knowledge_points"]:
            lines.append(f"  - `{kp['kp_id']}` {kp['dimension']}" + (f"  → skill `{kp['skill_id']}`" if kp.get("skill_id") else "  → skill 待关联"))
        lines.append(f"- **诱导题方向**（{len(r['trap_designs'])} 个）：")
        for t in r["trap_designs"]:
            lines.append(f"  - `{t['trap_id']}` {t['myth'][:78]}")
        lines.append(f"- **检验项**（{len(r['check_items'])} 个）：")
        for c in r["check_items"]:
            flags = []
            flags.append(c["question_type"])
            if c["has_verify_path"]:
                flags.append("含核实路径")
            if c["distractors_are_boundary_violations"]:
                flags.append("含越界干扰项")
            gap = "  ⚠️缺核实路径" if c["verify_path_required"] and not c["has_verify_path"] else ""
            lines.append(f"  - `{c['check_id']}` {c['question'][:70]}  {'＋'.join(flags)}{gap}")
        lines.append("")

# 扩课方向
lines += [
    "## 五、后续扩课方向（课程库未覆盖的知识维度）",
    "",
    "| 知识库维度 | 条数 | 课程库现状 | 建议动作 |",
    "|---|---|---|---|",
    "| `disease_foundation` | 42 | ✅ 已成课 | 已交付 |",
    "| `treatment_landscape` | 42 | ⬜ 未成课 | **下一步优先**——与话术轨道的「场景适配性」直接相关 |",
    "| `clinical_evidence` | 42 | ⬜ 未成课 | 对应证据引用质量轨道，是 D3 知识轨道的核心 |",
    "| `pipeline_literacy` | 29 | ⬜ 未成课 | 对应在研/获批边界，是合规红线的高发区 |",
    "| `product_basics` | 20 | ⬜ 未成课 | 产品基础速查，可做成一页式速查卡而非完整课件 |",
    "",
    "**扩课不需要重新设计流程**——现有 `build_course_skeletons.py` → agent 编写 → `validate_specs.py` → `render_courses.py` 全链路可复用，",
    "只需把骨架来源从 `disease_foundation` 换成其他维度即可。",
    "",
    "## 六、接入陪练 Agent 的前置条件",
    "",
    "| 前置 | 状态 | 阻塞谁 |",
    "|---|---|---|",
    "| D3 门控规则冻结（阈值/权重/降档）| ⏳ Phase 0 进行中 | 知识轨道评分合成 |",
    "| 检验题 rubric 与分值补齐 | ⬜ 未做（知识库原始为全人评）| 知识轨道自动评分 |",
    "| 42 门课医学审核 | ⬜ 未做（全为 pending_medical_review）| 正式开课 |",
    "| 临床层数据（说明书/文献）| ⬜ 未接入 | 涉及具体数值的考核点 |",
    "",
    "> **结论**：映射表本身已完成，不阻塞任何后续工作。",
    "> 真正阻塞自动评分的是 **rubric 补齐** 与 **D3 门控冻结** 两件事，与课程内容无关。",
]
open(os.path.join(OUT, "course-mapping.md"), "w", encoding="utf-8").write("\n".join(lines))

print(f"✅ 映射表已生成 → {OUT}/course-mapping.md")
print(f"   课程 {len(rows)} 门 | 知识考察点 {n_kp} | 诱导题 {n_trap} | 检验项 {n_chk}")
print(f"   边界判断题 {n_bnd} 道，其中含核实路径 {n_bnd_ok}/{n_bnd}" + (f"  ⚠️ 缺: {n_bnd_bad}" if n_bnd_bad else "  ✅ 全覆盖"))
print(f"   含越界干扰项 {n_viol}/{n_chk}")
print(f"   领域 {len(area_groups)} 个")
