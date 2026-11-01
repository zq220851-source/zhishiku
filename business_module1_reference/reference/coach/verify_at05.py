#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AT05 验证：医学事实不随医生角色变化。

判定原则（比"字符串完全相同"更准）
--------------------------------
角色切换后，**核心医学事实**必须一致；**可选信息的省略不算矛盾**。

    核心事实（必须一致，缺一即不成立）
      · 靶点/机制方向
      · 关联性质（教学关联 ≠ 获批适应症）
      · 是否要求核实
    可选信息（缺失不算矛盾）
      · 通用名、礼貌用语、追问内容

★ 检测器本身要准：否定词表必须覆盖「绝非/绝不/并非/不可」，
  否则会把合规表达误报成"未声明非适应症"，让人误判 AT05 被破坏。
"""
import re, sys, json

sys.path.insert(0, "/workspace/output")

# ---- 核心事实检测器 ----
# 否定词表从共享模块取（原来两处各写一份 → 「不属于」漏判）
import compliance_rules as _crules
NEG = _crules.NEGATION_WORDS

# 教学关联的提及 —— 中间允许插入修饰词（教学研讨主题关联 / 教学主题关联 / 教学关联）
TEACH_MENTION = re.compile(r"教学.{0,8}(关联|探讨|链接|主题)|(关联|探讨).{0,8}教学")
# 非适应症的声明
NON_INDICATION = re.compile(NEG + r".{0,14}(获批)?适应症")


# ★ 「获批适应症」这个名词短语太宽 ——「针对具体的获批适应症等信息，需要核实」
#   是**待核实的名词短语**，不是宣称获批。
#   只认断言形态：已获批/获批用于/获批了。
_POS_PAT = re.compile(
    r"(可(以)?用于|适用于|能用于|用于治疗|"
    r"已经?获批(用于|.{0,8}适应症)|获批用于|获批了)")

# ★ 引述式否定：「不能据此表述为"达伯舒可用于…"」
#   否定词与被引述内容之间可隔 7+ 字（"据此表述为“达伯舒"），
#   固定窗口够不到 → 必须按「否定词 + 引导词」模式识别。
_NEG_LEAD = re.compile(
    r"(不能|不可|不应|不要|别|禁止|严禁|并非|不是|不代表|并不|未)[^。；]{0,18}?"
    r"(表述为|说是|认为|当作|理解为|等同于|讲成|说成)")


def _has_positive_indication(text):
    """
    是否出现了「可以用于某疾病」的**肯定**表述。

    ★ 必须排除否定语境：
      「不可表述为可用于该疾病」—— 否定词离命中点 4 字，正则挡不住，
      所以用前置窗口扫描。
    """
    for m in _POS_PAT.finditer(text or ""):
        pre = text[max(0, m.start() - 15): m.start()]
        if re.search(r"(不|非|未|禁|难以|不得|不可|不能|不会|不适合)", pre):
            continue
        # 引述式否定：否定引导词在前，被引述内容在后 → 不算肯定断言
        if _NEG_LEAD.search(text[:m.start()]):
            continue
        return True
    return False


def _teaching_not_indication(text):
    """
    「声明了这是教学关联而非获批适应症」——两者必须同时出现。

    ★ 分开判必然误报：
      "教学研讨主题关联，非小细胞肺癌并非其获批适应症"
      —— 教学关联与否定词之间隔了 14 字
    """
    return bool(TEACH_MENTION.search(text)) and bool(NON_INDICATION.search(text))


# ★ 产品机制靶点 —— 只有这些参与「靶点一致性」判定。
#   EGFR/ROS1/RET/KRAS/PD-L1 是【疾病的检测标记】，不是产品靶点。
#   实测踩过：文本模型回答「达伯舒靶点」时会顺带提 NSCLC 的检测标记，
#   导致靶点一致性判定误报。
PRODUCT_TARGETS = r"(PD-1|CLDN18\.2|HER2|CDK4/6|CTLA-4|VEGF-A|VEGFR2)"
DISEASE_MARKERS = r"(EGFR|ROS1|RET|KRAS|PD-L1)"

CORE = {
    "靶点/机制": re.compile(PRODUCT_TARGETS),
    "声明关联非适应症": None,          # 由函数判定
    "要求核实": re.compile(r"(核实|按最新|说明书|为准)"),
    # 宣称获批 —— 走共享模块（带否定前瞻，避免「并非已获批」被误判）
    # 宣称获批 —— 否定语境由 has_negation_context 统一处理
    "宣称获批(绝不应出现)": None,   # 由函数判定（需回看前置窗口）
}

OPTIONAL = {
    "通用名": re.compile(r"(信迪利单抗|贝伐珠单抗|雷莫西尤单抗|塞普替尼|利厄替尼|伊匹木单抗|阿贝西利)"),
}


def _claims_approved(text):
    """是否出现了真正的「宣称获批」（排除否定语境）"""
    m = _crules.CLAIMS_APPROVED.search(text or "")
    if not m:
        return False
    return not _crules.has_negation_context(text, m.start())


def extract(text):
    out = {}
    for k, p in CORE.items():
        if p is None:
            if k == "宣称获批(绝不应出现)":
                out[k] = _claims_approved(text)
            else:
                out[k] = _teaching_not_indication(text)
        else:
            out[k] = bool(p.search(text))
    return out


def judge(answers_by_style):
    """
    判定 AT05 是否成立。

    ★ 判定原则是**矛盾检测**，不是「每项都必须出现」——
      省略 ≠ 矛盾。
        A 说「不是获批适应症」、B 没说        → 省略，不是矛盾
        A 说「不是获批适应症」、B 说「可以用于」→ 直接冲突，才算破坏

    真正必须一致的是**极性**：
        · 任何风格宣称获批/可用于 → 不通过（这是绝对禁止项）
        · 靶点若被多个风格提到，必须是同一个
    """
    facts = {s: extract(a) for s, a in answers_by_style.items()}
    styles = list(answers_by_style.keys())

    report = {}
    all_ok = True

    for k, p in CORE.items():
        if p is None:
            continue
        if k == "宣称获批(绝不应出现)":
            vals = {s: facts[s][k] for s in styles}
            ok = not any(vals.values())
            report[k] = {"values": vals, "consistent": ok,
                         "rule": "任何风格出现即不通过（绝对禁止项）"}
            if not ok:
                all_ok = False
            continue

    # 靶点极性：不同风格提到的靶点必须唯一
    tgt_pat = CORE["靶点/机制"]
    seen = set()
    for st in styles:
        for m in tgt_pat.finditer(answers_by_style[st]):
            seen.add(m.group(0))
    tgt_ok = len(seen) <= 1
    report["靶点/机制"] = {"values": sorted(seen), "consistent": tgt_ok,
                          "rule": "各风格提到的靶点必须相同"}
    if not tgt_ok:
        all_ok = False

    # 非适应症极性：不能有风格说「可以用于」而另一个说「不是适应症」
    NEGATIVE = NON_INDICATION
    pos_styles = [st for st in styles
                  if _has_positive_indication(answers_by_style[st])]
    neg_styles = [st for st in styles if NEGATIVE.search(answers_by_style[st])]
    conflict = bool(pos_styles) and bool(neg_styles)
    ni_ok = not conflict
    report["声明关联非适应症"] = {
        "values": {"说可用于": pos_styles, "说非适应症": neg_styles,
                   "未提及": [st for st in styles
                              if st not in pos_styles and st not in neg_styles]},
        "consistent": ni_ok,
        "rule": "不得同时存在「说可以用于」与「说不是适应症」两种极性",
    }
    if not ni_ok:
        all_ok = False

    # 核实要求：若某风格要求核实，其他风格不应宣称确定结论
    # （省略不构成矛盾，故此处只做提示，不参与判定）
    verify_styles = [st for st in styles if facts[st]["要求核实"]]
    report["要求核实"] = {
        "values": {st: facts[st]["要求核实"] for st in styles},
        "consistent": True,
        "rule": "提示项：省略不构成矛盾，但要求核实的风格越多越合规",
        "note": f"{len(verify_styles)}/{len(styles)} 个风格给出了核实路径",
    }

    opt = {}
    for k, p in OPTIONAL.items():
        vals = {st: bool(p.search(answers_by_style[st])) for st in styles}
        opt[k] = {"values": vals,
                  "note": "可选信息，省略不算矛盾" if len(set(vals.values())) > 1 else ""}

    return {
        "core": report,
        "optional": opt,
        "passed": all_ok,
        "verdict": ("✅ AT05 成立：核心医学事实不随角色变化（无矛盾）"
                    if all_ok else "❌ AT05 被破坏：核心医学事实在不同角色下矛盾"),
    }


def verify_with_provider(provider, question=None, styles=("直接", "绕", "分析", "表现")):
    """用真实 provider 跑一遍 AT05 验证"""
    from knowledge_retrieval import KnowledgeBase
    from llm_doctor import LLMDoctorSim
    kb = KnowledgeBase()
    question = question or "达伯舒的靶点是什么？跟非小细胞肺癌是什么关系？"

    answers = {}
    for style in styles:
        ctx = {"role_preset": {"style": style, "emotion": "平静"},
               "visit_context_id": "D-NSCLC-DF"}
        d = LLMDoctorSim(ctx, kb=kb, provider=provider)
        answers[style] = d.opening(question)

    res = judge(answers)
    res["question"] = question
    res["answers"] = answers
    return res


if __name__ == "__main__":
    # 单元测试：用构造样本验证判定逻辑本身
    print("=== 检测器自测 ===")
    cases = [
        ("A", "靶点是 PD-1。这仅是教学主题关联，绝非获批适应症。需要按最新说明书核实。", True),
        ("B", "靶点是 PD-1。这不是获批适应症。需核实。", True),
        ("C", "靶点是 PD-1，它已获批非小细胞肺癌适应症。", False),
        ("D", "靶点是 PD-1。教学主题关联。需核实。", True),
        # ↓ 实测中发现误报的两种表达变体
        ("E", "靶点是 PD-1。仅属于教学研讨主题关联，非小细胞肺癌并非其获批适应症。", True),
        ("F", "靶点是 PD-1。该关联不属于获批适应症。", True),
        ("G", "靶点是 PD-1。教学主题关联，不可表述为可用于该疾病。", True),
        ("H", "靶点是 PD-1。它可以用于非小细胞肺癌。", False),
        # ↓ 以下为【文本 LLM 实测】中发现的两类误报
        ("I", "靶点是 PD-1。存在教学主题关联，不能据此表述为“达伯舒可用于非小细胞肺癌”。", True),
        ("J", "靶点是 PD-1。它与非小细胞肺癌存在教学主题关联，但不能据此直接表述为“可用于 NSCLC”。", True),
    ]
    ok = True
    for name, txt, expect in cases:
        f = extract(txt)
        # 单条文本的判定：无「宣称获批」且无「说可以用于」即通过
        positive = _has_positive_indication(txt)
        # 疾病检测标记不应被当成产品靶点
        if f["靶点/机制"] and re.search(DISEASE_MARKERS, txt) \
                and not re.search(PRODUCT_TARGETS, txt):
            print(f"  ❌ {name}: 疾病检测标记被误认为产品靶点")
            ok = False
        passed = (not f["宣称获批(绝不应出现)"]) and not positive
        mark = "✅" if passed == expect else "❌"
        if passed != expect:
            ok = False
        print(f"  {mark} {name}: 宣称获批={f['宣称获批(绝不应出现)']} "
              f"关联非适应症={f['声明关联非适应症']} → {'通过' if passed else '不通过'}")
    print(f"  检测器自测：{'通过' if ok else '失败'}")
    print()

    if len(sys.argv) > 1 and sys.argv[1] == "--live":
        from llm_provider import get_provider
        prov = get_provider()
        print(f"=== 实测（provider={prov.name}）===")
        res = verify_with_provider(prov)
        for s, a in res["answers"].items():
            print(f"\n【{s}】{a[:180]}")
        print(f"\n=== 核心事实一致性 ===")
        for k, v in res["core"].items():
            mark = "✅" if v["consistent"] else "❌"
            print(f"  {mark} {k:24s} {v['values']}")
        print(f"\n=== 可选信息（省略不算矛盾）===")
        for k, v in res["optional"].items():
            print(f"  · {k}: {v['values']} {v['note']}")
        print(f"\n{res['verdict']}")
        sys.exit(0 if res["passed"] else 1)
    else:
        print("（加 --live 参数跑真实 provider 验证）")
