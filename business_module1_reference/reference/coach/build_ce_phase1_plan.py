#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
为临床维度课程（CE/PL/PB）生成编写计划。
一期范围 21 门，按维度+领域分组为 4 个并行任务。
"""
import json, os, glob

from config import BASE, PATHS
SKEL_DIR = os.path.join(BASE, "course-skeletons-ce")
PHASE1 = json.load(open(os.path.join(SKEL_DIR, "_phase1.json"), encoding="utf-8"))
idx = json.load(open(os.path.join(SKEL_DIR, "_index.json"), encoding="utf-8"))

sel = [e for e in idx
       if e["condition_id"] in PHASE1["phase1_conditions"]
       or e["condition_id"] in PHASE1["phase1_assets"]]

# 分组：CE 按领域切，PL/PB 合并成资产组（切两半）
ce = [e for e in sel if e["dimension"] == "clinical_evidence"]
assets = [e for e in sel if e["dimension"] != "clinical_evidence"]

groups = []
# CE：肿瘤 6 门一组，血液/其他 2 门一组
onco = [e for e in ce if e["area_id"] == "A-ONCO"]
other = [e for e in ce if e["area_id"] != "A-ONCO"]
if onco:
    groups.append(("ce-onco", onco))
if other:
    groups.append(("ce-other", other))
# 资产：PL + PB 共 13 门，切两半
half = len(assets) // 2
groups.append(("asset-1", assets[:half]))
groups.append(("asset-2", assets[half:]))

GUIDE = {
    "clinical_evidence": """### 本批次的教学重点（clinical_evidence 维度）

这一维度训练的是**读一项研究的方法**，不是记住某项研究的结果。

**三组必须区分的概念**（每门课都要用到）：

| 区分 | 各自回答什么问题 | 典型陷阱 |
|---|---|---|
| 单臂研究 vs 随机对照 | 有无同期对照，能不能回答"比现有治疗强" | 用单臂的缓解率直接和另一项试验的化疗比 |
| 替代终点 vs 临床终点 | 指标变化 vs 患者真正获益 | 把 ORR/PFS 的改善说成 OS 获益 |
| 入组人群 vs 真实门诊人群 | 研究结论能覆盖到谁 | 把经过筛选的入组标准当成"所有患者都适用" |

**医生提问的设计方向**：医生质疑"你这个证据够不够硬"——考察代表能不能逐项说清这项研究回答了什么、**没回答什么**。

**禁止**：具体试验名称、样本量、p 值、HR 数值。本课只讲方法，不讲某项研究的数据。
""",
    "pipeline_literacy": """### 本批次的教学重点（pipeline_literacy 维度）

核心是**「披露状态 ≠ 审批状态」**，两者必须分别讲、分别标注。

骨架里 `related_pipeline` 给了两个真实状态字段，课程必须都用上并说清区别：
- `reported_status`（研发方披露口径，如「全球III期及中国关键性研究」）——**这是披露，不是批准**
- `approval_status`（审批状态，如 `research_asset_not_approved`）——**这是审批状态本身**

**医生提问的设计方向**：医生问"你们这个项目现在什么状态，我能不能用/介绍"——
考察代表能不能说清"披露到哪一步"与"审批到哪一步"是两件事，且都不能由自己下结论。

**禁止**：把在研资产的机制方向说成已获批适应症；禁止预测审批时间表。
**资产与疾病的关联一律是 educational_topic_not_indication（教学主题关联，非获批适应症）**，课程里提到时必须体现这一层。
""",
    "product_basics": """### 本批次的教学重点（product_basics 维度）

核心是**核查路径**，不是背诵产品信息。

**必须讲清**：通用名与靶点可核实；**适应症必须查最新 NMPA 说明书与企业合规版本，不得推断**。

**医生提问的设计方向**：医生问"XX 药是干什么的/适应症是什么"——
考察代表在被问到具体适应症时，是说出不确定并给出核实路径，还是编一个看似确定的答案。

