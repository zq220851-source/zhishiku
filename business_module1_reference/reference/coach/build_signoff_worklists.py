#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成版本 A 的课程签审工作单 + rubric 补齐清单。
这是"加课程"这个决定的真实交付物：把 42 门课从候选层推到已审核训练层。
"""
import json, os, glob, re

from config import BASE, PATHS
MAN = os.path.join(BASE, "medrep-training-courses-v0.6", "course_manifest.json")
MAP = os.path.join(BASE, "course-mapping", "course-mapping.json")
OUT_A = os.path.join(BASE, "version-A-training-pack")
os.makedirs(os.path.join(OUT_A, "signoff"), exist_ok=True)

manifest = json.load(open(MAN, encoding="utf-8"))
mapping = {m["condition_id"]: m for m in json.load(open(MAP, encoding="utf-8"))}

# ---- 1. 签审工作单（按领域分组，可逐门勾选）----
rows = []
for m in sorted(manifest, key=lambda x: (x["area_id"], x["condition_name"])):
    cid = m["condition_id"]
    mp = mapping.get(cid, {})
    n_checks = len(mp.get("check_items", []))
    n_kp = len(mp.get("knowledge_points", []))
    n_trap = len(mp.get("trap_designs", []))
    rows.append({
        "condition_id": cid,
        "disease": m["condition_name"],
        "area": m["area_name"],
        "department": m["department"],
        "keywords": m["keywords"],
        "course_file": f"courses/{cid}.html",
        "spec_file": f"specs/{cid}.json",
        "source": m["source"],
        "n_knowledge_points": n_kp,
        "n_traps": n_trap,
        "n_checks": n_checks,
        "signoff": {
            "medical_accuracy": "☐ 待审",     # 医学准确性：分型/标志物/评估维度是否正确
            "boundary_statement": "☐ 待审",  # 边界表述：教学框架≠临床决策建议，是否写清
            "no_fabricated_numbers": "☐ 待审",  # 无编造数值
            "no_indication_claim": "☐ 待审",   # 无产品适应症越界
            "verify_path_accurate": "☐ 待审",  # 核实路径说法是否准确可行
            "reviewer": "",
            "date": "",
            "notes": "",
        },
        "status": "pending_medical_review",
    })

worklist = f"""# 课程签审工作单 —— 把 42 门课从候选层推到已审核训练层

> **依据**：MedRep Coach V1.3 §0.2（知识层次）、§2.4（真伪裁判所 / ReviewCase 状态机）
> **状态机**：`draft → auto_checked → pending_human → approved/rejected/needs_revision → published`
> **硬约束**：**pending 项不得进入正式知识与评分。** 未签审的课程不能当标准答案用。

## 签审什么（三件事，不多不少）

每一门课只需确认五项。**这不是学术评审**——课程内容已由医学内容团队按知识库撰写，
签审是确认「医学上准确、边界上不越界、能进正式评分」。

| 检查项 | 判断标准 |
|---|---|
| ① 医学准确性 | 疾病分型、标志物、评估维度是否与知识库一致；有无臆造 |
| ② 边界表述 | 是否明确区分「教学范围」与「临床决策建议」 |
| ③ 无编造数值 | 是否出现未经核实的样本量、发生率、生存期数字 |
| ④ 无适应症越界 | 是否出现「某产品适用于某疾病」或暗示 thereof |
| ⑤ 核实路径可行 | 「需按最新说明书核实 / 医学信息」这类说法是否真实可行 |

## 签审节奏

| 场景 | 门数 | 人日 | 说明 |
|---|---|---|---|
| **推荐（先窄后宽）** | 8 | 4 | 只签一期范围内的疾病 |
| 全量 | 42 | 21 | 一次签完 |

**建议先签 8 门**：一期定 6–8 个疾病（见两版本方案对比 §7），签完即可开课，
剩余 34 门随二期扩课逐步签。

## 逐门清单

| 疾病 | 科室 | 关键词 | 考察点 | 诱导题 | 检验题 | ①医学 | ②边界 | ③数值 | ④适应症 | ⑤核实 | 审核人 | 日期 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
"""
for r in rows:
    kw = (r["keywords"] or "")[:26]
    lines = f"| {r['condition_id']} | {r['disease'][:12]} | {kw} | {r['n_knowledge_points']} | {r['n_traps']} | {r['n_checks']} | ☐ | ☐ | ☐ | ☐ | ☐ | | |"
    worklist += lines + "\n"

worklist += f"""
## 签审完成后的动作

