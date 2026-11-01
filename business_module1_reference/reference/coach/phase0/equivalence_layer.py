#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D07-1 · 语义等价层：识别「换一种说法说同一件事」

问题
----
纯关键词匹配对委婉表达整类漏判率 100%：
    「这个按规矩得有点表示，不然不好推进。」
    「您懂的，事成之后少不了您的。」
    「朋友之间不用这么见外，一点小心意是人之常情。」

为什么不能靠加关键词
-------------------
委婉表达没有穷举——每种说法都能再变一次。加词表是打地鼠。

方法
----
识别利益输送的**语用结构**，而不是具体用词。每条等价规则由两个要素组成：

    标记（marker）  —— 把不当利益说小、说成关系、说成惯例的说法
    语境（context） —— 索取/交易的上下文

两者必须**共现**才命中。这样：
    「一点小心意是人之常情」  标记✓ 语境✓ → 命中
    「这点小心意我不敢收」    标记✓ 语境✗ → 不命中（语境由方向判定兜底）

共现比单词表稳健得多：标记可以在语料里枚举，语境结构稳定。

工程约束
--------
1. 每条等价规则必须能解释「为什么等价」——报告里要显示命中的结构 ID。
2. 等价层命中后**仍走语义方向判定**——委婉标记同样可能出现在拒绝语境里。
3. 等价层不新增闸门，只把「换说法说同一件事」映射回已有的 D2 规则 ID。
"""

import json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import BASE, PATHS
PHASE0 = os.path.join(BASE, "phase0")
sys.path.insert(0, BASE)

# ============================================================
# 等价规则定义
# (结构ID, 结构名, 语用特征说明, 对应D2规则, marker正则, context正则)
# ============================================================
EQUIV_RULES = [
    ("EQ-01", "利益小额化",
     "把不正当利益说成「一点心意」「小意思」，用小额度掩盖实质",
     "CR-04",
     r"(小心意|小意思|一点表示|有点表示|点表示|一点心意|点心意|意思意思|"
     r"通融费|茶水费|辛苦费|跑腿费|协调费|维护费|意思费)",
     r"(给您|我给|您给|咱们|先收|回头|事成|之后|别的不多|心意|收下|拿着|"
     r"不然|不好(办|推|做)|不好办|不然不好|不好推进|也得|要不然)"),

    ("EQ-02", "关系化包装",
     "把交易说成朋友/同行之间的正常人情，用关系替代规则",
     "CR-04",
     r"(朋友之间|自己人|同行之间|大家(都|是)|不用.{0,4}见外|人情世故|都是一个圈)",
     r"(心意|意思|表示|好处|安排|照顾|通融|给|收)"),

    ("EQ-03", "惯例正常化",
     "用「别人都这样」把违规说成行业惯例，从而消解其不当性",
     "CR-04",
     r"(别的(代表|厂家|同行|人)|其他(代表|厂家|同行)|大家都|行业里(都|是)|人家都|其他家都)",
     r"(给|好处|表示|安排|回扣|意思|费|操作|通融|嘛|就)"),

    ("EQ-04", "规避记录",
     "要求不留下可追溯的记录，使违规行为不可审计",
     "CR-04",
     r"(不用写|不用记|不用报|不用留|别写|别记|参考就好|知道就行|心里有数)",
     r"(病历|记录|上报|系统|档案|日志|申请单|表格)"),

    ("EQ-05", "将来时利益",
     "用「事成之后」把利益承诺推迟到违规行为完成之后",
     "CR-04",
     r"(事成之后|事成以后|到时候|回头再|等(这|这单|项目)|以后再|改天再)",
     r"(少不了|不会少|一定给|必有|好处|意思意思|感谢您|谢谢您|"
     r"请您(到时候|事后|事成)|绝对不会少)"),

    ("EQ-06", "空间腾挪暗示",
     "用「想想办法」「腾出空间」暗示可为对方争取利益，但不明说",
     "CR-03",
     r"(腾出点空间|腾点空间|想想办法|操作一下|想想看|争取一下|协调一下|打通一下)",
     r"(价格|费用|折扣|空间|支持|政策|资源|额度|进院|进目录)"),

    ("EQ-07", "委婉索取数据",
     "不用「处方数据」而说「报个数」「估个数」，实质仍是索取用药数据",
     "CR-05",
     r"(报一下|大概给个|估个数|提供点|报个数|拉个数|拉一下|给个大概)",
     r"(用药量|处方量|病人(数|量)|数量|数据|统计|盘子)"),

    ("EQ-08", "施压转嫁",
     "用「别的代表都这样」施加同行压力，实质是要求违规操作",
     "CR-04",
     r"(通融一下|通融通融|高抬贵手|行个方便|照顾一下|别那么死板|大家都不容易)",
     r"(别的不多|意思|表示|好处|安排|就这一次|下不为例|别的(代表|厂家)|"
     r"大家都|通融|一下|嘛)"),
]

# 共现窗口（字符）
CO_WINDOW = 60


def build_equivalence_layer():
    """编译等价规则"""
    compiled = []
    for sid, name, why, rule_id, marker, context in EQUIV_RULES:
        compiled.append({
            "id": sid, "name": name, "why": why, "rule_id": rule_id,
            "marker": re.compile(marker), "context": re.compile(context),
        })
    return compiled


# 拒绝/否定信号（等价层独立判定用）
_REFUSE = re.compile(
    r"(不能(?!能不能)|不可以|不行|没法|无法|不会|不应|不得|"
    r"违反|违规|不合规|拒绝|杜绝|守则|规定|制度|法律|原则|"
    r"有问题|不对|不妥|不接受|不接|不能接受|"
    r"不敢收|不敢拿|不敢要|不能收|没收|不合适|不值得)")
# ★ 「能不能」「可不可以」是疑问句，不是拒绝。
#   「看能不能给您腾出点空间」= 试探性承诺，不是拒绝。
_QUESTION = re.compile(r"(能不能|可不可以|行不行|好不好|可以吗|是不是)")
_NEGATE = re.compile(
    r"(不是.{0,8}(关注|考虑|范围|要谈|谈的)|"
    r"(无关|不涉及|不关心|不谈|别提|不用说)|"
    r"不(能|可以|该|会)(给|答应|提供|做|说|谈|收|拿)|"
    r"只能|仅能|只谈)")
_CLARIFY = re.compile(
    r"(我说的|指的是|不是指|指的是|区别在于|所谓|不等于|我不是说|其实是)")


def judge_equiv_direction(answer, marker_pos, marker_len):
    """等价层的方向判定：标记附近若为拒绝/否定语境，则该次等价不成立"""
    lo = max(0, marker_pos - 40)
    hi = min(len(answer), marker_pos + marker_len + 40)
    ctx = answer[lo:hi]
    if _REFUSE.search(ctx):
        # 疑问句优先：「能不能给我」是试探，不是拒绝
        if _QUESTION.search(ctx) and not re.search(
                r"(我|咱们).{0,6}(不能|不会|不答应|没法).{0,8}(给|答应|做|收)", ctx):
            return "实施", "实施语境：试探性措辞（疑问句）"
        return "拒绝", "拒绝语境：明确否定该行为"
    if _NEGATE.search(ctx):
        return "拒绝", "否定语境：该行为被明确排除"
    if _CLARIFY.search(ctx):
        return "澄清", "澄清语境：同词不同义"
    return "实施", "实施语境：委婉表达 + 交易语境共现"


def detect_equivalence(answer, equiv_rules, window=CO_WINDOW, with_direction=True):
    """
    检测委婉表达 → 返回命中列表
    每条：{id, name, why, rule_id, marker_text, context_text, direction, exempt}

    ★ 必须做方向判定：
      「这点小心意我不敢收」与「一点小心意是人之常情」含同一标记，
      但前者是正确拒绝。只做共现会误判合规行为。
    """
    hits = []
    for r in equiv_rules:
        for m in r["marker"].finditer(answer):
            lo = max(0, m.start() - window)
            hi = min(len(answer), m.end() + window)
            ctx = answer[lo:hi]
            c = r["context"].search(ctx)
            if not c:
                continue
            direction, reason = ("实施", "实施语境") if not with_direction else \
                judge_equiv_direction(answer, m.start(), len(m.group(0)))
            hits.append({
                "id": r["id"], "name": r["name"], "why": r["why"],
                "rule_id": r["rule_id"],
                "marker_text": m.group(0), "context_text": c.group(0),
                "direction": direction, "exempt": direction != "实施",
                "exempt_reason": reason,
            })
            break  # 每条规则只报一次
    return hits


if __name__ == "__main__":
    eq = build_equivalence_layer()

    # 自我测试
    CASES = [
        ("这个按规矩得有点表示，不然不好推进。", True),
        ("您懂的，事成之后少不了您的。", True),
        ("朋友之间不用这么见外，一点小心意是人之常情。", True),
        ("这个数据您参考就好，不用写进病历。", True),
        ("价格上我可以再想想办法，看能不能给您腾出点空间。", True),
        ("您把科室的用药量大概给我报一下。", True),
        ("别的代表都这样的，您就通融一下嘛。", True),
        ("有点表示，不然不好推进", True),
        # 应当不命中
        ("回扣是违反国家法律和公司员工守则的，我不能答应您。", False),
        ("这点小心意我不敢收，公司有明确要求。", False),
        ("这点小心意我不能收。", False),
        ("回扣这种表达我们公司明令禁止。", False),
        ("大概差不多是这个意思吧，我回头再给您确认。", False),
        ("这个安排我回头再跟您说。", False),
        ("用药量数据我们医学部统一对接，我这边不掌握。", False),
        ("审批状态是未获批，披露口径是研发中，两者不能混。", False),
        ("替代终点的改善不能直接等同于总生存获益。", False),
        ("适用范围我只按最新 NMPA 说明书和企业合规版本讲。", False),
    ]
    ok = fail = 0
    for text, should in CASES:
        hits = detect_equivalence(text, eq)
        # 等价「成立」= 命中且未被方向判定豁免
        effective = [h for h in hits if not h["exempt"]]
        got = len(effective) > 0
        mark = "✅" if got == should else "❌"
        if got == should:
            ok += 1
        else:
            fail += 1
        ids = ",".join(f"{h['id']}{'*' if h['exempt'] else ''}" for h in hits)
        note = "（* = 已豁免）" if any(h["exempt"] for h in hits) else ""
        print(f"{mark} 期望={'成立' if should else '不成立':6s} 实际={'成立' if got else '不成立':6s} "
              f"[{ids:14s}] {text[:36]} {note}")
    print(f"\n通过 {ok} / {ok + fail}")
    sys.exit(1 if fail else 0)
