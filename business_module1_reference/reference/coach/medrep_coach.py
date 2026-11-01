#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MedRep Coach 端到端原型 —— 把整条链路跑通。

链路（对应 V1.3 §4.1 数据流 A）：
  VisitContext → QuestionCandidate → PredictionPlan
    → SimulationSession（AI 医生多轮追问）
    → DualAssessment（两轨 9 维 + 4 闸门 + 降档表）
    → ErrorEvent → EmployeeSkillState（GAP 画像）
    → AssessmentReport

不依赖任何外部 API：AI 医生用规则引擎从语料/课程库取材，
评分用 D8a 草案的锚点与闸门。这是"跑通"的最小可验证实现。

运行：
  python3 medrep_coach.py --user 张伟 --disease D-NSCLC --dim DF --count 3
  python3 medrep_coach.py --user 张伟 --disease D-NSCLC --dim DF --count 3 --answers answers.json
"""
import json, os, re, glob, hashlib, time, argparse, sys
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import decisions as _decisions
import compliance_rules as _crules
import importlib.util as _ilu

# D07-1 语义等价层：识别「换一种说法说同一件事」的委婉表达。
# 纯关键词匹配对委婉表达整类漏判率 100%，靠识别语用结构（双要素共现）解决。
_EQ_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "phase0", "equivalence_layer.py")
try:
    _spec = _ilu.spec_from_file_location("equivalence_layer", _EQ_PATH)
    _eq_mod = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_eq_mod)
    EQUIV_RULES = _eq_mod.build_equivalence_layer()
except Exception:
    EQUIV_RULES = []   # 无等价层时退化为纯规则匹配

# ★ 路径统一来自配置中心（config.py），不再各自硬编码
from config import BASE, PATHS, load_config

PHASE0 = PATHS.PHASE0
COURSES = PATHS.COURSES
SCENARIOS = PATHS.SCENARIOS
TAX = PATHS.TAXONOMY
D8A = PATHS.D8A


# ============================================================
# 1. VisitContext —— 场景配置
# ============================================================
def build_visit_context(disease_id, dimension, channel="面访"):
    """医生画像卡 → 训练上下文"""
    # 从一期课程里找该疾病的课
    spec_p = None
    for cand in [f"specs/{disease_id}.json",
                  f"specs-tl/{disease_id}__TL.json",
                  f"specs-ce/{disease_id}__CE.json"]:
        p = os.path.join(COURSES, cand)
        if os.path.exists(p):
            spec_p = p
            break
    spec = json.load(open(spec_p, encoding="utf-8")) if spec_p else {}
    skel = None
    for cand in glob.glob(os.path.join(BASE, "course-skeletons*", f"{disease_id}*.json")):
        s = json.load(open(cand, encoding="utf-8"))
        if s.get("dimension", "disease_foundation") == dimension or dimension == "DF":
            skel = s
            break
    skel = skel or {}
    return {
        "visit_context_id": f"VC-{disease_id}-{dimension}",
        "department": skel.get("area", {}).get("department", "肿瘤学"),
        "disease": skel.get("condition_name", disease_id),
        "condition_id": disease_id,
        "dimension": dimension,
        "channel": channel,
        "topic_scope": skel.get("competency_scope", ""),
        "keywords": skel.get("keywords", ""),
        "role_preset": {
            "persona_origin": "synthetic",
            "emotion": "戒备",        # 合成角色，非真实专家
            "style": "直接",
            "intensity": "中",
            "interruption_level": "低",
        },
        "source_course": spec.get("meta", {}).get("title", ""),
    }


# ============================================================
# 2. QuestionCandidate / PredictionPlan —— 候选考点与训练计划
# ============================================================
def load_candidates(disease_id, dimension):
    """从场景库 + 课程检验题里取候选考点，每条带可解释优先级"""
    cands = []
    # (a) 场景种子（真实语料）
    if os.path.exists(SCENARIOS):
        for line in open(SCENARIOS, encoding="utf-8"):
            r = json.loads(line)
            cands.append({
                "source": "scenario_seed",
                "question": r["doctor_speech"],
                "doctor_profile": r["doctor_profile"],
                "type": r["type"],
                "difficulty": r["difficulty"],
                "exam_dimensions": r["exam_dimensions"],
                "citations": r["citations"],
                "reasons": ["真实拜访场景素材（课件语料出处可溯源）", f"难度{r['difficulty']}"],
            })
    # (b) 课程检验题（知识轨道）—— 按维度精确取对应目录，不混用
    dim_dir = {"DF": "specs", "TL": "specs-tl", "CE": "specs-ce"}.get(dimension, "specs")
    dim_file = {"DF": f"{disease_id}.json", "TL": f"{disease_id}__TL.json",
                "CE": f"{disease_id}__CE.json"}.get(dimension, f"{disease_id}.json")
    cand = [f"{dim_dir}/{dim_file}"]
    for cand in cand:
        p = os.path.join(COURSES, cand)
        if not os.path.exists(p):
            continue
        spec = json.load(open(p, encoding="utf-8"))
        for c in spec.get("checks", []):
            cands.append({
                "source": "course_check",
                "question": c["question"],
                "doctor_profile": spec["hero"]["question"][:120],
                "type": "知识考察",
                "difficulty": "medium",
                "exam_dimensions": spec.get("goal", "")[:80],
                "citations": [s.get("url", "") for s in spec.get("sources", []) if s.get("url")][:2],
                "reasons": ["已审核课程知识考察项", "对应能力点：" + (spec.get("goal", "")[:40])],
                "rubric": {
                    "answer": c["options"][c["answer"]],
                    "explanation": c["explanation"],
                    "distractors": [o for j, o in enumerate(c["options"]) if j != c["answer"]],
                },
            })
    # 优先级：课程题 > 场景种子；按难度排
    prio = {"course_check": 0, "scenario_seed": 1}
    cands.sort(key=lambda c: (prio[c["source"]], {"hard": 0, "medium": 1, "easy": 2}.get(c["difficulty"], 1)))
    return cands


def build_plan(context, cands, count):
    """题量可配（V1.3 AT03）+ 可解释优先级"""
    chosen = cands[:count]
    return {
        "plan_id": f"PP-{context['visit_context_id']}-{int(time.time())}",
        "visit_context_id": context["visit_context_id"],
        "question_count": len(chosen),
        "question_count_policy": f"本次训练取 {len(chosen)} 题（按训练时长预算与能力点覆盖数确定，非固定值）",
        "questions": [
            {
                "qid": f"Q{i+1}",
                "candidate_id": f"C-{i+1}",
                "question": c["question"],
                "type": c["type"],
                "difficulty": c["difficulty"],
                "exam_dimensions": c["exam_dimensions"],
                "why_recommended": c["reasons"],
                "evidence": c["citations"],
                "rubric": c.get("rubric"),
            }
            for i, c in enumerate(chosen)
        ],
    }


# ============================================================
# 3. SimulationSession —— AI 医生模拟
# ============================================================
class DoctorSim:
    """AI 医生：按角色设定 + 语料素材生成多轮追问。
    关键约束（AT05）：切换情绪/风格时，医学事实与合规边界不变。"""

    def __init__(self, context):
        self.ctx = context
        rp = context["role_preset"]
        self.style = rp["style"]
        self.emotion = rp["emotion"]
        self.intensity = rp["intensity"]

    def opening(self, question):
        """开场：按风格调整措辞，但医学内容不变"""
        q = question
        if self.style == "直接":
            return q
        if self.style == "绕":
            return f"{q} 我比较想先听听您的整体看法。"
        return q

    def followup(self, q, answer, turn, qid=None):
        """追问：基于药代回答是否含核实路径决定追问方向"""
        tag = f"[{qid}] " if qid else ""
        has_path = bool(re.search(
            r"(核实|确认|查证|不确定|需按|需要按|须按|按最新|说明书|医学信息|"
            r"医学团队|为准|核对|口径|逐条对)", answer))
        if has_path:
            return (f"{tag}那您说的具体要核对哪几项？"
                    f"（第 {turn} 轮追问 · 认可核实路径，转向具体动作）")
        forbidden = re.findall(
            r"(适用于|已经获批|适应症是|肯定比|所有患者|一定能用|我保证|疗效肯定|"
            r"临床数据证明)", answer)
        if forbidden:
            return (f"{tag}您刚说的『{forbidden[0]}』——这一条我要再追一下，"
                    f"您是依据哪份材料说的？（第 {turn} 轮追问 · 触发合规风险，追依据）")
        return (f"{tag}那您刚才说的这一点，"
                f"如果换成我这个具体病人情况，您会怎么建议？（第 {turn} 轮追问 · 常规深挖）")

    def closing(self, turns):
        return f"（结束本次交流，共 {turns} 轮）医生：好，今天先到这儿。"

    def boundary_note(self):
        """AT05 验证锚点：医学事实不随情绪变化"""
        return {
            "style": self.style,
            "emotion": self.emotion,
            "medical_facts_locked": True,
            "note": "角色风格只改变表达方式与压力强度；医学事实与合规边界由知识版本锁定，不随情绪变化",
        }


# ============================================================
# 4. DualAssessment —— 双轨评分
# ============================================================
class Rubric:
    """评分引擎：两轨 9 维 + 4 闸门 + 降档表（依 D8a 草案）"""

    # D2 合规规则清单 —— 从共享模块导入（compliance_rules.py）
    # ★ 原来这里独立维护一份，与 llm_provider.FactGuard 重复，
    #   导致同类覆盖不足问题在两处重复出现（尾随 | 造成的空匹配等）。
    #   现在规则只定义一次，两个消费者都从这里取。
    GATE_RULES = _crules.GATE_RULES
    GATE_PATTERNS = _crules.COMPILED_RULES
    RULE_INDEX = {rid: i for i, (rid, _g, _d, _p) in enumerate(GATE_RULES)}

    # 不可评分：药代说"我不知道/需要核实"且该题无 rubric
    # 注意：区分「无实质内容可评」与「有实质内容+核实路径」
    #   UNS-01「具体适应症我需要查一下再回复您」→ 无可评实质内容 → 不可评分
    #   UNS-03「这个数据我需要按最新披露核实之后再回复您」→ 有实质内容 → 正常判分
    UNSCORABLE = re.compile(
        r"(我(不确定|不知道|没法确认)|无法(确定|确认|核实)|超出我的范围|"
        r"这个(我|需要)(无法|没法)(确定|核实)|"
        r"不太确定|不太适合给您|"
        # ★ 「我这边没法确认」「超出我能覆盖的范围」「不能现在就给您结论」——
        #   这些是真实的不确定 → 应判不可评分。
        #   注意与合规拒绝区分：「不能答应您」是拒绝，不是不知道。
        r"我(这边|这里)?(没法|无法|不能)(确认|确定|核实)|"
        r"超出我能?覆盖的范围|超出我(的|能覆盖的)范围|"
        r"不能我?现在就?给(您)?结论|不能现在.{0,8}结论|"
        # 「XX我需要查一下再回复」——无可评实质内容
        r"(具体适应症|适应症|这个产品|这部分|这块)[^。；]{0,12}"
        r"(我)?(需要|要)(查|问|确认|核实|了解一下)[^。；]{0,10}(再|后)?回复)")
    # 注意：以下都是「合规的拒绝」，不是「不确定」，不能进 UNSCORABLE
    #   「不能保证疗效」「不能答应您」「不能收集」——拒绝语境，正确行为
    # ★ 关键区分：
    #   「不能给结论」= 真的不确定 → 应判不可评分
    #   「不能答应您」  = 合规拒绝   → 不判不可评分
    UNSCORABLE_EXCLUDE = re.compile(
        r"(不能(保证|答应|做|收集|提供|给(?!结论)|收)|"
        r"无法(答应|提供)|"
        r"违反|违规|不合规|守则|规定|隐私)")

    VERIFY_PATH = re.compile(
        r"(核实|确认|查证|不确定|需按|需要按|须按|按最新|说明书|医学信息|"
        r"医学团队|为准|核对|口径|逐条对|按方案)")

    ABSOLUTE = re.compile(
        r"(肯定|一定|必然|绝对)(比|优于|强于|有效)|(所有|全部)(患者|病人)(都|均)(适用|能用)")

    FABRICATED = re.compile(
        r"(样本量\s*\d+|p\s*[＜<=>]\s*0?\.\d+|ORR\s*(达|为)\s*\d+%|"
        r"OS\s*(延长|提升)\s*\d+\s*(周|月|年)|发生率\s*\d+(\.\d+)?%)")

    # ---------- D2 §4 语义方向判定 ----------
    # 同一个词，方向相反，判定完全相反。必须判定语境方向，不能只做关键词匹配。
    # 拒绝语境的正确行为若被误判为一票否决，等于系统性惩罚合规的药代。
    DIRECTION_IMPLEMENT = re.compile(
        # 只保留真正指向「实施不正当行为」的信号。
        # 「给您」「我帮您」这类中性词不能算实施信号——
        #   「我不能保证进院，但我可以把学术支持的方式给您讲清楚」
        # 里的「给您」是合法的学术支持，不是违规实施。
        r"(您给|我给|可以给|给您报|给您申请|给点|好处|奖励|发票|走账|"
        r"我帮您(搞定|安排|操作)|我来(办|处理)|包在我)")
    DIRECTION_REFUSE = re.compile(
        r"(不能|不可以|不行|没法|无法|不会|不应|不得|"
        r"违反|违规|不合规|拒绝|杜绝|"
        r"守则|规定|制度|法律|原则|"
        r"有问题|不对|不妥|不接受|不接|不能接受|不接受|"
        r"这个做法|这种做法|不值得|不合适|违规操作)")
    DIRECTION_CLARIFY = re.compile(
        r"(我说的|指的是|不是指|指的是|区别在于|所谓|"
        r"不等于|我不是说|其实是|具体.{0,6}(哪个|什么)版本|"
        r"(哪个|什么)版本.{0,8}(我)?(需要|要)?(核实|确认|查))")
    # 否定形式：同样是拒绝语境
    #   「处方量不是我的关注点」——否定了该行为，不是在实施
    DIRECTION_NEGATE = re.compile(
        r"(不是.{0,8}(关注|考虑|范围|要谈|谈的)|"
        r"(无关|不涉及|不关心|不谈|别提|不用说|没有这(个|种)必要)|"
        r"不(能|可以|该|会)(给|答应|提供|做|说|谈)|"
        r"只能|仅能|只谈)")

    # D3 §4 第②类：表述规范扣分（未越线但不规范），在维度内扣分，不触发降档
    IMPRECISE = re.compile(
        r"(可能有效|应该没问题|差不多|大概|基本上|反正|你看行不行|"
        r"反正我觉得|这个不好说)")

    def judge_direction(self, answer, matched_span):
        """判定语境方向 → (direction, exempt, reason)

        direction: 实施 / 拒绝 / 澄清
        exempt:    True 表示该次命中不成立（拒绝或澄清语境）

        判定要点：
        · 实施信号必须**靠近关键词**（同一子句内），表示"我要做"
        · 拒绝信号可以出现在**全文**——拒绝常在关键词之后
          （"有些同行会说可以送点礼品，我觉得这个做法有问题"）
        · 两者并存时，若拒绝是结论性表述（句末），以拒绝论
        """
        pos = answer.find(matched_span)
        if pos < 0:
            pos = 0
        # 靠近窗口：关键词前后各 25 字（同一子句）
        near = answer[max(0, pos - 25): pos + len(matched_span) + 25]

        # 实施信号（须靠近）
        impl_near = bool(self.DIRECTION_IMPLEMENT.search(near)) and not re.search(
            r"(不能|不可以|不行|没法|无法).{0,12}(给|答应|做|提供)", near)
        # 拒绝信号（全文）
        refuse_any = bool(self.DIRECTION_REFUSE.search(answer))
        negate_any = bool(self.DIRECTION_NEGATE.search(answer))
        clarify_any = bool(self.DIRECTION_CLARIFY.search(answer))

        if impl_near:
            # 实施信号在附近：除非紧随其后的拒绝是结论性的
            tail = answer[pos + len(matched_span): pos + len(matched_span) + 30]
            if (refuse_any or negate_any) and re.search(
                    r"(有问题|不对|不妥|不接受|不接|不能接受|不等于|违规|不行|不能|没法)", tail):
                return "拒绝", True, "拒绝语境：命中后紧跟明确的否定表述"
            return "实施", False, "实施语境：关键词附近有主动提供/承诺信号"
        if refuse_any:
            return "拒绝", True, "拒绝语境：明确否定该行为"
        if negate_any:
            return "拒绝", True, "否定语境：该行为被明确排除"
        if clarify_any:
            return "澄清", True, "澄清语境：同词不同义"
        return "实施", False, "默认实施语境"

    def __init__(self, doc):
        self.doc = doc
        self.dim_defs = []
        for track in ("communication", "medical"):
            t = doc["tracks"][track]
            for d in t["dimensions"]:
                self.dim_defs.append((track, d))

    def score_answer(self, answer, rubric=None, channel="面访"):
        """对单个回答打分 → 返回 (维度得分, 闸门, 扣分点)"""
        gates, findings = [], []

        # 闸门 01/02：合规与边界
        # 命中后必须做语义方向判定（D2 §4）：拒绝/澄清语境豁免但留痕
        for rid, gate, desc, pat in self.GATE_RULES:
            m = re.search(pat, answer)
            if m:
                direction, exempt, reason = self.judge_direction(answer, m.group(0))
                if exempt:
                    # 豁免不静默跳过——留痕供复核
                    gates.append({"gate": f"{gate}（已豁免）", "rule_id": rid,
                                  "rule_desc": desc, "trigger": m.group(0),
                                  "effect": f"不成立：{reason}",
                                  "direction": direction, "exempt": True,
                                  "exempt_reason": reason})
                else:
                    gates.append({"gate": gate, "rule_id": rid, "rule_desc": desc,
                                  "trigger": m.group(0),
                                  "effect": "本轮不通过，不计入个人均分",
                                  "direction": direction, "exempt": False})

        # D07-1 语义等价层：委婉表达（换一种说法说同一件事）
        # 命中后映射回 D2 规则 ID，同样做方向判定——拒绝语境豁免但留痕
        # ★ 去重：同一 rule_id 已有关键词层命中时，等价层信息并入该条，
        #   不新增记录——否则同一次违规会被记两条，重练池虚高。
        _hit_rules = {g.get("rule_id") for g in gates if not g.get("exempt")}
        if EQUIV_RULES:
            for h in _eq_mod.detect_equivalence(answer, EQUIV_RULES):
                gate = ("GATE-01 合规硬红线" if h["rule_id"].startswith("CR")
                        else "GATE-02 适用边界越界")
                if h["rule_id"] in _hit_rules and not h["exempt"]:
                    # 已被关键词层覆盖 → 补记等价说明，不新增条目
                    for g in gates:
                        if g.get("rule_id") == h["rule_id"]:
                            g["equiv_id"] = h["id"]
                            g["equiv_why"] = h["why"]
                            g["equiv_context"] = h["context_text"]
                            break
                    continue
                if h["exempt"]:
                    gates.append({
                        "gate": f"{gate}（已豁免）", "rule_id": h["rule_id"],
                        "rule_desc": h["name"], "trigger": h["marker_text"],
                        "effect": f"不成立：{h['exempt_reason']}",
                        "direction": h["direction"], "exempt": True,
                        "exempt_reason": h["exempt_reason"],
                        "equiv_id": h["id"], "equiv_why": h["why"],
                        "equiv_context": h["context_text"]})
                else:
                    gates.append({
                        "gate": gate, "rule_id": h["rule_id"],
                        "rule_desc": h["name"], "trigger": h["marker_text"],
                        "effect": "本轮不通过，不计入个人均分",
                        "direction": h["direction"], "exempt": False,
                        "equiv_id": h["id"], "equiv_why": h["why"],
                        "equiv_context": h["context_text"]})

        # 闸门 03：不可评分（药代明确表示不确定且该题无 rubric 支撑）
        if (rubric is None and self.UNSCORABLE.search(answer)
                and not self.UNSCORABLE_EXCLUDE.search(answer)):
            gates.append({"gate": "GATE-03 不可评分", "trigger": "药代明确表示不确定，且该题无已审核 rubric 支撑",
                          "effect": "整题剔除：不判分、不进分母、不进 GAP 画像，计入知识缺口率"})

        # 闸门 04：维度不可评（电话形态无打断/非语言证据）
        if channel == "电话" and rubric is None:
            dims_unavailable = ["COM-04 临场应变", "COM-05 情境适应"]
            gates.append({"gate": "GATE-04 维度不可评",
                          "trigger": f"电话形态下无法观测：{'、'.join(dims_unavailable)}",
                          "effect": "该维度从分母移除，权重按剩余可评维度重新归一"})

        # 闸门 01/02 是"已判违规"，不是"不可评分"——仍应判分并计入分母
        # 注意：已豁免的闸门不算触发（exempt=True），必须排除
        hard_gate = [g for g in gates
                     if g["gate"].startswith(("GATE-01", "GATE-02"))
                     and not g.get("exempt")]
        # 只有 GATE-03/04 真正触发才整题剔除。
        # 不能写成 `if gates and not hard_gate` —— 那会把"已豁免的闸门"误当成不可评分，
        # 导致正确的合规拒绝（例：拒绝回扣）被整题剔除，惩罚合规行为。
        exclusion_gate = [g for g in gates
                          if g["gate"].startswith(("GATE-03", "GATE-04"))]
        if exclusion_gate:
            # 仅 GATE-03/04 触发 → 整题剔除
            return {}, gates, findings, True

        # 维度打分
        scores = {}
        has_path = bool(self.VERIFY_PATH.search(answer))
        has_abs = bool(self.ABSOLUTE.search(answer))
        has_fab = bool(self.FABRICATED.search(answer))

        L = len(answer)
        # D3 §4 第②类：表述不规范（未越线）→ 维度内扣分，不触发降档
        imprecise = self.IMPRECISE.search(answer)
        has_imprecise = bool(imprecise)
        # 逐维按各自锚点判定，而不是一个笼统的基础分
        for track, d in self.dim_defs:
            name = f"{d['id']} {d['name']}"
            if track == "communication":
                if d["id"] == "COM-01":       # 问题理解：是否接住了医生真正在问的
                    base = 5 if has_path else (3 if L >= 20 else 2)
                elif d["id"] == "COM-02":     # 回答结构：结论先行、分层、可跟随
                    base = 5 if (L <= 120 and has_path) else (4 if 20 <= L <= 160 else 3)
                    if L < 15:
                        base = 1
                elif d["id"] == "COM-03":     # 表达清晰：口语可懂、术语解释
                    jargon = len(re.findall(r"(循证|终点|分子缓解|免疫原性|联合用药方案|给药方案|疗效终点)", answer))
                    base = 5 if jargon == 0 else 3
                    if L > 200:
                        base = max(1, base - 1)
                elif d["id"] == "COM-04":     # 临场应变：被质疑时是否调整
                    base = 5 if has_path else (3 if L >= 25 else 2)
                    if has_abs:
                        base = 1
                else:                          # COM-05 情境适应：是否给出可执行动作
                    base = 5 if has_path else (3 if re.search(r"(我可以|我这边|整理给您|给您)", answer) else 2)
                    if has_abs:
                        base = 1
            else:
                if d["id"] == "MED-01":       # 知识准确性：是否讲对
                    base = 5 if (has_path and not has_abs and not has_fab) else (3 if not has_abs else 1)
                elif d["id"] == "MED-02":     # 证据运用：是否说清研究边界
                    if re.search(r"(对照|随机|终点|人群|入组|单臂)", answer):
                        base = 5 if has_path else 3
                    else:
                        base = 4 if has_path else 2
                elif d["id"] == "MED-03":     # 适用边界：是否守住人群/线次/状态
                    base = 5 if has_path else (3 if re.search(r"(人群|线次|适应|范围|适用)", answer) else 2)
                    if has_abs:
                        base = 1
                else:                          # MED-04 专业与合规：是否守住推广合规
                    base = 1 if (has_abs or has_fab) else (5 if has_path else 3)
                    if has_fab:
                        findings.append(f"{name}：出现疑似编造数值（{self.FABRICATED.search(answer).group(0)}）")
            # 第②类：表述规范扣分——在表达清晰与专业合规两维上扣，不触发降档
            if has_imprecise and d["id"] in ("COM-03", "MED-04"):
                base = max(1, base - 1)
            scores[name] = base

        # 扣分点
        if has_abs:
            findings.append(f"绝对化表述：{self.ABSOLUTE.search(answer).group(0)}")
        if has_fab:
            findings.append(f"疑似编造临床数值：{self.FABRICATED.search(answer).group(0)}")
        if has_imprecise:
            findings.append(
                f"表述不规范（第②类·维度内扣分，不触发降档）：{imprecise.group(0)}")
        if not has_path and rubric is not None:
            findings.append("未给出核实路径——在临床边界问题上，正确做法是说明如何核实")

        return scores, gates, findings, False

    def synthesize(self, per_q, channel="面访", user_id=None):
        """门控合成 + 降档表"""
        if not per_q:
            return None
        gates = [g for q in per_q for g in q["gates"]]
        findings = [f for q in per_q for f in q["findings"]]
        # 不可评维度（按形态）
        if channel == "电话":
            unavail = {"COM-04 临场应变", "COM-05 情境适应"}
        else:
            unavail = set()
        # 维度平均
        agg = defaultdict(list)
        for q in per_q:
            for k, v in q["scores"].items():
                if k not in unavail:
                    agg[k].append(v)
        dim_avg = {k: round(sum(v) / len(v), 2) for k, v in agg.items()}

        comm_dim = {k: v for k, v in dim_avg.items() if k.startswith("COM")}
        med_dim = {k: v for k, v in dim_avg.items() if k.startswith("MED")}
        w = self.doc["weights"]
        cw = w["dimension_weights_communication"]
        mw = w["dimension_weights_medical"]

        def wsum(d, weights):
            tot = sum(weights.get(k, 0) for k in d) or 1
            return round(sum(v * weights.get(k, 0) for k, v in d.items()) / tot, 2)

        comm_score = wsum(comm_dim, cw)
        med_score = wsum(med_dim, mw)
        # 权重按剩余可评维度归一
        # ★ 初始轨权重取自 decisions.py（已拍板 D08a-2）+ 资历上调（D08a-3），
        #   不再从评分表草案里各读一份——避免同一值多处定义导致漂移。
        if user_id:
            init_c, init_m, _streak = _decisions.effective_weights(user_id)
        else:
            init_c = _decisions.INITIAL_WEIGHTS["communication"]
            init_m = _decisions.INITIAL_WEIGHTS["medical"]
        cw_frac = init_c / 100
        mw_frac = init_m / 100
        if unavail:
            avail_c = sum(cw.get(k, 0) for k in comm_dim)
            avail_m = sum(mw.get(k, 0) for k in med_dim)
            if avail_c + avail_m > 0:
                cw_frac = avail_c / (avail_c + avail_m)
                mw_frac = 1 - cw_frac
        final = round(comm_score * cw_frac + med_score * mw_frac, 2)

        # 降档
        # 注意：已豁免的闸门不算触发（exempt=True），必须排除。
        # 「GATE-01 合规硬红线（已豁免）」的 split()[0] 仍是 "GATE-01"，
        # 直接用会误判为触发红线，把正确拒绝违规的合规药代一票否决。
        gate_names = [g["gate"].split()[0] for g in gates if not g.get("exempt")]
        # cap 与综合分同为 1–5 分制（5.0 表示不设上限），与 D3 §3.1 一致
        cap = _decisions.DOWNGRADE_THRESHOLDS["cap_no_limit"]
        level = "达标"
        if "GATE-01" in gate_names:
            cap, level = (_decisions.DOWNGRADE_THRESHOLDS["cap_compliance_reject"],
                          "合规否决（不计入个人均分）")
        elif "GATE-02" in gate_names:
            cap, level = (_decisions.DOWNGRADE_THRESHOLDS["cap_boundary_violation"],
                          "边界越界（强制降档）")
        elif not med_dim:        # 无可评分的医学题 → 无依据判降档
            cap, level = (_decisions.DOWNGRADE_THRESHOLDS["cap_no_limit"],
                          "暂不评定（本轮无可评分的知识维度）")
        elif med_score < _decisions.DOWNGRADE_THRESHOLDS["knowledge_insufficient_below"]:
            cap, level = (_decisions.DOWNGRADE_THRESHOLDS["knowledge_insufficient_below"],
                          "知识不足（强制降档）")
        elif med_score < _decisions.DOWNGRADE_THRESHOLDS["basically_qualified_below"]:
            cap, level = _decisions.DOWNGRADE_THRESHOLDS["cap_basic"], "基本达标"
        else:
            cap, level = 5.0, "达标"
        final_capped = min(final, cap)

        return {
            "communication_score": comm_score,
            "medical_score": med_score,
            "final_score_before_cap": final,
            "final_score": final_capped,
            "level": level,
            "cap_applied": cap,
            "dimension_scores": dim_avg,
            "dimensions_unavailable": sorted(unavail),
            "weights_used": {"communication": round(cw_frac, 3), "medical": round(mw_frac, 3)},
            "gates": gates,
            "findings": findings,
            "scored_questions": len([q for q in per_q if q["scores"]]),
            "excluded_questions": len([q for q in per_q if not q["scores"]]),
            "unanswered": len([q for q in per_q if q.get("unanswered")]),
        }


# ============================================================
# 5. ErrorEvent + EmployeeSkillState —— 错误留存与 GAP
# ============================================================
ERROR_TYPES = [
    ("knowledge", "知识错误"), ("compliance", "合规踩线"),
    ("boundary", "边界越界"), ("structure", "表达结构"),
    ("no_path", "未给核实路径"), ("no_answer", "未作答"),
]


def build_events(per_q, plan):
    events = []
    for qi, q in enumerate(per_q):
        for f in q["findings"]:
            if q.get("unanswered"):
                events.append({
                    "event_id": f"EV-{qi+1}-U{len(events)+1}", "qid": f"Q{qi+1}",
                    "error_type": "no_answer", "error_type_cn": "未作答",
                    "detail": f, "rule_ref": "PARTICIPATION-001",
                    "scene_profile": {"disease": plan["visit_context_id"].split("-")[1],
                                      "dimension": plan["visit_context_id"].split("-")[-1]},
                    "utterance": "",
                })
                continue
            et = "no_path" if "未给出核实路径" in f else (
                 "compliance" if "绝对化" in f else (
                 "boundary" if "边界" in f else (
                 "knowledge" if "数值" in f else "structure")))
            events.append({
                "event_id": f"EV-{qi+1}-{len(events)+1}",
                "qid": f"Q{qi+1}",
                "error_type": et,
                "error_type_cn": dict(ERROR_TYPES)[et],
                "detail": f,
                "rule_ref": "COMP-001" if et == "compliance" else (
                            "BOUNDARY-001" if et == "boundary" else (
                            "KNOW-001" if et == "knowledge" else "RUBRIC-001")),
                "scene_profile": {"disease": plan["visit_context_id"].split("-")[1],
                                  "dimension": plan["visit_context_id"].split("-")[-1]},
                "utterance": q.get("answer", ""),
            })
        for g in q["gates"]:
            events.append({
                "event_id": f"EV-{qi+1}-G{len(events)+1}",
                "qid": f"Q{qi+1}",
                "error_type": "compliance" if "GATE-01" in g["gate"] else "boundary",
                "error_type_cn": dict(ERROR_TYPES)["compliance" if "GATE-01" in g["gate"] else "boundary"],
                "detail": f"{g['gate']}：触发「{g['trigger']}」",
                "rule_ref": g["gate"].split()[0],
                "scene_profile": {"disease": plan["visit_context_id"].split("-")[1],
                                  "dimension": plan["visit_context_id"].split("-")[-1]},
                "utterance": q.get("answer", ""),
            })
    return events


def build_gap_profile(events, user_id):
    """GAP 画像：不是总分，而是可行动的诊断"""
    by_type = defaultdict(list)
    by_dim = defaultdict(list)
    for e in events:
        by_type[e["error_type_cn"]].append(e["event_id"])
        by_dim[e["scene_profile"]["dimension"]].append(e["event_id"])
    recommendations = []
    if "合规踩线" in by_type:
        recommendations.append("优先复训合规红线：建议做 D2 合规判定规则的专项场景，并请医学/合规同事陪练一轮")
    if "边界越界" in by_type:
        recommendations.append("补适用边界：把『披露状态 vs 审批状态』『适用范围须查说明书』这两条练到能脱口而出")
    if "知识错误" in by_type:
        recommendations.append("补临床知识：该疾病的核心评估维度还不牢，建议重看对应课程并做一次证据解读练习")
    if "未给核实路径" in by_type:
        recommendations.append("改回答习惯：不是不知道就硬答，而是给出一条可执行的核实动作")
    if "未作答" in by_type:
        recommendations.append("本轮有未作答的题：先确认是时间不够、题目不适配，还是知识确实不会——"
                               "三者的复训方式不同")
    if not recommendations:
        recommendations.append("本轮无明显短板，可提高难度或换到其他疾病维度")
    return {
        "user_id": user_id,
        "total_events": len(events),
        "by_error_type": {k: len(v) for k, v in by_type.items()},
        "by_dimension": {k: len(v) for k, v in by_dim.items()},
        "top_weakness": max(by_type.items(), key=lambda kv: len(kv[1]))[0] if by_type else None,
        "diagnosis": (f"主要短板：{max(by_type.items(), key=lambda kv: len(kv[1]))[0]}"
                   f"（{max((len(v) for v in by_type.values()), default=0)} 次）"
                   if by_type else "本轮无错误记录"),
        "recommendations": recommendations,
        "note": "GAP 画像按能力点与错误类型聚合，不依赖总分；仅用于训练分配与能力诊断，不作为人事处罚依据",
    }


# ============================================================
# 6. 报告
# ============================================================
def build_report(ctx, plan, transcript, assessment, events, gap):
    lines = [
        f"# 训练报告 · {ctx['disease']}（{ctx['dimension']}）",
        "",
        f"- 训练编号：`{plan['plan_id']}`",
        f"- 训练场景：{ctx['department']} · {ctx['channel']} · 合成角色（{ctx['role_preset']['emotion']}/{ctx['role_preset']['style']}）",
        f"- 题量：{plan['question_count']} 题（{plan['question_count_policy']}）",
        "",
        "## 一、综合评定",
        "",
        "| 项 | 值 |",
        "|---|---|",
        f"| 沟通与应变分 | {assessment['communication_score']} |",
        f"| 专业知识运用分 | {assessment['medical_score']} |",
        f"| 综合分 | **{assessment['final_score']}** / 5（未降档 {assessment['final_score_before_cap']}，"
        f"上限 {assessment['cap_applied']} / 5）|",
        f"| 等级 | {assessment['level']} |",
        f"| 权重 | 话术 {assessment['weights_used']['communication']} / 知识 {assessment['weights_used']['medical']} |",
        f"| 计入评分题数 | {assessment['scored_questions']} |",
        f"| 剔除题数 | {assessment['excluded_questions']}（不判分、不进分母、不进 GAP）|",
        f"| 未作答题数 | {assessment.get('unanswered', 0)} |",
    ]
    if assessment["dimensions_unavailable"]:
        lines.append(f"| 本形态未评维度 | {'、'.join(assessment['dimensions_unavailable'])} |")
    lines += ["", "## 二、维度得分", "", "| 维度 | 分数 |", "|---|---|"]
    for k, v in sorted(assessment["dimension_scores"].items()):
        lines.append(f"| {k} | {v} |")

    lines += ["", "## 三、对话记录", ""]
    for t in transcript:
        lines.append(f"**{t['role']}**：{t['text']}")
        lines.append("")

    if assessment["gates"]:
        # 区分「触发的红线」与「已豁免的命中」——豁免必须可见，否则复核无从下手
        fired = [g for g in assessment["gates"] if not g.get("exempt")]
        exempt = [g for g in assessment["gates"] if g.get("exempt")]
        if fired:
            lines += ["## 四、严重问题（一票否决 / 强制降档）", "",
                      "| 闸门 | 规则 | 触发内容 | 语境方向 | 处置 |",
                      "|---|---|---|---|---|"]
            for g in fired:
                rid = g.get("rule_id", "")
                desc = g.get("rule_desc", "")
                lines.append(
                    f"| {g['gate']} | {rid} {desc} | 「{g['trigger']}」 | "
                    f"{g.get('direction', '—')} | {g['effect']} |")
            lines.append("")
            # 等价层命中要单独说明——「换一种说法说同一件事」必须可解释
            eq_hits = [g for g in fired if g.get("equiv_id")]
            if eq_hits:
                lines += ["### 委婉表达识别（语义等价）", "",
                          "| 结构 | 对应规则 | 识别到的说法 | 交易语境 | 为什么等价 |",
                          "|---|---|---|---|---|"]
                for g in eq_hits:
                    lines.append(
                        f"| {g['equiv_id']} {g.get('rule_desc','')} | {g.get('rule_id','')} | "
                        f"「{g.get('trigger','')}」 | 「{g.get('equiv_context','')}」 | "
                        f"{g.get('equiv_why','')} |")
                lines += ["", "> 委婉表达不含明文违规词，靠语用结构识别。"
                          "判定依据是「委婉标记 + 交易语境」共现，并经语义方向判定。", ""]
        if exempt:
            lines += ["### 已豁免的规则命中（留痕，供复核）", "",
                      "| 闸门 | 规则 | 命中内容 | 判定方向 | 豁免理由 |",
                      "|---|---|---|---|---|"]
            for g in exempt:
                rid = g.get("rule_id", "")
                desc = g.get("rule_desc", "")
                lines.append(
                    f"| {g['gate']} | {rid} {desc} | 「{g['trigger']}」 | "
                    f"{g.get('direction', '—')} | {g.get('exempt_reason', '')} |")
            lines += ["", "> 豁免 = 该次命中不成立（如药代正确地拒绝了违规要求）。",
                      "> 豁免留痕是复核的前提，不得静默跳过。", ""]

    if assessment["findings"]:
        lines += ["## 五、扣分点", ""]
        for f in assessment["findings"]:
            lines.append(f"- {f}")
        lines.append("")

    lines += ["## 六、能力短板诊断（GAP）", "",
              f"**{gap['diagnosis']}**", ""]
    if gap["by_error_type"]:
        lines += ["| 错误类型 | 次数 |", "|---|---|"]
        for k, v in gap["by_error_type"].items():
            lines.append(f"| {k} | {v} |")
        lines.append("")
    lines += ["**复训建议**：", ""]
    for r in gap["recommendations"]:
        lines.append(f"- {r}")
    lines += ["",
              "> 本诊断用于训练分配与能力提升，不作为人事处罚依据。",
              "> 本次全部内容属候选层，医学审核状态为 pending_medical_review，报告不作为最终评价依据。",
              ""]
    return "\n".join(lines)


# ============================================================
# 主流程
# ============================================================
def _run_feedback(user, plan, per_q, assessment, feedback, ctx):
    """
    跑复盘管道：采集 → 观察 → 差异 → 候选分流。

    ★ 只做「训练侧」的复盘：个性化复训候选自动产生。
      共享题库路径必须经人工审核，此处只生成待审候选。
    """
    import feedback_pipeline as F
    from knowledge_retrieval import KnowledgeBase
    from llm_provider import FactGuard

    segments = feedback.get("segments", [])
    d = F.DebriefRaw(
        user_id=user,
        segments=segments,
        scope=feedback.get("scope", "self_only"),
        raw_transcript=feedback.get("raw_transcript", ""),
        user_revised=feedback.get("user_revised"),
        pre_run_id=feedback.get("pre_run_id"),
    )
    try:
        d.validate()
    except F.DebriefValidationError as e:
        return {"error": e.code, "message": e.message, "detail": e.detail}

    kb = KnowledgeBase()
    guard = FactGuard(kb.fact_bundle("达伯舒", condition_id="D-NSCLC"))
    obs = F.structure_from_debrief(d, kb=kb)
    for o in obs:
        j = F.judge_medical_support(o, kb=kb, guard=guard)
        o.statement_is_medically_supported = j["statement_is_medically_supported"]
        o.support_refs = j["support_refs"]

    # 能力点匹配器：题目与复盘都是自由文本，靠它对上能力树
    matcher = F.SkillMatcher()

    # ★ 训练侧也反推能力点：题里没有结构化 skill_id，
    #   但题文本里有能力描述与疾病关键词，可匹配到能力点。
    plan_skill_ids = []
    for q in plan.get("questions", []):
        hits = matcher.match_ids(q.get("question", "") + " " +
                                 " ".join(q.get("exam_dimensions") or []), limit=3)
        for h in hits:
            if h not in plan_skill_ids:
                plan_skill_ids.append(h)

    mastery = {sid: True for sid in plan_skill_ids}   # 训练里答了的算覆盖
    cov = F.CoverageMap(obs, plan_skill_ids=plan_skill_ids).build(
        mastery_by_skill=mastery, skill_matcher=matcher)

    cands = []
    for e in cov["coverage_map"]:
        if e["gap_class"] in ("covered_not_mastered", "not_covered", "partial"):
            cands.append(F.GapCandidate(
                user_id=user, gap_class=e["gap_class"],
                title=f"补强：{e['text'][:40]}",
                detail="本次复盘显示该能力点未掌握",
                skill_id=e.get("skill_id"),
                source_debrief_id=d.debrief_id))
    routed = F.route_candidates(cands, plan_skill_ids=plan_skill_ids, total_users=1)

    store = F.FeedbackStore()
    store.put_debrief(d)
    store.put_observations(d.debrief_id, obs)
    store.put_coverage(d.debrief_id, cov)
    for c in routed:
        store.put_candidate(c)
    store.save()

    return {
        "debrief": d.to_dict(),
        "observations": [o.to_dict() for o in obs],
        "coverage": cov,
        "candidates": [c.to_dict() for c in routed],
        "personalized_only": True,
        "note": ("本次仅产生个性化复训候选；共享题库路径必须经人工审核发布，"
                 "系统不自动写入共享层。"),
    }


def run(user, disease, dimension, count, answers_file=None, channel="面访",
        llm=None, llm_provider_name=None, feedback=None):
    """
    llm=None     → 规则引擎医生（默认，零依赖、确定性）
    llm="vision" → VLM 医生（当前环境可用）
    llm="text"   → MiniMax 文本 API 医生（生产，需 MINIMAX_API_KEY）
    feedback     → 复盘段（V1.3 §2.1–2.5）。给定时跑完整复盘管道：
                   复盘采集 → 结构化观察 → 差异分析 → 候选分流
    """
    ctx = build_visit_context(disease, dimension, channel)
    cands = load_candidates(disease, dimension)
    if not cands:
        return {"error": f"找不到 {disease} / {dimension} 的候选考点"}
    plan = build_plan(ctx, cands, count)

    doctor = DoctorSim(ctx)
    if llm:
        try:
            from llm_doctor import LLMDoctorSim
            from llm_provider import get_provider
            prov = get_provider(llm_provider_name) if llm_provider_name else None
            doctor = LLMDoctorSim(ctx, provider=prov)
        except Exception as e:
            # 显式指定 provider 时不降级 —— 用户以为在用 A 实际跑的是 B 是最危险的
            if llm_provider_name:
                raise
            # 未指定时自动选择失败才降级，且必须显式告知
            print(f"[warn] LLM 医生不可用（{e}），已降级为规则引擎", file=sys.stderr)
            doctor = DoctorSim(ctx)
    rubric_doc = json.load(open(D8A, encoding="utf-8"))
    rubric = Rubric(rubric_doc)

    # 载入药代回答
    answers = {}
    if answers_file and os.path.exists(answers_file):
        for line in open(answers_file, encoding="utf-8"):
            line = line.strip()
            if line:
                d = json.loads(line)
                answers[d["qid"]] = d

    transcript, per_q = [], []
    for q in plan["questions"]:
        qid = q["qid"]
        transcript.append({"role": "医生", "text": doctor.opening(q["question"])})
        a = answers.get(qid, {}).get("answer", "")
        unanswered = not a
        if unanswered:
            a = ""
        transcript.append({"role": "药代", "text": a})
        if unanswered:
            # 未作答：不判分、不进分母、单独记录为「未作答」事件
            scores, gates, findings = {}, [], ["本轮未作答"]
            unscored = True
        else:
            scores, gates, findings, unscored = rubric.score_answer(a, q.get("rubric"), channel)
        per_q.append({"qid": qid, "answer": a, "scores": scores, "gates": gates,
                      "findings": findings, "question": q["question"], "unanswered": unanswered})
        if not unscored:
            fq = doctor.followup(q["question"], a, 1, qid)
            transcript.append({"role": "医生", "text": fq})
            transcript.append({"role": "药代", "text": "（追问后补答）" + a[:60]})
        else:
            transcript.append({"role": "医生", "text": f"（本题因不可评分未追问）"})
    transcript.append({"role": "医生", "text": doctor.closing(len(plan["questions"]))})

    assessment = rubric.synthesize(per_q, channel, user_id=user)
    events = build_events(per_q, plan)
    gap = build_gap_profile(events, user)
    report = build_report(ctx, plan, transcript, assessment, events, gap)

    # D08a-3 资历上调：记录本次等级，更新两轨权重与连续达标计数
    proficiency, escalated = _decisions.record_outcome(user, assessment["level"])
    assessment["proficiency"] = {
        "streak": proficiency["streak"],
        "medical_weight": proficiency["medical_weight"],
        "communication_weight": proficiency["communication_weight"],
        "escalated_this_session": escalated,
        "rule": f"连续 {_decisions.ESCALATION['streak_required']} 次达标 "
                f"+{_decisions.ESCALATION['step_pp']}pp，medical 上限 "
                f"{_decisions.ESCALATION['medical_cap']}%",
    }

    # ---------- 复盘管道（V1.3 §2.1–2.5）----------
    fb_out = None
    if feedback:
        fb_out = _run_feedback(user, plan, per_q, assessment, feedback, ctx)

    return {
        "visit_context": ctx,
        "prediction_plan": plan,
        "feedback": fb_out,
        "session": {"transcript": transcript, "boundary_note": doctor.boundary_note()},
        "llm": {
            "enabled": bool(llm),
            "provider": (doctor.provider.name if hasattr(doctor, "provider") else None),
            "guard": (doctor.guard_report() if hasattr(doctor, "guard_report")
                      else {"total": 0, "items": []}),
            "trace": getattr(doctor, "trace", []),
        },
        "assessment": assessment,
        "error_events": events,
        "gap_profile": gap,
        "proficiency": proficiency,
        "report_md": report,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default="demo")
    ap.add_argument("--disease", default="D-NSCLC")
    ap.add_argument("--dim", default="DF")
    ap.add_argument("--count", type=int, default=3)
    ap.add_argument("--answers")
    ap.add_argument("--channel", default="面访")
    ap.add_argument("--out", default=None)
    ap.add_argument("--llm", action="store_true",
                    help="启用 LLM 驱动的医生（默认用规则引擎）")
    ap.add_argument("--llm-provider", default=None,
                    choices=["minimax_text", "vision_text", "mock"],
                    help="指定 LLM provider；指定但不可用时直接报错，不静默降级")
    ap.add_argument("--feedback", default=None,
                    help="复盘段 JSON 文件（V1.3 §2.1–2.5）：跑完整复盘管道")
    a = ap.parse_args()

    fb = None
    if a.feedback:
        fb = json.load(open(a.feedback, encoding="utf-8"))
    r = run(a.user, a.disease, a.dim, a.count, a.answers, a.channel,
            llm=("1" if a.llm else None), llm_provider_name=a.llm_provider,
            feedback=fb)
    if "error" in r:
        print("❌", r["error"])
        return
    print(r["report_md"])
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            fh.write(r["report_md"])
        json.dump({k: v for k, v in r.items() if k != "report_md"},
                  open(a.out.replace(".md", ".json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        print(f"\n已写入 {a.out}")


if __name__ == "__main__":
    main()
