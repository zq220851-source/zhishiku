#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
已拍板决策 —— 单一事实来源。

D08a-1~3 已于 2026-10-31 拍板，本模块是它们在代码里的唯一落点。
D08a-4（降档阈值）**未拍板**，必须等标注集回归校准，不得在此给确定值。

为什么单独建模块
----------------
原先这些值散落在 D8a 评分表草案、端到端原型代码、Phase 0 文档三处，
改一处忘另一处就会不一致（本次交付前就发现过同类问题：
一期配置、签审工作单、索引页三者脱节）。

所以：拍板值只在这里定义一次，其他地方 import。
"""
import json, os
from datetime import datetime, timezone

from config import BASE, PATHS

# ============================================================
# D08a-1 分值档位（已拍板）
# ============================================================
SCALE_MIN = 1.0
SCALE_MAX = 5.0
SCALE_ANCHORS = (5, 3, 1)          # D8a 锚点三档

# ============================================================
# D08a-2 两轨初始权重（已拍板）
# ============================================================
INITIAL_WEIGHTS = {
    "communication": 60,            # 话术
    "medical": 40,                  # 知识
}

# ============================================================
# D08a-3 资历上调规则（已拍板）
# ============================================================
ESCALATION = {
    "streak_required": 3,           # 连续 3 次达标
    "step_pp": 5,                   # 每次 +5 个百分点转向 medical
    "medical_cap": 60,              # medical 轨上限 60%（话术下限 40%）
    "reset_on": "知识不足（强制降档）",  # 出现即重置连续计数
}

# ============================================================
# D08a-4 降档阈值 —— 未拍板，待校准集
# ============================================================
# ⚠️ 以下为讨论初值，未经标注集验证，不得用于正式考核。
#     V1.3 §5.4：所有数值阈值需在先导标注集建立后确定。
DOWNGRADE_THRESHOLDS = {
    "_status": "discussion_draft_pending_calibration",
    "knowledge_insufficient_below": 2.5,   # 1–5 分制：医学轨低于此值判「知识不足」
    "basically_qualified_below": 3.5,      # 医学轨低于此值判「基本达标」
    "cap_basic": 4.0,                      # 基本达标时的综合分上限
    "cap_boundary_violation": 2.5,         # GATE-02 边界越界的上限
    "cap_compliance_reject": 0.0,          # GATE-01 合规否决的上限
    "cap_no_limit": 5.0,                   # 不设上限
}

# ============================================================
# 资历状态持久化
# ============================================================
STATE_DIR = PATHS.STATE_DIR
STATE_FILE = os.path.join(STATE_DIR, "proficiency_state.json")


def _load_all():
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        return json.load(open(STATE_FILE, encoding="utf-8"))
    except Exception:
        return {}


def _save_all(d):
    os.makedirs(STATE_DIR, exist_ok=True)
    tmp = STATE_FILE + ".tmp"
    json.dump(d, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    os.replace(tmp, STATE_FILE)


def get_state(user_id):
    """取某药代的资历状态（不存在则初始化）"""
    allst = _load_all()
    return allst.get(user_id, {
        "user_id": user_id,
        "streak": 0,                 # 连续达标次数
        "medical_weight": INITIAL_WEIGHTS["medical"],
        "communication_weight": INITIAL_WEIGHTS["communication"],
        "history": [],               # 每次训练的等级
        "updated_at": None,
    })


def record_outcome(user_id, level):
    """
    记录一次训练结果，按 D08a-3 更新权重。

    level 取值与 D3 §3 一致：
      达标 / 基本达标 / 知识不足（强制降档）/ 边界越界（强制降档）/ 合规否决（...）
    """
    st = get_state(user_id)
    escalated = False

    if level == "达标":
        st["streak"] += 1
        if st["streak"] >= ESCALATION["streak_required"]:
            # 每满 3 次连续达标才上调一次，然后重新计数（周期性奖励，非累加）
            new_m = min(st["medical_weight"] + ESCALATION["step_pp"],
                        ESCALATION["medical_cap"])
            if new_m != st["medical_weight"]:
                st["medical_weight"] = new_m
                st["communication_weight"] = 100 - new_m
                escalated = True
            # 无论是否已到上限，计数重置——下一轮重新满 3 次才再上调
            st["streak"] = 0
    elif level.startswith("暂不评定"):
        # ★ 「暂不评定」不是训练结果（无可评分的知识维度），
        #   不进历史、不动连续计数。
        #   否则一次空跑会莫名打断连续达标，导致资历上调永远触发不了。
        return st, False
    elif ESCALATION["reset_on"] in level or level.startswith("合规否决"):
        # 出现降档或合规否决 → 连续计数重置（权重不回退）
        st["streak"] = 0
    else:
        # 基本达标 → 连续计数清零但权重保留
        st["streak"] = 0

    st["history"].append({
        "level": level,
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    })
    st["history"] = st["history"][-20:]      # 只留最近 20 次
    st["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")

    allst = _load_all()
    allst[user_id] = st
    _save_all(allst)
    return st, escalated


def effective_weights(user_id):
    """当前应使用的两轨权重（含 GATE-04 重分配前的初始值）"""
    st = get_state(user_id)
    return st["communication_weight"], st["medical_weight"], st["streak"]


if __name__ == "__main__":
    print("=== 已拍板决策 ===")
    print(f"  D08a-1 分值档位      : {SCALE_MIN}–{SCALE_MAX}（锚点 {SCALE_ANCHORS}）")
    print(f"  D08a-2 初始权重      : 话术 {INITIAL_WEIGHTS['communication']} / 知识 {INITIAL_WEIGHTS['medical']}")
    print(f"  D08a-3 资历上调      : 连续 {ESCALATION['streak_required']} 次达标 +{ESCALATION['step_pp']}pp，"
          f"medical 上限 {ESCALATION['medical_cap']}%")
    print(f"  D08a-4 降档阈值      : {DOWNGRADE_THRESHOLDS['_status']}")
    print()
    print("=== 资历上调自测 ===")
    u = "_selftest"
    allst = _load_all()
    allst.pop(u, None)
    _save_all(allst)
    for i in range(1, 5):
        st, esc = record_outcome(u, "达标")
        print(f"  第 {i} 次达标 → medical {st['medical_weight']}% "
              f"streak={st['streak']} {'← 已上调' if esc else ''}")
    st, _ = record_outcome(u, "知识不足（强制降档）")
    print(f"  降档后 → medical {st['medical_weight']}% streak={st['streak']}（权重不回退，计数重置）")
    allst = _load_all()
    allst.pop(u, None)
    _save_all(allst)
