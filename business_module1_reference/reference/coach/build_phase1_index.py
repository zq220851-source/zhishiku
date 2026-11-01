#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成一期专属索引页：8 个疾病 × 多个维度的矩阵视图。
培训师实际使用视图——按疾病看有哪些课、按维度看覆盖了什么。
"""
import json, os, glob, html, time

from config import BASE, PATHS
A = os.path.join(BASE, "version-A-training-pack")
os.makedirs(A, exist_ok=True)

cfg = json.load(open(os.path.join(A, "phase1-config.json"), encoding="utf-8"))
PHASE1 = cfg["phase1"]["conditions"]

DIM_LABEL = {
    "DF": ("疾病基础", "disease_foundation", "分型逻辑与评估维度"),
    "TL": ("治疗格局", "treatment_landscape", "机制类别与适用边界"),
    "CE": ("证据解读", "clinical_evidence", "研究设计与证据质量"),
    "PL": ("管线认知", "pipeline_literacy", "披露状态与审批状态"),
    "PB": ("产品基础", "product_basics", "通用名靶点与核查路径"),
}
DIM_ORDER = ["DF", "TL", "CE", "PL", "PB"]

# 收集所有课程
courses = {}
# ★ 目录名必须与版本 A 包内一致。
#   包内是 specs*/ 与 courses*/，这里原写 course-specs*/ 与 course-html*，
#   导致索引页 37 个链接全部失效（404）。
# ★ spec 与 html 都从版本 A 包内读——包是唯一事实来源。
#   原先从 BASE 下的 course-specs*/ 读、链到 course-html*，
#   与包内 specs*/ + courses*/ 都不一致，索引页 37 个链接全失效。
PACK = os.path.join(BASE, "version-A-training-pack")
for spec_dir, html_dir, short in [("specs", "courses", "DF"),
                                 ("specs-tl", "courses-tl", "TL"),
                                 ("specs-ce", "courses-ce", "CE")]:
    for f in sorted(glob.glob(os.path.join(PACK, spec_dir, "*.json"))):
        cid = os.path.basename(f)[:-5]
        if "__" in cid:
            base, sh = cid.split("__")
        else:
            base, sh = cid, short
        if base not in PHASE1 and sh not in ("PL", "PB"):
            continue
        # PL/PB 是资产视角，只在一期产品范围内
        if sh in ("PL", "PB"):
            if base not in {p["id"] for p in cfg["phase1"]["products"]}:
                continue
        hp = os.path.join(PACK, html_dir, f"{cid}.html")
        if not os.path.exists(hp):
            continue
        spec = json.load(open(f, encoding="utf-8"))
        courses.setdefault(base, {})[sh] = {
            "cid": cid, "title": spec["meta"]["title"],
            "html": f"{html_dir}/{cid}.html",
            "keywords": spec.get("keywords", ""),
        }

# 资产视角的课单独成组
asset_courses = {}
for base, dims in list(courses.items()):
    if set(dims.keys()) & {"PL", "PB"}:
        for sh in ("PL", "PB"):
            if sh in dims:
                asset_courses.setdefault(base, {})[sh] = dims.pop(sh)
        if not dims:
            del courses[base]

total = sum(len(v) for v in courses.values()) + sum(len(v) for v in asset_courses.values())

# ---------- 疾病维度矩阵 ----------
matrix_rows = []
for cid in PHASE1:
    dims = courses.get(cid, {})
    name = next((c["title"].split("：")[0] for c in dims.values()), cid)
    cells = []
    for sh in DIM_ORDER:
        if sh in dims:
            d = dims[sh]
            cells.append(f'<td class="has"><a href="{d["html"]}"><span class="dim">{sh}</span>'
                         f'<span class="t">{html.escape(d["title"].split("：",1)[-1])}</span></a></td>')
        else:
            cells.append('<td class="none">—</td>')
    matrix_rows.append(f'<tr><th>{html.escape(name)}<span class="cid">{cid}</span></th>{"".join(cells)}</tr>')

# ---------- 资产维度矩阵 ----------
asset_rows = []
for pid, dims in sorted(asset_courses.items()):
    name = list(dims.values())[0]["title"].split("：")[0]
    cells = []
    for sh in DIM_ORDER:
        if sh in dims:
            d = dims[sh]
            cells.append(f'<td class="has"><a href="{d["html"]}"><span class="dim">{sh}</span>'
                         f'<span class="t">{html.escape(d["title"].split("：",1)[-1])}</span></a></td>')
        else:
            cells.append('<td class="none">—</td>')
    asset_rows.append(f'<tr><th>{html.escape(name)}<span class="cid">{pid}</span></th>{"".join(cells)}</tr>')

prod_rows = ""
for p in cfg["phase1"]["products"]:
    nm = p["name"]
    mech = p.get("mechanism_topic") or "—"
    st = "已商业化" if p["status"] == "commercialized" else "在研"
    if p["status"] == "pipeline":
        rs = (p.get("reported_status") or "—")
        ast = p.get("approval_status") or "—"
        prod_rows += (f'<tr><td class="pname">{html.escape(nm)}</td><td>{html.escape(mech)}</td>'
                      f'<td><span class="tag-pipe">在研</span></td>'
                      f'<td class="small">{html.escape(rs)}</td>'
                      f'<td class="small mono">{html.escape(ast)}</td></tr>')
    else:
        prod_rows += (f'<tr><td class="pname">{html.escape(nm)}</td><td>{html.escape(mech)}</td>'
                      f'<td><span class="tag-comm">已商业化</span></td><td class="small">—</td>'
                      f'<td class="small">—</td></tr>')

page = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>医药代表培训课程库 · 一期</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#fafaf7;color:#1a1a18;font-family:'PingFang SC','Microsoft YaHei',-apple-system,sans-serif;
font-size:15px;line-height:1.6;padding:0 20px 60px}}
.wrap{{max-width:1080px;margin:0 auto}}
header{{padding:44px 0 24px;border-bottom:2px solid #1a1a18;margin-bottom:30px}}
h1{{font-size:29px;font-weight:700;letter-spacing:-.02em;margin-bottom:8px}}
.sub{{color:#5a5a54;font-size:14.5px;max-width:700px}}
.stats{{display:flex;gap:26px;margin-top:18px;flex-wrap:wrap}}
.stat b{{font-size:24px;font-weight:700;display:block;line-height:1.2}}
.stat span{{font-size:12px;color:#78786f}}
h2{{font-size:18px;font-weight:600;margin:34px 0 12px;padding-bottom:8px;border-bottom:1px solid #dddcd4;
display:flex;align-items:baseline;gap:10px}}
h2 .n{{font-size:12px;color:#78786f;font-weight:400}}
table{{width:100%;border-collapse:separate;border-spacing:0;background:#fff;border:1px solid #e3e2da;
border-radius:12px;overflow:hidden;font-size:13.5px}}
th,td{{padding:9px 12px;text-align:left;border-bottom:1px solid #efeee8;vertical-align:top}}
tr:last-child th,tr:last-child td{{border-bottom:none}}
thead th{{font-size:11px;letter-spacing:.05em;color:#78786f;font-weight:600;background:#f5f5f1;
text-transform:uppercase;border-bottom:1px solid #e3e2da}}
tbody th{{font-weight:600;white-space:nowrap;background:#fbfbf8}}
tbody th .cid{{display:block;font-family:ui-monospace,Menlo,monospace;font-size:11px;color:#a0a09a;font-weight:400}}
td.has{{background:#fff}}
td.has a{{display:block;text-decoration:none;color:inherit;border-left:3px solid #0d7d70;padding-left:9px}}
td.has a:hover .t{{text-decoration:underline}}
td.has .dim{{display:inline-block;font-family:ui-monospace,Menlo,monospace;font-size:10px;color:#0d7d70;
background:#eef4f2;padding:1px 5px;border-radius:4px;margin-bottom:2px}}
td.has .t{{display:block;font-size:12.5px;color:#3a3a35}}
td.none{{color:#c8c8c0;text-align:center}}
.mono{{font-family:ui-monospace,Menlo,monospace;font-size:11.5px}}
.small{{font-size:12px;color:#5a5a54}}
.pname{{font-weight:600}}
.tag-comm{{font-size:11px;padding:2px 8px;border-radius:5px;background:#d1fae5;color:#065f46}}
.tag-pipe{{font-size:11px;padding:2px 8px;border-radius:5px;background:#fef3c7;color:#92400e}}
.note{{background:#fff;border-left:3px solid #d97706;padding:13px 16px;margin:20px 0;border-radius:0 8px 8px 0;
font-size:13.5px;color:#5a5a54}}
.legend{{display:flex;gap:16px;margin:12px 0 0;font-size:12.5px;color:#78786f;flex-wrap:wrap}}
.legend b{{color:#1a1a18;font-weight:600}}
footer{{border-top:1px solid #dddcd4;padding-top:16px;margin-top:34px;color:#78786f;font-size:12.5px}}
@media(max-width:820px){{
 .row-hide{{display:none}}
 th,td{{padding:7px 8px;font-size:12.5px}}
}}
</style></head><body><div class="wrap">
<header>
<h1>医药代表培训课程库 · 一期</h1>
<p class="sub">治疗领域：{cfg['phase1']['therapeutic_area']['name']}　·　疾病 {len(PHASE1)} 个　·　每个疾病多个知识维度的课。点任一格进入该课（单文件离线 HTML，可直接分发）。</p>
<div class="stats">
<div class="stat"><b>{total}</b><span>门课程</span></div>
<div class="stat"><b>{len(PHASE1)}</b><span>疾病</span></div>
<div class="stat"><b>{len(cfg['phase1']['products'])}</b><span>产品与管线</span></div>
<div class="stat"><b>{cfg['phase1']['pilot']['weeks']}</b><span>周试点</span></div>
</div>
</header>

<div class="note"><strong>使用边界：</strong>本库全部内容属 V1.3 的<strong>新信息候选层</strong>——来源可溯源、允许带不确定性展示，但<strong>未经 ReviewCase 签审，不得作为正式评分依据或标准答案</strong>。
产品与疾病的关联一律为教学主题关联（educational_topic_not_indication），不代表获批适应症；课程中「披露状态」与「审批状态」分别表述，不得合并。</div>

<h2>疾病课程矩阵 <span class="n">按疾病 × 知识维度</span></h2>
<div class="legend">
<b>DF</b> 疾病基础 · 分型逻辑与评估维度　
<b>TL</b> 治疗格局 · 机制类别与适用边界　
<b>CE</b> 证据解读 · 研究设计与证据质量　
<b>PL</b> 管线认知 · 披露状态与审批状态　
<b>PB</b> 产品基础 · 通用名靶点与核查路径
</div>
<table>
<thead><tr><th>疾病</th>{"".join(f'<th class="row-hide">{DIM_LABEL[s][0]}<br><span style="font-weight:400;font-size:10px">{DIM_LABEL[s][2]}</span></th>' for s in DIM_ORDER)}</tr></thead>
<tbody>{"".join(matrix_rows)}</tbody></table>

<h2>产品与管线课程矩阵 <span class="n">按资产 × 知识维度</span></h2>
<table>
<thead><tr><th>产品 / 管线</th>{"".join(f'<th class="row-hide">{DIM_LABEL[s][0]}</th>' for s in DIM_ORDER)}</tr></thead>
<tbody>{"".join(asset_rows)}</tbody></table>

<h2>一期产品范围 <span class="n">{len(cfg['phase1']['products'])} 个</span></h2>
<table>
<thead><tr><th>产品 / 管线</th><th>机制方向</th><th>状态</th><th class="row-hide">披露口径</th><th class="row-hide">审批状态</th></tr></thead>
<tbody>{prod_rows}</tbody></table>

<footer>医药代表培训课程库 · 一期 · 生成于 {time.strftime('%Y-%m-%d %H:%M')} ·
签审工作单与 rubric 工作单见 signoff/ · 一期配置见 phase1-config.json</footer>
</div></body></html>"""

open(os.path.join(A, "index-phase1.html"), "w", encoding="utf-8").write(page)
print(f"✅ 一期索引页已生成：index-phase1.html（{total} 门课 / {len(PHASE1)} 疾病）")
print("  疾病维度:", {c: sorted(v.keys()) for c, v in sorted(courses.items())})
print("  资产维度:", {c: sorted(v.keys()) for c, v in sorted(asset_courses.items())})
