#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
语料检索工具 — 供专家 agent 在 bash 中调用。

用法:
  python3 corpus_search.py 关键词 [关键词2 ...]        # AND 匹配，返回片段
  python3 corpus_search.py --or 关键词 [关键词2 ...]    # OR 匹配
  python3 corpus_search.py --full 关键词               # 返回完整 slide 文本
  python3 corpus_search.py --list                       # 列出全部课件
  python3 corpus_search.py --topics                     # 列出主题聚合

输出为纯文本，含：课件编号 / 标题 / Slide 号 / 原文片段
"""
import os, sys, json, re, glob

TXT = "/workspace/output/phase0/corpus_txt"

_cache = {}


def load():
    if _cache:
        return _cache
    for f in sorted(glob.glob(os.path.join(TXT, "*.txt"))):
        raw = open(f, encoding="utf-8").read()
        stem = os.path.basename(f)[:-4]
        body = raw.split("\n", 1)[1] if "\n" in raw else raw
        parts = re.split(r"\n===== Slide (\d+) =====\n", body)
        slides = []
        for i in range(1, len(parts), 2):
            slides.append((int(parts[i]), parts[i + 1].strip()))
        _cache[stem] = {
            "code": stem.split("-")[0],
            "title": stem.split("-", 1)[1] if "-" in stem else stem,
            "slides": slides,
        }
    return _cache


def main():
    argv = sys.argv[1:]
    if not argv:
        print(__doc__)
        return
    data = load()

    if argv[0] == "--list":
        for stem, d in sorted(data.items(), key=lambda kv: kv[1]["code"]):
            print(f"{d['code']}\t{d['title']}\t{len(d['slides'])} slides")
        return

    if argv[0] == "--topics":
        mp = json.load(open("/workspace/output/phase0/topic_map.json", encoding="utf-8"))
        agg = {}
        for e in mp:
            for t in e["topics"]:
                agg.setdefault(t, []).append(e["code"])
        for t, codes in sorted(agg.items(), key=lambda kv: -len(kv[1])):
            print(f"{t} ({len(codes)}): {', '.join(codes)}")
        return

    full = False
    mode_and = True
    args = []
    for a in argv:
        if a == "--full":
            full = True
        elif a == "--or":
            mode_and = False
        else:
            args.append(a)

    if not args:
        print("需要关键词")
        return

    results = []
    for stem, d in data.items():
        for n, text in d["slides"]:
            if not text:
                continue
            hit = (all(a in text for a in args) if mode_and
                   else any(a in text for a in args))
            if hit:
                results.append((d["code"], d["title"], n, text))

    print(f"命中 {len(results)} 个 slide（关键词：{' AND '.join(args) if mode_and else ' OR '.join(args)}）\n")
    for code, title, n, text in results:
        print(f"───── [{code}] {title} · Slide {n} ─────")
        if full:
            print(text)
        else:
            # 输出命中词的上下文
            for a in args:
                for m in re.finditer(re.escape(a), text):
                    s = max(0, m.start() - 120)
                    e = min(len(text), m.end() + 180)
                    print("…" + text[s:e].replace("\n", " ⏎ ") + "…")
                    break
        print()


if __name__ == "__main__":
    main()
