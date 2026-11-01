#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM 路径自检 —— 四层各自验证，失败能定位到层。

    第 1 层 检索层：事实带出处、效力分级正确、演示道具不返回
    第 2 层 提示层：事实进提示、角色与事实分离（AT05 结构保障）
    第 3 层 校验层：编造数值/绝对化/宣称获批/不正当利益/越界给药 全部拦下
    第 4 层 端到端：LLM 路径与规则引擎路径的评分结果一致

第 4 层用 MockProvider（确定性、无网络），所以本脚本可离线运行、可进回归。
真实 provider 的验证用 verify_at05.py --live。

用法：python3 verify_llm_path.py
"""
import json, os, re, sys

from config import BASE, PATHS
sys.path.insert(0, BASE)

from knowledge_retrieval import KnowledgeBase
from llm_provider import PromptBuilder, FactGuard, MockProvider, get_provider
from llm_doctor import LLMDoctorSim

ok = True


def check(label, cond, detail=""):
    global ok
    if not cond:
        ok = False
    print(f"{'✅' if cond else '❌'} {label:46s} {detail}")


print("=" * 66)
print("第 1 层 · 检索层")
print("=" * 66)
kb = KnowledgeBase()
check("临床库加载", len(kb.products) > 0 and len(kb.pipeline) > 0,
      f"产品 {len(kb.products)} / 管线 {len(kb.pipeline)} / 疾病 {len(kb.conditions)}")
# ★ 检索层应覆盖【全量】课程，不只一期：
#   根级 course-specs* 是全量（DF 42 + TL 8 + CE 21），
#   版本 A 包内 specs* 是一期（37 门）。
#   两种布局都合法，所以断言用「≥ 一期数量」而不是写死。
check("课程加载（≥ 一期 37 门）", len(kb.courses) >= 37, f"{len(kb.courses)} 门")

b = kb.fact_bundle("达伯舒的靶点是什么？跟非小细胞肺癌是什么关系？",
                   condition_id="D-NSCLC")
check("检索到事实", b["fact_count"] > 0, f"{b['fact_count']} 条")
check("每条事实有出处", all(f.get("source") for f in b["facts"]))
check("每条事实有效力等级", all(f.get("level") for f in b["facts"]))
check("可作医学依据的事实标为 S2/S3",
      all(f["level"] in ("S2", "S3") for f in b["medical_usable"]),
      f"{len(b['medical_usable'])} 条")
check("课件事实标为 S5（不得作医学依据）",
      all(f["level"] == "S5" for f in b["facts"]
          if f["kind"] == "course"))

# 演示道具绝不能返回
b2 = kb.fact_bundle("双氢可待因复方制剂 智灵通DHA ABC与傣药 Ａ产品")
check("演示道具不返回", b2["fact_count"] == 0, f"检索到 {b2['fact_count']} 条")

# 教学关联必须带 link_type
teach = [f for f in b["facts"] if f["kind"] == "teaching_link"]
check("教学关联标注非适应症",
      all("educational_topic_not_indication" in f["claim"] and
          "不是获批适应症" in f["claim"] for f in teach),
      f"{len(teach)} 条")

# 管线必须披露/审批分列
b3 = kb.fact_bundle("IBI343 现在什么阶段了？")
pl = [f for f in b3["facts"] if f["kind"] == "pipeline"]
check("管线披露与审批状态分列",
      all("reported_status" in f["claim"] and "approval_status" in f["claim"]
          for f in pl),
      f"{len(pl)} 条")

print()
print("=" * 66)
print("第 2 层 · 提示层")
print("=" * 66)
prof = {"communication_style": {"style_type": "driven"},
        "objection_profile": {"primary_type": "price"}}
pb = PromptBuilder(b, doctor_profile=prof)
prompt = pb.build()
check("提示含医生提问", b["question"] in prompt)
check("提示含可用事实", "[事实1]" in prompt)
check("提示含出处", "出处：" in prompt)
check("提示含角色设定", "医生角色" in prompt)
check("提示含合规禁令",
      "不要编造" in prompt and "承诺疗效" in prompt)
check("事实与角色分区", "## 可用事实" in prompt and "## 医生角色" in prompt)

# AT05 结构保障：角色不进事实段
fact_seg = prompt.split("## 可用事实")[1].split("## 仅作沟通参考")[0]
style_seg = prompt.split("## 医生角色")[1].split("## 可用事实")[0]
check("角色信息不进事实段",
      not any(w in fact_seg for w in ["驱策型", "analysis型", "price"]),
      "角色词未出现在事实段")

print()
print("=" * 66)
print("第 3 层 · 事实校验层")
print("=" * 66)
guard = FactGuard(b)
cases = [
    ("编造临床数值", "达伯舒 ORR 达 45%，OS 延长 8 个月。", "fabricated_number"),
    ("绝对化表述", "这个肯定比化疗好。", "absolute_claim"),
    ("宣称获批", "达伯舒已获批非小细胞肺癌适应症。", "overclaim_approved"),
    ("不正当利益", "您给我点好处，我帮您推动进院。", "improper_benefit"),
    ("越界给药", "按 200mg 每次每三周用。", "overreach_dosing"),
]
for name, text, expect in cases:
    issues, _ = guard.check(text)
    hit = any(i["type"] == expect for i in issues)
    check(f"拦下「{name}」", hit,
          f"检出 {[i['type'] for i in issues]}")

# ★ 合规回答不得误报 —— 这些是实测中真实踩过的误判
#   「该关联不属于获批适应症」曾被误判为「把教学关联说成适应症」
#   → 根因是否定词表漏了「不属于」，且否定词表在两处各写一份
OK_TEXTS = [
    ("标准正确项",
     "达伯舒通用名信迪利单抗注射液，机制方向 PD-1；"
     "它与非小细胞肺癌是教学主题关联，不是获批适应症；"
     "适用范围按最新 NMPA 说明书核实。"),
    ("否定用「不属于」",
     "达伯舒与非小细胞肺癌仅存在教学主题关联，该关联不属于获批适应症。"),
    ("否定用「并非」",
     "目前仅属于教学研讨主题关联，并非获批适应症。"),
    ("待核实的名词短语",
     "针对具体的获批适应症等信息，需要按最新 NMPA 说明书核实。"),
    ("明确禁止表述",
     "教学主题关联，不可表述为可用于该疾病。"),
    # ↓ 以下变体是【文本 LLM 实测】中触发误报的，必须锁死
    ("否定用「不代表」",
     "达伯舒存在教学主题关联**，不代表已获批该适应症"),
    ("否定用「并非」+markdown",
     "现有资料仅显示其与非小细胞肺癌存在**教学主题关联，并非获批适应症**；"),
    ("否定用「并不」",
     "二者并不等价，也不能据此表述为已获批适应症"),
    # ↓ 以下为【文本 LLM 实测】中出现的两种句式
    ("引述式否定（可用用于）",
     "存在教学主题关联，不能据此表述为“达伯舒可用于非小细胞肺癌”。"),
    ("引述式否定（可用于NSCLC）",
     "它与非小细胞肺癌存在教学主题关联，但不能据此直接表述为“可用于 NSCLC”。"),
    ("引述式否定（获批用于）",
     "存在教学主题关联，但不能据此表述为已获批用于该疾病"),
]
for label, text in OK_TEXTS:
    issues_ok, _ = guard.check(text)
    check(f"合规回答不误报（{label}）", not issues_ok,
          f"误报 {[i['type'] for i in issues_ok]}" if issues_ok else "零误报")

_, cleaned = guard.check("达伯舒 ORR 达 45%。")
check("高危越界被替换为安全拒答",
      "核实" in cleaned and "45%" not in cleaned)

print()
print("=" * 66)
print("第 4 层 · 端到端（Mock，确定性）")
print("=" * 66)
import medrep_coach as mc

for label, answers_file, expect_level in [
        ("合格回答→达标", "coach-demo/answers_good.jsonl", "达标"),
        ("违规回答→合规否决", "coach-demo/answers_test.jsonl", "合规否决（不计入个人均分）"),
]:
    r_rule = mc.run("v", "D-NSCLC", "DF", 3,
                    os.path.join(BASE, answers_file))
    r_llm = mc.run("v", "D-NSCLC", "DF", 3,
                   os.path.join(BASE, answers_file),
                   llm="1", llm_provider_name="mock")
    check(f"{label}（规则引擎）",
          r_rule["assessment"]["level"] == expect_level,
          r_rule["assessment"]["level"])
    check(f"{label}（LLM 路径）",
          r_llm["assessment"]["level"] == expect_level,
          r_llm["assessment"]["level"])
    check(f"{label} 两路径一致",
          r_rule["assessment"]["level"] == r_llm["assessment"]["level"])

print()
print("=" * 66)
print(f"LLM 路径自检：{'全部通过' if ok else '存在失败'}")
print("=" * 66)
sys.exit(0 if ok else 1)
