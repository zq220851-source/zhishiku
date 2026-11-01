#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复超长选项 —— 语义压缩而非截断。

方法：
  1. 若选项含分号/句号，切成多个语义单元，保留"核心主张 + 核实路径提示"两段
  2. 若选项超长且含"需要按...核实/确认/回复"这类尾巴，把核实路径移到 explanation
  3. 压缩后的选项仍需能区分对错：保留关键标志物/维度词
"""
import json, glob, os, re, sys

SPEC_DIR = "/workspace/output/course-specs"
LIMIT = 78  # 留 2 字余量


def compress(opt, target_len=None):
    """把长选项压成短的核心主张句，保留可判别性。
    target_len: 若给出，则压缩到不超过该长度（用于均衡正确项与错误项）
    """
    o = opt.strip()
    limit = min(LIMIT, target_len) if target_len else LIMIT

    parts = re.split(r"[。；;]", o)
    parts = [p.strip() for p in parts if p.strip()]

    verify_marks = ("不确定", "需要按", "需要以", "需按", "以最新", "核实", "会请医学",
                    "不能凭", "回复您", "请医学", "确认后", "以说明书", "以方案", "以披露",
                    "具体能覆盖", "回复。", "再回复")

    cands = []
    for p in parts:
        if any(m in p for m in verify_marks):
            continue
        p2 = re.sub(r"^(我先说清两件事[：:]?|我先把话说清楚[：:]?|我拆成两件事讲[：:]?|"
                    r"通常要结合|要先说清|关键在于|我要跟您说清楚[：:]?|我先说清[：:]?)",
                    "", p).strip()
        if len(p2) >= 10:
            cands.append(p2)

    # 优先选既短又含判别性关键词的
    for c in cands:
        if len(c) <= limit:
            return c + "。"
    if cands:
        c = min(cands, key=len)
        if len(c) <= LIMIT:
            # 还太长：在逗号处断
            m = re.match(r"^(.{10,%d})[，,]" % LIMIT, c)
            if m:
                return m.group(1) + "。"
            return c[:LIMIT] + "…"
    return o[:limit] + "…"


def main():
    args = sys.argv[1:]
    files = sorted(glob.glob(os.path.join(SPEC_DIR, "*.json")))
    if "--file" in args:
        files = [args[args.index("--file") + 1]]
    fixed_files = 0
    fixed_opts = 0
    for f in files:
        try:
            spec = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        changed = False
        for ci, c in enumerate(spec.get("checks", [])):
            opts = c.get("options", [])
            a = c.get("answer")
            # 第一步：长度压缩
            for oi, o in enumerate(opts):
                if len(str(o)) > LIMIT:
                    new = compress(str(o))
                    tail = str(o)
                    moved = [s for s in re.split(r"[。；;]", tail)
                             if any(m in s for m in ("不确定", "需要按", "需按", "以最新", "核实",
                                                    "会请医学", "不能凭", "请医学", "以说明书",
                                                    "以方案", "以披露", "回复您"))]
                    if moved:
                        extra = "；".join(x.strip() for x in moved) + "。"
                        if extra not in c.get("explanation", ""):
                            c["explanation"] = c.get("explanation", "").rstrip() + extra
                    opts[oi] = new
                    changed = True
                    fixed_opts += 1
            # 第二步：均衡 —— 正确项显著长于错误项时，再压缩正确项
            if isinstance(a, int) and 0 <= a < len(opts):
                wrong_max = max([len(str(opts[k])) for k in range(len(opts)) if k != a] or [0])
                corr_len = len(str(opts[a]))
                if corr_len > wrong_max * 1.6 and corr_len > 40:
                    target = max(24, int(wrong_max * 1.15))
                    new = compress(str(opts[a]), target_len=target)
                    if len(new) < len(str(opts[a])):
                        opts[a] = new
                        changed = True
                        fixed_opts += 1
        if changed:
            json.dump(spec, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
            fixed_files += 1
    print(f"修复 {fixed_opts} 个超长选项，涉及 {fixed_files} 份 spec")


if __name__ == "__main__":
    main()
