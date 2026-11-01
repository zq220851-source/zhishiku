#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一期包一致性检查 —— 防止「配置/清单/工作单/索引」与磁盘实际脱节。

为什么需要这个
--------------
本次交付前发现的一类真实缺陷：
  · phase1-config.json 里 8 门 TL 课还写着 status=to_build（课已建好，配置没回填）
  · 签审工作单只覆盖 8 门 DF（一期 37 门里只有 8 门能签审）
  · course_manifest_all.json 是空列表 []

共同点：**同一件事被多个脚本各写一份，改一处忘另一处**。
这些不会报错，只会让签审范围、索引、范围声明悄悄错位。

所以这里做交叉核对，把脱节变成可检测的失败。

用法：python3 verify_phase1_consistency.py
"""
import json, os, glob, sys, re
from collections import Counter

from config import BASE, PATHS
A = os.path.join(BASE, "version-A-training-pack")
ok = True

# ★ 一期包（version-A-training-pack）是独立交付物，原型包可能不含它。
#   缺了就跳过相关检查并明确说明，不能报失败 —— 那是另一个包的职责。
HAS_VERSION_A = os.path.isdir(A)
if not HAS_VERSION_A:
    print("ℹ️  未找到 version-A-training-pack（独立交付物）—— 跳过一期包一致性检查")
    print("=" * 66)
    print("一期包一致性：跳过（该检查属于 version-A 包）")
    print("=" * 66)
    sys.exit(0)


def check(label, cond, detail=""):
    global ok
    if not cond:
        ok = False
    print(f"{'✅' if cond else '❌'} {label:42s} {detail}")


# ---- 磁盘实际课程 ----
disk = {}
for sub in ("specs", "specs-tl", "specs-ce"):
    d = os.path.join(A, sub)
    if not os.path.isdir(d):
        continue
    for f in sorted(os.listdir(d)):
        if f.endswith(".json"):
            disk[f"{sub}/{f}"] = True
N_DISK = len(disk)

# ---- 配置 ----
cfg = json.load(open(os.path.join(A, "phase1-config.json"), encoding="utf-8"))
p1 = cfg["phase1"]
cfg_specs = set()
for co in cfg["courses"]:
    for dk in ("df", "tl", "ce"):
        d = co.get(dk)
        if d and d.get("status") == "ready_pending_signoff":
            cfg_specs.add(d["spec"])
for pr in p1["products"]:
    d = pr.get("course")
    if d and d.get("status") == "ready_pending_signoff":
        cfg_specs.add(d["spec"])

check("配置声明的课程数 = 磁盘实际",
      p1["total_courses"] == N_DISK,
      f"配置 {p1['total_courses']} vs 磁盘 {N_DISK}")
check("配置课程清单 = 磁盘文件（无漏无多）",
      cfg_specs == set(disk.keys()),
      f"差集 {sorted(cfg_specs ^ set(disk.keys()))[:3] if cfg_specs != set(disk.keys()) else '无'}")
check("配置里无残留 to_build",
      not any(co.get(k, {}).get("status") == "to_build"
              for co in cfg["courses"] for k in ("df", "tl", "ce")),
      "")

# ---- 清单 ----
man_path = os.path.join(A, "course_manifest_all.json")
man = json.load(open(man_path, encoding="utf-8"))
man_specs = {c["spec"] for c in man["courses"]}
check("course_manifest_all 与磁盘一致",
      man_specs == set(disk.keys()),
      f"清单 {len(man_specs)} vs 磁盘 {N_DISK}")
check("course_manifest_all 非空",
      len(man["courses"]) > 0,
      f"{len(man['courses'])} 门")
check("清单全部标记待医学审核",
      all(c.get("review_status") == "pending_medical_review" for c in man["courses"]),
      "")

# ---- 签审工作单 ----
sw_path = os.path.join(A, "signoff/phase1-signoff-focus.json")
sw = json.load(open(sw_path, encoding="utf-8"))
sw_specs = {i["spec_file"] for i in sw["items"] if i.get("spec_file")}
check("签审工作单覆盖全部课程",
      sw_specs == set(disk.keys()),
      f"工作单 {len(sw_specs)} vs 磁盘 {N_DISK}")
check("签审工作单每条 5 个签审格",
      all(len(i.get("signoff", {})) == 5 for i in sw["items"]),
      "")
check("签审工作单全部待审",
      all(i.get("status") == "pending_medical_review" for i in sw["items"]),
      "")

# ---- 索引页 ----
idx_path = os.path.join(A, "index-phase1.html")
idx = open(idx_path, encoding="utf-8").read()
# 索引页引用的是课程 html（不是 spec 路径）
idx_html = set(re.findall(r'(courses(?:-tl|-ce)?/[^"\'<>\s]+\.html)', idx))
# 磁盘上的课程 html
disk_html = set()
for sub in ("courses", "courses-tl", "courses-ce"):
    d = os.path.join(A, sub)
    if not os.path.isdir(d):
        continue
    for f in os.listdir(d):
        if f.endswith(".html"):
            disk_html.add(f"{sub}/{f}")
check("索引页引用了课程文件（正则有效）",
      len(idx_html) > 0,
      f"索引引用 {len(idx_html)} 个 / 磁盘 {len(disk_html)} 个")
check("索引页引用的课程文件都存在",
      all(os.path.exists(os.path.join(A, s)) for s in idx_html),
      f"缺失 {[s for s in idx_html if not os.path.exists(os.path.join(A, s))][:3]}")
check("索引页覆盖全部课程",
      idx_html == disk_html,
      f"差集 {sorted(idx_html ^ disk_html)[:3] if idx_html != disk_html else '无'}")

# ---- 产品关联口径 ----
bad_link = [p["id"] for p in p1["products"]
            if p.get("link_type") != "educational_topic_not_indication"]
check("产品关联一律 educational_topic_not_indication",
      not bad_link,
      f"异常 {bad_link}" if bad_link else "")

# ---- 管线资产的披露/审批分列 ----
pl_bad = [p["id"] for p in p1["products"]
          if p["status"] == "pipeline"
          and (not p.get("reported_status") or not p.get("approval_status"))]
check("管线资产同时有 reported_status 与 approval_status",
      not pl_bad,
      f"缺失 {pl_bad}" if pl_bad else "")

print()
print("=" * 62)
print(f"一期包一致性：{'全部通过' if ok else '存在不一致'}")
sys.exit(0 if ok else 1)
