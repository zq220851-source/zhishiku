#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MiniMax key 状态诊断 —— 充值后先跑这个，确认能用再跑训练。

用法：
    export MINIMAX_API_KEY=sk-xxx
    python3 check_llm_key.py

只做三件事，不改任何状态：
    1. 认证是否通过（/v1/models 能否列出模型）
    2. 账户余额是否够（实际发一次最小请求）
    3. LLM 医生链路是否通（检索→提示→生成→校验）
"""
import os, sys, json

from config import BASE, PATHS
sys.path.insert(0, BASE)

from llm_provider import MinimaxTextProvider, LLMProviderError, get_provider

KEY = os.environ.get("MINIMAX_API_KEY", "")
if not KEY:
    print("❌ 未设置 MINIMAX_API_KEY")
    print("   export MINIMAX_API_KEY=sk-你的key")
    sys.exit(1)

p = MinimaxTextProvider()
print(f"key 前缀: {KEY[:12]}…  长度 {len(KEY)}")
print()

# 1) 认证
print("【1】认证检查")
try:
    models = p.list_models()
    print(f"  ✅ 认证通过，可用模型 {len(models)} 个")
    for m in models[:5]:
        print(f"     - {m}")
    if p.model not in models:
        print(f"  ⚠️  默认模型 {p.model} 不在列表里，建议改用 {models[0]}")
except LLMProviderError as e:
    print(f"  ❌ {e}")
    sys.exit(1)
except Exception as e:
    print(f"  ❌ {type(e).__name__}: {e}")
    sys.exit(1)

# 2) 余额
print()
print("【2】余额检查（发一次最小请求）")
try:
    text, meta = p.generate("只回答两个字：你好")
    print(f"  ✅ 调用成功：{text[:60]}")
    if meta.get("usage"):
        print(f"     usage: {meta['usage']}")
except LLMProviderError as e:
    print(f"  ❌ {e}")
    if e.code in (1007, 1008):
        prefix = KEY[:8]
        print()
        print("  ┌────────────────────────────────────────────────────────┐")
        print("  │ 你的 key 前缀是 sk-api- —— 这是【按量付费 API Key】      │")
        print("  │ 它只扣【账户余额】，不消耗 Token Plan / Coding Plan 额度 │")
        print("  └────────────────────────────────────────────────────────┘")
        print()
        print("  两种可能：")
        print()
        print("  A) 你的额度确实在 Token Plan / Coding Plan")
        print("     → 去控制台 Billing / Token Plan 页面复制【Subscription Key】")
        print("       （前缀是 sk-cp-），把那个 key 给我或换上去即可")
        print()
        print("  B) 你的额度是账户余额，只是显示口径不同")
        print("     → 在控制台充值区确认【账户余额】> 0")
        print()
        print("  两种凭证不通用：sk-api- 与 sk-cp- 不能互换。")
        print()
        print("  换成 Subscription Key 后：")
        print("    python3 medrep_coach.py … --llm --llm-provider minimax_text")
        print()
        print("  当前可用（无需 key）：--llm --llm-provider vision_text")
    sys.exit(2)

# 3) LLM 医生链路
print()
print("【3】LLM 医生链路")
try:
    from knowledge_retrieval import KnowledgeBase
    from llm_doctor import LLMDoctorSim
    kb = KnowledgeBase()
    d = LLMDoctorSim({"role_preset": {"style": "直接"},
                       "visit_context_id": "D-NSCLC-DF"},
                      kb=kb, provider=p)
    ans = d.opening("达伯舒的靶点是什么？跟非小细胞肺癌是什么关系？")
    print(f"  医生开场：{ans[:220]}")
    g = d.guard_report()
    print(f"  FactGuard：{g['total']} 个问题")
    print()
    print("✅ 全链路可用")
except Exception as e:
    print(f"  ❌ {type(e).__name__}: {e}")
    sys.exit(3)