**禁止**：列举具体适应症、用法用量、疗程天数等需说明书支撑的内容。
**产品与疾病的关联一律是 educational_topic_not_indication（教学主题关联，非获批适应症）**。
""",
}

TPL = """```
  "comparison": {{"kind":"comparison","title":"","instruction":"","items":[{{"title":"","facts":["","","",""]}}],"observation":""}}
  "process":     {{"kind":"process","title":"","instruction":"","stages":[{{"title":"","body":""}}],"observation":""}}
  "concept-map": {{"kind":"concept-map","title":"","instruction":"","nodes":[{{"id":"n1","label":"","role":"prerequisite","connectsTo":["n2"]}}],"observation":""}}
```
`role` 只能是 `prerequisite`/`core`/`unlock`；`connectsTo` 必须指向本课已存在的 id。
"""

HEAD = """你要为 {n} 门课程编写完整教学 spec（dimension = {dim}）。

## 你负责的课程
{cond_list}

{guide}

## 工作方法

### 第一步：逐个读骨架
读 `/workspace/output/course-skeletons-ce/<id>__<short>.json`。骨架关键字段：
- `keywords`：该疾病/资产的真实标志物 —— **必须用到**
- `competency_scope` / `scope_items`：本课覆盖的维度
- `core_question`：知识库给出的原始题目（可改写为更真实的医生提问）
- `expected_checks`：知识库给出的标准答案覆盖点 —— **必须覆盖**
- `related_products` / `related_pipeline`：关联产品与在研资产（含 reported_status / approval_status / link_type）
- `source`：来源（source_id + 标题 + URL + asof_date）
- `visual_kind`：该课要用的可视化模式
- `_constraints`：红线清单（15 条，逐条遵守）

### 第二步：写 spec
填满所有字段，输出完整 lesson spec JSON，结构见下。
`meta`、`hero`、`goal`、`assumptions`、`map`、`hook`、`analogy`、`steps`、`misconceptions`、`checks`、`recall`、`sources`、`visual` 都要有。

**文件名**：写到 `/workspace/output/course-specs-ce/<id>__<short>.json`（目录需自建）。

### 第三步：自检
```bash
cd /workspace/output && python3 validate_specs_v2.py --spec-dir course-specs-ce --skel-dir course-skeletons-ce
```
必须 0 错误才算完成。

