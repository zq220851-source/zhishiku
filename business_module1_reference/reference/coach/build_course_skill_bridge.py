#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
打通课程 ↔ SkillTaxonomy 能力点。

课程考察点与 skill 能力点已验证 148/148 同名精确匹配。本脚本生成双向索引：
  course→skill ：这门课练的是哪些能力点
  skill→course ：这个能力点由哪门课承载（无课覆盖的能力点 = 培训缺口）
"""
import json, os, glob, re
from collections import defaultdict

from config import BASE, PATHS
TAX = os.path.join(BASE, "skill-taxonomy", "skill-taxonomy.json")
MAP = os.path.join(BASE, "course-mapping", "course-mapping.json")
OUT = os.path.join(BASE, "skill-taxonomy")

tax = json.load(open(TAX, encoding="utf-8"))
mapping = json.load(open(MAP, encoding="utf-8"))

# skill 索引：(condition_name, name) -> skill
# 另建资产 ID 索引：资产类 skill 的 condition_name 是品牌名，但 ID 里带资产代号
skill_idx = {}
skill_by_asset = {}
for s in tax["skills"]:
    if s["tree"] != "knowledge" or not s.get("condition_name"):
        continue
    skill_idx[(s["condition_name"], s["name"])] = s
    # SK-K-<ASSET>-PROD-01 / SK-K-<ASSET>-PIPE-01 → 资产代号
    m = re.match(r"SK-K-([A-Za-z0-9]+)-(PROD|PIPE)-", s["skill_id"])
    if m:
        skill_by_asset[(m.group(1).upper(), m.group(2))] = s

# 反向：skill → 课程
skill2course = defaultdict(list)
course2skill = {}

for r in mapping:
    cid = r["condition_id"]
    dim = r.get("dimension", "disease_foundation")
    ctitle = r.get("course_title", "")
    hits = []
    for kp in r.get("knowledge_points", []):
        key = (r["condition_name"], kp["dimension"])
        sk = skill_idx.get(key)
        # 资产类课程：整个课程对应 1 个资产 skill（该资产的 PROD/PIPE 能力点）
        if not sk:
            dim2 = {"product_basics": "PROD", "pipeline_literacy": "PIPE"}.get(dim)
            if dim2:
                sk = skill_by_asset.get((cid.upper(), dim2))
                if sk and kp is r["knowledge_points"][0]:
                    pass  # 首个考察点承载资产 skill
                elif sk:
                    continue
        if sk:
            hits.append({
                "kp_id": kp["kp_id"], "skill_id": sk["skill_id"],
                "dimension": kp["dimension"],
                "v13_evaluation_items": sk.get("v13_evaluation_items", []),
                "axes": sk.get("axes", []),
            })
            skill2course[sk["skill_id"]].append({
                "condition_id": cid, "dimension": dim,
                "course_title": ctitle, "kp_id": kp["kp_id"],
                "course_file": r.get("course_file"),
            })
    course2skill[(cid, dim)] = hits

# 覆盖统计
all_skills = {s["skill_id"]: s for s in tax["skills"] if s["tree"] == "knowledge"}
covered = set(skill2course.keys())
gap = [sid for sid in all_skills if sid not in covered]

report = {
    "version": "v1.3-aligned",
    "generated_at": __import__("time").strftime("%Y-%m-%d %H:%M"),
    "summary": {
        "total_knowledge_skills": len(all_skills),
        "covered_by_courses": len(covered),
        "uncovered": len(gap),
        "coverage_rate": round(len(covered) / len(all_skills), 4) if all_skills else 0,
        "courses_indexed": len(course2skill),
    },
    "course_to_skill": {f"{c}|{d}": v for (c, d), v in course2skill.items()},
    "skill_to_course": {k: v for k, v in skill2course.items()},
    "uncovered_skills": [
        {"skill_id": sid, "name": all_skills[sid]["name"],
         "condition": all_skills[sid].get("condition_name"),
         "dimensions": all_skills[sid].get("dimensions", []),
         "v13_evaluation_items": all_skills[sid].get("v13_evaluation_items", [])}
        for sid in sorted(gap)
    ],
}
with open(os.path.join(OUT, "course-skill-bridge.json"), "w", encoding="utf-8") as fh:
    json.dump(report, fh, ensure_ascii=False, indent=2)

# 人读版
L = [
    "# 课程 ↔ 能力点 双向索引",
    "",
    "> 把培训课程与陪练 Agent 的知识轨道接上：每门课练哪些能力点，每个能力点由哪门课承载。",
    "> 生成方式：课程考察点与 SkillTaxonomy 能力点按「疾病 + 维度」同名精确匹配。",
    "",
    "## 一、覆盖总览",
    "",
    "| 项 | 值 |",
    "|---|---|",
    f"| 知识能力点总数 | {report['summary']['total_knowledge_skills']} |",
    f"| 已被课程覆盖 | {report['summary']['covered_by_courses']} |",
    f"| **未覆盖** | **{report['summary']['uncovered']}** |",
    f"| 覆盖率 | {report['summary']['coverage_rate']:.1%} |",
    f"| 已索引课程 | {report['summary']['courses_indexed']} 门 |",
    "",
]
if gap:
    L += ["## 二、未被课程覆盖的能力点（培训缺口）", "",
          "这些能力点在陪练 Agent 里会被考到，但目前没有对应课程承载——要么补课，要么在陪练中降级处理。", "",
          "| 能力点 | 疾病 | 维度 | V1.3 评价项 |", "|---|---|---|---|"]
    for g in report["uncovered_skills"][:40]:
        L.append(f"| `{g['skill_id']}` | {g['condition']} | {'/'.join(g['dimensions'])} | "
                 f"{'/'.join(g['v13_evaluation_items'])} |")
    if len(gap) > 40:
        L.append(f"| … | 其余 {len(gap)-40} 条见 JSON | | |")
else:
    L += ["## 二、未被课程覆盖的能力点", "", "**无缺口** —— 每个知识能力点都有课程承载。", ""]

L += ["", "## 三、课程 → 能力点", "", "| 课程 | 覆盖的能力点 |", "|---|---|"]
for (cid, dim), hits in sorted(course2skill.items()):
    names = ", ".join(f"`{h['skill_id']}`" for h in hits[:4])
    more = f" 等 {len(hits)} 个" if len(hits) > 4 else ""
    L.append(f"| {cid} / {dim} | {names}{more} |")

open(os.path.join(OUT, "course-skill-bridge.md"), "w", encoding="utf-8").write("\n".join(L))

print(f"✅ 双向索引已生成 → {OUT}/course-skill-bridge.{{json,md}}")
print(f"   知识能力点 {len(all_skills)} 个 | 课程覆盖 {len(covered)} 个 | 缺口 {len(gap)} 个")
print(f"   覆盖率 {report['summary']['coverage_rate']:.1%}")
if gap:
    print("   缺口示例:")
    for g in report["uncovered_skills"][:6]:
        print(f"     {g['skill_id']} {g['name'][:26]} ({g['condition']})")
