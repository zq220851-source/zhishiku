#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
打包医药培训课程库 → 可分发 zip。

产出结构：
  medrep-training-courses-v0.6/
    README.md                  课程库总说明（边界声明、审核状态、使用方式）
    index.html                 课程索引页（按治疗领域分组）
    courses/<CID>.html         42 门课（离线单文件）
    specs/<CID>.json           42 门课的教学 spec（可复编/可改造）
    course_manifest.json       课程清单与元数据
    USAGE.md                   培训师使用说明（如何开课、如何改、如何审核）
"""
import json, glob, os, shutil, zipfile, time, hashlib, re

from config import BASE, PATHS
SPECS = os.path.join(BASE, "course-specs")
HTML = os.path.join(BASE, "course-html")
SKELS = os.path.join(BASE, "course-skeletons")
CLIN = os.path.join(BASE, "clinical/medrep-innovent-clinical-knowledge-v0.5")
OUTDIR = os.path.join(BASE, "medrep-training-courses-v0.6")
ZIP = os.path.join(BASE, "medrep-training-courses-v0.6.zip")

if os.path.exists(OUTDIR):
    shutil.rmtree(OUTDIR)
os.makedirs(os.path.join(OUTDIR, "courses"))
os.makedirs(os.path.join(OUTDIR, "specs"))

# ---- 1. 收集 ----
index = json.load(open(os.path.join(SKELS, "_index.json"), encoding="utf-8"))
manifest = []
for e in index:
    cid = e["condition_id"]
    sp = os.path.join(SPECS, f"{cid}.json")
    hp = os.path.join(HTML, f"{cid}.html")
    if not (os.path.exists(sp) and os.path.exists(hp)):
        print(f"  ⚠️ 跳过 {cid}（缺 spec 或 html）")
        continue
    spec = json.load(open(sp, encoding="utf-8"))
    skel = json.load(open(os.path.join(SKELS, f"{cid}.json"), encoding="utf-8"))
    shutil.copy2(sp, os.path.join(OUTDIR, "specs", f"{cid}.json"))
    shutil.copy2(hp, os.path.join(OUTDIR, "courses", f"{cid}.html"))
    h = open(hp, encoding="utf-8").read()
    ext = re.findall(r'<(?:script|link|img)[^>]*(?:src|href)="(https?://[^"]+)"', h)
    manifest.append({
        "condition_id": cid,
        "condition_name": e["name"],
        "area_id": e["area_id"],
        "area_name": e["area_name"],
        "department": e["department"],
        "title": spec["meta"]["title"],
        "duration": spec["meta"]["duration"],
        "visual_kind": e["visual_kind"],
        "keywords": e["keywords"],
        "competency_scope": e["scope"],
        "area_core_competencies": e["area_core"],
        "source": {
            "source_id": e["source_id"],
            "title": e["source_title"],
            "url": e["source_url"],
            "asof_date": e["asof_date"],
        },
        "related_products": skel.get("related_products", []),
        "related_pipeline": skel.get("related_pipeline", []),
        "medical_review": skel.get("medical_review"),
        "grading_mode": skel.get("grading_mode"),
        "link_type_note": "educational_topic_not_indication",
        # ---- V1.3 对齐字段 ----
        "spec_version": "v1.3-aligned",
        "knowledge_layer": "candidate",
        "knowledge_layer_note": "新信息候选层 —— 未经 ReviewCase 签审，不得作为正式评分依据或标准答案（V1.3 §0.2）",
        "v13_dimension": skel.get("dimension", "disease_foundation"),
        "v13_evaluation_items": ["知识准确性", "证据运用", "适用边界", "专业与合规要求"],
        "v13_module": "01-前沿预测 / 1.3 专业问题预测",
        "requires_medical_review": True,
        "files": {"html": f"courses/{cid}.html", "spec": f"specs/{cid}.json"},
        "bytes": len(h.encode()),
        "offline_ok": len(ext) == 0,
    })

with open(os.path.join(OUTDIR, "course_manifest.json"), "w", encoding="utf-8") as fh:
    json.dump(manifest, fh, ensure_ascii=False, indent=2)

# 索引页
if os.path.exists(os.path.join(HTML, "index.html")):
    shutil.copy2(os.path.join(HTML, "index.html"), os.path.join(OUTDIR, "index.html"))

# ---- 2. README ----
areas = {}
for m in manifest:
    areas.setdefault((m["area_id"], m["area_name"], m["department"]), []).append(m)

n_ok = sum(1 for m in manifest if m["offline_ok"])
n_pending = sum(1 for m in manifest if m["medical_review"] == "pending_medical_review")

readme = f"""# 医药代表培训课程库 · v0.6（V1.3 对齐）

