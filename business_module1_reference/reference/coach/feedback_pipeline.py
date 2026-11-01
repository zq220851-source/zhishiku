#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
反馈管道 —— V1.3 §2.1–2.5，版本 B 的核心。

四个环节：
    ① 复盘采集   DebriefRaw
    ② 结构化观察 Observation
    ③ 差异分析   CoverageMap + GapCandidate
    ④ 审核发布   ReviewCase → ScenarioVersion

★ 三条不可违反的约定
--------------------
1. **状态转移写在程序里，不能靠 LLM 自由写状态。**
   LLM 可以辅助「把自由文本结构化成 Observation」，
   但 `captured → transcribed → … → published` 每一步都由 `transition()` 校验。
   LLM 只能*请求*转移，不能*决定*转移。

2. **两个事实概念必须分开**：
   `statement_is_medically_supported` —— 医学论断是否有依据
   `event_occurrence_verified`     —— 事件发生是否有佐证
   「医生好像不认可」属于 inference，**不得自动写成确定性字段**。

3. **两条进化路径不可合并**：
   个性化复训（自动，仅该员工） vs 共享题库更新（必须审核，影响全体）
   共享层与个人训练层**数据隔离**。

★ 一条事实边界（贯穿全部环节）
------------------------------
复盘是代表的报告。我们能核验的是**专业知识依据**，
**不能仅凭单人复盘证明一次现场交流的完整真相**。
所以 observation_quality 永远随结论一起记录。
"""
import json, os, re, uuid, hashlib
from datetime import datetime, timezone

# ★ 路径统一来自配置中心
from config import BASE, PATHS

STATE_DIR = os.path.join(PATHS.STATE_DIR, "feedback")
DB_FILE = PATHS.FEEDBACK_STATE


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _uid(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _hash(obj):
    return "sha256:" + hashlib.sha256(
        json.dumps(obj, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]


# ============================================================
# 禁入内容检测
# ============================================================
# 患者可识别信息 —— 直接姓名/病历号/住院号/床号等
PATIENT_PII = re.compile(
    r"(病案号|病历号|住院号|门诊号|床号\s*[:：]?\s*\d+|"
    r"身份证\s*\d{6,}|手机号\s*[:：]?\s*1\d{10}|"
    r"患者姓名\s*[:：]|张?[\u4e00-\u9fa5]{2,3}先生\s*\d{1,3}岁)")

# 未经授权的现场录音
UNAUTHORIZED_RECORDING = re.compile(
    r"(录音|录了音|录了一段|拍了视频|拍了照片|录像)")

# 临床不良反应 —— 需引导走法定/企业报告路径
AE_PATTERN = re.compile(
    r"(不良反应|不良事件|副作用|严重不良|过敏|皮疹|肝功能(异常|受损)|"
    r"肾功能(异常|受损)|呼吸困难|住院|死亡|SAE|严重不良事件)")


class DebriefValidationError(ValueError):
    """复盘内容不合规 —— 必须阻断，不是警告"""

    def __init__(self, code, message, detail=None):
        super().__init__(message)
        self.code = code
        self.message = message      # 常规访问方式
        self.detail = detail


# ============================================================
# 环节 ① 复盘采集 DebriefRaw
# ============================================================
# 三个主引导问题
GUIDE_QUESTIONS = [
    ("q1", "对方问了什么", "reported_question"),
    ("q2", "我怎么回答", "self_answer"),
    ("q3", "我哪里不确定", "unresolved"),
]

# 来源标记：三者不可混用
SOURCE_KINDS = ("verbatim", "summary", "inference")
SOURCE_CN = {"verbatim": "原话", "summary": "概括", "inference": "推断"}


class DebriefRaw:
    """
    复盘采集的原始记录。

    ★ 每个段落必须标明来源（原话/概括/推断）——
      三者不可混用。混用会让下游把「推断」当成「原话」，
      进而把主观推测写成专家的确定性字段。
    """

    REQUIRED_FIELDS = ["occurred_at", "submitted_at", "scope",
                       "raw_transcript", "user_revised"]

    def __init__(self, user_id, segments, occurred_at=None, scope="self_only",
                 raw_transcript="", user_revised=None, pre_run_id=None,
                 debrief_id=None, version=1, revision_of=None):
        self.debrief_id = debrief_id or _uid("DR")
        self.user_id = user_id
        self.segments = segments
        self.occurred_at = occurred_at or _now()
        self.submitted_at = _now()
        self.scope = scope                  # 权限范围
        self.raw_transcript = raw_transcript
        self.user_revised = user_revised if user_revised is not None else raw_transcript
        self.pre_run_id = pre_run_id
        self.version = version
        self.revision_of = revision_of
        self.status = "captured"
        self.audit = [{"at": self.submitted_at, "actor": user_id,
                       "action": "capture", "version": version}]

    # ---------- 校验 ----------
    def validate(self):
        """校验不通过则抛 DebriefValidationError —— 阻断，不是警告"""
        # 1) 必填字段
        for f in self.REQUIRED_FIELDS:
            val = getattr(self, f, None)
            if val is None or (isinstance(val, str) and not val.strip()):
                raise DebriefValidationError(
                    "MISSING_FIELD", f"必填字段缺失：{f}", {"field": f})

        # 2) 每个段落必须标来源，且来源必须在三分类内
        for i, seg in enumerate(self.segments):
            src = seg.get("source")
            if src not in SOURCE_KINDS:
                raise DebriefValidationError(
                    "MISSING_SOURCE_MARK",
                    f"第 {i+1} 段未标明来源（必须是 原话/概括/推断 之一）",
                    {"index": i, "got": src})
            if not seg.get("text", "").strip():
                raise DebriefValidationError(
                    "EMPTY_SEGMENT", f"第 {i+1} 段内容为空", {"index": i})

        # 3) 禁入：患者可识别信息
        blob = " ".join([s.get("text", "") for s in self.segments] +
                        [self.raw_transcript, self.user_revised])
        m = PATIENT_PII.search(blob)
        if m:
            raise DebriefValidationError(
                "PATIENT_PII",
                f"检测到患者可识别信息（{m.group(0)}），不得录入。"
                "请去除可识别信息后重新提交。",
                {"matched": m.group(0)})

        # 4) 禁入：未经授权的现场录音
        m = UNAUTHORIZED_RECORDING.search(blob)
        if m and self.scope != "authorized_recording":
            raise DebriefValidationError(
                "UNAUTHORIZED_RECORDING",
                f"检测到现场录音/影像（{m.group(0)}）但未标注授权。"
                "未经授权的现场录音不得录入。",
                {"matched": m.group(0)})

        # 5) 特殊流程：临床不良反应 → 引导走法定/企业报告路径
        self.ae_detected = None
        m = AE_PATTERN.search(blob)
        if m:
            self.ae_detected = m.group(0)
            # 不阻断，但必须打上引导标记，且在下游不得作为训练素材

        return True

    # ---------- 修订（可撤回性）----------
    def revise(self, segments=None, user_revised=None, scope=None, actor=None):
        """
        提交后允许修订。修订会：
          · 版本号 +1
          · 状态回到 transcribed（触发重新解析）
          · 记录审计
        差异重算由调用方重新跑 CoverageMap 完成。
        """
        if segments is not None:
            self.segments = segments
        if user_revised is not None:
            self.user_revised = user_revised
        if scope is not None:
            self.scope = scope
        self.version += 1
        self.submitted_at = _now()
        self.status = "captured"          # 回到起点 → 重新解析
        self.audit.append({
            "at": self.submitted_at, "actor": actor or self.user_id,
            "action": "revise", "version": self.version,
            "revision_of": self.revision_of or self.debrief_id,
        })
        return self

    def to_dict(self):
        return {
            "debrief_id": self.debrief_id, "user_id": self.user_id,
            "status": self.status, "version": self.version,
            "occurred_at": self.occurred_at, "submitted_at": self.submitted_at,
            "scope": self.scope, "pre_run_id": self.pre_run_id,
            "revision_of": self.revision_of,
            "raw_transcript": self.raw_transcript,
            "user_revised": self.user_revised,
            "segments": self.segments,
            "ae_detected": getattr(self, "ae_detected", None),
            "ae_guidance": ("检测到临床不良反应信息。本系统不能替代法定/企业报告路径，"
                            "请按公司规定走不良反应报告流程。"
                            if getattr(self, "ae_detected", None) else None),
            "audit": self.audit,
            "fact_boundary": ("复盘是代表的报告；本系统只能核验专业知识依据，"
                              "不能仅凭单人复盘证明一次现场交流的完整真相。"),
        }


# ============================================================
# 环节 ② 结构化观察 Observation
# ============================================================
OBSERVATION_KINDS = ["reported_question", "self_answer", "inference", "unresolved"]
OBSERVATION_CN = {
    "reported_question": "对方提出的专业问题",
    "self_answer": "代表自述的回答",
    "inference": "主观推测",
    "unresolved": "未解决的问题",
}


class Observation:
    """
    结构化观察。

    ★ 两个事实概念分开：
        statement_is_medically_supported —— 医学论断是否有依据
        event_occurrence_verified     —— 事件发生是否有佐证
      「医生好像不认可」是 inference：
        医学论断无（本来就不是论断）；事件发生**未验证**（无佐证）。
      绝不能因为是 inference 就自动写成"确定性字段"。
    """

    def __init__(self, kind, text, source="summary", skill_id=None,
                 evidence_topic=None, intent=None,
                 statement_is_medically_supported=None,
                 event_occurrence_verified=False,
                 support_refs=None, observation_quality="single_self_report",
                 observation_id=None):
        if kind not in OBSERVATION_KINDS:
            raise ValueError(f"未知 observation kind：{kind}")
        self.observation_id = observation_id or _uid("OB")
        self.kind = kind
        self.text = text
        self.source = source
        self.skill_id = skill_id
        self.evidence_topic = evidence_topic
        self.intent = intent
        self.statement_is_medically_supported = statement_is_medically_supported
        self.event_occurrence_verified = bool(event_occurrence_verified)
        self.support_refs = support_refs or []
        self.observation_quality = observation_quality

    def to_dict(self):
        return {
            "observation_id": self.observation_id,
            "kind": self.kind, "kind_cn": OBSERVATION_CN[self.kind],
            "text": self.text, "source": self.source,
            "source_cn": SOURCE_CN.get(self.source, self.source),
            "skill_id": self.skill_id,
            "evidence_topic": self.evidence_topic,
            "intent": self.intent,
            "statement_is_medically_supported": self.statement_is_medically_supported,
            "event_occurrence_verified": self.event_occurrence_verified,
            "support_refs": self.support_refs,
            "observation_quality": self.observation_quality,
        }


def structure_from_debrief(debrief: DebriefRaw, kb=None, skill_map=None):
    """
    把 DebriefRaw 结构化成 Observation 列表。

    ★ 本函数只做「结构化」，不做医学判定 ——
      医学支撑判定由 judge_medical_support() 用检索层 + 规则层做。
      主观推测（inference）不做医学判定，直接标为不支撑。

    kind 的映射规则来自三个主引导问题。
    """
    obs = []
    for seg in debrief.segments:
        kind = seg.get("kind")
        text = seg.get("text", "")
        src = seg.get("source", "summary")
        if kind not in OBSERVATION_KINDS:
            kind = _infer_kind(text)
        o = Observation(
            kind=kind, text=text, source=src,
            skill_id=seg.get("skill_id"),
            evidence_topic=seg.get("evidence_topic"),
            intent=seg.get("intent"),
            statement_is_medically_supported=None,   # 待判定
            event_occurrence_verified=(src == "verbatim"),
            observation_quality="single_self_report",
        )
        obs.append(o)
    return obs


_KIND_HINTS = [
    ("reported_question", re.compile(r"(他问|她问|医生问|问的是|提问)")),
    ("self_answer", re.compile(r"(我(说|答|回|讲|告诉)|我说的是)")),
    ("unresolved", re.compile(r"(没(谈拢|说清|确定)|不确定|拿不准|悬着|没回)")),
]


def _infer_kind(text):
    for kind, pat in _KIND_HINTS:
        if pat.search(text):
            return kind
    return "unresolved"


# ============================================================
# 环节 ③ 差异分析 CoverageMap + GapCandidate
# ============================================================
GAP_CLASSES = ["covered_mastered", "covered_not_mastered", "not_covered",
               "partial", "unknown"]
GAP_CN = {
    "covered_mastered": "已覆盖且掌握",
    "covered_not_mastered": "已覆盖但没掌握",
    "not_covered": "未覆盖",
    "partial": "部分覆盖",
    "unknown": "记录不清，无法判定",
}


class CoverageMap:
    """
    覆盖图 —— 三级比对，不能只按文字相似度。

    三级：① 能力点 skill_id ② 医学证据主题 evidence_topic ③ 提问意图 intent
    """

    def __init__(self, observations, plan_skill_ids=None, topic_index=None,
                 intent_index=None):
        self.observations = observations
        self.plan_skill_ids = plan_skill_ids or []
        self.topic_index = topic_index or {}
        self.intent_index = intent_index or {}

    def _match_level(self, obs):
        """
        返回 (匹配层级, 依据)
        层级：skill_id > evidence_topic > intent > none

        ★ 区分两种「不在计划里」：
          · 匹配到能力点但计划未覆盖 → skill_id 层级，分类为 not_covered
            （记录清楚，只是本次训练没练到 → 该纳入下期计划）
          · 三级都没命中 → none，分类为 unknown
            （记录不清，无法判定）
        """
        if obs.skill_id:
            if obs.skill_id in self.plan_skill_ids:
                return "skill_id", f"能力点 {obs.skill_id} 命中计划"
            # 匹配到能力点但不在本次计划 → 该能力点属于未覆盖
            return "skill_id_outside_plan", f"能力点 {obs.skill_id} 已识别，但不在本次训练计划内"
        if obs.evidence_topic and obs.evidence_topic in self.topic_index:
            return "evidence_topic", f"医学证据主题「{obs.evidence_topic}」命中"
        if obs.intent and obs.intent in self.intent_index:
            return "intent", f"提问意图「{obs.intent}」命中"
        return "none", "三级比对均未命中"

    def build(self, mastery_by_skill=None, skill_matcher=None):
        """
        生成覆盖图。

        mastery_by_skill: {skill_id: True/False} —— 该能力点是否掌握
                          （来自训练记录；缺省视为未掌握）
        skill_matcher:   SkillMatcher —— 观察未标 skill_id 时自动匹配能力点
        """
        mastery_by_skill = mastery_by_skill or {}
        entries = []
        covered_skills = set()

        for obs in self.observations:
            # 未标 skill_id → 用 SkillMatcher 自动匹配（复盘是自由文本）
            # ★ 但 inference（主观推测）不匹配能力点 ——
            #   推测不是能力点的表现，把它挂到能力点会制造虚假的定位。
            if (not obs.skill_id and skill_matcher is not None
                    and obs.kind != "inference"):
                hits = skill_matcher.match(obs.text, limit=1)
                if hits:
                    obs.skill_id = hits[0][0]
                    obs.match_note = (f"自动匹配能力点 {hits[0][0]}"
                                      f"（{hits[0][1].get('name','')}），"
                                      f"命中词 {hits[0][2][:2]}")
            level, evidence = self._match_level(obs)
            if level == "none":
                cls = "unknown"
            elif level == "skill_id_outside_plan":
                # 能力点已识别，但本次训练计划没覆盖 → 该能力点未覆盖
                covered_skills.add(obs.skill_id)
                cls = "not_covered"
            elif level == "skill_id":
                covered_skills.add(obs.skill_id)
                # ★ 能力点自动匹配上的，算「已覆盖」——
                #   但是否掌握仍看训练记录（mastery_by_skill）
                cls = ("covered_mastered" if mastery_by_skill.get(obs.skill_id)
                       else "covered_not_mastered")
            elif level == "evidence_topic":
                cls = "partial"     # 主题命中但能力点未精确命中
            else:
                cls = "partial"     # 仅意图命中 → 弱证据

            entries.append({
                "observation_id": obs.observation_id,
                "skill_id": obs.skill_id,
                "kind": obs.kind,
                "text": obs.text[:120],
                "gap_class": cls,
                "gap_class_cn": GAP_CN[cls],
                "match_level": level,
                # ★ 必须随差异结论记录
                "match_evidence": evidence,
                "observation_quality": obs.observation_quality,
                "statement_is_medically_supported": obs.statement_is_medically_supported,
                "event_occurrence_verified": obs.event_occurrence_verified,
            })

        # ★ 计划内但本次复盘未观察到的能力点 → unknown（不是 not_covered）
        #   理由：一次复盘没谈到 ≠ 没覆盖。
        #   「未覆盖」需要训练侧证据（这个能力点没被训到），
        #   否则会生成大量假的复训候选。
        for sid in self.plan_skill_ids:
            if sid not in covered_skills:
                entries.append({
                    "observation_id": None,
                    "skill_id": sid,          # ★ 未观察条目也要带 skill_id
                    "kind": "coverage_gap",
                    "text": f"计划覆盖的能力点 {sid} 在本次复盘中未被观察到",
                    "gap_class": "unknown",
                    "gap_class_cn": GAP_CN["unknown"],
                    "match_level": "none",
                    "match_evidence": "本次复盘未涉及该能力点；"
                                      "未观察到 ≠ 未覆盖，需训练侧证据才能判定",
                    "observation_quality": "single_self_report",
                    "statement_is_medically_supported": None,
                    "event_occurrence_verified": False,
                })

        counts = Counter_(e["gap_class"] for e in entries)
        return {
            "coverage_map": entries,
            "counts": {c: counts.get(c, 0) for c in GAP_CLASSES},
            "external_wording": ("复盘报告的题目覆盖情况"),
            "fact_boundary": ("这是【复盘报告的题目覆盖情况】，"
                              "不是对真实医生言行的预测或验证。"),
        }


def Counter_(items):
    d = {}
    for i in items:
        d[i] = d.get(i, 0) + 1
    return d


class GapCandidate:
    """
    差异候选 —— 通往两条进化路径的分叉点。

    ★ 两条路径不可合并：
        · 个性化复训  —— 自动，仅该员工
        · 共享题库更新 —— 必须审核发布，影响全体
    """

    def __init__(self, user_id, gap_class, title, detail,
                 skill_id=None, evidence_topic=None, source_debrief_id=None,
                 candidate_id=None):
        # user_id=None 表示【去标识化】的共享层候选
        self.candidate_id = candidate_id or _uid("GC")
        self.user_id = user_id
        self.gap_class = gap_class
        self.title = title
        self.detail = detail
        self.skill_id = skill_id
        self.evidence_topic = evidence_topic
        self.source_debrief_id = source_debrief_id
        # 路径分流
        self.path = None          # "personalized" | "shared_library"
        self.review_case_id = None
        self.status = "proposed"

    def to_dict(self):
        return {
            "candidate_id": self.candidate_id, "user_id": self.user_id,
            "gap_class": self.gap_class, "gap_class_cn": GAP_CN.get(self.gap_class),
            "title": self.title, "detail": self.detail,
            "skill_id": self.skill_id, "evidence_topic": self.evidence_topic,
            "source_debrief_id": self.source_debrief_id,
            "path": self.path, "status": self.status,
            "review_case_id": self.review_case_id,
        }


def route_candidates(candidates, plan_skill_ids=None, skill_uncovered_count=None,
                     total_users=1):
    """
    两条进化路径**并行**产生候选 —— 不是二选一。

    ★ 规格：「两条进化路径不可合并」
      | 路径 | 触发 | 审批 | 影响范围 |
      | 个性化复训 | 员工训练表现 | 无需签审（自动）| 仅该员工 |
      | 共享题库更新 | GapCandidate 经审核 | 必须审核发布 | 影响全体 |

      同一个 gap 对这个员工是复训需求，对组织可能也是有价值的新考点 ——
      所以两条路径各自产生候选，但**不能合并成一条**。

    ★ 数据隔离：共享层候选**去标识化**（不含 user_id、原文、姓名），
      个人层候选只在本人可见范围内。

    共享层的触发条件（较严，宁缺勿滥）：
      · 该能力点在计划中，且**全员都未覆盖**（真正的组织级缺口）
        —— skill_uncovered_count[sid] 是「未覆盖该能力点的员工数」，
           达到 total_users 才算组织级缺口。
      · 或该差异涉及合规红线（需要审核才能进题库）
    """
    skill_uncovered_count = skill_uncovered_count or {}
    plan_skill_ids = plan_skill_ids or []

    out = []
    for c in candidates:
        # ---- 路径 A：个性化复训（自动，仅该员工）----
        p = GapCandidate(
            user_id=c.user_id, gap_class=c.gap_class,
            title=c.title, detail=c.detail,
            skill_id=c.skill_id, evidence_topic=c.evidence_topic,
            source_debrief_id=c.source_debrief_id)
        p.path = "personalized"
        p.status = "auto_assigned"
        out.append(p)

        # ---- 路径 B：共享题库更新（必须审核）----
        s = GapCandidate(
            # ★ 去标识化：不带 user_id
            user_id=None, gap_class=c.gap_class,
            title=c.title, detail="（去标识化的组织级候选）" + c.detail,
            skill_id=c.skill_id, evidence_topic=c.evidence_topic,
            source_debrief_id=None)      # ★ 不带原文来源 id
        # 触发判定
        org_level_gap = (c.skill_id and c.skill_id in plan_skill_ids
                         and skill_uncovered_count.get(c.skill_id, 0) >= total_users)
        if org_level_gap:
            s.path = "shared_library"
            s.status = "pending_review"
            out.append(s)
    return out


# ============================================================
# 环节 ④ 审核与场景版本发布 ReviewCase → ScenarioVersion
# ============================================================
# 状态机 —— 转移写在程序里，LLM 只能请求不能决定
REVIEW_STATES = [
    "captured", "transcribed", "user_confirmed", "gap_analyzed",
    "review_pending", "approved", "rejected", "needs_revision",
    "scenario_proposed", "tested", "published", "retired",
]

# 合法转移表
REVIEW_TRANSITIONS = {
    "captured":        ["transcribed", "needs_revision", "rejected"],
    "transcribed":     ["user_confirmed", "needs_revision", "rejected"],
    "user_confirmed":  ["gap_analyzed", "needs_revision", "rejected"],
    "gap_analyzed":    ["review_pending", "rejected"],
    "review_pending":  ["approved", "rejected", "needs_revision"],
    "approved":        ["scenario_proposed", "rejected"],     # ★ 审核通过 ≠ 自动发布
    "needs_revision":  ["transcribed", "gap_analyzed", "rejected"],
    "rejected":        [],                                     # 终态
    "scenario_proposed": ["tested", "rejected"],
    "tested":          ["published", "rejected"],             # ★ 必须经回归测试才可发布
    "published":       ["retired"],                            # ★ 可回滚（保留可回放）
    "retired":         [],
}


class ReviewCase:
    """
    审核用例。

    ★ 状态转移由 `transition()` 强制校验 ——
      任何非法转移抛异常，且写进审计（谁在什么时候想干什么）。
    ★ 审核与发布分离：approved 之后还要 scenario_proposed → tested → published。
    ★ 被拒候选不得进入任何正式训练。
    """

    def __init__(self, case_id=None, source_type="gap_candidate",
                 source_id=None, payload=None, policy_version="V1.3"):
        self.case_id = case_id or _uid("RC")
        self.source_type = source_type
        self.source_id = source_id
        self.payload = payload or {}
        self.policy_version = policy_version
        self.status = "captured"
        self.audit = [{"at": _now(), "actor": "system", "action": "create",
                       "from": None, "to": "captured"}]
        self.scenario_version = None

    def transition(self, to_state, actor, reason=None, evidence=None):
        """
        合法状态转移。非法转移抛错并记录审计。

        ★ 这是「状态不能由 LLM 自由写」的执行点：
          LLM 可以输出一个意图，由调用方转成 transition() 调用；
          但转移是否合法、是否需要审批，全部由这张表决定。
        """
        allowed = REVIEW_TRANSITIONS.get(self.status, [])
        if to_state not in allowed:
            self.audit.append({
                "at": _now(), "actor": actor, "action": "transition_rejected",
                "from": self.status, "to": to_state,
                "reason": reason, "outcome": "illegal_transition",
                "allowed": allowed,
            })
            raise DebriefValidationError(
                "ILLEGAL_TRANSITION",
                f"非法状态转移：{self.status} → {to_state}。"
                f"当前允许：{allowed or '（终态，无出边）'}",
                {"from": self.status, "to": to_state, "allowed": allowed})

        # ★ 运算符优先级：写成显式括号，避免 `A and not B or C` 的坑
        #   LLM 不得执行【任何】状态转移 —— 规格：状态转移写在程序与数据库事务中，
        #   不能靠 LLM 自由写状态。LLM 只能*请求*转移，由本函数校验。
        if actor in (None, "", "llm", "system_auto"):
            raise DebriefValidationError(
                "ACTOR_NOT_AUTHORIZED",
                f"状态转移必须由具名人工执行，不能由 LLM/系统自动执行"
                f"（目标状态 {to_state}）",
                {"to": to_state, "actor": actor})

        prev = self.status
        self.status = to_state
        self.audit.append({
            "at": _now(), "actor": actor, "action": "transition",
            "from": prev, "to": to_state, "reason": reason,
            "evidence": evidence,
        })
        return self

    def to_dict(self):
        return {
            "case_id": self.case_id, "source_type": self.source_type,
            "source_id": self.source_id, "payload": self.payload,
            "status": self.status, "policy_version": self.policy_version,
            "audit": self.audit,
            "scenario_version": self.scenario_version,
            "audit_note": ("reviewer、证据链、政策版本、结果、时间、理由全部可查"),
        }


class ScenarioVersion:
    """
    场景版本 —— 发布后的可回放单元。

    ★ 版本可回滚：原版本保持可回放；重大问题支持回滚（retired 但不删）。
    """

    def __init__(self, version_id, content, case_id, author,
                 version_no=1, supersedes=None):
        self.version_id = version_id
        self.content = content
        self.case_id = case_id
        self.author = author
        self.version_no = version_no
        self.supersedes = supersedes
        self.status = "draft"
        self.created_at = _now()
        self.content_hash = _hash(content)

    def to_dict(self):
        return {
            "version_id": self.version_id, "case_id": self.case_id,
            "author": self.author, "version_no": self.version_no,
            "supersedes": self.supersedes, "status": self.status,
            "created_at": self.created_at, "content_hash": self.content_hash,
        }


# ============================================================
# 能力点匹配（对接 skill-taxonomy）
# ============================================================
class SkillMatcher:
    """
    把复盘文本映射到能力树上的能力点。

    ★ 为什么需要它：
      训练计划里的题带的是能力点描述文本，不是结构化 skill_id；
      复盘文本更是自由文本。两边要能做三级比对，
      就必须有统一的「文本 → skill_id」通道。

    ★ 匹配方式：能力点的 name 与 keywords 命中。
      不做语义模型 —— 能力树本身是关键词组织的（222 个能力点，
      每个带 keywords），关键词匹配足够且可解释。
    """

    def __init__(self, taxonomy_path=None, bridge_path=None, course_dirs=None):
        taxonomy_path = taxonomy_path or PATHS.TAXONOMY
        bridge_path = bridge_path or PATHS.SKILL_BRIDGE
        course_dirs = course_dirs or [
            PATHS.COURSE_SPECS, PATHS.COURSE_SPECS_TL, PATHS.COURSE_SPECS_CE]
        self.skills = []
        if os.path.exists(taxonomy_path):
            data = json.load(open(taxonomy_path, encoding="utf-8"))
            self.skills = data.get("skills", [])
        self._course_text = self._load_course_text(course_dirs)
        self._bridge = self._load_bridge(bridge_path)
        self._load_entities()
        self._index = []
        for sk in self.skills:
            name = sk.get("name") or ""
            concepts = self._concepts_from_name(name)
            core = set(concepts.get("core", set()))
            general = set(concepts.get("general", set()))
            if name:
                # ★ 短能力点名（如「单臂」）本身就是精确概念 → core
                #   长的（多为整句描述）放 general
                (core if len(name) <= 4 else general).add(name)
            # ★ keywords / dimensions 是【受控词表】里的专有概念
            #   （如「单臂」「PD-1」「NSCLC」）—— 不是自由文本，
            #   不会有「获批」那种通用词的歧义问题，放 core。
            for kw in str(sk.get("keywords") or "").split(";"):
                if kw.strip():
                    core.add(kw.strip())
            for d in sk.get("dimensions") or []:
                core.add(d)
            # ★ 产品/疾病专有名词 —— 明确无歧义
            core |= self._entity_terms(sk["skill_id"])
            # ★ 用关联课程的标题与教学主线扩展词表
            #   原因：复盘是自由文本（「是不是获批适应症」），
            #   能力点是关键词组织的（「免疫或靶向治疗适用人群」）——
            #   存在词汇鸿沟，靠课程主线里的表述搭桥。
            general |= self._course_terms(sk["skill_id"])
            self._index.append((sk["skill_id"], core, general, sk))

    # 能力点名的后缀词 —— 去掉后剩下的才是核心概念
    _SUFFIXES = ("异议", "抗拒", "的处理", "的处理方式", "应对", "处理", "讲解",
                 "辨析", "应用", "的理解", "的准备")

    @staticmethod
    def _concepts_from_name(name):
        """
        从能力点名里提取核心概念。

        ★ 关键：优先取「」内的引号内容。
          能力树里的沟通能力点命名高度规整：
            SK-C-OBJ-01  处理「价格异议」
            SK-C-STAGE-RESIST-01  应对「拖延的抗拒」
          这些引号内的词是**语料原生的类别词**（D0 的七类异议、六种抗拒），
          是复盘自由文本与能力树之间最可靠的桥。

        其次才是去掉后缀的词干（价格异议→价格、拖延的抗拒→拖延）。
        """
        if not name:
            return set()
        out = set()
        core = set()

        # ① 引号内容 —— 最高优先级
        for q in re.findall(r"[「『\"“]([^」』\"”]{2,20})[」』\"”]", name):
            core.add(q)
            # 去掉后缀的词干
            for suf in SkillMatcher._SUFFIXES:
                if q.endswith(suf) and len(q) - len(suf) >= 2:
                    core.add(q[:-len(suf)])
            # 去掉"的"
            if "的" in q:
                for part in q.split("的"):
                    if len(part) >= 2:
                        core.add(part)

        # ② 整体名去掉前缀动词后的词干
        m = re.match(r"^(处理|应对|区分|讲解|辨析|识别|应用|理解|准备|考察|覆盖)(.+)$", name)
        if m:
            rest = m.group(2)
            out.add(rest)
            for suf in SkillMatcher._SUFFIXES:
                if rest.endswith(suf) and len(rest) - len(suf) >= 2:
                    out.add(rest[:-len(suf)])

        # ③ 尾部概念词（适用人群 / 证据边界 / 状态边界 …）
        tail = re.sub(r"[（）()、，,：:；;／/｜|\s]", "", name)
        for n in (6, 5, 4):
            if len(tail) >= n:
                out.add(tail[-n:])

        # 引号内容单独放一组：匹配时权重更高
        return {"core": core, "general": out}

    def _entity_terms(self, skill_id):
        """
        能力点对应的产品名/疾病名 —— 明确无歧义的强特征。

        skill_id 里嵌了实体 id：
          SK-K-DABOSHU-PROD-01 → 产品 daboshu
          SK-K-D-NSCLC-001      → 疾病 D-NSCLC
        """
        out = set()
        # ★ 不要写 SK-[KC]-D?([A-Z0-9]+)-：可选的 D? 会把
        #   SK-K-DABOSHU-PROD-01 拆成 "ABOSHU"，匹配不到产品。
        m = re.search(r"SK-[KC]-([A-Z0-9]+)-", skill_id)
        if not m:
            return out
        eid = m.group(1)
        for prod in self._products.get(eid, []):
            out.add(prod)
        for cond in self._conditions.get(eid, []):
            out.add(cond)
        return out

    def _load_entities(self):
        """产品名与疾病名（来自临床库）—— 强匹配词来源"""
        prods, conds = {}, {}
        db_path = PATHS.CLIN_DB
        if not os.path.exists(db_path):
            self._products, self._conditions = prods, conds
            return
        try:
            import sqlite3
            db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            db.row_factory = sqlite3.Row
            for r in db.execute("select product_id, brand, generic_name from med_products"):
                names = [r["brand"], r["generic_name"]]
                for n in names:
                    if n:
                        prods.setdefault(r["product_id"].upper(), []).append(n)
                        # 品牌名去掉「注射液/片/胶囊」等剂型后缀也作别名
                        short = re.sub(r"(注射液|片|胶囊|口服溶液)$", "", n)
                        if short != n and len(short) >= 2:
                            prods[r["product_id"].upper()].append(short)
            for r in db.execute("select condition_id, name, keywords from clinical_conditions"):
                names = [r["name"]]
                for kw in str(r.get("keywords") or "").split(";"):
                    if kw.strip():
                        names.append(kw.strip())
                conds.setdefault(r["condition_id"].upper(), []).extend(
                    [n for n in names if n])
            db.close()
        except Exception:
            pass
        self._products, self._conditions = prods, conds

    def _load_bridge(self, path):
        if not os.path.exists(path):
            return {}
        try:
            return json.load(open(path, encoding="utf-8")).get("course_to_skill", {})
        except Exception:
            return {}

    @staticmethod
    def _load_course_text(course_dirs):
        """课程 spec 的标题与教学主线 —— 能力点扩展词表的来源"""
        out = {}
        for d in course_dirs:
            if not os.path.isdir(d):
                continue
            for f in os.listdir(d):
                if not f.endswith(".json"):
                    continue
                try:
                    j = json.load(open(os.path.join(d, f), encoding="utf-8"))
                except Exception:
                    continue
                cid = f[:-5]
                text = " ".join(str(x) for x in [
                    (j.get("meta") or {}).get("title", ""),
                    j.get("goal", ""),
                    (j.get("hero") or {}).get("question", ""),
                ])
                out[cid] = text
        return out

    def _course_terms(self, skill_id):
        """从关联课程里提取该能力点的扩展概念词"""
        terms = set()
        for cid, entries in self._bridge.items():
            for e in entries if isinstance(entries, list) else []:
                if e.get("skill_id") != skill_id:
                    continue
                text = self._course_text.get(cid, "")
                # 从课程文本里抽取关键概念片段
                for kw in re.findall(r"[\u4e00-\u9fa5]{3,8}", text):
                    if any(k in kw for k in ("适用", "人群", "边界", "关联", "适应",
                                             "证据", "对照", "终点", "线次",
                                             "状态", "获批", "在研", "核实")):
                        terms.add(kw)
        return terms

    def match(self, text, limit=3):
        """
        返回命中的能力点 [(skill_id, skill, 命中词)]。

        ★ 打分：命中词越长越具体 → 权重越高。
          「价格异议」命中 > 「价格」命中 > 「获批」命中
          （后者是通用词，容易误命中一堆管线能力点）。
        """
        if not text:
            return []
        hits = []
        for sid, core, general, sk in self._index:
            m_core = [t for t in core if len(t) >= 2 and t in text]
            m_gen = [t for t in general if len(t) >= 2 and t in text]
            if not m_core and not m_gen:
                continue
            matched = m_core or m_gen
            # 权重：核心命中 ×2，最长命中词越长分越高
            weight = (len(m_core) * 2 + len(m_gen)) * 100 + max(len(t) for t in matched)
            hits.append((sid, sk, matched, weight))
        hits.sort(key=lambda h: (-h[3], h[0]))
        return [(sid, sk, m) for sid, sk, m, _w in hits[:limit]]

    def match_ids(self, text, limit=3):
        return [h[0] for h in self.match(text, limit)]

    def for_condition(self, condition_id):
        """某疾病下的全部能力点"""
        return [sk for sk in self.skills if sk.get("parent_id") == condition_id]


# ============================================================
# 医学支撑判定（复用检索层 + 规则层，不另起一套）
# ============================================================
def judge_medical_support(observation, kb=None, guard=None):
    """
    判定「医学论断是否有依据」。

    ★ 与「事件是否发生」严格分开：
        医学论断无依据  ≠  事件没发生
        两者独立记录，不互相推导。

    判定方式（复用已有模块，不另写一套规则）：
      1. inference 类观察 —— 主观推测，本身不是医学论断 → 不支撑、且不应被写成确定性字段
      2. 用 FactGuard 检查文本是否触碰红线 → 触碰则不支撑
      3. 用检索层看能否找到对应的库内事实 → 找到则有依据（带出处）
    """
    # ★ 只有【代表自己的陈述】才可能构成医学论断：
    #     reported_question —— 医生的提问，不是代表的论断
    #     inference        —— 主观推测，不是论断
    #     unresolved       —— 未解决的问题，没有论断
    #   把这三种也判成「医学有依据」会制造虚假的确定性。
    if observation.kind != "self_answer":
        why_map = {
            "reported_question": "这是对方提出的问题，不是代表的医学论断",
            "inference": "inference 是主观推测，不是医学论断；"
                         "既不判定为有依据，也不得写成确定性字段",
            "unresolved": "这是未解决的问题，没有可判定的医学论断",
        }
        return {
            "statement_is_medically_supported": False,
            "support_refs": [],
            "why": why_map.get(observation.kind, "非陈述类观察，不作医学论断判定"),
            "event_occurrence_verified": observation.event_occurrence_verified,
            "separation_note": ("医学论断是否有依据 与 事件是否发生 有佐证 —— "
                                "两者独立，不互相推导"),
        }

    refs = []
    supported = None
    why = ""

    if guard is not None:
        issues, _ = guard.check(observation.text)
        if issues:
            supported = False
            why = "文本触碰合规红线：" + "；".join(i["why"] for i in issues[:2])
        else:
            supported = True
            why = "未触碰合规红线"

    if kb is not None and observation.evidence_topic:
        bundle = kb.fact_bundle(observation.text)
        med = bundle.get("medical_usable", [])
        if med:
            refs = [{"claim": f["claim"][:120], "source": f["source"], "level": f["level"]}
                    for f in med[:3]]
            if supported is None:
                supported = True
                why = f"检索到 {len(med)} 条库内事实支撑"
        elif supported is None:
            supported = False
            why = "库内未检索到对应事实"

    if supported is None:
        supported = False
        why = why or "缺少可核验依据"

    return {
        "statement_is_medically_supported": supported,
        "support_refs": refs,
        "why": why,
        # ★ 事件发生与否独立，不由上面的结论推导
        "event_occurrence_verified": observation.event_occurrence_verified,
        "separation_note": ("医学论断是否有依据 与 事件是否发生 有佐证 —— "
                            "两者独立，不互相推导"),
    }


# ============================================================
# 持久化
# ============================================================
class FeedbackStore:
    """轻量持久化 —— 共享层与个人训练层隔离"""

    def __init__(self, path=DB_FILE):
        self.path = path
        self.data = {"debriefs": {}, "observations": {}, "coverage": {},
                     "gap_candidates": {}, "review_cases": {}, "scenarios": {},
                     "personalized_plans": {}, "shared_library": {}}
        self._load()

    def _load(self):
        if os.path.exists(self.path):
            try:
                self.data = json.load(open(self.path, encoding="utf-8"))
            except Exception:
                pass

    def save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = self.path + ".tmp"
        json.dump(self.data, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)

    # ---- 写入 ----
    def put_debrief(self, d):
        self.data["debriefs"][d.debrief_id] = d.to_dict()

    def put_observations(self, debrief_id, obs):
        for o in obs:
            self.data["observations"][o.observation_id] = o.to_dict()
        self.data["observations"].setdefault("_by_debrief", {})
        self.data["observations"]["_by_debrief"][debrief_id] = [o.observation_id for o in obs]

    def put_coverage(self, debrief_id, cov):
        self.data["coverage"][debrief_id] = cov

    def put_candidate(self, c):
        self.data["gap_candidates"][c.candidate_id] = c.to_dict()

    def put_review_case(self, rc):
        self.data["review_cases"][rc.case_id] = rc.to_dict()

    def put_scenario(self, sv):
        self.data["scenarios"][sv.version_id] = sv.to_dict()

    # ---- 隔离读取 ----
    def personalized_for(self, user_id):
        """只返回该员工自己的数据 —— 共享层与个人层不混"""
        out = {"debriefs": [], "candidates": [], "plans": []}
        for d in self.data["debriefs"].values():
            if d.get("user_id") == user_id:
                out["debriefs"].append(d)
        for c in self.data["gap_candidates"].values():
            if c.get("user_id") == user_id and c.get("path") == "personalized":
                out["candidates"].append(c)
        out["plans"] = self.data["personalized_plans"].get(user_id, [])
        return out

    def shared_library(self):
        """共享题库 —— 只含已发布且未 retired 的版本"""
        return [s for s in self.data["scenarios"].values()
                if s.get("status") == "published"]
