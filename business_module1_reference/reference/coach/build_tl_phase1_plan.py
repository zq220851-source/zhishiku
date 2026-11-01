#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
为版本 A 一期生成 TL 维度扩课计划（8 门，2 个并行任务）。

复用 build_prompts_v2.py 的 TL 教学指导，但只针对一期 8 个疾病。
产出：course-plan-tl-phase1.yaml
"""
import json, os, glob, re

from config import BASE, PATHS
PHASE1 = ["D-NSCLC", "D-BREAST", "D-HCC", "D-GC",
          "D-CRC", "D-OVARIAN", "D-GBM", "D-CERVICAL"]
SHORT = "TL"

# TL 教学指导（与 build_prompts_v2.py 一致，但补充一期产品语境）
GUIDE = """### 本批次的教学重点（treatment_landscape 维度）

这一维度的核心是**三层区分**，这是本批次每门课必须讲透的东西：

| 层 | 是什么 | 代表可以怎么讲 | 不能怎么讲 |
|---|---|---|---|
| ① 诊疗常识 | 公开教科书级共识（分期体系、评估流程、通用治疗思路） | 可以讲，属于专业共同语言 | — |
| ② 已批准药物信息 | 已获批产品的说明书内容 | 讲之前必须说明"以最新NMPA说明书为准" | 不能把某药说成"适用于本病" |
| ③ 研究性方案 | 在研资产的机制方向、研究设计 | 只能说"该领域在研方向包括…" | 不能当第②层讲，不能说适应症 |

**每门课都要让学员能分清这三层。** 建议的误区设计：把③讲成②（如"在研的 XX ADC 已进入后期研究，可以在病房里按 XX 癌的适应症介绍它"）。

**医生提问的设计方向**：医生会问"这个方向现在能用到什么程度"——考察代表能不能说清"已获批的到哪一步、在研的到哪一步、两者不能混"。

**禁止**：列举具体药物名称并声称其用于本病；给出具体疗效数值（ORR/PFS/OS 的数字）——本课只讲"有哪些治疗维度"与"如何判断证据质量"。

### 一期语境补充

本批次对应产品范围（来自临床知识库真实映射，`link_type` 一律为 `educational_topic_not_indication`）：
{product_ctx}

**产品的正确讲法**：只能说"该领域涉及的产品机制方向"，以及该产品的**披露状态与审批状态必须分开**（研发方披露 ≠ 监管批准）。具体人群、线次、给药条件一律交给"按最新说明书与医学信息核实"。
"""

TPL = """```
  "comparison": {{"kind":"comparison","title":"","instruction":"","items":[{{"title":"","facts":["","","",""]}}],"observation":""}}
  "process":     {{"kind":"process","title":"","instruction":"","stages":[{{"title":"","body":""}}],"observation":""}}
  "concept-map": {{"kind":"concept-map","title":"","instruction":"","nodes":[{{"id":"n1","label":"","role":"prerequisite","connectsTo":["n2"]}}],"observation":""}}
```
`role` 只能是 `prerequisite`/`core`/`unlock`；`connectsTo` 必须指向本课已存在的 id。
"""

HEAD = """你要为 {n} 门疾病基础课编写完整教学 spec，维度是 **{dim}**（V1.3 对齐口径）。

## 你负责的疾病
{cond_list}

{guide}

## 工作方法

### 第一步：逐个读骨架
读 `/workspace/output/course-skeletons-tl/<condition_id>__TL.json`。骨架关键字段：
- `keywords`：该疾病的真实标志物/维度关键词 —— **这是你写内容时的核心依据，必须用到**
- `competency_scope` / `scope_items`：本课要覆盖的维度
- `teaching_focus` / `core_question`：本维度的教学落点
- `area.core_competencies`：所属治疗领域的通用核心能力
- `expected_checks`：知识库给出的标准答案覆盖点
- `related_products` / `related_pipeline`：关联产品与在研资产（**只作教学背景**）
- `visual_kind`：该课要用的可视化模式
- `_constraints`：本维度的红线（含维度特有红线）

