#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
反馈管道自检 —— V1.3 §2.1–2.5 的硬约束逐条验证。

每条检查对应规格里的一句约束。全部离线、可回归。

用法：python3 verify_feedback_pipeline.py
"""
import os, sys, json, shutil, tempfile

from config import BASE, PATHS
sys.path.insert(0, BASE)

import feedback_pipeline as F

ok = True


def check(label, cond, detail=""):
    global ok
    if not cond:
        ok = False
    print(f"{'✅' if cond else '❌'} {label:52s} {detail}")


def expect_raise(label, fn, code=None):
    global ok
    try:
        fn()
        ok = False
        print(f"❌ {label:52s} 未抛错")
    except F.DebriefValidationError as e:
        hit = (code is None or e.code == code)
        if not hit:
            ok = False
        print(f"{'✅' if hit else '❌'} {label:52s} [{e.code}]")
    except Exception as e:
        ok = False
        print(f"❌ {label:52s} {type(e).__name__}: {e}")


# ============================================================
print("=" * 68)
print("环节 ① 复盘采集")
print("=" * 68)

good = F.DebriefRaw(
    user_id="张伟", scope="self_only", raw_transcript="t", user_revised="t",
    segments=[{"kind": "self_answer", "source": "verbatim", "text": "我说这个要走核实"}])
check("合规复盘通过校验", good.validate())

# 来源标记必填
no_src = F.DebriefRaw(user_id="张伟", scope="self_only", raw_transcript="t", user_revised="t",
                       segments=[{"kind": "self_answer", "text": "没说来源"}])
expect_raise("缺来源标记被阻断", no_src.validate, "MISSING_SOURCE_MARK")

bad_src = F.DebriefRaw(user_id="张伟", scope="self_only", raw_transcript="t", user_revised="t",
                        segments=[{"kind": "self_answer", "source": "随便写的", "text": "x"}])
expect_raise("非法来源标记被阻断", bad_src.validate, "MISSING_SOURCE_MARK")

# 必填字段
miss = F.DebriefRaw(user_id="张伟", scope="self_only", raw_transcript="", user_revised="",
                     segments=[{"kind": "self_answer", "source": "verbatim", "text": "x"}])
expect_raise("必填字段缺失被阻断", miss.validate, "MISSING_FIELD")

# 禁入：患者 PII
pii = F.DebriefRaw(user_id="张伟", scope="self_only", raw_transcript="t", user_revised="t",
                    segments=[{"kind": "self_answer", "source": "verbatim",
                               "text": "病案号 123456 的张先生"}])
expect_raise("患者可识别信息被阻断", pii.validate, "PATIENT_PII")

# 禁入：未授权录音
rec = F.DebriefRaw(user_id="张伟", scope="self_only", raw_transcript="t", user_revised="t",
                   segments=[{"kind": "self_answer", "source": "verbatim", "text": "我录了一段"}])
expect_raise("未经授权录音被阻断", rec.validate, "UNAUTHORIZED_RECORDING")

# 临床不良反应 → 引导而非阻断
ae = F.DebriefRaw(user_id="张伟", scope="self_only", raw_transcript="t", user_revised="t",
                  segments=[{"kind": "self_answer", "source": "verbatim",
                             "text": "他说出现严重不良反应"}])
ae.validate()
check("临床不良反应不阻断但打引导标记",
      ae.ae_detected is not None and "法定/企业报告" in ae.to_dict()["ae_guidance"],
      ae.ae_detected)

# 可撤回性：修订 → 版本+1 → 回到待解析
v0 = good.version
good.revise(segments=[{"kind": "self_answer", "source": "summary", "text": "改过的"}],
            actor="张伟")
check("修订后版本号递增", good.version == v0 + 1, f"v{v0}→v{good.version}")
check("修订后回到待解析状态", good.status == "captured", good.status)
check("修订留审计", len(good.audit) >= 2, f"{len(good.audit)} 条")

# ============================================================
print()
print("=" * 68)
print("环节 ② 结构化观察")
print("=" * 68)

d = F.DebriefRaw(user_id="张伟", scope="self_only", raw_transcript="t", user_revised="t",
                 segments=[
                     {"kind": "reported_question", "source": "verbatim", "text": "他问获批没"},
                     {"kind": "self_answer", "source": "verbatim", "text": "我说要走核实"},
                     {"kind": "inference", "source": "inference", "text": "他好像不认可"},
                     {"kind": "unresolved", "source": "summary", "text": "价格没谈拢"}])
obs = F.structure_from_debrief(d)
check("生成 4 条观察", len(obs) == 4)
check("四种 kind 齐备",
      {o.kind for o in obs} == set(F.OBSERVATION_KINDS))

# 两个事实概念分开
from knowledge_retrieval import KnowledgeBase
from llm_provider import FactGuard
kb = KnowledgeBase()
guard = FactGuard(kb.fact_bundle("达伯舒的靶点", condition_id="D-NSCLC"))
inf = [o for o in obs if o.kind == "inference"][0]
j = F.judge_medical_support(inf, kb=kb, guard=guard)
check("inference 不判定为有医学依据",
      j["statement_is_medically_supported"] is False)
check("inference 的事件发生标记为未验证",
      j["event_occurrence_verified"] is False)
check("两个概念各自独立返回",
      "statement_is_medically_supported" in j and "event_occurrence_verified" in j)

# 只有 self_answer 才可能判为有依据
for kind in ("reported_question", "inference", "unresolved"):
    o = [x for x in obs if x.kind == kind][0]
    jj = F.judge_medical_support(o, kb=kb, guard=guard)
    check(f"{kind} 不产生「医学有依据」",
          jj["statement_is_medically_supported"] is False)

# 越界陈述 → 无依据
bad_o = F.Observation(kind="self_answer", text="达伯舒已获批非小细胞肺癌适应症",
                      source="verbatim")
jb = F.judge_medical_support(bad_o, kb=kb, guard=guard)
check("触碰红线的陈述判为无依据",
      jb["statement_is_medically_supported"] is False, jb["why"][:40])

# ============================================================
print()
print("=" * 68)
print("环节 ③ 差异分析")
print("=" * 68)

sm = F.SkillMatcher()   # 能力点匹配器（后面章节也用）
cov = F.CoverageMap(obs, plan_skill_ids=["MED-03", "COM-05", "MED-01"],
                    topic_index={"t1": "主题"}, intent_index={"i1": "意图"}
                    ).build(mastery_by_skill={"MED-03": True})
check("覆盖图条目非空", len(cov["coverage_map"]) > 0, f"{len(cov['coverage_map'])} 条")
check("五分类齐全", set(cov["counts"]) == set(F.GAP_CLASSES))
check("每条都带 match_evidence",
      all("match_evidence" in e and e["match_evidence"] for e in cov["coverage_map"]))
check("每条都带 observation_quality",
      all("observation_quality" in e for e in cov["coverage_map"]))
# ★ 关键语义：计划内但复盘未观察到 → unknown，不是 not_covered
#   （一次复盘没谈到 ≠ 没覆盖。否则会产生大量假的复训候选。）
check("计划内未被复盘观察到的能力点判为 unknown（非 not_covered）",
      cov["counts"]["not_covered"] == 0 and cov["counts"]["unknown"] >= 1,
      f"not_covered={cov['counts']['not_covered']} unknown={cov['counts']['unknown']}")

# 计划外但复盘观察到的能力点 → not_covered（新增考点候选）
# ★ 断言方式：任何「匹配到能力点但不在计划内」的观察，都必须判 not_covered。
#   不依赖具体能力点 ID，避免测试数据与词表耦合。
cov_out = F.CoverageMap(
    obs, plan_skill_ids=["SK-NOT-IN-PLAN"]
).build(skill_matcher=sm)
outside = [e for e in cov_out["coverage_map"]
           if e.get("skill_id") and e["skill_id"] != "SK-NOT-IN-PLAN"
           and e["match_level"] == "skill_id_outside_plan"]
check("计划外但复盘观察到的能力点判为 not_covered（新增考点候选）",
      len(outside) > 0 and all(e["gap_class"] == "not_covered" for e in outside),
      f"{[(e.get('skill_id'), e['gap_class']) for e in outside][:2]}")

# 反向断言：计划内的能力点即使复盘没提到，也不能判 not_covered
plan_only = F.CoverageMap(
    obs, plan_skill_ids=["SK-K-DABOSHU-PROD-01"]
).build(skill_matcher=sm)
not_covered_ids = [e.get("skill_id") for e in plan_only["coverage_map"]
                   if e["gap_class"] == "not_covered"]
check("计划内能力点不会因「复盘未提及」被判 not_covered",
      "SK-K-DABOSHU-PROD-01" not in not_covered_ids,
      f"误判 {not_covered_ids}")
check("对外表述用「复盘报告的题目覆盖情况」",
      "复盘报告的题目覆盖情况" in cov["external_wording"])
check("带事实边界声明", "不是对真实医生言行的预测" in cov["fact_boundary"])

# ============================================================
print()
print("=" * 68)
print("能力点匹配（对接 skill-taxonomy）")
print("=" * 68)

check("能力树已加载", len(sm.skills) == 222, f"{len(sm.skills)} 个")

CASES = [
    ("达伯舒跟非小细胞肺癌是什么关系", "SK-K-DABOSHU-PROD-01"),
    ("价格上他不接受，说太贵", "SK-C-OBJ-01"),
    ("他拖延着不给我答复", "SK-C-STAGE-RESIST-01"),
    ("他转换话题岔开了", "SK-C-STAGE-RESIST-04"),
]
for text, expect in CASES:
    ids = sm.match_ids(text)
    check(f"「{text[:16]}」→ {expect}", expect in ids, str(ids[:2]))

# 库外药品不应匹配任何能力点
outside = sm.match_ids("奥利司他片能治非小细胞肺癌吗")
check("库外药品不匹配能力点", len(outside) == 0, str(outside[:2]))

# 能力点匹配的复盘 → 覆盖图
cov2 = F.CoverageMap(obs, plan_skill_ids=["SK-K-DABOSHU-PROD-01", "SK-C-OBJ-01"]
                      ).build(skill_matcher=sm)
check("自动匹配能力点后不再是 unknown",
      cov2["counts"]["unknown"] >= 1)   # inference 不应被匹配
matched = [e for e in cov2["coverage_map"] if e.get("match_level") == "skill_id"]
check("有观察命中到能力点", len(matched) > 0, f"{len(matched)} 条")
inf_e = [e for e in cov2["coverage_map"] if e["kind"] == "inference"]
check("inference 不挂能力点（不制造虚假定位）",
      all(e.get("match_level") != "skill_id" for e in inf_e))

# ============================================================
print()
print("=" * 68)
print("环节 ④ 状态机与审核发布")
print("=" * 68)

rc = F.ReviewCase(source_type="gap_candidate", source_id="X", payload={})
expect_raise("跳步转移被拦截",
             lambda: rc.transition("published", actor="李娜"), "ILLEGAL_TRANSITION")
expect_raise("LLM 不得执行状态转移",
             lambda: rc.transition("transcribed", actor="llm"), "ACTOR_NOT_AUTHORIZED")
expect_raise("无署名 actor 被拦截",
             lambda: rc.transition("transcribed", actor=None), "ACTOR_NOT_AUTHORIZED")

rc.transition("transcribed", actor="系统")
check("合法转移成功", rc.status == "transcribed")
check("非法转移也留审计",
      any(a.get("action") == "transition_rejected" for a in rc.audit))

# 终态无出边
rc2 = F.ReviewCase()
rc2.status = "rejected"
expect_raise("终态无出边", lambda: rc2.transition("transcribed", actor="李娜"),
             "ILLEGAL_TRANSITION")

# 审核与发布分离
rc3 = F.ReviewCase()
for st, actor in [("transcribed", "系统"), ("user_confirmed", "张伟"),
                  ("gap_analyzed", "系统"), ("review_pending", "系统"),
                  ("approved", "李娜")]:
    rc3.transition(st, actor=actor)
check("审核通过后不是自动发布", rc3.status == "approved")
# ★ 正确语义：approved 不能直接到 published；必须经 tested
check("approved 不能直接跳到 published（审核与发布分离）",
      "published" not in F.REVIEW_TRANSITIONS["approved"],
      f"approved 出边={F.REVIEW_TRANSITIONS['approved']}")
check("published 只能由 tested 进入（须经回归测试）",
      F.REVIEW_TRANSITIONS.get("published") is not None and
      "published" in F.REVIEW_TRANSITIONS["tested"] and
      "published" not in F.REVIEW_TRANSITIONS["approved"])
check("完整发布链路存在",
      "scenario_proposed" in F.REVIEW_TRANSITIONS["approved"] and
      "tested" in F.REVIEW_TRANSITIONS["scenario_proposed"] and
      "published" in F.REVIEW_TRANSITIONS["tested"])

# 可回滚
rc3.transition("scenario_proposed", actor="李娜")
rc3.transition("tested", actor="系统")
rc3.transition("published", actor="李娜")
check("发布成功", rc3.status == "published")
rc3.transition("retired", actor="李娜")
check("可回滚（retired 为终态但记录保留）", rc3.status == "retired")

# 审计链完整
audit_ok = all(k in rc3.audit[-1] for k in ("at", "actor", "action", "from", "to"))
check("审计链含时间/执行者/动作/前后状态", audit_ok)

# ============================================================
print()
print("=" * 68)
print("两条进化路径与数据隔离")
print("=" * 68)

cands = [F.GapCandidate(user_id="张伟", gap_class="not_covered", title="t1", detail="d1",
                         skill_id="MED-01"),
         F.GapCandidate(user_id="张伟", gap_class="covered_not_mastered", title="t2", detail="d2",
                         skill_id="COM-05")]
routed = F.route_candidates(cands, plan_skill_ids=["MED-01"], total_users=1,
                            skill_uncovered_count={"MED-01": 1})
pers = [c for c in routed if c.path == "personalized"]
shared = [c for c in routed if c.path == "shared_library"]
check("个性化候选自动分配（无需签审）",
      all(c.status == "auto_assigned" for c in pers), f"{len(pers)} 个")
check("共享候选须审核",
      all(c.status == "pending_review" for c in shared), f"{len(shared)} 个")
check("共享候选已去标识化（无 user_id）",
      all(c.user_id is None for c in shared))
check("共享候选不含原文来源 id",
      all(c.source_debrief_id is None for c in shared))
check("两条路径并行产生，不合并",
      len(routed) > len(cands), f"{len(cands)} 差异 → {len(routed)} 候选")

# 存储隔离
tmpd = tempfile.mkdtemp()
try:
    st = F.FeedbackStore(os.path.join(tmpd, "f.json"))
    dd = F.DebriefRaw(user_id="张伟", scope="self_only", raw_transcript="t", user_revised="t",
                      segments=[{"kind": "self_answer", "source": "verbatim", "text": "x"}])
    st.put_debrief(dd)
    for c in routed:
        st.put_candidate(c)
    st.save()
    check("本人可见自己的数据", len(st.personalized_for("张伟")["debriefs"]) == 1)
    check("他人不可见",
          len(st.personalized_for("王芳")["debriefs"]) == 0)
    check("个人层不含共享层候选",
          all(c["path"] == "personalized"
              for c in st.personalized_for("张伟")["candidates"]))
finally:
    shutil.rmtree(tmpd, ignore_errors=True)

print()
print("=" * 68)
print(f"反馈管道自检：{'全部通过' if ok else '存在失败'}")
print("=" * 68)
sys.exit(0 if ok else 1)
