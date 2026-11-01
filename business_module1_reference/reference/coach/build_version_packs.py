#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 D0 场景种子表抽取结构化场景库，产出两个版本的可交付包。

版本 A（含课程）：课程 + 场景种子的"训练内容包"
版本 B（不含课程）：仅场景种子 + 复盘驱动素材（不含课程）

产出：
  scenario-library.jsonl        48 条结构化场景（两版共用底座）
  version-A-training-pack/      含课程版
  version-B-training-pack/      不含课程版
"""
import json, os, re, glob, shutil, zipfile, time
from collections import Counter

from config import BASE, PATHS
PHASE0 = os.path.join(BASE, "phase0")
D0 = os.path.join(PHASE0, "D0-语料资产库.md")
COURSE = os.path.join(BASE, "medrep-training-courses-v0.6")
OUTLIB = os.path.join(BASE, "scenario-library.jsonl")

DIFF_MAP = {"🟢": "easy", "🟡": "medium", "🔴": "hard"}
TYPE_MAP = {"拒绝": "rejection", "异议": "objection", "追问": "followup", "压力": "pressure"}


def parse_scenarios():
    raw = open(D0, encoding="utf-8").read()
    if "### 6.2" not in raw:
        return []
    seg = raw.split("### 6.2")[1].split("### 6.3")[0]
    rows = []
    for line in seg.split("\n"):
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.split("|")[1:-1]]
        if len(cells) < 6:
            continue
        num, stype, profile, speech, dim, diff = cells[:6]
        if not num.isdigit():
            continue
        # 提取所有出处
        cites = re.findall(r"\[([A-Z]\d+)\s*S(\d+)\]", f"{profile} {speech} {dim}")
        cites = [f"[{c[0]} S{c[1]}]" for c in cites]
        rows.append({
            "scenario_id": f"SCN-{int(num):03d}",
            "type": TYPE_MAP.get(stype, stype),
            "type_cn": stype,
            "doctor_profile": re.sub(r"\s*`?\[[A-Z]\d+\s*S\d+\]`?\s*", "", profile).strip(),
            "doctor_speech": re.sub(r"\s*`?\[[A-Z]\d+\s*S\d+\]`?\s*", "", speech).strip(),
            "exam_dimensions": re.sub(r"\s*`?\[[A-Z]\d+\s*S\d+\]`?\s*", "", dim).strip(),
            "difficulty": DIFF_MAP.get(diff, "medium"),
            "difficulty_cn": diff,
            "citations": cites,
        })
    return rows


def build():
    rows = parse_scenarios()
    if not rows:
        print("未解析到场景种子")
        return
    with open(OUTLIB, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"场景库已抽取：{len(rows)} 条 → {OUTLIB}")

    stats = Counter(r["type"] for r in rows)
    diffs = Counter(r["difficulty"] for r in rows)
    print(f"  类型: {dict(stats)}")
    print(f"  难度: {dict(diffs)}")

    # 关联 SkillTaxonomy 的沟通树能力点
    tax_p = os.path.join(BASE, "skill-taxonomy", "skill-taxonomy.json")
    obj_skill = {}
    if os.path.exists(tax_p):
        t = json.load(open(tax_p, encoding="utf-8"))
        for s in t["skills"]:
            if s["tree"] == "communication" and s["skill_id"].startswith("SK-C-OBJ"):
                nm = s["name"].replace("处理「", "").replace("」", "")
                obj_skill[nm] = s["skill_id"]
    print(f"  可关联的异议类 skill: {len(obj_skill)}")

    # ---------- 版本 A：含课程 ----------
    a_dir = os.path.join(BASE, "version-A-training-pack")
    if os.path.exists(a_dir):
        shutil.rmtree(a_dir)
    os.makedirs(os.path.join(a_dir, "scenarios"))
    shutil.copy2(OUTLIB, os.path.join(a_dir, "scenarios", "scenario-library.jsonl"))

    a_readme = f"""# 版本 A · 含课程训练包

> 面向「**有课程作为训练内容**」的部署形态。课程是训练主体，场景种子是补充与变体来源。

## 内容构成

| 组成 | 数量 | 状态 |
|---|---|---|
| 疾病基础课 | 42 门 | 已生成，**全部为候选层（待医学审核）** |
| 场景种子 | {len(rows)} 条 | 已结构化，带语料出处 |
| 能力点字典 | 222 个 | SkillTaxonomy（知识 197 + 沟通 25）|
| 课程↔知识点映射 | 148 考察点 / 97 诱导题 / 84 检验项 | 已生成 |

## 训练内容从哪来

```
课程（42 门，签审后进已审核层）─┐
                                ├─→ 候选训练考点 → 演练 → 双轨评分 → 短板记录
场景种子（{len(rows)} 条）────────┘
```

课程按 SkillTaxonomy 的能力点组织成学习路径；场景种子用于同一能力点的**情境变体**——
同一条能力点在不同医生风格（直给型 / 绕圈型 / 抗拒型）下呈现不同问法。

