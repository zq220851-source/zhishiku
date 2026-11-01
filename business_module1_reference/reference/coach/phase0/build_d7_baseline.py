#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
构造 D7 判定回归基线集。

每条样本 = 一个 (输入回答, 期望判定) 对。用途：
  1. 规则引擎的单元测试用例
  2. 培训师标注集的种子（标注员在此基础上复核）
  3. D08a-4 降档阈值的回归基线

期望判定字段：
  expect_gate       期望触发的闸门（None = 不触发任何闸门）
  expect_direction  语义方向判定结果（仅对有方向歧义的规则有意义）
  expect_exempt     是否应豁免
  expect_unscorable 是否应判为不可评分
"""
import json, os

import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from config import BASE, PATHS
PHASE0 = os.path.join(BASE, "phase0")

# ---------------------------------------------------------------- 样本定义
# (sample_id, 规则组, 回答文本, 期望闸门, 期望方向, 期望豁免, 期望不可评分, 备注)
S = [
    # ===== GATE-01 CR-01 承诺疗效 =====
    ("CR01-01", "CR-01 承诺疗效",
     "这个药肯定有效，您放心给病人用。", "GATE-01", "实施", False, False,
     "典型违规：直接承诺疗效"),
    ("CR01-02", "CR-01 承诺疗效",
     "我不能保证疗效，临床研究显示的是 X，具体还得看说明书。", None, "拒绝", True, False,
     "拒绝语境豁免：否认承诺"),
    ("CR01-03", "CR-01 承诺疗效",
     "数据显示在这类人群里无进展生存有改善。", None, None, False, False,
     "合规表达：有来源限定，不触发"),
    ("CR01-04", "CR-01 承诺疗效",
     "疗效因人而异，我不能给您打包票。", None, "拒绝", True, False,
     "拒绝语境豁免"),

    # ===== GATE-01 CR-02 宣称获批 =====
    ("CR02-01", "CR-02 宣称获批",
     "这个已经获批用于非小细胞肺癌了。", "GATE-01", "实施", False, False,
     "典型违规：宣称未获批适应症"),
    ("CR02-02", "CR-02 宣称获批",
     "该资产的审批状态还是未获批，披露口径是研发中，两者不能混。", None, None, False, False,
     "正确项：披露状态与审批状态分开表述"),
    ("CR02-03", "CR-02 宣称获批",
     "我说的获批是指研究方案通过伦理审查，不是上市批准。", None, "澄清", True, False,
     "澄清语境豁免：同词不同义"),
    ("CR02-04", "CR-02 宣称获批",
     "在研资产目前披露口径是早期研发阶段，审批状态是 research_asset_not_approved。", None, None, False, False,
     "正确项：两个状态都讲清楚"),

    # ===== GATE-01 CR-03 承诺可及性 =====
    ("CR03-01", "CR-03 承诺可及性",
     "我保证能进你们医院目录。", "GATE-01", "实施", False, False,
     "典型违规：承诺可及性"),
    ("CR03-02", "CR-03 承诺可及性",
     "进目录要走医院的流程，我可以帮您了解需要准备哪些材料。", None, None, False, False,
     "正确项：说明流程不承诺结果"),
    ("CR03-03", "CR-03 承诺可及性",
     "我不能保证进院，但我可以把学术支持的方式给您讲清楚。", None, "拒绝", True, False,
     "拒绝语境豁免"),

    # ===== GATE-01 CR-04 回扣（语料锚点 A74 S77）=====
    ("CR04-01", "CR-04 回扣返利",
     "您给点好处，我这边好说话。", "GATE-01", "实施", False, False,
     "典型违规：接受回扣"),
    ("CR04-02", "CR-04 回扣返利",
     "回扣是违反国家法律和公司员工守则的，我不能答应您。", None, "拒绝", True, False,
     "★语料正向锚点 [A74 S77]：拒绝回扣是正确动作"),
    ("CR04-03", "CR-04 回扣返利",
     "您的意思是让我违规操作，这个不行。", None, "拒绝", True, False,
     "拒绝语境豁免：变体表达"),
    ("CR04-04", "CR-04 回扣返利",
     "学术活动费用按公司流程走，可以走合规的申请流程。", None, None, False, False,
     "合规的替代路径"),

    # ===== GATE-01 CR-05 统方 =====
    ("CR05-01", "CR-05 统方处方数据",
     "把您这边其他科室的处方数据给我看看。", "GATE-01", "实施", False, False,
     "典型违规：索取处方数据"),
    ("CR05-02", "CR-05 统方处方数据",
     "处方数据涉及患者隐私，我这边不掌握也不能收集。", None, "拒绝", True, False,
     "拒绝语境豁免"),

    # ===== GATE-01 CR-06 绝对化 =====
    ("CR06-01", "CR-06 绝对化优越",
     "我们是这个领域最好的、唯一的。", "GATE-01", "实施", False, False,
     "典型违规：绝对化用语"),
    ("CR06-02", "CR-06 绝对化优越",
     "在 X 研究人群中 Y 指标优于对照，限定条件我一起给您。", None, None, False, False,
     "合规表达：有限定条件的比较"),
    ("CR06-03", "CR-06 绝对化优越",
     "我不能说自己最好，只能把数据摆出来您自己判断。", None, "拒绝", True, False,
     "拒绝语境豁免"),

    # ===== GATE-01 CR-07 诋毁竞品 =====
    ("CR07-01", "CR-07 诋毁竞品",
     "那家产品根本不靠谱，临床数据都是造出来的。", "GATE-01", "实施", False, False,
     "典型违规：诋毁竞品"),
    ("CR07-02", "CR-07 诋毁竞品",
     "两款产品定位不同，我按公开资料给您对比。", None, None, False, False,
     "合规表达：客观对比"),

    # ===== GATE-01 CR-08 诱导处方 =====
    ("CR08-01", "CR-08 诱导处方",
     "您多开点，年底我给您申请奖励。", "GATE-01", "实施", False, False,
     "典型违规：以处方量换利益"),
    ("CR08-02", "CR-08 诱导处方",
     "您按临床需要决定，我这边提供的是学术信息。", None, None, False, False,
     "合规表达：不干预处方决策"),
    ("CR08-03", "CR-08 诱导处方",
     "处方量不是我的关注点，那属于科室的事。", None, "拒绝", True, False,
     "拒绝语境豁免"),

    # ===== GATE-02 BR-01 在研说成可用 =====
    ("BR01-01", "BR-01 在研说成可用",
     "这个在研的药物现在临床都可以用了。", "GATE-02", "实施", False, False,
     "典型越界：在研资产说成临床可用"),
    ("BR01-02", "BR-01 在研说成可用",
     "该资产仍在研发阶段，审批状态为未获批，目前不能作为可推广信息。", None, None, False, False,
     "正确项：明确研发阶段与审批状态"),

    # ===== GATE-02 BR-02 研究阶段等同获益 =====
    ("BR02-01", "BR-02 研究结果等同临床获益",
     "这个研究显示有效，所以临床上就能用了。", "GATE-02", "实施", False, False,
     "典型越界：研究结果直接等同临床获益"),
    ("BR02-02", "BR-02 研究结果等同临床获益",
     "替代终点的改善不能直接等同于总生存获益，这个我要按研究原文核实。", None, None, False, False,
     "正确项：终点层级说明 + 核实路径"),

    # ===== GATE-02 BR-03 适应症断言 =====
    ("BR03-01", "BR-03 适应症断言",
     "这个药就是给这类病人用的，您放心用。", "GATE-02", "实施", False, False,
     "典型越界：断言适用范围"),
    ("BR03-02", "BR-03 适应症断言",
     "适用范围我只按最新 NMPA 说明书和企业合规版本讲，不做推断。", None, None, False, False,
     "正确项：核实路径"),

    # ===== GATE-02 BR-04 越界用药建议 =====
    ("BR04-01", "BR-04 越界用药建议",
     "您这边可以按 200mg 每次、每三周一次的方案用。", "GATE-02", "实施", False, False,
     "典型越界：给出给药方案"),
    ("BR04-02", "BR-04 越界用药建议",
     "用法用量以说明书为准，用药决策由您依据患者情况判断。", None, None, False, False,
     "正确项：不越界给方案"),

    # ===== GATE-02 BR-06 教学关联混淆 =====
    ("BR06-01", "BR-06 教学关联混淆",
     "这个产品在很多科室都用，适应症很广。", "GATE-02", "实施", False, False,
     "典型越界：把教学主题关联说成适应症"),
    ("BR06-02", "BR-06 教学关联混淆",
     "这个课程是教学主题关联，不代表获批适应症。", None, None, False, False,
     "正确项：明确区分"),

    # ===== 不可评分（GATE-03）=====
    ("UNS-01", "GATE-03 不可评分",
     "这个产品的具体适应症我需要查一下再回复您。", None, None, False, True,
     "药代明确表示不确定 + 无已审核 rubric 支撑"),
    ("UNS-02", "GATE-03 不可评分",
     "抱歉，这部分我不太确定，不太适合给您一个结论。", None, None, False, True,
     "明确不确定"),
    ("UNS-03", "GATE-03 不可评分",
     "这个数据我需要按最新披露核实之后再回复您。", None, None, False, False,
     "有核实路径且内容可评：不算不可评分"),
    ("UNS-04", "GATE-03 不可评分",
     "说明书上没有这个适应症，我这边不能这么说。", None, None, False, False,
     "合规的边界回应，不判不可评分"),

    # ===== 未作答 =====
    ("NA-01", "未作答",
     "", None, None, False, False,
     "空回答：记为未作答事件，不判低分不判不可评分"),
    ("NA-02", "未作答",
     "   ", None, None, False, False,
     "空白字符：同上"),
]

samples = []
for sid, grp, ans, gate, direction, exempt, unscorable, note in S:
    samples.append({
        "sample_id": sid,
        "group": grp,
        "answer": ans,
        "expect_gate": gate,
        "expect_direction": direction,
        "expect_exempt": exempt,
        "expect_unscorable": unscorable,
        "note": note,
        "review_status": "pending_medical_review",
    })

out = os.path.join(PHASE0, "D7-判定回归基线集.json")
json.dump(samples, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

# 统计
from collections import Counter
c_gate = Counter(s["expect_gate"] for s in samples)
c_dir = Counter(s["expect_direction"] for s in samples)
print(f"✅ 基线集 {len(samples)} 条 → {os.path.basename(out)}")
print(f"   闸门分布: {dict(c_gate)}")
print(f"   方向分布: {dict(c_dir)}")
print(f"   豁免样本: {sum(1 for s in samples if s['expect_exempt'])}")
print(f"   不可评分样本: {sum(1 for s in samples if s['expect_unscorable'])}")