> **定位：可溯源的内部培训课程设计基础数据。**
> 本库不是经医学事务审批的药品说明书，不是临床决策建议，也不是可直接用于自动评分的评分金标准。
>
> **V1.3 分层定位**：按 MedRep Coach V1.3 §0.2 的知识层次，本库全部内容属于
> **新信息候选层**——允许带不确定性展示、必须有清晰来源和使用限制。
> **未经 ReviewCase 签审，不得作为正式评分依据或标准答案。**

生成时间：{time.strftime('%Y-%m-%d %H:%M')}

## 本版包含

- **{len(manifest)} 门疾病基础课**，覆盖 {len(areas)} 个治疗领域
- 每门课一个**独立离线 HTML 文件**（{n_ok}/{len(manifest)} 份确认无外部运行时依赖，可直接分发、可断网使用）
- 每门课附**教学 spec JSON**（可复编、可改造、可接入其他渲染器）
- `course_manifest.json` —— 课程清单与元数据（含来源、版本日期、审核状态）
- `index.html` —— 课程索引页，按治疗领域分组

## 治疗领域覆盖

| 领域 | 科室 | 门数 |
|---|---|---|
"""
for (aid, aname, dept), ms in sorted(areas.items(), key=lambda kv: -len(kv[1])):
    readme += f"| {aname} | {dept} | {len(ms)} |\n"

readme += f"""
## 必须先读的四条边界

这四条写进了每一门课的内容与检验题，是本库与普通科普课件的核心区别。

### 1. 产品与疾病的关联 ≠ 适应症
本库中产品与疾病的关联类型一律为 `educational_topic_not_indication`——**这是教学主题关联，不是获批适应症**。
课程中提到某产品时，只讲「该领域涉及的产品机制方向」。任何"某药适用于某病"的表述都不成立。

### 2. 在研 ≠ 申报中 ≠ 已获批
`expanded_pipeline` 中 `reported_status`（研发方披露状态）与 `approval_status`（审批状态）分列两栏，含义不同。
课程里讲在研资产时，披露状态与审批状态必须分开表述。

### 3. 教学框架 ≠ 临床决策建议
每门课的 `competency_scope` 是**教学评估范围**，说明这门课覆盖哪些维度；它不是该疾病唯一的知识框架，更不是临床决策依据。

### 4. 不编造临床数值
本库**不含**样本量、发生率、p 值、生存期等具体数值——这些需要以最新说明书与审阅过的文献为准。
遇到需要数值的问题，正确做法是说明信息来源并给出核实路径，而不是给一个看似确定的数字。
**这一点被做成了每门课的检验题**：正确选项是"承认不确定 + 给出核实路径"，而不是背数字。

## 审核状态

| 项目 | 状态 |
|---|---|
| 课程内容医学审核 | **{n_pending}/{len(manifest)} 门为 `pending_medical_review`** — 全部待医学团队审核后方可正式开课 |
| 题目自动评分 | **不可直接启用**。知识库原始 `grading_mode` 全部为 `human_rubric_required` / `source_grounded_human_review` |
| 引用出处 | 每门课 `sources` 均标注来源名称、链接与版本日期（`asof_date`） |
| 数据新鲜度 | 依据 2026-10-31 时点的公开披露口径，后续可能更新 |