## 输出结构
```json
{{
  "meta": {{"title":"","subject":"","age":"医药代表（入职 0–6 个月）","duration":"15 分钟","language":"zh-CN"}},
  "hero": {{"eyebrow":"","question":"一个真实医生会问的问题（要有销售压力感）","promise":"学员通过操作能验证什么"}},
  "goal": "可衡量的学习目标，一条句",
  "assumptions": ["默认学员已知的先修知识"],
  "map": {{"prerequisites":[],"core":"","unlocks":[]}},
  "hook": {{"title":"","body":"","prompt":""}},
  "visual": {{...}},
  "analogy": {{"title":"","body":"","limit":"这个类比在哪里不成立（必须写清楚）"}},
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

1. **禁止 web 搜索。** 临床事实只能来自骨架字段（source_id + 表名 + 记录 ID）。
2. **禁止声称任何产品已获批该疾病适应症。**
3. **禁止编造临床数值。**
4. **禁止把研究结论表述为临床决策建议。**
5. **每门课至少 1 条误区指向"超出证据边界的表述"。**
6. **每门课至少 1 道检验题的正确答案是"承认不确定 + 给出核实路径"**——
   ⚠️ **核实路径必须写在正确项本身**，不能只写在 explanation 里。
   正确项形如「需按最新说明书与医学信息核实」「需按研究方案核对人群与线次」，
   不要写成「单臂研究没有同期对照」这种纯知识结论。
7. **每门课至少 1 道检验题的干扰项含绝对化或越界表述**（"所有患者都适用""肯定比竞品好""在研项目已获批"）。
8. **steps 3–5 步**；**checks 2 道**；**misconceptions 2 条**；**sources 2–3 条**（必须含骨架的 source_url）。
9. 医生提问必须**用该疾病/资产的具体标志物或维度**。
10. **选项 ≤ 80 字，解析 ≤ 240 字。** 超长就把"选项 + 解析"拆开：选项只留可判定的核心主张，细节与核实路径放进 explanation；但**核实路径必须留在正确项里**。
11. **正确项与错误项长度量级要相当**——不能把完整话术塞进正确项。

## 自检完成后
输出简短总结（纯文本）：
```
完成 <分组名>：<门数> 门
- <ID>__<short> 课程标题 | visual=<kind> | checks=<n>
...
自检：validate_specs_v2.py 通过（N 份 spec，M 个错误）
```
"""

VERIFY = """独立验证本批次课程 spec（/workspace/output/course-specs-ce/ 下属于 {tag} 的文件）。

**不要只信作者的总结，自己核**：

1. **跑校验器**：`cd /workspace/output && python3 validate_specs_v2.py --spec-dir course-specs-ce --skel-dir course-skeletons-ce`，本批次必须 0 错误。
2. **逐个读 spec** 检查校验器查不出的部分：
   - 内容是否针对该疾病/资产的**具体标志物**？关键词一个都没用到 → FAIL。
   - **同批次内是否雷同**？换个名字就能互换 → FAIL。
   - 医生提问是否真实可信？考卷腔 → FAIL。
3. **本维度特有红线**（最高优先级）：
   - CE：是否讲清单臂 vs 随机对照 / 替代终点 vs 临床终点 / 入组人群 vs 真实人群三组区分？教学正文出现具体试验数值 → FAIL。
   - PL：是否把 `reported_status`（披露口径）与 `approval_status`（审批状态）**分开表述**？把在研说成已获批 → FAIL。
   - PB：是否讲清"适应症须查最新 NMPA 说明书与企业合规版本，不得推断"？列举具体适应症/用法用量 → FAIL。
   - 三者共同：教学正文出现"某产品适用于某疾病" → FAIL。
4. **核实路径必须在正确项本身**（不是只在解析里）：
   逐题看 `options[answer]` 的文本。若正确项是纯知识结论（如"单臂研究没有同期对照"）
   而核实动作只写在 explanation → FAIL。这是本批次最容易出的问题，务必逐题核。
   至少 1 道题的**边界判断题**正确项须含核实动作。
5. **sources 是否包含骨架的 source.url**？缺 → FAIL。
6. sources 是否含"教学框架不等于临床决策建议"这一层边界说明？缺 → FAIL。

FAIL 条件：校验器有错、关键词未使用、同批次雷同、三组区分缺失、越界表述、编造数值、核实路径不在正确项、缺出处链接、缺边界说明、长度超限。
逐个文件列出结论，最后给一行总结：`<门数> 门，通过 <n>，失败 <m>`。
**判定行必须是回复的最后一行，单独成行：`VERDICT: PASS` 或 `VERDICT: FAIL`**（没有判定行会被引擎判失败并无限重试）。
"""

lines = [
    "version: 1",
    "plan:",
    "  name: '版本 A 一期扩课 · 临床维度 21 门（CE 证据 / PL 管线 / PB 产品）'",
    "  max_concurrency: 4",
    "  max_consecutive_failures: 2",
    "  max_cycles: 5",
    "  auto_reject_retries: 1",
    "tasks:",
]

for tag, es in groups:
    dims = sorted(set(e["dimension"] for e in es))
    cond_list = "\n".join(
        f"- **{e['condition_id']}__{e['short']}** {e['name']} ｜ visual={e['visual_kind']} "
        f"｜ 关键词：{e['keywords']} ｜ scope：{e['scope']}"
        for e in es)
    guide = "\n".join(GUIDE[d] for d in dims if d in GUIDE)
    prompt = HEAD.format(n=len(es), dim=" / ".join(dims), cond_list=cond_list, guide=guide)
    lines.append(f"  - id: ce-{tag}")
    lines.append(f"    title: '临床维度课编写 {tag}：{' · '.join(e['name'][:8] for e in es[:3])}{'…' if len(es) > 3 else ''}'")
    lines.append("    prompt: |")
    for ln in prompt.split("\n"):
        lines.append("      " + ln if ln else "")
    lines.append("    assigned_to: course-author")
    lines.append("    verified_by:")
    lines.append("      - Verifier")
    lines.append("    verify_prompt: |")
    for ln in VERIFY.format(tag=f"ce-{tag}").split("\n"):
        lines.append("      " + ln if ln else "")
    lines.append("    timeout_ms: 1800000")

out = os.path.join(BASE, "course-plan-ce-phase1.yaml")
open(out, "w", encoding="utf-8").write("\n".join(lines))
print(f"✅ 计划已生成：{out}")
for tag, es in groups:
    print(f"  ce-{tag}: {len(es)} 门 · {sorted(set(e['dimension'] for e in es))}")
    for e in es:
        print(f"      {e['condition_id']}__{e['short']}")
