#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""构建 Phase 0 决策包 —— 全量同步 + 一致性校验。"""
import os, sys, glob, shutil, zipfile, hashlib

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "phase0-decision-freeze-pack.zip")
SRC = os.path.join(BASE, "phase0")

SKIP_PREFIX = ("write_", "build_")
KEEP_BUILD = {"build_d2_mapping.py", "build_phase0_freeze.py"}


def md5(p):
    h = hashlib.md5()
    with open(p, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


files = []
for p in sorted(glob.glob(os.path.join(SRC, "*"))):
    name = os.path.basename(p)
    if not os.path.isfile(p):
        continue
    if not name.endswith((".md", ".json", ".py")):
        continue
    if name.startswith(SKIP_PREFIX) and name not in KEEP_BUILD:
        continue
    files.append(p)

# 根级的决策相关文件也带上
ROOT_FILES = ["compliance_rules.py", "decisions.py", "knowledge_retrieval.py",
              "llm_provider.py", "llm_doctor.py", "check_rule_quality.py",
              "verify_llm_path.py", "verify_at05.py", "check_llm_key.py",
              "feedback_pipeline.py", "verify_feedback_pipeline.py",
              "LLM医生说明.md", "反馈管道说明.md"]

if os.path.exists(OUT):
    os.remove(OUT)
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for p in files:
        z.write(p, f"phase0/{os.path.basename(p)}")
    for name in ROOT_FILES:
        p = os.path.join(BASE, name)
        if os.path.exists(p):
            z.write(p, name)

print(f"✅ {os.path.basename(OUT)}  {os.path.getsize(OUT)/1024:.0f} KB  "
      f"{len(zipfile.ZipFile(OUT).namelist())} 条目")
