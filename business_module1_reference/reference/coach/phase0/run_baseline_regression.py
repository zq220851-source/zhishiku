#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D7 判定回归：拿 41 条基线样本跑评分引擎，核对期望判定。

用法：
    python3 run_baseline_regression.py
    python3 run_baseline_regression.py --verbose
"""
import json, os, sys, argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import BASE, PATHS
PHASE0 = os.path.join(BASE, "phase0")
sys.path.insert(0, BASE)

import importlib.util
spec = importlib.util.spec_from_file_location("coach", os.path.join(BASE, "medrep_coach.py"))
coach = importlib.util.module_from_spec(spec)
spec.loader.exec_module(coach)

ap = argparse.ArgumentParser()
ap.add_argument("--verbose", action="store_true")
args = ap.parse_args()

samples = json.load(open(os.path.join(PHASE0, "D7-判定回归基线集.json"), encoding="utf-8"))
rubric = coach.Rubric(json.load(open(os.path.join(PHASE0, "D8a-评分表草案.json"), encoding="utf-8")))

passed, failed = 0, []
for s in samples:
    ans = s["answer"]
    if not ans.strip():
        continue  # 未作答样本走另一条路径

    scores, gates, findings, unscored = rubric.score_answer(ans)

    # 实际触发的闸门（排除已豁免）
    fired = [g for g in gates
             if g["gate"].startswith(("GATE-01", "GATE-02")) and not g.get("exempt")]
    actual = fired[0]["gate"].split()[0] if fired else None

    exp_gate = s["expect_gate"]
    exp_exempt = s["expect_exempt"]
    exp_unscorable = s["expect_unscorable"]

    problems = []
    if exp_gate and actual != exp_gate:
        problems.append(f"闸门应为 {exp_gate}，实际 {actual or '未触发'}")
    if not exp_gate and actual:
        problems.append(f"不应触发闸门，实际触发 {actual}")
    if exp_exempt:
        exempt_gates = [g for g in gates if g.get("exempt")]
        if not exempt_gates:
            problems.append("应豁免但未记录豁免")
    if exp_unscorable and not unscored:
        problems.append("应判不可评分但判了分")
    if not exp_unscorable and unscored:
        problems.append("不应判不可评分但剔除了")

    if problems:
        failed.append((s, problems))
    else:
        passed += 1

    if args.verbose:
        mark = "✅" if not problems else "❌"
        print(f"{mark} {s['sample_id']:10s} | {s['group'][:22]:24s} | "
              f"{(problems[0] if problems else 'OK')}")
        if args.verbose and not problems:
            print(f"    「{ans[:60]}」")

print()
print("=" * 62)
print(f"通过 {passed} / {passed + len(failed)}")
if failed:
    print(f"\n失败 {len(failed)} 条：")
    for s, probs in failed:
        print(f"  ❌ {s['sample_id']} | {s['group']}")
        print(f"     「{s['answer'][:70]}」")
        for p in probs:
            print(f"     → {p}")
    sys.exit(1)
print("✅ 全部通过")
