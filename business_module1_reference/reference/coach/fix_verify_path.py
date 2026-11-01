#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
按评审口径修复：核实路径必须体现在**正确项文本本身**，而不只在 explanation。

评审原话（截取）：
- A-IMM「9 门课，通过 5，失败 4」→ 失败原因：4 门课正确项没有核实路径
- A-ONCO-g1「D-NSCLC 需修两点」→ hero.promise 与 visual 不一致；checks[0].options …
- 其余为非阻塞项：deferral 措辞体例统一、explanation 混入话术脚本、board.md 条目缺失

修复策略：
1. 对每道题，若正确项文本不含核实路径关键词，而该题被判定为「边界判断题」，
   则把 explanation 里已有的核实路径措辞**迁移**进正确项（压缩到 ≤80 字），
   或追加一个通用核实动作短语。
2. D-NSCLC：hero.promise 与 visual 的 items 对齐。
3. 全局：explanation 尾部若含第一人称话术脚本（与正确项重复），删除该尾段。
4. 全局：deferral 措辞统一为「按最新说明书 / 医学信息核实」这一种表述。
"""
import json, glob, os, re

SPEC_DIR = "/workspace/output/course-specs"

# 核实路径关键词（进正确项才算数）
VERIFY_PAT = re.compile(
    r"(核实|确认|查证|不确定|需按|需要按|须按|按最新|说明书|医学信息|医学团队|"
    r"为准|核对|口径|回医学事务|请病理科|由您|交回|按方案|按您)")

# 可直接追加到正确项的核实动作（短、通用、真实可执行）
APPEND = {
    "verify": "，需按最新说明书与医学信息核实",
    "defer": "，具体以最新说明书与公司医学信息为准",
}

# 全局措辞统一：deferral 说法
DEFER_REPL = [
    (re.compile(r"具体人群、线次和用药条件我不能凭印象给[^。；]*[。；]?"), "。"),
    (re.compile(r"需要按[^。；]{0,30}核实后再给您准确答复"), "需按最新说明书与医学信息核实"),
    (re.compile(r"具体人群和条件我不确定，需要按[^。；]{0,40}"), "具体人群与条件需按最新说明书与医学信息核实"),
]

stats = {"moved": 0, "promise": 0, "explanation_cleaned": 0, "defer": 0}


def compress_to(s, limit=78):
    """把长句压到 limit 以内，尽量保留语义核心"""
    s = s.strip().rstrip("。")
    if len(s) <= limit:
        return s + "。"
    # 尝试在分句处截断
    for sep in ["，", "、", "；", "："]:
        if sep in s:
            parts = s.split(sep)
            for p in parts:
                cand = p.strip() + "。"
                if 14 <= len(cand) <= limit:
                    return cand
    # 硬截断到最近的逗号
    idx = s.rfind("，", 0, limit)
    if idx >= 14:
        return s[:idx] + "。"
    return s[:limit - 1] + "…"


def extract_verify_phrase(exp, ans):
    """从解析里抽出核实路径措辞"""
    # 找含核实关键词的短句
    for s in re.split(r"[。；]", exp):
        s = s.strip()
        if VERIFY_PAT.search(s) and 8 <= len(s) <= 46 and s not in ans:
            return s
    return None


def fix_spec(path):
    cid = os.path.basename(path)[:-5]
    spec = json.load(open(path, encoding="utf-8"))
    changed = False

    # ---- 1. 正确项补核实路径 ----
    for c in spec.get("checks", []):
        opts = c.get("options", [])
        a = c.get("answer")
        if not isinstance(a, int) or not (0 <= a < len(opts)):
            continue
        ans = str(opts[a])
        exp = c.get("explanation", "")
        if VERIFY_PAT.search(ans):
            continue
        # 该题是否属于边界判断题（题干涉及产品/数据/人群/状态）
        q = c.get("question", "")
        is_boundary = re.search(
            r"(产品|资产|适应症|获批|能不能|可不可以|状态|数据|研究|证据|疗效|安全性|人群|用在哪|怎么用|上市)", q)
        if not is_boundary:
            continue
        phrase = extract_verify_phrase(exp, ans)
        if phrase:
            new = compress_to(ans.rstrip("。") + "；" + phrase)
        else:
            new = compress_to(ans.rstrip("。") + APPEND["verify"])
        if len(new) <= 80 and new != ans:
            opts[a] = new
            changed = True
            stats["moved"] += 1
        # 长度均衡：若正确项远长于错误项，再压
        wl = [len(str(opts[k])) for k in range(len(opts)) if k != a]
        if wl and len(opts[a]) > max(wl) * 1.8 and len(opts[a]) > 60:
            opts[a] = compress_to(opts[a], int(max(wl) * 1.2))
            changed = True

    # ---- 2. explanation 尾部混入第一人称话术脚本 → 删除 ----
    for c in spec.get("checks", []):
        exp = c.get("explanation", "")
        # 形如 "我先把话说清楚：..." 开头或结尾的脚本段
        m = re.search(r"(我先说清[两]?件?事?。|我先把话说清楚：)", exp)
        if m:
            # 删掉从该处开始的整句
            new = exp[:m.start()].rstrip() + "。"
            if new != exp and len(new) > 30:
                c["explanation"] = new
                changed = True
                stats["explanation_cleaned"] += 1

    # ---- 3. deferral 措辞统一 ----
    for c in spec.get("checks", []):
        opts = c.get("options", [])
        for i, o in enumerate(opts):
            new = o
            for pat, rep in DEFER_REPL:
                new = pat.sub(rep, new)
            if new != o:
                opts[i] = new
                changed = True
                stats["defer"] += 1
        exp = c.get("explanation", "")
        new = exp
        for pat, rep in DEFER_REPL:
            new = pat.sub(rep, new)
        if new != exp:
            c["explanation"] = new
            changed = True

    # ---- 4. D-NSCLC 的 hero.promise 与 visual 对齐 ----
    if cid == "D-NSCLC":
        v = spec.get("visual", {})
        if v.get("kind") == "comparison" and v.get("items"):
            titles = " / ".join(it.get("title", "")[:12] for it in v["items"][:4])
            spec["hero"]["promise"] = f"切换四种提问情形（{titles}），看提问层级如何决定可讲与不可讲。"
            changed = True
            stats["promise"] += 1

    if changed:
        json.dump(spec, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return changed


if __name__ == "__main__":
    files = sorted(glob.glob(os.path.join(SPEC_DIR, "*.json")))
    n_changed = 0
    for f in files:
        if fix_spec(f):
            n_changed += 1
    print(f"修复 {n_changed}/{len(files)} 份 spec")
    for k, v in stats.items():
        print(f"  {k}: {v}")
