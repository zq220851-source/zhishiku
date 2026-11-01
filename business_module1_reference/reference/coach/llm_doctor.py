#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM 驱动的医生 —— 接入 medrep_coach 的 DoctorSim。

设计要点
--------
1. **LLM 负责「像人说话」**，不负责医学事实。
   医学事实来自 knowledge_retrieval 的 fact bundle，经提示交给 LLM，
   再由 FactGuard 独立校验 —— 三层都不信任模型的自述。

2. **AT05 的落地方式**：角色（风格/情绪）只进 prompt 的「医生角色」段，
   **不进事实段**。所以换角色时 fact bundle 完全不变。
   → 可用「同问题、不同风格，医学事实片段必须一致」来实测验证。

3. **降级链**：LLM 不可用 → 规则引擎 DoctorSim（现有实现）。
   任何一层失败都不应让训练流程崩掉。

4. **每次调用都留痕**：prompt、原始输出、校验问题、清洗后输出 ——
   训练产品的每一次 AI 生成都要可复核。
"""
import os, sys, json, re

from config import BASE, PATHS
sys.path.insert(0, BASE)

from knowledge_retrieval import KnowledgeBase
from llm_provider import PromptBuilder, FactGuard, get_provider, MockProvider


class LLMDoctorSim:
    """
    LLM 驱动的医生。接口与 medrep_coach.DoctorSim 保持一致，
    以便在引擎里可插拔替换。
    """

    def __init__(self, context, kb=None, provider=None, trace=None):
        self.ctx = context
        self.kb = kb or KnowledgeBase()
        self.provider = provider or get_provider()
        self.trace = trace if trace is not None else []
        self.guard_hits = []          # 校验拦下的问题（供报告展示）

    # ---------- 风格映射 ----------
    _STYLE_MAP = {
        "直接": ("driven", "直奔结果，要一个明确结论"),
        "绕": ("benevolent", "温和，会关心你的处境"),
        "分析": ("analytical", "先要数据与逻辑，问「依据是什么」"),
        "表现": ("expressive", "爱互动，喜欢有来有回"),
    }

    def _profile(self):
        rp = self.ctx.get("role_preset", {})
        style = rp.get("style", "直接")
        key, desc = self._STYLE_MAP.get(style, self._STYLE_MAP["直接"])
        return {
            "communication_style": {"style_type": key},
            "objection_profile": {"primary_type": rp.get("objection") or
                                   rp.get("primary_objection")},
            "resistance_style": {"form": rp.get("resistance")},
        }, desc

    # ---------- 检索 ----------
    def _bundle(self, question):
        cid = self.ctx.get("condition_id") or self.ctx.get("disease_id")
        # 从 context 推疾病
        if not cid:
            m = re.search(r"(D-[A-Z]+)", str(self.ctx.get("visit_context_id", "")))
            cid = m.group(1) if m else None
        return self.kb.fact_bundle(question, condition_id=cid)

    # ---------- 开场 ----------
    def opening(self, question):
        bundle = self._bundle(question)
        prof, _desc = self._profile()
        pb = PromptBuilder(bundle, doctor_profile=prof)
        prompt = pb.build()
        text, meta = self.provider.generate(prompt)
        issues, cleaned = FactGuard(bundle).check(text)
        self.trace.append({
            "stage": "opening", "question": question,
            "prompt": prompt, "raw": text, "cleaned": cleaned,
            "issues": issues, "meta": meta,
            "fact_ids": [f["id"] for f in bundle["facts"]],
        })
        if issues:
            self.guard_hits.extend(issues)
        return cleaned or question

    # ---------- 追问 ----------
    def followup(self, q, answer, turn, qid=None):
        """LLM 追问：医生针对药代回答继续问。医学事实仍受检索层约束。"""
        tag = f"[{qid}] " if qid else ""
        question_text = str(q).split("下列回应最合适的是？")[0].strip()
        bundle = self._bundle(question_text)
        prof, _desc = self._profile()
        pb = PromptBuilder(bundle, doctor_profile=prof)
        pb.rubric_hint = (
            f"这是一次拜访的第 {turn} 轮追问。代表刚才的回答是：「{answer[:120]}」。"
            "请提出下一个更具体、更难回避的问题（可直接引用代表刚才的说法）。"
            "不要自己回答这个问题——你是医生。")
        prompt = pb.build()
        text, meta = self.provider.generate(prompt)
        issues, cleaned = FactGuard(bundle).check(text)
        self.trace.append({
            "stage": "followup", "turn": turn, "qid": qid,
            "rep_answer": answer, "prompt": prompt, "raw": text,
            "cleaned": cleaned, "issues": issues, "meta": meta,
        })
        if issues:
            self.guard_hits.extend(issues)
        if not cleaned:
            # 规则兜底：与原引擎行为一致
            return (f"{tag}那您刚才说的这一点，"
                    f"如果换成我这个具体病人情况，您会怎么建议？"
                    f"（第 {turn} 轮追问 · 常规深挖）")
        return f"{tag}{cleaned}"

    def closing(self, turns):
        return f"（结束本次交流，共 {turns} 轮）医生：好，今天先到这儿。"

    def boundary_note(self):
        """AT05 验证锚点：医学事实不随情绪变化"""
        rp = self.ctx.get("role_preset", {})
        return {
            "style": rp.get("style"),
            "emotion": rp.get("emotion"),
            "llm_provider": self.provider.name,
            "guard_issues": len(self.guard_hits),
            "note": ("医学事实由检索层锁定，不进入角色提示；"
                     "角色只影响措辞与提问顺序"),
        }

    def guard_report(self):
        """FactGuard 拦截汇总——写进训练报告，便于复核 AI 生成质量"""
        if not self.guard_hits:
            return {"total": 0, "items": [], "note": "本次生成未触发事实校验问题"}
        return {
            "total": len(self.guard_hits),
            "items": self.guard_hits,
            "note": ("这些是 AI 生成内容中越出检索范围或触碰合规红线的部分，"
                     "已被 FactGuard 替换为安全拒答"),
        }


# ============================================================
# AT05 验证：同问题不同角色，医学事实必须一致
# ============================================================
def verify_at05_fact_invariance(kb=None, provider=None):
    """
    验证「医学事实不随角色情绪变化」。

    方法：同一个医学问题，用 4 种医生风格各跑一次，
          比较各自 fact bundle 里的医学事实串是否完全相同。

    ★ 注意：这里比较的是**送进模型的上下文**，不是模型输出——
      模型措辞可以变，但模型能看到的医学依据必须一字不差。
    """
    kb = kb or KnowledgeBase()
    question = "达伯舒的靶点是什么？跟非小细胞肺癌是什么关系？"
    results = []
    for style in ["直接", "绕", "分析", "表现"]:
        ctx = {"role_preset": {"style": style, "emotion": "平静"},
               "visit_context_id": "D-NSCLC-DF"}
        d = LLMDoctorSim(ctx, kb=kb, provider=provider or MockProvider())
        bundle = d._bundle(question)
        med_facts = [f["claim"] for f in bundle["medical_usable"]]
        results.append({"style": style, "med_facts": med_facts})

    base = results[0]["med_facts"]
    same = all(r["med_facts"] == base for r in results)
    return {
        "question": question,
        "styles": [r["style"] for r in results],
        "identical": same,
        "fact_count": len(base),
        "facts": base,
        "verdict": "✅ AT05 成立：医学事实不随角色变化" if same
                   else "❌ AT05 被破坏：不同角色的医学事实不一致",
    }


if __name__ == "__main__":
    kb = KnowledgeBase()
    r = verify_at05_fact_invariance(kb)
    print(f"问题：{r['question']}")
    print(f"角色：{r['styles']}")
    print(f"医学事实条数：{r['fact_count']}")
    for f in r["facts"]:
        print(f"  · {f[:96]}")
    print(f"\n{r['verdict']}")

    # provider 可用性
    print("\n=== Provider 可用性 ===")
    for name in ["minimax_text", "vision_text", "mock"]:
        p = get_provider(name)
        print(f"  {name:16s} available={p.available()}")
    print(f"  自动选择 → {get_provider().name}")