## 一期上线前的阻塞项

1. **42 门课逐门医学签审**（21 人日）→ 从候选层推到已审核训练层
2. **84 道检验题补 rubric 与分值**（14 人日）→ 现有全为人评，无法机器评分
3. **课程接入 KnowledgeCandidate 流程**（8 人日）
4. **学习路径编排**（6 人日）

⚠️ **按 V1.3 §0.2，未签审的课程不得进入正式评分。** 跳过签审直接使用，等于违反产品最核心的约束。

## 场景种子速览

| 类型 | 条数 |
|---|---|
"""
    for k, v in stats.items():
        a_readme += f"| {k} | {v} |\n"
    a_readme += "\n"
    a_readme += "| 难度 | 条数 |\n|---|---|\n"
    for k, v in diffs.items():
        a_readme += f"| {k} | {v} |\n"
    a_readme += """
每条场景都带 `citations`（课件出处）、`doctor_profile`（医生画像条件）、`doctor_speech`（医生原话，可直接改写为提问）、`exam_dimensions`（建议考察维度）。

## 文件
```
version-A-training-pack/
├── README.md                    本文件
├── scenarios/scenario-library.jsonl   {len(rows)} 条结构化场景
└── (课程包见 medrep-training-courses-v0.6.zip)
```
"""
    open(os.path.join(a_dir, "README.md"), "w", encoding="utf-8").write(a_readme)

    # ---------- 版本 B：不含课程 ----------
    b_dir = os.path.join(BASE, "version-B-training-pack")
    if os.path.exists(b_dir):
        shutil.rmtree(b_dir)
    os.makedirs(os.path.join(b_dir, "scenarios"))
    os.makedirs(os.path.join(b_dir, "feedback"))
    shutil.copy2(OUTLIB, os.path.join(b_dir, "scenarios", "scenario-library.jsonl"))

    b_readme = f"""# 版本 B · 不含课程训练包

> 面向「**不建课程库，训练内容由真实复盘驱动**」的部署形态。
> 场景种子只作冷启动底座，主要内容来自一线药代提交的真实拜访复盘。

## 内容构成

| 组成 | 数量 | 说明 |
|---|---|---|
| 场景种子（冷启动底座）| {len(rows)} 条 | 带语料出处，用于冷启动期与复盘缺口交叉验证 |
| 能力点字典 | 222 个 | SkillTaxonomy —— **B 版的核心**：复盘问题与训练考点都映射到同一 skill_id |
| 反馈管道规范 | 4 环节 | 复盘采集 → 结构化观察 → 差异分析 → 审核发布 |
| 课程 | **0** | 本版不含任何课程 |

## 内容从哪来

```
一线复盘 → Observation(原话/概述/推测) → GapCandidate(缺口候选)
                                                    ↓ 审核
                                              ScenarioVersion(场景 V2)
                                                    ↓
                                     候选训练考点 → 演练 → 双评分 → 短板记录
                                                    ↓
                                          回到复盘（闭环）
```

**B 版的进化来自真实数据，不来自预先编写的课程。** 这也意味着它的冷启动期没有现成训练素材——
场景种子只能覆盖 {len(rows)} 个场景，而真实拜访的问题分布远不止于此。

## 与版本 A 的本质差异

| | 版本 A（含课程）| 版本 B（不含课程）|
|---|---|---|
| 训练内容来源 | 预先编写的课程 | 真实复盘产生 |
| 首次可用 | 快（课程在库）| 慢（需积累复盘）|
| 持续投入 | 低（内容可复用）| 高（每轮复盘需人工）|
| 瓶颈 | 医学审核产能 | 一线药代参与度 |
| 内容新鲜度 | 靠周更审计 | 天然新鲜 |
| 进化回路 | 二期接通 | 一期即通 |

## B 版的四个必备环节（42 人日）

| ID | 环节 | 人日 | 关键约束 |
|---|---|---|---|
| S1-B1 | 复盘采集（DebriefRaw）| 8 | 3 个主引导问题；原话/概括/推断须可区分；敏感信息拦截；不良反应走法定流程 |
| S1-B2 | 结构化观察（Observation）| 10 | kind 四分；span 可回溯；**主观推测不得固化为医生人格事实** |
| S1-B3 | 差异分析（CoverageMap + GapCandidate）| 12 | 三级比对；差异五分类；**无预演 ID 不算命中率** |
| S1-B4 | 审核与版本发布（ReviewCase → ScenarioVersion）| 12 | 审核与发布分离；V2 可回滚到 V1 |

## 一期落地建议

- 治疗领域：实体瘤与肿瘤免疫
- 疾病数：3–5 个（B 版靠现场数据自然覆盖，不需要预置广覆盖）
- 试点规模：20 名药代 × **12 周**（必须跑够复盘轮次才有数据）
- 冷启动：用 {len(rows)} 条场景种子撑过前 2–3 周

