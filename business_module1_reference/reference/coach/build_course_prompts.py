#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
为 course-author agent 生成「每个治疗领域一份」的编写 prompt。
每个领域一个任务，并行执行。
"""
import json, os

SKEL_DIR = "/workspace/output/course-skeletons"
OUT = "/workspace/output/course-prompts"

areas = json.load(open(os.path.join(SKEL_DIR, "_areas.json"), encoding="utf-8"))
index = json.load(open(os.path.join(SKEL_DIR, "_index.json"), encoding="utf-8"))
by_cond = {e["condition_id"]: e for e in index}

os.makedirs(OUT, exist_ok=True)

BASE_INSTR = """你要为 {n} 门疾病基础课编写完整教学 spec。这 {n} 门课属于同一个治疗领域，可以共享领域认知，但**每门课的内容必须针对该疾病的具体分型/标志物/评估维度，不可套用模板**——同一个领域下的不同疾病，分型逻辑和医生提问完全不同。

## 你负责的疾病
{cond_list}

## 工作方法（严格按此执行）

### 第一步：逐个读骨架
对每个疾病，读 `/workspace/output/course-skeletons/<condition_id>.json`。骨架里有：
- `keywords`：该疾病的真实标志物/维度关键词（如 FGFR2;fusion、MSI-H;dMMR、CLDN18.2;HER2）——**这是你写内容时的核心依据**
- `competency_scope` / `scope_items`：该疾病基础诊疗背景要覆盖的维度
- `area.core_competencies`：所属治疗领域的通用核心能力
- `expected_checks`：知识库给出的标准答案覆盖点
- `related_products` / `related_pipeline`：关联产品与在研资产（**只作教学背景，见下方红线**）
- `visual_kind`：该课要用的可视化模式（comparison / process / concept-map）

### 第二步：为每个疾病写 spec
把骨架的 `_fill` 字段全部填满，输出为**完整的 lesson spec JSON**（结构见下方"输出结构"）。
`meta`、`hero`、`goal`、`map`、`hook`、`analogy`、`steps`、`misconceptions`、`checks`、`recall`、`sources`、`visual` 全部要有。

### 第三步：写文件
把每门课的 spec 写到 `/workspace/output/course-specs/<condition_id>.json`。
注意：目录需要自己创建。

## 输出结构（lesson spec 契约）

```json
{{
  "meta": {{
    "title": "课程标题",
    "subject": "治疗领域（科室）",
    "age": "医药代表（入职 0–6 个月）",
    "duration": "15 分钟",
    "language": "zh-CN"
  }},
  "hero": {{
    "eyebrow": "领域 · 疾病",
    "question": "一个真实医生会问的问题（要有销售压力感）",
    "promise": "学员通过操作能验证什么"
  }},
  "goal": "可衡量的学习目标，一条句",
  "assumptions": ["默认学员已知的先修知识"],
  "map": {{
    "prerequisites": ["先修 1-3 条"],
    "core": "核心概念",
    "unlocks": ["掌握后能做的 1-3 件事"]
  }},
  "hook": {{
    "title": "先做一个判断",
    "body": "把学员拉进场景",
    "prompt": "先自己给答案，再操作验证"
  }},
  "visual": {{ ... 按 visual_kind 用对应结构 ... }},
  "analogy": {{
    "title": "类比标题",
    "body": "类比内容",
    "limit": "这个类比在哪里不成立（必须写清楚）"
  }},
  "steps": [
    {{"label": "01", "title": "步骤名", "body": "内容"}}
  ],
  "misconceptions": [
    {{"myth": "常见误解", "correction": "正确说法", "why": "为什么这样重要"}}
  ],
  "checks": [
    {{"question": "检验题", "options": ["A","B","C","D"], "answer": 1, "explanation": "解析（要说清为什么其他选项错）"}}
  ],
  "recall": {{
    "prompt": "闭卷回忆题",
    "hint": "提示",
    "answer": "参考答案"
  }},
  "sources": [
    {{"label": "来源名", "detail": "来源细节", "url": "https://..."}}
  ]
}}
```

### visual 三种模式的结构（严格按 visual_kind 选）

**comparison**（2–4 项）：
```json
"visual": {{
  "kind": "comparison",
  "title": "标题",
  "instruction": "操作指引",
  "items": [
    {{"title": "情形名", "facts": ["要点1", "要点2", "要点3", "要点4"]}}
  ],
  "observation": "操作后应观察到什么"
}}
```

