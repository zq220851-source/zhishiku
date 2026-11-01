#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量渲染 v2 —— 支持多维度 spec 目录，输出到对应 html 目录，并生成合并索引。

用法：
  python3 render_courses_v2.py --spec-dir course-specs-tl --out course-html-tl --skel-dir course-skeletons-tl --dim treatment_landscape
  python3 render_courses_v2.py --all     # 渲染所有维度并生成总索引
"""
import json, glob, os, subprocess, sys, html, re, argparse

from config import BASE, PATHS
PLUGIN = ("/workspace/.plugin-cache/sha256-tree-v1-3f9c8346318647058caf3d9cbf15065c3617767322a9eba236662a37a45217c4"
          "/skills/visualize-k12-concepts/scripts/generate_visual_lesson.py")

DIMS = [
    # (维度, 短码, spec目录, html目录, skel目录, 中文名)
    ("disease_foundation", "DF", "course-specs", "course-html", "course-skeletons", "疾病基础与分型"),
    ("treatment_landscape", "TL", "course-specs-tl", "course-html-tl", "course-skeletons-tl", "治疗格局与适用边界"),
    ("clinical_evidence", "CE", "course-specs-ce", "course-html-ce", "course-skeletons-ce", "证据解读与研究质量"),
    ("treatment_landscape_phase1", "TL", "course-specs-tl", "course-html-tl", "course-skeletons-tl", "治疗格局与适用边界（一期）"),
]


def render(spec_path, out_dir):
    cid = os.path.basename(spec_path)[:-5]
    out = os.path.join(out_dir, f"{cid}.html")
    os.makedirs(out_dir, exist_ok=True)
    r = subprocess.run([sys.executable, PLUGIN, "--spec", spec_path, "--output", out],
                       capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        msg = (r.stdout + r.stderr).strip().split("\n")[-1][:150]
        return cid, False, msg
    h = open(out, encoding="utf-8").read()
    ext = re.findall(r'<(?:script|link|img)[^>]*(?:src|href)="(https?://[^"]+)"', h)
    if ext:
        return cid, False, f"外部运行时依赖: {ext[:2]}"
    return cid, True, f"{len(h.encode()):,} 字节"


def render_dim(dim, short, spec_dir, html_dir, skel_dir):
    specs = sorted(glob.glob(os.path.join(BASE, spec_dir, "*.json")))
    if not specs:
        print(f"  [{short}] 无 spec")
        return {}
    ok = 0
    results = {}
    for s in specs:
        cid, good, msg = render(s, os.path.join(BASE, html_dir))
        results[cid] = (good, msg)
        if good:
            ok += 1
        else:
            print(f"    ❌ {cid}: {msg}")
    print(f"  [{short}] {ok}/{len(specs)} 渲染成功")
    return results


def build_master_index(all_results):
    """生成跨维度总索引"""
    sections = []
    total = 0
    total_ok = 0
    for dim, short, spec_dir, html_dir, skel_dir, dim_cn in DIMS:
        results = all_results.get(dim, {})
        if not results:
            continue
        idx_p = os.path.join(BASE, skel_dir, "_index.json")
        if not os.path.exists(idx_p):
            continue
        idx = json.load(open(idx_p, encoding="utf-8"))
        rows = []
        for e in sorted(idx, key=lambda x: (x["area_id"], x["name"])):
            cid = f"{e['condition_id']}__{short}" if short != "TL" else e["condition_id"] + "__TL"
            good = results.get(cid, (False, ""))[0]
            href = f"{html_dir}/{cid}.html"
            rows.append(
                f'<tr><td class="cid">{e["condition_id"]}</td>'
                f'<td><a href="{href}">{html.escape(e["name"])}</a></td>'
                f'<td class="dim">{dim_cn}</td>'
                f'<td class="kw">{html.escape(e["keywords"] or "")}</td>'
                f'<td class="kind">{e["visual_kind"]}</td>'
                f'<td class="st">{"✅" if good else "⏳"}</td></tr>')
        n = len(idx)
        ng = sum(1 for e in idx if results.get(f"{e['condition_id']}__{short}", (False,))[0])
        total += n
        total_ok += ng
        sections.append(
            f'<section><h2>{dim_cn} <span class="cnt">{ng}/{n} 门</span></h2>'
            f'<p class="core">{html.escape(idx[0].get("area_core") or "")}</p>'
            f'<table><thead><tr><th>ID</th><th>疾病</th><th>维度</th><th>关键词</th><th>可视化</th><th>状态</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></section>')

    page = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>医药代表培训课程库 · 总索引</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#fafaf7;color:#1a1a18;font-family:'PingFang SC','Microsoft YaHei',-apple-system,sans-serif;
font-size:15px;line-height:1.6;padding:0 20px 60px}}
.wrap{{max-width:1080px;margin:0 auto}}
header{{padding:48px 0 26px;border-bottom:2px solid #1a1a18;margin-bottom:32px}}
h1{{font-size:30px;font-weight:700;letter-spacing:-.02em;margin-bottom:10px}}
.sub{{color:#5a5a54;font-size:14.5px;max-width:760px}}
.stats{{display:flex;gap:30px;margin-top:20px;flex-wrap:wrap}}
.stat b{{font-size:26px;font-weight:700;display:block;line-height:1.2}}
.stat span{{font-size:12px;color:#78786f}}
.note{{background:#fff;border-left:3px solid #d97706;padding:13px 16px;margin:22px 0;border-radius:0 8px 8px 0;
font-size:13.5px;color:#5a5a54}}
section{{margin-bottom:36px}}
section h2{{font-size:19px;font-weight:600;padding-bottom:9px;border-bottom:1px solid #dddcd4;display:flex;align-items:baseline;gap:10px}}
.cnt{{font-size:12px;color:#78786f;font-weight:400}}
.core{{font-size:13px;color:#78786f;margin:9px 0 12px}}
table{{width:100%;border-collapse:collapse;background:#fff;border:1px solid #e3e2da;border-radius:12px;overflow:hidden;font-size:13.5px}}
th{{text-align:left;font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:#78786f;font-weight:600;
padding:9px 14px;border-bottom:1px solid #e3e2da;background:#f5f5f1}}
td{{padding:8px 14px;border-bottom:1px solid #efeee8}}
tr:last-child td{{border-bottom:none}}
tr:hover{{background:#fafaf6}}
a{{color:#0d7d70;text-decoration:none}} a:hover{{text-decoration:underline}}
.cid{{font-family:ui-monospace,Menlo,monospace;font-size:12px;color:#78786f}}
.dim{{font-size:12px;color:#78786f}}
.kw{{font-size:12px;color:#78786f;max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.kind{{font-size:11px;padding:2px 7px;background:#eef4f2;color:#0d7d70;border-radius:5px;white-space:nowrap}}
.st{{text-align:center}}
footer{{border-top:1px solid #dddcd4;padding-top:18px;margin-top:36px;color:#78786f;font-size:12.5px}}
@media(max-width:760px){{.kw,.dim{{display:none}}table{{font-size:13px}}}}
</style></head><body><div class="wrap">
<header>
<h1>医药代表培训课程库</h1>
<p class="sub">按临床知识库的 competency_items 维度成课。每门课是一个独立离线 HTML 文件，可直接分发、断网使用。</p>
<div class="stats">
<div class="stat"><b>{total}</b><span>门课程</span></div>
<div class="stat"><b>{total_ok}</b><span>已渲染</span></div>
<div class="stat"><b>{len([d for d in DIMS if all_results.get(d[0])])}</b><span>知识维度</span></div>
<div class="stat"><b>100%</b><span>离线单文件</span></div>
</div>
</header>
<div class="note"><strong>使用边界：</strong>本库定位为内部培训课程设计基础数据，<strong>不是经医学事务审批的药品说明书，也不是临床决策建议</strong>。
产品与疾病的关联是教学主题关联（educational_topic_not_indication），不代表获批适应症；在研资产与已获批产品严格区分。
每门课的医学审核状态见课程清单，全部需医学团队审核后方可正式开课。</div>
{"".join(sections)}
<footer>医药代表培训课程库 · 各维度独立成课，可按需分发</footer>
</div></body></html>"""
    open(os.path.join(BASE, "course-html", "index-all.html"), "w", encoding="utf-8").write(page)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--spec-dir")
    ap.add_argument("--out")
    ap.add_argument("--skel-dir")
    ap.add_argument("--dim")
    args = ap.parse_args()

    all_results = {}
    if args.all:
        for dim, short, sd, hd, kd, cn in DIMS:
            print(f"渲染 {cn}（{short}）...")
            all_results[dim] = render_dim(dim, short, sd, hd, kd)
        build_master_index(all_results)
        print(f"\n总索引 → {BASE}/course-html/index-all.html")
    else:
        dim = args.dim
        short = {"treatment_landscape": "TL", "clinical_evidence": "CE"}[dim]
        r = render_dim(dim, short, args.spec_dir, args.out, args.skel_dir)
        all_results[dim] = r
        print(f"→ {BASE}/{args.out}")


if __name__ == "__main__":
    main()
