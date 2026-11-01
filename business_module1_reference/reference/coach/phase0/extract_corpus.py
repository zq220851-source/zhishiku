#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从医药代表培训课件库抽取纯文本，产出可检索语料。
1) .pptx -> python-pptx 直接抽（按 slide 顺序）
2) .ppt  -> 先 LibreOffice 转 .pptx，再同上
输出: corpus_txt/<原名>.txt，每个文件带 slide 分隔标记与来源元信息
"""
import os, sys, json, subprocess, shutil, glob, re

SRC = "/workspace/output/phase0/corpus/医药代表培训"
CONV = "/workspace/output/phase0/corpus/_converted"
OUT = "/workspace/output/phase0/corpus_txt"
os.makedirs(CONV, exist_ok=True)
os.makedirs(OUT, exist_ok=True)

from pptx import Presentation


def extract_pptx(path):
    """抽取 pptx 全部文本，保留 slide 边界"""
    prs = Presentation(path)
    slides = []
    for idx, slide in enumerate(prs.slides, 1):
        chunks = []

        def walk(shapes):
            for sh in shapes:
                # 组合形状递归
                if sh.shape_type == 6:  # GROUP
                    try:
                        walk(sh.shapes)
                        continue
                    except Exception:
                        pass
                # 表格
                if getattr(sh, "has_table", False):
                    try:
                        for row in sh.table.rows:
                            cells = [c.text.strip() for c in row.cells if c.text.strip()]
                            if cells:
                                chunks.append(" | ".join(cells))
                    except Exception:
                        pass
                # 文本框
                if sh.has_text_frame:
                    t = sh.text_frame.text.strip()
                    if t:
                        chunks.append(t)
                # 备注页
                try:
                    if sh.has_notes_slide:
                        nt = sh.notes_slide.notes_text_frame.text.strip()
                        if nt:
                            chunks.append("[备注] " + nt)
                except Exception:
                    pass

        walk(slide.shapes)
        # 合并被拆散的 run 时保留换行
        slides.append((idx, chunks))

    out = []
    for idx, chunks in slides:
        out.append(f"\n===== Slide {idx} =====")
        for c in chunks:
            c = re.sub(r"\n{3,}", "\n\n", c)
            out.append(c)
    return "\n".join(out)


def main():
    files = sorted(glob.glob(os.path.join(SRC, "*")), key=lambda p: (
        int(re.match(r"A(\d+)", os.path.basename(p)).group(1)) if re.match(r"A(\d+)", os.path.basename(p)) else 999))
    pptx_files = [f for f in files if f.lower().endswith(".pptx")]
    ppt_files = [f for f in files if f.lower().endswith(".ppt")]

    # 1. 转换 .ppt
    if ppt_files:
        print(f"[convert] {len(ppt_files)} 个 .ppt -> .pptx", flush=True)
        cmd = ["soffice", "--headless", "--convert-to", "pptx", "--outdir", CONV] + ppt_files
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=5400,
                           env={**os.environ, "HOME": "/tmp/lo_home"})
        print(r.stdout[-2000:], flush=True)
        if r.returncode != 0:
            print("STDERR:", r.stderr[-2000:], flush=True)

    # 2. 抽取
    manifest = []
    all_txt = []
    for f in files:
        base = os.path.basename(f)
        stem = os.path.splitext(base)[0]
        if f.lower().endswith(".ppt"):
            cand = os.path.join(CONV, stem + ".pptx")
            if not os.path.exists(cand):
                print(f"[skip] 转换失败: {base}", flush=True)
                continue
            src_used = cand
        else:
            src_used = f
        try:
            text = extract_pptx(src_used)
        except Exception as e:
            print(f"[err] {base}: {e}", flush=True)
            continue
        outp = os.path.join(OUT, stem + ".txt")
        header = f"# 来源文件: {base}\n# 课件编号: {stem.split('-')[0]}\n# 标题: {stem.split('-',1)[1] if '-' in stem else stem}\n"
        with open(outp, "w", encoding="utf-8") as fh:
            fh.write(header + text)
        n_slides = text.count("===== Slide ")
        n_chars = len(text)
        manifest.append({"stem": stem, "title": stem.split('-', 1)[1] if '-' in stem else stem,
                         "file": base, "slides": n_slides, "chars": n_chars, "txt": os.path.basename(outp)})
        all_txt.append(f"\n\n@@@@@@@@ FILE: {stem} ({base}) slides={n_slides} @@@@@@@@\n" + text)
        print(f"[ok] {base}: {n_slides} slides, {n_chars} chars", flush=True)

    with open(os.path.join(OUT, "_manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)
    with open("/workspace/output/phase0/corpus_all.txt", "w", encoding="utf-8") as fh:
        fh.write("".join(all_txt))
    tot = sum(m["slides"] for m in manifest)
    print(f"\n[DONE] {len(manifest)} files, {tot} slides, "
          f"{sum(m['chars'] for m in manifest)} chars -> {OUT}", flush=True)


if __name__ == "__main__":
    main()