## 文件
```
version-B-training-pack/
├── README.md                    本文件
├── scenarios/scenario-library.jsonl   {len(rows)} 条冷启动场景
└── feedback/
    └── feedback-pipeline-spec.md     反馈管道规范（4 环节）
```
"""
    open(os.path.join(b_dir, "README.md"), "w", encoding="utf-8").write(b_readme)

    # ---------- B 版反馈管道规范 ----------
    fb = """# 反馈管道规范（B 版核心）

> 对应 V1.3 §2.1–2.5。这四个环节是 B 版的进化来源，不可省略。

## 环节 1：复盘采集（DebriefRaw）

| 项 | 规定 |
|---|---|
| 三个主引导问题 | ①对方问了什么 ②我怎么回答 ③我哪里不确定 |
| 来源标记 | 每段内容须标明 **原话 / 概括 / 推断** —— 三者不可混用 |
| 必填字段 | 原始转写、用户修订稿、发生时间、提交时间、可选预演 ID、权限范围 |
| 禁入字段 | 患者可识别信息、未经授权的现场录音 |
| 特殊流程 | 识别到临床不良反应信息 → **引导走法定/企业报告路径，不以本系统替代** |
| 可撤回性 | 提交后允许修订；修订触发重新解析与差异重算 |

**关键事实边界**：复盘是代表的报告。我们能核验的是专业知识依据，**不能仅凭单人复盘证明一次现场交流的完整真相**。

## 环节 2：结构化观察（Observation）

四个 kind：

| kind | 含义 | 示例 |
|---|---|---|
| `reported_question` | 对方提出的专业问题 | "他问头对头数据" |
| `self_answer` | 代表自述的回答 | "我说了我们有头对头" |
| `inference` | 主观推测 | "他好像不认可" |
| `unresolved` | 未解决的问题 | "价格那块没谈拢" |

**两个概念必须分开，不可互相替代**：

- `statement_is_medically_supported` —— 医学论断是否有依据
- `event_occurrence_verified` —— 事件发生是否有佐证

「医生好像不认可」属于 `inference`，**不得自动写成专家的确定性字段**。

## 环节 3：差异分析（CoverageMap + GapCandidate）

**三级比对**（不能只按文字相似度）：

1. 能力点（skill_id）
2. 医学证据主题
3. 提问意图

**差异五分类**：

| 分类 | 含义 |
|---|---|
| `covered_mastered` | 已覆盖且掌握 |
| `covered_not_mastered` | 已覆盖但没掌握 → 补强训练 |
| `not_covered` | 未覆盖 → 新增考点候选 |
| `partial` | 部分覆盖 |
| `unknown` | 记录不清，无法判定 |

**必须随差异结论记录**：`match_evidence`（匹配依据）与 `observation_quality`（样本质量，来自单人回忆）。

**对外表述规范**：用「**复盘报告的题目覆盖情况**」，不要直接声称"预测了真实医生的言行"。

## 环节 4：审核与场景版本发布（ReviewCase → ScenarioVersion）

```
captured → transcribed → user_confirmed → gap_analyzed
   → review_pending → approved/rejected → scenario_proposed → tested → published
```

| 规则 | 说明 |
|---|---|
| 审核与发布分离 | 审核通过 ≠ 自动发布，需经回归测试 |
| 状态转移 | 写在程序与数据库事务中，**不能靠 LLM 自由写状态** |
| 版本可回滚 | 原版本保持可回放；重大问题支持回滚 |
| 被拒候选 | 不得进入任何正式训练 |
| 审计 | reviewer、证据链、政策版本、结果、时间、理由全部可查 |

## 两条进化路径不可合并

| 路径 | 触发 | 审批 | 影响范围 |
|---|---|---|---|
| **个性化复训** | 员工训练表现 | 无需签审（自动）| 仅该员工 |
| **共享题库更新** | GapCandidate 经审核 | **必须审核发布** | 影响全体 |

共享层与个人训练层**数据隔离**。
"""
    open(os.path.join(b_dir, "feedback", "feedback-pipeline-spec.md"), "w", encoding="utf-8").write(fb)

    # ---------- 打两个 zip ----------
    for name, d in [("version-A-training-pack", a_dir), ("version-B-training-pack", b_dir)]:
        zp = os.path.join(BASE, f"{name}.zip")
        if os.path.exists(zp):
            os.remove(zp)
        with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
            for root, dirs, files in os.walk(d):
                for f in sorted(files):
                    p = os.path.join(root, f)
                    z.write(p, os.path.relpath(p, os.path.dirname(d)))
        with zipfile.ZipFile(zp) as z:
            ok = z.testzip() is None
        print(f"✅ {name}.zip  {os.path.getsize(zp)/1024:.0f} KB  完整性={'通过' if ok else '损坏'}")


if __name__ == "__main__":
    build()
