#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查 GATE_RULES 每条正则的语法与括号平衡。

踩过两次括号坑，这个检查器常驻。
关键：不能用 "))," 做切分锚点——那会把外层组的 ")" 当成 Python 层结束符吃掉。
改用「下一条规则开头」作为切分边界。
"""
import re, sys

src = open('/workspace/output/medrep_coach.py', encoding='utf-8').read()
m = re.search(r'GATE_RULES = \[(.*?)\n    # 编译', src, re.S)
if not m:
    print("❌ 未找到 GATE_RULES"); sys.exit(1)
block = m.group(1)

# 按下一条 ("XX", 开头切分，最后一段到块尾
chunks = re.split(r'\n        \("(?=[A-Z]{2}-\d+")', block)
bad = 0
for ch in chunks[1:]:
    rid = re.match(r'([A-Z]{2}-\d+)', ch).group(1)
    pat = "".join(re.findall(r'r"([^"]*)"', ch))
    bal = pat.count("(") - pat.count(")")
    if bal != 0:
        bad += 1
        print(f"❌ {rid}: 括号不平衡 {bal:+d}")
        print(f"   {pat}")
        continue
    try:
        re.compile(pat)
        print(f"✅ {rid}: {len(pat)} 字符")
    except re.error as e:
        bad += 1
        print(f"❌ {rid}: {e}")
        print(f"   {pat}")

print(f"\n{'全部通过' if bad == 0 else f'{bad} 条有问题'}")
sys.exit(1 if bad else 0)
