#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
课程 spec 校验器 v2 —— 支持多维度目录与维度特有红线。

用法：
  python3 validate_specs_v2.py --spec-dir course-specs-tl --skel-dir course-skeletons-tl
  python3 validate_specs_v2.py --file course-specs-tl/D-NSCLC__TL.json
"""
import json, glob, os, re, sys, argparse

# ---- 通用红线 ----
INDICATION_CLAIM = [
    (re.compile(r"(某|该)?(药|产品|制剂)[^。；\n]{0,12}(获批|适应症|适用于)[^。；\n]{0,20}(癌|瘤|炎|病)"), "产品适应症越界"),
    (re.compile(r"(适应症|获批)[^。；\n]{0,10}(信达|达伯|达攸|苏立|信迪利|贝伐珠|阿达木|利妥昔|佩米替尼|曲妥珠|IBI)"), "产品适应症越界"),
]
FABRICATED_NUM = [
    (re.compile(r"(样本量|n\s*=\s*\d+|p\s*[＜<=>]\s*0?\.\d+|HR\s*[＜<=>]|OS\s*(延长|提升|降低)\s*\d+\s*(周|月|年|%)|发生率\s*\d+(\.\d+)?%|中位生存\s*\d+|ORR\s*(达|为|提升)\s*\d+)"), "疑似编造临床数值"),
]
ABSOLUTE = [
    (re.compile(r"(肯定|一定|必然|绝对)(比|优于|强于|有效)"), "绝对化表述"),
    (re.compile(r"(所有|全部)(患者|病人)(都|均)(适用|能用)"), "绝对化表述"),
]
GRAY = ["回扣", "临床费", "统方", "处方数据", "好处费", "返利", "二次公关"]

# ---- 维度特有红线 ----
DIM_EXTRA = {
    "treatment_landscape": [
        (re.compile(r"(在研|研究性)[^。；\n]{0,20}(适应症|获批|可推广|可以推广)"), "把研究性方案当已获批"),
    ],
    "clinical_evidence": [
        (re.compile(r"(单臂|非随机)[^。；\n]{0,20}(优于|强于|比[^。；\n]{0,8}好)"), "跨研究直接比较"),
    ],
    "pipeline_literacy": [
        (re.compile(r"(已获批|获批上市|可以推广)[^。；\n]{0,20}(研究|在研|管线)"), "在研当获批"),
    ],
    "disease_foundation": [],
}

REQUIRED = ["meta", "hero", "goal", "assumptions", "map", "hook", "visual",
            "analogy", "steps", "misconceptions", "checks", "recall", "sources"]
META_FIELDS = ["title", "subject", "age", "duration", "language"]
HERO_FIELDS = ["eyebrow", "question", "promise"]
RECALL_FIELDS = ["prompt", "hint", "answer"]
OPT_MAX, EXPL_MAX = 80, 240


def check_spec(spec):
    errs, warns = [], []
    for k in REQUIRED:
        if k not in spec:
            errs.append(f"缺少必填节 '{k}'")
    if errs:
        return errs, warns
    for f in META_FIELDS:
        if not str(spec["meta"].get(f, "")).strip():
            errs.append(f"meta.{f} 为空")
    for f in HERO_FIELDS:
        if not str(spec["hero"].get(f, "")).strip():
            errs.append(f"hero.{f} 为空")
    for f in RECALL_FIELDS:
        if not str(spec["recall"].get(f, "")).strip():
            errs.append(f"recall.{f} 为空")
    for f in ["prerequisites", "core", "unlocks"]:
        if not spec["map"].get(f):
            errs.append(f"map.{f} 为空")
    for f in ["prerequisites", "unlocks"]:
        if not isinstance(spec["map"].get(f), list) or not spec["map"][f]:
            errs.append(f"map.{f} 必须是非空数组")
    for sec, fields in [("hook", ["title", "body", "prompt"]),
                         ("analogy", ["title", "body", "limit"])]:
        for f in fields:
            if not str(spec[sec].get(f, "")).strip():
                errs.append(f"{sec}.{f} 为空")

    steps = spec["steps"]
    if not isinstance(steps, list) or not (3 <= len(steps) <= 5):
        errs.append(f"steps 应为 3–5 步，实际 {len(steps) if isinstance(steps,list) else '非数组'}")
    else:
        for i, s in enumerate(steps):
            for f in ["label", "title", "body"]:
                if not str(s.get(f, "")).strip():
                    errs.append(f"steps[{i}].{f} 为空")

    mis = spec["misconceptions"]
    if not isinstance(mis, list) or len(mis) < 2:
        errs.append(f"misconceptions 至少 2 条，实际 {len(mis) if isinstance(mis,list) else '非数组'}")
    else:
        for i, m in enumerate(mis):
            for f in ["myth", "correction", "why"]:
                if not str(m.get(f, "")).strip():
                    errs.append(f"misconceptions[{i}].{f} 为空")

    chk = spec["checks"]
    if not isinstance(chk, list) or len(chk) < 2:
        errs.append(f"checks 至少 2 道，实际 {len(chk) if isinstance(chk,list) else '非数组'}")
    else:
        for i, c in enumerate(chk):
            if not str(c.get("question", "")).strip():
                errs.append(f"checks[{i}].question 为空")
            opts = c.get("options")
            if not isinstance(opts, list) or len(opts) < 3:
                errs.append(f"checks[{i}].options 至少 3 个")
            else:
                a = c.get("answer")
                if not isinstance(a, int) or not (0 <= a < len(opts)):
                    errs.append(f"checks[{i}].answer 索引 {a} 越界（{len(opts)} 项）")
                for j, o in enumerate(opts):
                    if len(str(o)) > OPT_MAX:
                        errs.append(f"checks[{i}].options[{j}] {len(str(o))} 字超 {OPT_MAX}，需拆成短选项")
                if isinstance(a, int) and 0 <= a < len(opts):
                    cl = len(str(opts[a]))
                    wl = [len(str(opts[k])) for k in range(len(opts)) if k != a]
                    if wl and cl > max(wl) * 1.8 and cl > 60:
                        errs.append(f"checks[{i}] 正确项({cl})显著长于错误项({max(wl)})，需压缩为同等量级")
            if len(str(c.get("explanation", ""))) > EXPL_MAX:
                errs.append(f"checks[{i}].explanation {len(str(c.get('explanation','')))} 字超 {EXPL_MAX}")
            if not str(c.get("explanation", "")).strip():
                errs.append(f"checks[{i}].explanation 为空")

    srcs = spec["sources"]
    if not isinstance(srcs, list) or len(srcs) < 2:
        errs.append(f"sources 至少 2 条，实际 {len(srcs) if isinstance(srcs,list) else '非数组'}")
    else:
        for i, s in enumerate(srcs):
            if not str(s.get("label", "")).strip():
                errs.append(f"sources[{i}].label 为空")
            if not str(s.get("detail", "")).strip():
                errs.append(f"sources[{i}].detail 为空")
        if not any("http" in str(s.get("url", "")) for s in srcs):
            warns.append("sources 缺少带 http 的出处链接")

    v = spec["visual"]
    kind = v.get("kind")
    if kind == "comparison":
        items = v.get("items")
        if not isinstance(items, list) or not (2 <= len(items) <= 4):
            errs.append(f"visual.items 应为 2–4 项，实际 {len(items) if isinstance(items,list) else '非数组'}")
        else:
            for i, it in enumerate(items):
                if not str(it.get("title", "")).strip():
                    errs.append(f"visual.items[{i}].title 为空")
                fa = it.get("facts")
                if not isinstance(fa, list) or not (1 <= len(fa) <= 6):
                    errs.append(f"visual.items[{i}].facts 应为 1–6 条")
    elif kind == "process":
        st = v.get("stages")
        if not isinstance(st, list) or not (3 <= len(st) <= 7):
            errs.append(f"visual.stages 应为 3–7 段，实际 {len(st) if isinstance(st,list) else '非数组'}")
        else:
            for i, x in enumerate(st):
                if not str(x.get("title", "")).strip() or not str(x.get("body", "")).strip():
                    errs.append(f"visual.stages[{i}] 缺 title/body")
    elif kind == "concept-map":
        nodes = v.get("nodes")
        if not isinstance(nodes, list) or not (3 <= len(nodes) <= 9):
            errs.append(f"visual.nodes 应为 3–9 个，实际 {len(nodes) if isinstance(nodes,list) else '非数组'}")
        else:
            ids = set()
            for i, n in enumerate(nodes):
                nid = str(n.get("id", "")).strip()
                if not nid:
                    errs.append(f"visual.nodes[{i}].id 为空")
                if nid in ids:
                    errs.append(f"visual.nodes id 重复: {nid}")
                ids.add(nid)
                if not str(n.get("label", "")).strip():
                    errs.append(f"visual.nodes[{i}].label 为空")
                if n.get("role") not in {"prerequisite", "core", "unlock"}:
                    errs.append(f"visual.nodes[{i}].role 必须是 prerequisite/core/unlock")
            for i, n in enumerate(nodes):
                for tgt in n.get("connectsTo", []) or []:
                    if tgt not in ids:
                        errs.append(f"visual.nodes[{i}].connectsTo 指向不存在的 id: {tgt}")
    else:
        errs.append(f"visual.kind 非法: {kind}")
    if not str(v.get("observation", "")).strip():
        errs.append("visual.observation 为空")

    # ---- 红线扫描 ----
    body = json.dumps({k: spec[k] for k in ["hero", "goal", "steps", "map", "hook", "analogy"]},
                      ensure_ascii=False)
    for pat, label in INDICATION_CLAIM + FABRICATED_NUM + ABSOLUTE:
        m = pat.search(body)
        if m:
            errs.append(f"[红线] {label}: {m.group(0)[:50]}")
    for g in GRAY:
        if g in body:
            errs.append(f"[红线] 教学正文出现灰色手法词: {g}")
    if isinstance(mis, list):
        if not any(re.search(r"(适应症|获批|在研|证据|终点|外推|所有|全部|数值|数据)",
                             json.dumps(m, ensure_ascii=False)) for m in mis):
            warns.append("误区未指向证据边界类问题")
    if isinstance(chk, list):
        has = any(re.search(r"(核实|确认|查证|不确定|按最新|说明书|医学信息|医学团队|为准|核对|口径)",
                            chk[i].get("options", [""])[chk[i]["answer"]] + chk[i].get("explanation", ""))
                  for i in range(len(chk)) if isinstance(chk[i].get("answer"), int)
                  and 0 <= chk[i]["answer"] < len(chk[i].get("options", [])))
        if not has:
            warns.append("没有检验题的正确项体现『承认不确定 + 给出核实路径』")
    return errs, warns


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec-dir", default=None)
    ap.add_argument("--skel-dir", default=None)
    ap.add_argument("--file", default=None)
    args = ap.parse_args()

    if args.file:
        files = [args.file]
        skel_dir = args.skel_dir
    else:
        sd = args.spec_dir or "course-specs"
        files = sorted(glob.glob(os.path.join("/workspace/output", sd, "*.json")))
        skel_dir = args.skel_dir
    if not files:
        print("无 spec 文件")
        return 1

    total_err = 0
    for f in files:
        cid = os.path.basename(f)[:-5]
        try:
            spec = json.load(open(f, encoding="utf-8"))
        except Exception as e:
            print(f"❌ {cid}: JSON 解析失败 — {e}")
            total_err += 1
            continue
        errs, warns = check_spec(spec)

        # 骨架交叉核对
        if skel_dir:
            sp = os.path.join("/workspace/output", skel_dir, f"{cid}.json")
            if os.path.exists(sp):
                skel = json.load(open(sp, encoding="utf-8"))
                url = (skel.get("source") or {}).get("url")
                blob = json.dumps(spec, ensure_ascii=False)
                if url and url not in blob:
                    warns.append("spec 中未出现骨架的 source.url")
                kws = [k for k in (skel.get("keywords") or "").split(";") if k.strip()]
                if kws and not any(k in blob for k in kws):
                    errs.append(f"[红线] 未使用该疾病的任何关键词: {kws[:3]}")
                if spec.get("visual", {}).get("kind") != skel.get("visual_kind"):
                    errs.append(f"visual.kind({spec.get('visual',{}).get('kind')}) 与骨架({skel.get('visual_kind')})不一致")
                # 维度特有红线
                dim = skel.get("dimension", "")
                body = json.dumps({k: spec[k] for k in ["hero", "goal", "steps", "map", "hook", "analogy"]},
                                  ensure_ascii=False)
                for pat, label in DIM_EXTRA.get(dim, []):
                    m = pat.search(body)
                    if m:
                        errs.append(f"[红线·{dim}] {label}: {m.group(0)[:40]}")

        if errs:
            print(f"❌ {cid}: {len(errs)} 个错误")
            for e in errs[:6]:
                print(f"     · {e}")
        else:
            w = f"（{len(warns)} 提醒）" if warns else ""
            print(f"✅ {cid}{w}")
            for x in warns[:2]:
                print(f"     · 提醒: {x}")
        total_err += len(errs)

    print(f"\n{'='*58}")
    print(f"{len(files)} 份 spec，{total_err} 个错误")
    return 1 if total_err else 0


if __name__ == "__main__":
    sys.exit(main())
