#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D08a 评分表草案 —— 两套评分量表 + 严重错误闸门（待医学事务与培训拍板）。

依据 V1.3 §1.5 的维度命名，叠加本项目已产出的：
- D0 语料资产库的锚点话术与扣分信号
- SkillTaxonomy 的 222 个能力点（作为评分项的挂载点）
- 42 门课的 rubric 工作单（作为校准样本来源）

产出：
  phase0/D8a-评分表草案.md      人读版
  phase0/D8a-评分表草案.json    机器可读（可导入评分引擎）
"""
import json, os, glob, re

from config import BASE, PATHS
PHASE0 = os.path.join(BASE, "phase0")
MAP = os.path.join(BASE, "course-mapping", "course-mapping.json")
TAX = os.path.join(BASE, "skill-taxonomy", "skill-taxonomy.json")

mapping = {m["condition_id"]: m for m in json.load(open(MAP, encoding="utf-8"))}
tax = json.load(open(TAX, encoding="utf-8"))

# ---------- 轨道 A：沟通与应变五维（V1.3 §1.5）----------
COMM = [
    {
        "id": "COM-01", "name": "问题理解",
        "definition": "是否准确识别医生真正在问什么（含转问、追问、质疑、假意拒绝）",
        "anchors": {
            "5": "识别出表面问题与真实诉求的差距，并明确回应真实诉求",
            "3": "识别出问题大类，但未触及真实诉求",
            "1": "把医生的话按字面理解，答非所问",
        },
        "signals": [
            "把「医生好像不认可」当确认信息处理",
            "把试用/好奇当成真实采购意向",
            "没识别出医生在转移话题",
        ],
        "corpus_basis": "D0 §2.1 真实异议 vs 虚假异议（[A36 S161]）",
    },
    {
        "id": "COM-02", "name": "回答结构",
        "definition": "回答是否可跟随：结论先行、分层展开、留出核查口",
        "anchors": {
            "5": "先给结论，再给依据，明确说明不确定的部分与下一步",
            "3": "有结构但层次不清，或结论埋在中间",
            "1": "想到哪说到哪，学员无法跟随",
        },
        "signals": [
            "开场即讲机制，医生听不到他要的",
            "一次抛出多个并列点，无主次",
        ],
        "corpus_basis": "D0 §4.1 拜访阶段映射的产品 5 阶段",
    },
    {
        "id": "COM-03", "name": "表达清晰",
        "definition": "口语可懂、无黑话、术语即时解释、语速与停顿得当",
        "anchors": {
            "5": "术语当场解释，句子短，医生随时能接话",
            "3": "基本可懂但术语未解释",
            "1": "满口黑话，医生听不下去",
        },
        "signals": [
            "直接说「分子缓解」而不解释",
            "用「循证数据」「证据层级」等词而不落地",
        ],
        "corpus_basis": "D0 §3.2 沟通风格四型（[A36 S28]）",
    },
    {
        "id": "COM-04", "name": "临场应变",
        "definition": "被拒绝、被打断、被质疑时能否即时调整而不崩",
        "anchors": {
            "5": "承接住情绪、调整策略、给出下一步",
            "3": "情绪没接住，但能勉强调整",
            "1": "被拒绝后重复同一句话或转移话题",
        },
        "signals": [
            "被拒绝后反复强调产品优势",
            "医生打断后继续原来的话",
        ],
        "corpus_basis": "D0 §5 抗拒形态 6 类（[A71 S56]）",
    },
    {
        "id": "COM-05", "name": "情境适应",
        "definition": "同一知识在不同医生风格与场合下的表达适配",
        "anchors": {
            "5": "按当前医生的风格调整表达，医学内容不变",
            "3": "调整了但仍显生硬",
            "1": "对直给型医生仍绕圈子，或对绕圈型医生说教",
        },
        "signals": [
            "对「说话转大圈」的医生仍用极简表达",
            "忽略场合（诊室有候诊病人仍长谈）",
        ],
        "corpus_basis": "D0 §3.3 科室性格（[A1 S5]）+ §3.2 四型",
        "critical": "**同一审核知识包切换医生情绪时，本维度的语言风格可变，但医学事实与合规边界不得变（AT05）**",
    },
]

# ---------- 轨道 B：专业知识运用四项（V1.3 §1.5）----------
MED = [
    {
        "id": "MED-01", "name": "知识准确性",
        "definition": "分型、标志物、评估维度、机制与适应症边界是否讲对",
        "anchors": {
            "5": "分型/标志物/维度全部准确，且明确说明适用范围",
            "3": "主体正确但有个别维度含糊",
            "1": "关键维度讲错（如把单一标志物当适用标准）",
        },
        "signals": [
            "把 PD-L1 阳性说成免疫治疗的适用标准",
            "把 MSI 与 dMMR 混为一谈",
        ],
        "corpus_basis": "临床知识库 clinical_conditions.competency_scope",
        "skill_refs": "SK-K-*（知识树 197 个能力点）",
    },
    {
        "id": "MED-02", "name": "证据运用",
        "definition": "引用是否可溯源、设计与终点层级是否讲清、局限是否承认",
        "anchors": {
            "5": "讲清研究回答了什么、没回答什么，结论限于研究人群",
            "3": "引用正确但未讲局限",
            "1": "把替代终点说成临床获益，或跨试验比较",
        },
        "signals": [
            "单臂研究缓解率当优效证据",
            "把 ORR/PFS 的改善说成 OS 获益",
            "引用无出处",
        ],
        "corpus_basis": "D0 §5.7 灰色内容隔离 + 临床库 sources（52 条带 URL 与 asof_date）",
        "skill_refs": "SK-K-*（证据运用轴 148 个能力点）",
    },
    {
        "id": "MED-03", "name": "适用边界",
        "definition": "是否守住人群/线次/状态边界，是否给出核实路径",
        "anchors": {
            "5": "明确边界并给出核实路径（需按最新说明书与医学信息核实）",
            "3": "守住了边界但没说怎么核实",
            "1": "越过边界（宣称适用、宣称已获批、宣称人群覆盖）",
        },
        "signals": [
            "「XX 药在 XX 癌已获批适应症」",
            "把在研说成已上市",
            "人群/线次/状态不作限定直接讲",
        ],
        "corpus_basis": "D0 §5 灰色手法隔离清单 35 条 + D2 合规规则",
        "skill_refs": "SK-K-*（适用边界轴 148 个能力点）",
        "critical": "**这是硬红线维度。见下方严重错误闸门。**",
    },
    {
        "id": "MED-04", "name": "专业与合规要求",
        "definition": "是否遵守推广合规要求（不承诺疗效、不贬低竞品、不涉及利益）",
        "anchors": {
            "5": "全程合规，且遇到诱导时明确拒绝并说明理由",
            "3": "无违规但未识别诱导",
            "1": "触碰红线（承诺疗效/贬低竞品/暗示利益/超适应症）",
        },
        "signals": [
            "承诺疗效或保证效果",
            "贬低竞品",
            "涉及回扣/费用/统方等利益诉求",
            "医生要求回扣时未明确拒绝",
        ],
        "corpus_basis": "D2 合规判定规则 + D0 §5 灰色手法",
        "skill_refs": "SK-C-*（沟通树 25 个能力点）",
        "critical": "**一票否决维度。见下方严重错误闸门。**",
    },
]

# ---------- 严重错误闸门 ----------
GATES = [
    {
        "id": "GATE-01",
        "name": "合规硬红线（一票否决）",
        "triggers": [
            "承诺疗效或保证效果",
            "贬低竞品",
            "涉及回扣/返利/费用/统方等利益输送",
            "明示或暗示超说明书（超适应症）使用",
            "未经授权使用他人姓名或病例",
        ],
        "effect": "本轮判定为不通过；**不计入个人均分**（避免通过均分稀释惩罚）；记入重练池；组织层单独统计合规事件率",
        "source": "D2 合规判定规则表",
        "v13": "V1.3 §1.5「专业性严重错误不被流畅表达抵消」（AT12）",
    },
    {
        "id": "GATE-02",
        "name": "适用边界越界（强制降档）",
        "triggers": [
            "把在研资产说成已获批",
            "把研究领域关联说成适应症",
            "人群/线次/治疗位置不作限定",
            "把教学框架当作临床决策建议",
        ],
        "effect": "该轮 MED-03 直接计 0 分，**并触发综合评定的强制降档**（综合分上限见降档表）",
        "source": "D0 §5 灰色手法隔离 + V1.3 §1.5 适用边界",
        "v13": "V1.3 §1.3「不虚构某专家提问概率」+ §1.5 适用边界",
    },
    {
        "id": "GATE-03",
        "name": "不可评分（剔除而非扣分）",
        "triggers": [
            "该知识点在已审核知识包中无可信来源",
            "临床层数据未接入，无法核验具体数值",
            "多来源冲突且无法判定",
        ],
        "effect": "**整题剔除**：不判分、不进分母、不进 GAP 画像；单独计入知识缺口率指标",
        "source": "本项目 D3 规则 + D0 缺口清单 G-A1/G-A2",
        "v13": "V1.3 §1.5「无证据→待复核而非硬给精确分」",
        "critical": "**系统自身知识缺口导致的不可评分，绝不能让药代承担后果。**",
    },
    {
        "id": "GATE-04",
        "name": "维度不可评（权重重分配）",
        "triggers": [
            "该形态下无可观测证据（如电话形态下的打断应对、非语言节奏）",
            "ASR 严重错误导致该轮内容不可辨",
        ],
        "effect": "该维度从分母移除，权重按剩余可评维度重新归一；报告中显式标注「本形态未评 XX 维度」",
        "source": "本项目 D4 形态×维度可测性矩阵",
        "v13": "V1.3 §1.5「无证据或 ASR 严重错误→待复核」+ AT16",
    },
]

# ---------- 降档表 ----------
DOWNGRADE = [
    {"knowledge_score": "≥80 且 边界维度合格", "final_cap": "无上限（100）", "label": "达标"},
    {"knowledge_score": "60–79 且 边界维度合格", "final_cap": 89, "label": "基本达标"},
    {"knowledge_score": "<60", "final_cap": 74, "label": "知识不足（强制降档）"},
    {"knowledge_score": "任一，但触发 GATE-02", "final_cap": 59, "label": "边界越界（强制降档）"},
    {"knowledge_score": "触发 GATE-01", "final_cap": 0, "label": "合规否决（不计入均分）"},
]

# ---------- 权重 ----------
WEIGHTS = {
    "initial": {"communication": 60, "medical": 40},
    "dimension_weights_communication": {
        "COM-01 问题理解": 20, "COM-02 回答结构": 20, "COM-03 表达清晰": 15,
        "COM-04 临场应变": 25, "COM-05 情境适应": 20,
    },
    "dimension_weights_medical": {
        "MED-01 知识准确性": 30, "MED-02 证据运用": 25,
        "MED-03 适用边界": 30, "MED-04 专业与合规要求": 15,
    },
    "escalation_rule": {
        "trigger": "连续 3 次综合评定达标，且无 GATE-01 记录",
        "step": "medical 权重 +5 个百分点",
        "cap": "medical 权重上限 60%（即 communication 不低于 40）",
        "review": "每次上调须由培训师确认，并记录调整日期",
    },
    "note": "轨道 B 的四个维度之和为 100，轨道 A 的五个维度之和为 100；两轨按 communication/medical 比例合成",
}

# ---------- 校准样本来源 ----------
calib = {
    "method": "黄金测试集 + 人工标注，每维度 ≥50 条带标准分样本",
    "sources": [
        {"source": "42 门课（DF 维度）", "count": 84, "use": "检验题与标准答案，可直接作为 MED 轴校准样本"},
        {"source": "48 条场景种子", "count": 48, "use": "COM 轴校准样本（含 6 种抗拒形态）"},
        {"source": "SkillTaxonomy", "count": 222, "use": "评分项挂载点（每条 skill 对应可判定的评分行为）"},
    ],
    "consistency_metric": "与培训师评分的一致性，目标相关系数 ≥0.7",
    "pending": "需补齐 84 道题的 rubric（14 人日）与分值",
}

doc = {
    "version": "D08a-draft",
    "status": "待医学事务 + 培训拍板（D08a）",
    "baseline": "V1.3 §1.5 维度命名 + 本项目锚点话术与扣分信号",
    "tracks": {
        "communication": {"name": "沟通与应变", "dimensions": COMM},
        "medical": {"name": "专业知识运用", "dimensions": MED},
    },
    "gates": GATES,
    "downgrade_table": DOWNGRADE,
    "weights": WEIGHTS,
    "calibration": calib,
}

os.makedirs(PHASE0, exist_ok=True)
with open(os.path.join(PHASE0, "D8a-评分表草案.json"), "w", encoding="utf-8") as fh:
    json.dump(doc, fh, ensure_ascii=False, indent=2)

# ---------- 人读版 ----------
L = [
    "# D08a 评分表草案 —— 两套量表 + 严重错误闸门",
    "",
    "> **状态：待拍板（D08a）。** 维度命名与分项依 V1.3 §1.5；锚点话术、扣分信号、"
    "不可评分/不可评维度的处理来自本项目已产出（D0 语料资产库、SkillTaxonomy、课程 rubric 工作单）。",
    "> **需要医学事务给分值、需要培训给权重确认。**",
    "",
    "## 一、两条轨道",
    "",
    "| 轨道 | 维度数 | 初始权重 | 汇总方式 |",
    "|---|---|---|---|",
    "| A 沟通与应变 | 5 | 60% | 维度分加权求和 |",
    "| B 专业知识运用 | 4 | 40% | 维度分加权求和 |",
    "",
    "## 二、轨道 A：沟通与应变五维",
    "",
]
for d in COMM:
    L += [f"### {d['id']} {d['name']}", "",
          f"**定义**：{d['definition']}", "",
          "| 分 | 锚点 |", "|---|---|"]
    for k in ["5", "3", "1"]:
        L.append(f"| {k} | {d['anchors'][k]} |")
    L += ["", "**典型扣分信号**：", ""]
    L += [f"- {s}" for s in d["signals"]]
    L += ["", f"**语料依据**：{d['corpus_basis']}", ""]
    if d.get("critical"):
        L += [f"> ⚠️ {d['critical']}", ""]

L += ["## 三、轨道 B：专业知识运用四项", ""]
for d in MED:
    L += [f"### {d['id']} {d['name']}", "",
          f"**定义**：{d['definition']}", "",
          "| 分 | 锚点 |", "|---|---|"]
    for k in ["5", "3", "1"]:
        L.append(f"| {k} | {d['anchors'][k]} |")
    L += ["", "**典型扣分信号**：", ""]
    L += [f"- {s}" for s in d["signals"]]
    L += ["", f"**依据**：{d['corpus_basis']}　**挂载**：{d.get('skill_refs','—')}", ""]
    if d.get("critical"):
        L += [f"> ⚠️ {d['critical']}", ""]

L += ["## 四、严重错误闸门（优先于任何加权）", "",
      "| 闸门 | 触发条件 | 处置 |", "|---|---|---|"]
for g in GATES:
    L.append(f"| **{g['id']} {g['name']}** | {'；'.join(g['triggers'])} | {g['effect']} |")
L += ["", "### 各闸门详情", ""]
for g in GATES:
    L += [f"**{g['id']} {g['name']}**", "",
          "- 触发条件：" + "；".join(g["triggers"]),
          f"- 处置：{g['effect']}",
          f"- 依据：{g['source']}",
          f"- V1.3 对应：{g['v13']}", ""]
    if g.get("critical"):
        L += [f"> ⚠️ {g['critical']}", ""]

L += ["## 五、综合评定降档表", "", "| 条件 | 综合分上限 | 等级 |", "|---|---|---|"]
for r in DOWNGRADE:
    L.append(f"| {r['knowledge_score']} | {r['final_cap']} | {r['label']} |")
L += ["", "> **降档的逻辑**：话术再好、知识错了，在真实拜访中危害更大（V1.3 §1.5）。"
      "所以知识轨道是**降档触发器**，不是加权项。",
      "> 合规触发不是降档到低分，而是**不通过且不计均分**——两件事不能混。", ""]

L += ["## 六、权重", "",
      "| 项 | 值 |", "|---|---|",
      f"| 初始 | 话术 {WEIGHTS['initial']['communication']}% / 知识 {WEIGHTS['initial']['medical']}% |",
      "", "### 轨道 A 维度权重（合计 100）", "", "| 维度 | 权重 |", "|---|---|"]
for k, v in WEIGHTS["dimension_weights_communication"].items():
    L.append(f"| {k} | {v} |")
L += ["", "### 轨道 B 维度权重（合计 100）", "", "| 维度 | 权重 |", "|---|---|"]
for k, v in WEIGHTS["dimension_weights_medical"].items():
    L.append(f"| {k} | {v} |")
er = WEIGHTS["escalation_rule"]
L += ["", "### 资历上调规则", "",
      f"- 触发：{er['trigger']}",
      f"- 步长：{er['step']}",
      f"- 上限：{er['cap']}",
      f"- 复核：{er['review']}", "",
      "> ⚠️ 这是**初始值**，需 D08a 拍板。V1.3 未给具体数值，本草案数值来自本项目设计，需人工确认。", ""]

L += ["## 七、校准方案", "",
      f"- 方法：{calib['method']}",
      f"- 一致性目标：{calib['consistency_metric']}",
      f"- 待补：{calib['pending']}", "",
      "| 校准样本来源 | 数量 | 用途 |", "|---|---|---|"]
for s in calib["sources"]:
    L.append(f"| {s['source']} | {s['count']} | {s['use']} |")

L += ["", "## 八、要拍板的四件事", "",
      "| # | 决策点 | 现状 |", "|---|---|---|",
      "| 1 | 维度分值档位（5/3/1）是否够用？是否需要 0–5 连续分？| 草案用 5/3/1 三档锚点 |",
      "| 2 | 两轨初始权重 60/40 是否认可？| 草案沿用旧稿 |",
      "| 3 | 资历上调的触发条件与步长 | 草案：连续 3 次达标 +5pp，上限 60% |",
      "| 4 | 降档表的三档分界（80/60）与综合分上限（89/74/59）是否合理？| 草案值，未经校准 |",
      "",
      "> 第 4 项的数值**未经校准集验证**，只能作为讨论起点。V1.3 §5.4 明确："
      "「所有数值阈值需在先导标注集建立后确定；当前不能捏造验收成功率」。",
      "> 本草案的阈值同样是待校准的初值。", ""]

open(os.path.join(PHASE0, "D8a-评分表草案.md"), "w", encoding="utf-8").write("\n".join(L))

print("✅ D08a 评分表草案已生成")
print(f"   轨道 A {len(COMM)} 维 | 轨道 B {len(MED)} 维 | 闸门 {len(GATES)} 个 | 降档 {len(DOWNGRADE)} 档")
print(f"   挂载能力点：知识树 197 + 沟通树 25")