**process**（3–7 阶段）：
```json
"visual": {{
  "kind": "process",
  "title": "标题",
  "instruction": "操作指引",
  "stages": [
    {{"title": "阶段名", "body": "内容"}}
  ],
  "observation": "操作后应观察到什么"
}}
```

**concept-map**（3–9 节点）：
```json
"visual": {{
  "kind": "concept-map",
  "title": "标题",
  "instruction": "操作指引",
  "nodes": [
    {{"id": "n1", "label": "节点名", "role": "prerequisite", "connectsTo": ["n2"]}}
  ],
  "observation": "操作后应观察到什么"
}}
```
`role` 只能是 `prerequisite` / `core` / `unlock` 三者之一；`connectsTo` 必须指向本课中已存在的 id。

## 红线（违反即打回）

1. **禁止 web 搜索。** 所有临床事实只能来自骨架给出的字段。查不到就写「需临床层数据支撑，本课不涉及」。
2. **禁止声称任何产品已获批该疾病适应症。** `related_products` 的 link_type 是 educational_topic_not_indication。提到产品时只能说「该领域涉及的产品机制方向」。
3. **禁止编造临床数值**（样本量、发生率、p 值、OS/PFS 数字）。scope 给的是维度不是数值。
4. **禁止把 scope 当成该疾病唯一的知识框架**——它只是本课的范围，教学框架不等于临床决策建议。这句话要出现在课程里（可放 sources 的 caveat 或 analogy.limit）。
5. **每门课至少 1 条误区指向"超出证据边界的表述"。**
6. **每门课至少 1 道检验题的正确答案是"承认不确定 + 给出核实路径"**，而不是"背一个数字"。
7. **每门课至少 1 道检验题的干扰项包含绝对化或越界表述**（如"所有患者都适用""肯定比竞品好""在研项目已获批"）。
8. **steps 3–5 步**；**checks 2 道**；**misconceptions 2 条**；**sources 2–3 条**（必须包含该课的 source_url）。
9. 每门课的医生提问必须**用该疾病的具体标志物或维度**，不能是"这个药效果怎么样"这种通用问题。

## 自检（写完后逐个执行）

对每个 spec 运行校验：
```bash
cd /workspace/output && python3 validate_specs.py
```
该脚本会检查：JSON 合法、必填字段齐全、visual 结构符合对应 kind、checks 的 answer 索引合法、sources 含 url、misconceptions/checks 数量达标、以及**边界红线扫描**（是否出现"适用于/适应症/获批"等越界词、是否出现具体数值）。
必须全部通过才算完成。有问题就改，改完重跑。

全部 {n} 门课写完且自检通过后，输出一行总结：每门课的 condition_id、标题、visual kind、checks 题数。
"""

for area_id, info in sorted(areas.items()):
    conds = info["conditions"]
    cond_list = "\n".join(
        f"- **{c}** {by_cond[c]['name']} ｜ visual={by_cond[c]['visual_kind']} "
        f"｜ 关键词：{by_cond[c]['keywords']} ｜ scope：{by_cond[c]['scope']}"
        for c in conds)
    prompt = BASE_INSTR.format(n=len(conds), cond_list=cond_list)
    fname = f"area-{area_id}.md"
    with open(os.path.join(OUT, fname), "w", encoding="utf-8") as fh:
        fh.write(prompt)
    print(f"{fname}: {len(conds)} 门课")

# 拆成 6 个并行任务（A-ONCO 16 门拆成 4 组，每组 4 门）
print("\n--- A-ONCO 拆分 ---")
onco = areas["A-ONCO"]["conditions"]
groups = [onco[i:i+4] for i in range(0, len(onco), 4)]
for gi, g in enumerate(groups, 1):
    cond_list = "\n".join(
        f"- **{c}** {by_cond[c]['name']} ｜ visual={by_cond[c]['visual_kind']} "
        f"｜ 关键词：{by_cond[c]['keywords']} ｜ scope：{by_cond[c]['scope']}"
        for c in g)
    p = BASE_INSTR.format(n=len(g), cond_list=cond_list)
    with open(os.path.join(OUT, f"area-A-ONCO-g{gi}.md"), "w", encoding="utf-8") as fh:
        fh.write(p)
    print(f"  area-A-ONCO-g{gi}.md: {g}")