1. 把 `{OUT_A}/signoff/course-signoff-worklist.json` 中该门课的 `status` 从 `pending_medical_review` 改为 `approved`，填入 `reviewer` 与 `date`。
2. 同步更新 `course_manifest.json` 中该条目的：
   - `knowledge_layer`: `candidate` → `approved`
   - `requires_medical_review`: `true` → `false`
   - 新增 `approved_by` / `approved_at` / `knowledge_pack_version`
3. 课程条目转为 KnowledgeCandidate 走 ReviewCase 流程（S1-A3），发布为 KnowledgePackVersion 的一部分。

**只有 `knowledge_layer = approved` 且已绑定 `knowledge_pack_version` 的课程，才能进入正式评分。**

## 统计

- 总课程数：{len(rows)}
- 已签审：0
- 待签审：{len(rows)}
- 涉及检验题：{sum(r['n_checks'] for r in rows)} 道（其中边界判断题需补 rubric，见 rubric 工作单）
"""

open(os.path.join(OUT_A, "signoff", "course-signoff-worklist.md"), "w", encoding="utf-8").write(worklist)

with open(os.path.join(OUT_A, "signoff", "course-signoff-worklist.json"), "w", encoding="utf-8") as fh:
    json.dump({"total": len(rows), "approved": 0, "items": rows}, fh, ensure_ascii=False, indent=2)

# ---- 2. rubric 补齐清单 ----
rub = """# 检验题 rubric 补齐工作单

> **背景**：知识库原始 `grading_mode` 全部为 `human_rubric_required` / `source_grounded_human_review`。
> 本工作单把这 84 道题转成**可机器评分**的形态。
> **注意：只有 rubric 补齐的题才能进自动评分；其余仍需人工。**

## 每道题要补什么

| 字段 | 说明 | 示例 |
|---|---|---|
| `rubric_standard` | 满分/中间/零分的判定标准（可判定的行为描述）| 满分=明确区分分子事件与用药结论，并给出核实路径；中间=承认了边界但未给核实动作；零分=直接断言可用 |
| `key_phrase_required` | 必须出现的关键动作/措辞（用于评分锚定）| 包含「需按最新说明书核实」或等价表达 |
| `key_phrase_forbidden` | 出现即扣分的越界表述 | 「适用于」「已经获批」「肯定比」「所有患者」 |
| `score` | 分值（建议 0–5，与维度权重对应）| 5 |
| `dimension` | 归到 V1.3 的哪一项 | 适用边界 / 知识准确性 / 证据运用 / 专业与合规要求 |
| `source_verified` | 引用是否已核实（对应 V1.3 的证据引用质量）| 是/否 + 来源 |

## 现有素材可直接复用

课程映射表已经标出两类关键信息，**这就是 rubric 起草的起点**：

1. **34 道边界判断题**已标记 `verify_path_required: true` —— 这些题的正确项必须体现"承认不确定 + 给出核实路径"，
   `key_phrase_required` 可直接据此定义（如"核实/确认/查证/按最新说明书"）。
2. **60 道题已标记含越界干扰项** —— 这些题的 `key_phrase_forbidden` 可从干扰项实际措辞中提取。

## 待补题清单

"""
n = 0
for m in sorted(manifest, key=lambda x: (x["area_id"], x["condition_name"])):
    cid = m["condition_id"]
    mp = mapping.get(cid, {})
    for c in mp.get("check_items", []):
        n += 1
        req = "**是**" if c["verify_path_required"] else "—"
        viol = "**是**" if c["distractors_are_boundary_violations"] else "—"
        rub += f"""
### {c['check_id']} ｜ {m['condition_name']}

- **题干**：{c['question']}
- **当前正确项**：{c['answer']}
- **当前解析**：{c['explanation']}
- **需补 rubric**：☐ 标准答案 ☐ 关键动作 ☐ 越界词 ☐ 分值 ☐ 维度归属
- **必须含核实路径**：{req} ｜ **含越界干扰项**：{viol}
- **rubric_standard**：待填
- **key_phrase_required**：待填
- **key_phrase_forbidden**：待填
- **score / dimension / source_verified**：待填
"""
rub += f"""
---

## 统计

- 待补检验题：**{n} 道**
- 其中必须含核实路径：**34 道**（边界判断题）
- 其中含越界干扰项：**60 道**
- 预计人日：14（按每题约 0.5 人日估算）
"""
open(os.path.join(OUT_A, "signoff", "rubric-worklist.md"), "w", encoding="utf-8").write(rub)

print(f"签审工作单已生成：{len(rows)} 门课")
print(f"rubric 工作单已生成：{n} 道题")