**使用前必做**：由医学内容团队逐门审核，补齐标准答案、反例、引用版本与分值，才能进入正式培训或自动评分。

## 与 V1.3 的对齐说明

| V1.3 章节 | 本库的落实 |
|---|---|
| §0.2 两层知识结构 | 全部内容属候选层，manifest 每个条目带 `layer: candidate` 与 `medical_review` |
| §1.3 题目数量可变 | 每门课独立成课，不预设"每次练 3 题"；课内检验题 2 道为教学需要，非训练配额 |
| §1.3 优先级可解释 | 每门课 `hero.question` 即 AI 医生开场问法；`check_items` 标注题型与判别依据 |
| §1.5 双维评估 | 维度按 V1.3 命名：知识准确性 / 证据运用 / 适用边界 / 专业与合规要求 |
| §2.3 CoverageMap | `course-mapping/course-mapping.md` 给出 148 知识考察点 / 97 诱导题 / 84 检验项到 skill 的映射 |
| §3.5 知识沉淀 | 课内 `sources` 均带 URL 与 asof_date，作为 KnowledgeCandidate 的来源字段 |

**关于「高频」**：V1.3 的 D05 指出该词无统计口径、易造成虚假频次宣称。本库不使用"高频问题"这一表述，
统一称**候选训练考点**。课程正文里出现的"高频"仅用于描述某类错误的普遍性（如"最高频的越界表述"），
不构成频次宣称。

## 数据来源

本库的上游数据：
- **信达产品与疾病关联**：临床知识库 `product_condition_map` / `clinical_conditions` / `therapeutic_areas`
- **课程范围与题目框架**：临床知识库 `competency_items`（`disease_foundation` 维度，42 条）
- **公开医学教育来源**：临床知识库 `clinical_sources` / `sources`（含 URL 与 asof_date）

## 使用方式

1. 打开 `index.html` 浏览全部课程，按治疗领域分组
2. 单门课直接打开 `courses/<CID>.html`，**双击即可，无需服务器、无需联网**
3. 改造课程：编辑 `specs/<CID>.json` 后用渲染器重新生成
4. 接入陪练 Agent：见 `USAGE.md`

## 文件清单

```
medrep-training-courses-v0.6/
├── README.md                  本文件
├── USAGE.md                   培训师使用说明
├── index.html                 课程索引页
├── course_manifest.json       课程清单与元数据
├── courses/                   42 门课（离线单文件 HTML）
└── specs/                     42 门课的教学 spec（JSON）
```
"""
open(os.path.join(OUTDIR, "README.md"), "w", encoding="utf-8").write(readme)

# ---- 3. USAGE ----
usage = f"""# 培训师使用说明

## 一、开一节课的标准流程

| 步 | 动作 | 要点 |
|---|---|---|
| 1 | 选课 | 按学员负责的科室选对应疾病课程，见 `index.html` |
| 2 | 医学审核 | **必做**。该课程医学状态为 `pending_medical_review`，需医学内容团队确认适用范围、核实路径表述是否准确 |
| 3 | 试讲 | 打开 `courses/<CID>.html`，走一遍：先做判断 → 动手操作 → 听讲解 → 做检验 → 闭卷回忆 |
| 4 | 补评分 | 若要用于考核，需补齐标准答案、反例、引用版本与分值（原始 `grading_mode` 全为人评） |
| 5 | 归档 | 记录版本与 `asof_date`，来源变更时重新审核 |

## 二、学员会经历什么

每门课 10–20 分钟，五个环节：

1. **先做一个判断** —— 页面先抛出一个真实的医生提问，要求学员先给答案
2. **动手操作** —— 交互式可视化（对照台 / 流程 / 概念图），学员自己切换情形看变化
3. **分层讲解** —— 3–5 步拆解，附带边界说明
4. **误区纠正** —— 每门课 2 条常见误解，含"为什么会这样想"
5. **检验与闭卷回忆** —— 2 道带解析的检验题 + 1 道闭卷复述题

