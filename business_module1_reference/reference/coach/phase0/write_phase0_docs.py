#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
写 Phase 0 的 D1–D5 五份决策文档。

由 owner 直接编写（并行 agent 长时间零产出），内容严格取材于：
  - D0-语料资产库.md（已验收，726 处引用零杜撰）
  - D8a-评分表草案.md（两轨 9 维 + 4 闸门）
  - 一期 37 门课程（course-specs*/）
  - 信达临床知识库 v0.5
  - V1.3 开发文档
所有事实性表述带出处或标注为产品设计决策。
"""
import json, os, re, glob, sqlite3

import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from config import BASE, PATHS
PHASE0 = os.path.join(BASE, "phase0")
CLIN = os.path.join(BASE, "clinical/medrep-innovent-clinical-knowledge-v0.5")
COURSES = os.path.join(BASE, "version-A-training-pack")

# ---------- 读取素材 ----------
d8a = json.load(open(os.path.join(PHASE0, "D8a-评分表草案.json"), encoding="utf-8"))
d0 = open(os.path.join(PHASE0, "D0-语料资产库.md"), encoding="utf-8").read()
cfg = json.load(open(os.path.join(COURSES, "phase1-config.json"), encoding="utf-8"))
bridge = json.load(open(os.path.join(BASE, "skill-taxonomy", "course-skill-bridge.json"), encoding="utf-8"))

db = sqlite3.connect(os.path.join(CLIN, "medrep_clinical_knowledge_v0.5.sqlite"))
db.row_factory = sqlite3.Row
prod_rows = {r["product_id"]: dict(r) for r in db.execute("select * from med_products")}
pipe_rows = {r["asset_id"]: dict(r) for r in db.execute("select * from expanded_pipeline")}
cond_rows = {r["condition_id"]: dict(r) for r in db.execute("select * from clinical_conditions")}
csrc_rows = {r["source_id"]: dict(r) for r in db.execute("select * from clinical_sources")}

# 从 D0 抽取关键引用（供各文档引用）
def d0_grep(pat, n=3):
    out = []
    for line in d0.split("\n"):
        if re.search(pat, line):
            out.append(line.strip()[:180])
            if len(out) >= n:
                break
    return out

print("素材就绪")