### 第二步：写 spec
把骨架的 `_fill` 全部填满，输出完整 lesson spec JSON，结构见下。
`meta`、`hero`、`goal`、`assumptions`、`map`、`hook`、`analogy`、`steps`、`misconceptions`、`checks`、`recall`、`sources`、`visual` 都要有。

**文件名**：写到 `/workspace/output/course-specs-tl/<condition_id>__TL.json`（目录需自建）。

### 第三步：自检
```bash
cd /workspace/output && python3 validate_specs_v2.py --spec-dir course-specs-tl --skel-dir course-skeletons-tl
```
必须 0 错误才算完成。

## 输出结构
```json
{{
  "meta": {{"title":"", "subject":"", "age":"医药代表（入职 0–6 个月）", "duration":"15 分钟", "language":"zh-CN"}},
  "hero": {{"eyebrow":"", "question":"一个真实医生会问的问题（要有销售压力感）", "promise":"学员通过操作能验证什么"}},
  "goal": "可衡量的学习目标，一条句",
  "assumptions": ["默认学员已知的先修知识"],
  "map": {{"prerequisites": [], "core": "", "unlocks": []}},
  "hook": {{"title":"", "body":"", "prompt":""}},
  "visual": {{...}},
  "analogy": {{"title":"", "body":"", "limit":"这个类比在哪里不成立（必须写清楚）"}},
  "steps": [{{"label":"01","title":"","body":""}}],
  "misconceptions": [{{"myth":"","correction":"","why":""}}],
  "checks": [{{"question":"","options":["","","",""], "answer":1, "explanation":""}}],
  "recall": {{"prompt":"","hint":"","answer":""}},
  "sources": [{{"label":"","detail":"","url":"https://..."}}]
}}
```

### visual 三种模式
""" + TPL + """
## 红线（违反即打回）

1. **禁止 web 搜索。** 事实只能来自骨架字段。
2. **禁止声称任何产品已获批该疾病适应症。**
3. **禁止编造临床数值。**
4. **禁止把 scope 当成该疾病唯一的知识框架**——这句话要出现在课程里。
5. **每门课至少 1 条误区指向"超出证据边界的表述"。**
6. **每门课至少 1 道检验题的正确答案是"承认不确定 + 给出核实路径"**——
   ⚠️ **核实路径必须写在正确项本身**，不能只写在 explanation 里。
   正确项形如"需按最新说明书与医学信息核实"、"需按研究方案核对人群"，
   不要写成"单臂研究没有同期对照"这种纯知识结论。
7. **每门课至少 1 道检验题的干扰项含绝对化或越界表述。**
8. **steps 3–5 步**；**checks 2 道**；**misconceptions 2 条**；**sources 2–3 条**（必须含骨架的 source_url）。
9. 医生提问必须**用该疾病的具体标志物或维度**。
10. **选项 ≤ 80 字，解析 ≤ 240 字。** 超长就把"选项 + 解析"拆开：选项只留可判定的核心主张，细节与核实路径放进 explanation；但**核实路径必须留在正确项里**。
11. **正确项与错误项长度量级要相当**——不能把完整话术塞进正确项。

## 自检完成后
输出简短总结（纯文本）：
```
完成 <分组名>：<门数> 门
- <CID>__TL 课程标题 | visual=<kind> | checks=<n>
...
自检：validate_specs_v2.py 通过（N 份 spec，M 个错误）
```
"""

VERIFY = """独立验证本批次课程 spec（/workspace/output/course-specs-tl/ 下属于 {tag} 的文件）。

**不要只信作者的总结，自己核**：

1. **跑校验器**：`cd /workspace/output && python3 validate_specs_v2.py --spec-dir course-specs-tl --skel-dir course-skeletons-tl`，本批次必须 0 错误。
2. **逐个读 spec** 检查校验器查不出的部分：
   - 内容是否针对该疾病的**具体标志物**？关键词一个都没用到 → FAIL。
   - **同批次内是否雷同**？换个疾病名就能互换 → FAIL。
   - 医生提问是否真实可信？考卷腔 → FAIL。
