#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
反馈管道端到端演示 —— 复盘 → 观察 → 差异 → 候选 → 审核 → 发布。

跑一遍就把 V1.3 §2.1–2.5 的四个环节走完，并展示：
  · 禁入内容被阻断
  · 临床不良反应的引导路径
  · 两个事实概念分开
  · 状态机拒绝非法转移
  · 两条进化路径分流
  · 共享层与个人层隔离
"""
import os, sys, json

from config import BASE, PATHS
sys.path.insert(0, BASE)

import feedback_pipeline as F
from knowledge_retrieval import KnowledgeBase
from llm_provider import FactGuard

kb = KnowledgeBase()
guard = FactGuard(kb.fact_bundle("达伯舒的靶点是什么？", condition_id="D-NSCLC"))
store = F.FeedbackStore()
# 演示前清场，保证每次跑结果一致
store.data = {"debriefs": {}, "observations": {}, "coverage": {},
               "gap_candidates": {}, "review_cases": {}, "scenarios": {},
               "personalized_plans": {}, "shared_library": {}}
store.save()

BAR = "═" * 66


def show(title):
    print(f"\n{BAR}\n{title}\n{BAR}")


# ============================================================
show("环节 ① 复盘采集 DebriefRaw")
# ============================================================
segments = [
    {"kind": "reported_question", "source": "verbatim",
     "text": "他问我达伯舒跟 NSCLC 是什么关系，是不是获批适应症",
     "evidence_topic": "teaching_link_vs_indication"},
    {"kind": "self_answer", "source": "verbatim",
     "text": "我说达伯舒是 PD-1 方向的产品，跟 NSCLC 只是教学主题关联，不是获批适应症"},
    {"kind": "inference", "source": "inference",
     "text": "他好像不太认可我的说法，可能觉得我在绕"},
    {"kind": "unresolved", "source": "summary",
     "text": "价格那块没谈拢，他没接话"},
]

debrief = F.DebriefRaw(
    user_id="张伟",
    segments=segments,
    scope="self_only",
    raw_transcript="达伯舒跟 NSCLC 什么关系？是不是获批适应症……",
    user_revised="达伯舒跟 NSCLC 什么关系？是不是获批适应症……",
)
debrief.validate()
print(f"✅ 复盘已采集：{debrief.debrief_id}（v{debrief.version}）")
print(f"   段落数 {len(debrief.segments)}，每段都标了来源：")
for s in debrief.segments:
    print(f"     · [{F.SOURCE_CN[s['source']]:4s}] {F.OBSERVATION_CN[s['kind']]}：{s['text'][:34]}")
print(f"   权限范围：{debrief.scope}")

# --- 禁入内容被阻断 ---
print()
bad = F.DebriefRaw(user_id="张伟", scope="self_only",
                   raw_transcript="x", user_revised="x",
                   segments=[{"kind": "self_answer", "source": "verbatim",
                              "text": "病案号 123456 的张先生，52岁，我跟他说这个肯定有效"}])
try:
    bad.validate()
    print("❌ 患者可识别信息未被阻断")
except F.DebriefValidationError as e:
    print(f"✅ 阻断「患者可识别信息」：[{e.code}] {e.message[:52]}")

bad2 = F.DebriefRaw(user_id="张伟", scope="self_only",
                    raw_transcript="x", user_revised="x",
                    segments=[{"kind": "self_answer", "source": "verbatim",
                               "text": "我录了一段他说的原话"}])
try:
    bad2.validate()
    print("❌ 未经授权录音未被阻断")
except F.DebriefValidationError as e:
    print(f"✅ 阻断「未经授权录音」：[{e.code}] {e.message[:48]}")

bad3 = F.DebriefRaw(user_id="张伟", scope="self_only",
                    raw_transcript="x", user_revised="x",
                    segments=[{"kind": "self_answer", "source": "verbatim",
                               "text": "他说用了以后出现严重不良反应"}])
bad3.validate()
print(f"✅ 临床不良反应 → 不阻断，但打引导标记：{bad3.ae_detected}")
print(f"   引导：{bad3.to_dict()['ae_guidance']}")

# ============================================================
show("环节 ② 结构化观察 Observation")
# ============================================================
obs = F.structure_from_debrief(debrief, kb=kb)
print(f"生成 {len(obs)} 条观察：")
for o in obs:
    j = F.judge_medical_support(o, kb=kb, guard=guard)
    o.statement_is_medically_supported = j["statement_is_medically_supported"]
    o.support_refs = j["support_refs"]
    tag = "医学有依据" if j["statement_is_medically_supported"] else "医学无依据"
    occ = "事件有佐证" if o.event_occurrence_verified else "事件无佐证"
    print(f"  · {o.kind:20s} | {tag} | {occ}")
    print(f"      {o.text[:52]}")
    if j["support_refs"]:
        print(f"      依据：{j['support_refs'][0]['source'][:62]}")
print()
print("★ 两个事实概念分开记录：")
inf = [o for o in obs if o.kind == "inference"][0]
print(f"  inference「{inf.text[:22]}」")
print(f"    statement_is_medically_supported = {inf.statement_is_medically_supported}"
      f"（主观推测，不是医学论断）")
print(f"    event_occurrence_verified     = {inf.event_occurrence_verified}"
      f"（无佐证）")
print("  → 没有因为是 inference 就写成「医生不认可」这种确定性字段")

# ============================================================
show("环节 ③ 差异分析 CoverageMap")
# ============================================================
# 计划里的能力点（真实 skill_id）
plan_skills = ["SK-K-DABOSHU-PROD-01", "SK-C-OBJ-01", "SK-K-D-NSCLC-003"]
# 能力点匹配器：复盘是自由文本，靠它对上能力树
matcher = F.SkillMatcher()
print(f"能力树已加载：{len(matcher.skills)} 个能力点")
print()

cov = F.CoverageMap(
    obs, plan_skill_ids=plan_skills,
    topic_index={"teaching_link_vs_indication": "教学关联 vs 适应症"},
    intent_index={"用药资格": "适用人群"},
).build(mastery_by_skill={"SK-K-DABOSHU-PROD-01": True},
        skill_matcher=matcher)

print(f"覆盖图共 {len(cov['coverage_map'])} 条，分类统计：")
for k, v in cov["counts"].items():
    print(f"  {F.GAP_CN[k]:16s} {v}")
print()
print("明细（每条都带 match_evidence 与 observation_quality）：")
for e in cov["coverage_map"]:
    print(f"  [{e['gap_class_cn']:12s}] {e['text'][:40]}")
    print(f"       匹配依据：{e['match_evidence'][:56]}｜样本质量：{e['observation_quality']}")
print()
print(f"对外表述：{cov['external_wording']}")
print(f"边界：{cov['fact_boundary']}")

# ============================================================
show("环节 ③→ 差异候选与两条路径分流")
# ============================================================
cands = []
for e in cov["coverage_map"]:
    if e["gap_class"] in ("covered_not_mastered", "not_covered"):
        c = F.GapCandidate(
            user_id="张伟", gap_class=e["gap_class"],
            title=f"补强：{e['text'][:34]}",
            detail="该能力点在本次复盘中未掌握，建议针对性复训",
            skill_id=e.get("skill_id"),
            source_debrief_id=debrief.debrief_id)
        cands.append(c)

# 两条路径并行产生候选（不是二选一）
routed = F.route_candidates(
    cands, plan_skill_ids=plan_skills, total_users=1,
    # 未覆盖该能力点的员工数（此处只有张伟一人，故 ≥1 即全员未覆盖）
    skill_uncovered_count={"SK-K-D-NSCLC-003": 1})
print(f"{len(cands)} 个差异 → 产生 {len(routed)} 个候选（两条路径并行）：")
for c in routed:
    if c.path == "personalized":
        path_cn = "个性化复训（自动，仅本人）"
    else:
        path_cn = "共享题库（须审核）"
    ident = f"标识={c.user_id}" if c.user_id else "★已去标识化"
    print(f"  · {F.GAP_CN[c.gap_class]:12s} → {path_cn:20s}｜{ident}｜状态 {c.status}")

print()
print("★ 共享层候选已去标识化（不含 user_id 与原文来源 id）—— 数据隔离")
shared = [c for c in routed if c.path == "shared_library"]
print(f"  共享候选 {len(shared)} 个，user_id 均为 {set(c.user_id for c in shared)}")
print(f"  共享候选 source_debrief_id 均为 {set(c.source_debrief_id for c in shared)}")

# ============================================================
show("环节 ④ ReviewCase 状态机")
# ============================================================
rc = F.ReviewCase(source_type="gap_candidate", source_id=cands[0].candidate_id,
                  payload=cands[0].to_dict())
print(f"初始状态：{rc.status}")

# 非法转移：captured → published（跳步）
try:
    rc.transition("published", actor="张伟")
    print("❌ 非法转移未被拦截")
except F.DebriefValidationError as e:
    print(f"✅ 拦截非法转移：[{e.code}] {e.message[:56]}")

# LLM 试图直接批准
try:
    rc.transition("transcribed", actor="system")
    rc.transition("user_confirmed", actor="张伟")
    rc.transition("gap_analyzed", actor="system")
    rc.transition("review_pending", actor="system")
    rc.transition("approved", actor="llm")
    print("❌ LLM 竟被允许批准")
except F.DebriefValidationError as e:
    print(f"✅ 拦截 LLM 越权批准：[{e.code}] {e.message[:44]}")

# 正常人工审核流程
rc.transition("approved", actor="李娜(医学审核)", reason="内容与语料一致")
print(f"✅ 人工批准 → {rc.status}")
rc.transition("scenario_proposed", actor="李娜(医学审核)")
print(f"   → {rc.status}")

# ★ 审核通过 ≠ 自动发布：还要经回归测试
sv = F.ScenarioVersion(version_id="SV-001",
                        content={"scenario": "达伯舒与 NSCLC 关系问询", "skill_id": "MED-03"},
                        case_id=rc.case_id, author="李娜(医学审核)")
sv.status = "tested"
rc.scenario_version = sv.to_dict()
rc.transition("tested", actor="system", reason="回归测试通过")
print(f"   → {rc.status}（回归测试通过）")
rc.transition("published", actor="李娜(医学审核)", reason="发布到共享题库")
sv.status = "published"
print(f"   → {rc.status} ✅")

# ── 共享候选走审核发布：影响全体 ──
shared_cand = shared[0] if shared else None
if shared_cand:
    rc_shared = F.ReviewCase(source_type="gap_candidate",
                              source_id=shared_cand.candidate_id,
                              payload=shared_cand.to_dict())
    for st, actor in [("transcribed", "系统"), ("user_confirmed", "李娜(医学审核)"),
                      ("gap_analyzed", "系统"), ("review_pending", "系统"),
                      ("approved", "李娜(医学审核)"), ("scenario_proposed", "李娜(医学审核)"),
                      ("tested", "系统")]:
        rc_shared.transition(st, actor=actor)
    sv_shared = F.ScenarioVersion(version_id="SV-SHARED-001",
                                   content={"scenario": "教学关联 vs 获批适应症（共享）",
                                             "skill_id": shared_cand.skill_id},
                                   case_id=rc_shared.case_id, author="李娜(医学审核)")
    sv_shared.status = "published"
    rc_shared.transition("published", actor="李娜(医学审核)")
    store.put_review_case(rc_shared)
    store.put_scenario(sv_shared)
    print(f"✅ 共享候选经审核发布：{sv_shared.to_dict()['version_id']}（影响全体）")

# ── 回滚演示：另起一个案例，发布后再回滚 ──
print()
rc2 = F.ReviewCase(source_type="gap_candidate", source_id="GC-demo-2",
                   payload={"scenario": "价格异议处理"})
for st, actor in [("transcribed", "系统"), ("user_confirmed", "张伟"),
                  ("gap_analyzed", "系统"), ("review_pending", "系统"),
                  ("approved", "李娜(医学审核)"), ("scenario_proposed", "李娜(医学审核)"),
                  ("tested", "系统")]:
    rc2.transition(st, actor=actor)
sv2 = F.ScenarioVersion(version_id="SV-002", content={"scenario": "价格异议处理"},
                        case_id=rc2.case_id, author="李娜(医学审核)")
sv2.status = "published"
rc2.transition("published", actor="李娜(医学审核)")
rc2.transition("retired", actor="李娜(医学审核)", reason="发现表述问题，回滚")
sv2.status = "retired"
print(f"✅ 可回滚：SV-002 → {rc2.status}（原版本仍保留可回放）")
print(f"   SV-001 保持 {sv.status}（published）")

# ============================================================
show("隔离与持久化")
# ============================================================
store.put_debrief(debrief)
store.put_observations(debrief.debrief_id, obs)
store.put_coverage(debrief.debrief_id, cov)
for c in cands:
    store.put_candidate(c)
store.put_review_case(rc)
store.put_scenario(sv)
store.put_review_case(rc2)
store.put_scenario(sv2)
for c in routed:
    store.put_candidate(c)
store.save()

mine = store.personalized_for("张伟")
print(f"张伟可见：复盘 {len(mine['debriefs'])} 条、个性化候选 {len(mine['candidates'])} 个")
other = store.personalized_for("王芳")
print(f"王芳可见：复盘 {len(other['debriefs'])} 条、个性化候选 {len(other['candidates'])} 个")
print("★ 共享层与个人训练层隔离 —— 药代看不到他人错误明细")
print(f"共享题库已发布版本：{len(store.shared_library())} 个（retired 的不计）")
for s_ in store.shared_library():
    print(f"   · {s_['version_id']} v{s_['version_no']} 作者 {s_['author']} 状态 {s_['status']}")
print("★ 共享版本不含任何员工标识 —— 影响全体但无法反查是谁提的")

print(f"\n{'=' * 66}\n四环节全部跑通\n{'=' * 66}")
