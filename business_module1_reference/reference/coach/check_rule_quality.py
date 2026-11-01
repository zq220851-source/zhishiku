#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
合规规则质量检查 —— 防止正则规则静默失效。

真实踩过的坑
------------
1. **尾随 `|`** → 产生空匹配分支 → 任何文本都命中该规则。
   当时的症状：CR-05「统方/处方数据」在完全无关的句子上也命中，
   一旦进入评分，会把正常回答误判成合规红线。
2. **括号不平衡** → 整个模块 import 失败。
3. **规则过宽** → 例如「我保证」把「我保证能进院」也算进承诺疗效。

所以规则必须可自动校验，不能靠人眼扫。

用法：python3 check_rule_quality.py
"""
import re, sys, os

from config import BASE, PATHS
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "phase0"))

ok = True


def bad(msg):
    global ok
    ok = False
    print(f"❌ {msg}")


def good(msg):
    print(f"✅ {msg}")


def check_module(mod_name):
    import importlib
    m = importlib.import_module(mod_name)
    print(f"\n=== {mod_name} ===")

    rules = getattr(m, "COMPILED_RULES", None)
    if not rules:
        print("（该模块无 COMPILED_RULES，跳过）")
        return

    # 1) 空匹配 —— 最危险：任何文本都会命中
    empties = []
    for rid, gate, desc, p in rules:
        m1 = p.search("")
        m2 = p.search("这是一句普通的话，没有任何关键词")
        if m1 or m2:
            empties.append((rid, (m1 or m2).group(0)))
    if empties:
        for rid, hit in empties:
            bad(f"{rid} 可匹配空串/无关文本（命中 {hit!r}）——"
                f"通常是尾随 '|' 造成的空匹配分支")
    else:
        good(f"无空匹配规则（{len(rules)} 条全部只匹配相关文本）")

    # 2) 尾随 |
    trailing = [rid for rid, _g, _d, p in rules if p.pattern.rstrip().endswith("|")]
    if trailing:
        bad(f"尾随 '|' 的规则：{trailing}")
    else:
        good("无尾随 '|'")

    # 3) 括号平衡（编译成功即通过，但显式检查更清楚）
    unbalanced = []
    for rid, _g, _d, p in rules:
        try:
            re.compile(p.pattern)
        except re.error as e:
            unbalanced.append((rid, str(e)))
    if unbalanced:
        for rid, e in unbalanced:
            bad(f"{rid} 正则语法错误：{e}")
    else:
        good("全部规则语法正确")

    # 4) 规则 ID 唯一
    ids = [rid for rid, _g, _d, _p in rules]
    dup = {i for i in ids if ids.count(i) > 1}
    if dup:
        bad(f"重复的规则 ID：{dup}")
    else:
        good(f"规则 ID 唯一（{len(ids)} 条）")

    # 5) 每条规则都有闸门归属与描述
    missing = [rid for rid, g, d, _p in rules if not g or not d]
    if missing:
        bad(f"缺少闸门归属或描述的规则：{missing}")
    else:
        good("每条规则都有闸门归属与描述")

    # 6) 命中样例 —— 每条规则至少要能被一个正例命中
    SAMPLES = {
        "CR-01": "我保证这个肯定有效",
        "CR-02": "这个已经获批用于非小细胞肺癌了",
        "CR-03": "我保证能进你们医院目录",
        "CR-04": "您给我点好处，我帮您推动进院",
        "CR-05": "您把科室的用药量大概给我报一下",
        "CR-06": "我是最好的、唯一的",
        "CR-07": "那家产品数据都是造的",
        "CR-08": "您多开点，年底我给您申请奖励",
        "BR-01": "这个在研的药物现在临床都可以用了",
        "BR-02": "研究里 PFS 改善了，那生存肯定也能改善",
        "BR-03": "这类病人用这个药是最合适的选择",
        "BR-04": "按 200mg 每次每三周用",
        "BR-05": "您这个病人我看就是术后复发",
    }
    miss_hit = []
    for rid, _g, _d, p in rules:
        if rid in SAMPLES and not p.search(SAMPLES[rid]):
            miss_hit.append(rid)
    if miss_hit:
        bad(f"正例无法命中的规则：{miss_hit}")
    else:
        good("每条规则都能被自己的正例命中")


def check_equivalence():
    """语义等价层同样要检查（空匹配会误伤合规表达）"""
    print("\n=== equivalence_layer ===")
    try:
        import equivalence_layer as E
    except Exception as e:
        print(f"（未加载：{e}）")
        return
    eq = E.build_equivalence_layer()
    empties = []
    for r in eq:
        if r["marker"].search("") or r["marker"].search("这是一句普通的话"):
            empties.append(r["id"])
    if empties:
        bad(f"语义等价层空匹配规则：{empties}")
    else:
        good(f"语义等价层无空匹配（{len(eq)} 条）")

    # 每个 marker 都要有对应的语境要求（否则单靠 marker 就会误伤）
    no_ctx = [r["id"] for r in eq if not r["context"].pattern]
    if no_ctx:
        bad(f"缺语境要求的等价规则：{no_ctx}")
    else:
        good("每条等价规则都有语境要求（双要素共现）")


if __name__ == "__main__":
    check_module("compliance_rules")
    check_equivalence()
    print()
    print("=" * 62)
    print(f"规则质量：{'全部通过' if ok else '存在问题'}")
    print("=" * 62)
    sys.exit(0 if ok else 1)
