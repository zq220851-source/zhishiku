#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
为任意维度生成编写 prompt（供 course-author 并行执行）。

用法：
  python3 build_prompts_v2.py --dimension treatment_landscape
  python3 build_prompts_v2.py --dimension clinical_evidence
"""
import json, os, argparse, glob

# 维度特定的教学指导（决定课程怎么"不一样"）
DIM_GUIDE = {
    "treatment_landscape": """### 本批次的教学重点（treatment_landscape 维度）

这一维度的核心是**三层区分**，这是本批次每门课必须讲透的东西：

| 层 | 是什么 | 代表可以怎么讲 | 不能怎么讲 |
|---|---|---|---|
| ① 诊疗常识 | 公开教科书级共识（分期体系、评估流程、通用治疗思路） | 可以讲，属于专业共同语言 | — |
| ② 已批准药物信息 | 已获批产品的说明书内容 | 讲之前必须说明"以最新NMPA说明书为准" | 不能把某药说成"适用于本病" |
| ③ 研究性方案 | 在研资产的机制方向、研究设计 | 只能说"该领域在研方向包括…" | 不能当第②层讲，不能说适应症 |

**每门课都要让学员能分清这三层。** 建议的误区设计：把③讲成②（如"在研的 XX ADC 已进入后期研究，可以在病房里按 XX 癌的适应症介绍"）。

**医生提问的设计方向**：医生会问"这个方向现在能用到什么程度"——考察代表能不能说清"已获批的到哪一步、在研的到哪一步、两者不能混"。
""",
    "clinical_evidence": """### 本批次的教学重点（clinical_evidence 维度）

这一维度训练的是**读一项研究的方法**，不是记住某项研究的结果。

**三组必须区分的概念**（每门课都要用到）：

| 区分 | 各自回答什么问题 | 典型陷阱 |
|---|---|---|
| 单臂研究 vs 随机对照 | 有无同期对照，能不能回答"比现有治疗强" | 用单臂的缓解率直接和另一项试验的化疗比 |
| 替代终点 vs 临床终点 | 指标变化 vs 患者真正获益 | 把 ORR/PFS 的改善说成 OS 获益 |
| 入组人群 vs 真实门诊人群 | 研究结论能覆盖到谁 | 把经过筛选的入组标准当成"所有患者都适用" |

**必须讲清研究设计的三个维度**：对照组（有无、怎么设）、随机化、人群与终点。

**医生提问的设计方向**：医生质疑"你这个证据够不够硬"——考察代表能不能逐项说清这项研究回答了什么、**没回答什么**。

**禁止**：具体试验名称、样本量、p 值、HR 数值。这门课教的是方法，不是结果。
""",
}


def build(dim, short, focus, outdir, prompts_dir):
    idx = json.load(open(os.path.join(outdir, "_index.json"), encoding="utf-8"))
    areas = json.load(open(os.path.join(outdir, "_areas.json"), encoding="utf-8"))
    os.makedirs(prompts_dir, exist_ok=True)

    guide = DIM_GUIDE.get(dim, "")

    def make_prompt(conds):
        cond_list = "\n".join(
            f"- **{c['condition_id']}** {c['name']} ｜ visual={c['visual_kind']} "
            f"｜ 关键词：{c['keywords']} ｜ scope：{c['scope']}"
            for c in conds)
        return f"""你要为 {len(conds)} 门疾病基础课编写完整教学 spec，维度是 **{dim}**。

## 你负责的疾病
{cond_list}

{guide}

## 工作方法

### 第一步：逐个读骨架
读 `/workspace/output/{os.path.basename(outdir)}/<condition_id>__{short}.json`。骨架关键字段：
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

**文件名**：写�� `/workspace/output/course-specs-{short.lower()}/<condition_id>__{short}.json`（目录需自建）。

### 第三步：自检
```bash
cd /workspace/output && python3 validate_specs_v2.py --spec-dir course-specs-{short.lower()} --skel-dir {os.path.basename(outdir)}
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
```json
"comparison": {{"kind":"comparison","title":"","instruction":"","items":[{{"title":"","facts":["","","",""]}}],"observation":""}}
"process":     {{"kind":"process","title":"","instruction":"","stages":[{{"title":"","body":""}}],"observation":""}}
"concept-map": {{"kind":"concept-map","title":"","instruction":"","nodes":[{{"id":"n1","label":"","role":"prerequisite","connectsTo":["n2"]}}],"observation":""}}
```
`role` 只能是 `prerequisite`/`core`/`unlock`；`connectsTo` 必须指向本课已存在的 id。

## 红线（违反即打回）

1. **禁止 web 搜索。** 事实只能来自骨架字段。
2. **禁止声称任何产品已获批该疾病适应症。**
3. **禁止编造临床数值。**
4. **禁止把 scope 当成该疾病唯一的知识框架**——这句话要出现在课程里。
5. **每门课至少 1 条误区指向"超出证据边界的表述"。**
6. **每门课至少 1 道检验题的正确答案是"承认不确定 + 给出核实路径"。**
7. **每门课至少 1 道检验题的干扰项含绝对化或越界表述。**
8. **steps 3–5 步**；**checks 2 道**；**misconceptions 2 条**；**sources 2–3 条**（必须含骨架的 source_url）。
9. 医生提问必须**用该疾病的具体标志物或维度**。
10. **选项 ≤ 80 字，解析 ≤ 240 字。** 超长就把"选项 + 解析"拆开：选项只留可判定的核心主张（20–45 字），细节与核实路径放进 `explanation`。
11. **正确项与错误项长度量级要相当**——不能把完整话术塞进正确项。

## 自检完成后
输出简短总结（纯文本）：
```
完成 <分组名>：<门数> 门
- <CID> 课程标题 | visual=<kind> | checks=<n>
...
自检：validate_specs_v2.py 通过（N 份 spec，M 个错误）
```
"""

    # 按领域分组，A-ONCO 拆 4 组
    tasks = []
    for aid, info in sorted(areas.items()):
        conds = [c for c in idx if c["area_id"] == aid]
        if not conds:
            continue
        if aid == "A-ONCO" and len(conds) > 8:
            groups = [conds[i:i + 4] for i in range(0, len(conds), 4)]
        else:
            groups = [conds]
        for gi, g in enumerate(groups, 1):
            tag = aid if len(groups) == 1 else f"{aid}-g{gi}"
            p = make_prompt(g)
            fn = os.path.join(prompts_dir, f"{dim}-{tag}.md")
            open(fn, "w", encoding="utf-8").write(p)
            tasks.append((tag, len(g), [c["condition_id"] for c in g]))

    print(f"[{dim}] {len(tasks)} 个任务")
    for tag, n, cids in tasks:
        print(f"  {tag}: {n} 门 ({cids[0]}…{cids[-1]})")
    return tasks


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dimension", required=True)
    args = ap.parse_args()
    short = {"treatment_landscape": "TL", "clinical_evidence": "CE"}[args.dimension]
    build(args.dimension, short, None,
          f"/workspace/output/course-skeletons-{short.lower()}",
          f"/workspace/output/course-prompts-{short.lower()}")