**关键设计**：检验题的正确答案通常是"承认不确定 + 给出核实路径"，而不是背一个数字。这训练的是医药代表最需要的判断力——知道自己不知道什么、去哪里核实。

## 三、改造一门课

课程由 `specs/<CID>.json` 驱动，改 JSON 后重新渲染：

```bash
# 渲染全部
python3 render_courses.py

# 只渲染某门
python3 render_courses.py --only D-NSCLC

# 改完先自检
python3 validate_specs.py
```

### 渲染器硬约束（改 spec 时必看）

| 字段 | 限制 |
|---|---|
| `checks[].options[]` | 每项 ≤ 80 字符 |
| `checks[].explanation` | ≤ 240 字符 |
| `visual.kind` | 只能是 `comparison` / `process` / `concept-map` |
| `visual.comparison.items` | 2–4 项，每项 `facts` 1–6 条 |
| `visual.process.stages` | 3–7 段 |
| `visual.concept-map.nodes` | 3–9 个，`role` ∈ `prerequisite`/`core`/`unlock`，`connectsTo` 必须指向已存在 id |

**选项长度超限怎么办**：不要截断。把长答案拆成"选项 + 解析"——选项只留可判定的核心主张（20–45 字），细节与核实路径放进 `explanation`（解析不受长度限制）。

## 四、内容红线（改课时同样适用）

1. 不写"某产品适用于某疾病"——关联类型是教学主题关联
2. 不编造临床数值——样本量、p 值、发生率、生存期一律不写
3. 不把在研说成已获批
4. 每门课至少 1 条误区指向"超出证据边界的表述"
5. 每门课至少 1 道检验题的正确项体现"承认不确定 + 给出核实路径"

`validate_specs.py` 会自动扫描以上红线。

## 五、接入陪练 Agent

| 课程元素 | 接入位置 |
|---|---|
| `recall`（闭卷回忆） | 陪练 Agent 的一次**知识轨道练习** |
| `misconceptions`（误区） | AI 医生**主动挖坑**的诱导题设计依据 |
| `checks`（检验题） | 知识轨道评分的题库来源（补齐标准答案后） |
| `map.prerequisites` | 学习路径的先修关系 |
| `meta.age` | 改为按 GAP 画像动态分配难度 |

## 六、已知缺口

| 缺口 | 影响 | 补法 |
|---|---|---|
| 无临床数值 | 涉及数据的问题只能给核实路径 | 补临床层数据（说明书/审阅过的文献） |
| 无医保/限方维度 | 价格与流程类问题只能定性 | 补政策口径，注明版本与生效日期 |
| 全部待医学审核 | 不能直接开课 | 医学内容团队逐门审核 |
| 无自动评分标准 | 不能做机器评分 | 补 rubric 与分值 |
"""
open(os.path.join(OUTDIR, "USAGE.md"), "w", encoding="utf-8").write(usage)

# ---- 4. 打 zip ----
if os.path.exists(ZIP):
    os.remove(ZIP)
with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for root, dirs, files in os.walk(OUTDIR):
        for f in sorted(files):
            p = os.path.join(root, f)
            z.write(p, os.path.relpath(p, os.path.dirname(OUTDIR)))

size = os.path.getsize(ZIP)
print(f"✅ 打包完成：{ZIP}")
print(f"   {len(manifest)} 门课 | {len(areas)} 个领域 | {size/1024/1024:.2f} MB")
print(f"   离线自包含确认：{n_ok}/{len(manifest)}")
print(f"   医学审核状态：{n_pending}/{len(manifest)} pending_medical_review")
# 校验 zip 完整性
with zipfile.ZipFile(ZIP) as z:
    bad = z.testzip()
    print(f"   zip 完整性: {'✅ 通过' if bad is None else '❌ 损坏于 '+bad}")
    print(f"   包含条目: {len(z.namelist())}")