3. **本维度特有红线**（最高优先级）：
   - **三层区分**（诊疗常识 / 已批准药物信息 / 研究性方案）有没有讲清、层次有没有混淆。
   - 教学正文（goal/steps/map/hero）出现"某产品获批/适用于某疾病" → FAIL。
   - 教学正文出现具体临床数值 → FAIL。
   - 在研资产被说成已获批 → FAIL。
4. **核实路径必须在正确项本身**（不是只在解析里）：
   逐题看 `options[answer]` 的文本。若正确项是纯知识结论（如"单臂研究没有同期对照"）
   而核实动作只写在 explanation → FAIL。这是本批次最容易出的问题，务必逐题核。
   至少 1 道题的**边界判断题**正确项须含核实动作。
5. **sources 是否包含骨架的 source.url**？缺 → FAIL。
6. sources 是否含"教学框架不等于临床决策建议"这一层边界说明？缺 → FAIL。
7. **选项与解析长度**：选项 ≤80 字、解析 ≤240 字。超了 → FAIL。

FAIL 条件：校验器有错、关键词未使用、同批次雷同、三层混淆、越界表述、编造数值、核实路径不在正确项、缺出处链接、缺边界说明、长度超限。
逐个文件列出结论，最后给一行总结：`<门数> 门，通过 <n>，失败 <m>`。
**判定行必须是回复的最后一行，单独成行：`VERDICT: PASS` 或 `VERDICT: FAIL`**（没有判定行会被引擎判失败并无限重试）。
"""

# 产品语境（按疾病分组）
cfg = json.load(open(os.path.join(BASE, "version-A-training-pack", "phase1-config.json"), encoding="utf-8"))
prod_by_cond = {}
for p in cfg["phase1"]["products"]:
    for cid in p["covers"]:
        prod_by_cond.setdefault(cid, []).append(p)

skels = {}
for cid in PHASE1:
    skels[cid] = json.load(open(os.path.join(BASE, "course-skeletons-tl", f"{cid}__TL.json"), encoding="utf-8"))

GROUPS = [("g1", PHASE1[:4]), ("g2", PHASE1[4:])]

lines = [
    "version: 1",
    "plan:",
    "  name: '版本 A 一期扩课 · treatment_landscape 维度 8 门'",
    "  max_concurrency: 2",
    "  max_consecutive_failures: 2",
    "  max_cycles: 4",
    "  auto_reject_retries: 1",
    "tasks:",
]

for tag, cids in GROUPS:
    cond_list = "\n".join(
        f"- **{c}** {skels[c]['condition_name']} ｜ visual={skels[c]['visual_kind']} "
        f"｜ 关键词：{skels[c]['keywords']} ｜ scope：{skels[c]['competency_scope']}"
        for c in cids)
    pctx = "\n".join(
        f"- {c} {skels[c]['condition_name']}：" +
        "、".join(f"{p['name']}（{p['mechanism_topic']}，{'已商业化' if p['status']=='commercialized' else '在研'}）"
                  for p in prod_by_cond.get(c, []))
        for c in cids)
    prompt = HEAD.format(n=len(cids), dim="treatment_landscape",
                          cond_list=cond_list,
                          guide=GUIDE.format(product_ctx=pctx))
    lines.append(f"  - id: tl-phase1-{tag}")
    lines.append(f"    title: 'TL 维度扩课 {tag}：{' · '.join(skels[c]['condition_name'][:8] for c in cids)}'")
    lines.append("    prompt: |")
    for ln in prompt.split("\n"):
        lines.append("      " + ln if ln else "")
    lines.append("    assigned_to: course-author")
    lines.append("    verified_by:")
    lines.append("      - Verifier")
    lines.append("    verify_prompt: |")
    for ln in VERIFY.format(tag=f"tl-phase1-{tag}").split("\n"):
        lines.append("      " + ln if ln else "")
    lines.append("    timeout_ms: 1800000")

out = os.path.join(BASE, "course-plan-tl-phase1.yaml")
open(out, "w", encoding="utf-8").write("\n".join(lines))
print(f"✅ TL 一期扩课计划已生成：{out}")
print(f"   2 个任务，各 {len(PHASE1)//2} 门")
for tag, cids in GROUPS:
    print(f"   tl-phase1-{tag}: {[skels[c]['condition_name'] for c in cids]}")
