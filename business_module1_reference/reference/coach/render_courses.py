#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量渲染：course-specs/*.json -> course-html/<condition_id>.html + 索引页
使用 K12 插件的 generate_visual_lesson.py 生成器（不重写渲染逻辑，保证离线自包含）。

用法：
  python3 render_courses.py            # 渲染全部并生成索引
  python3 render_courses.py --only D-NSCLC
"""
import json, glob, os, subprocess, sys, html, time

from config import BASE, PATHS
PLUGIN = ("/workspace/.plugin-cache/sha256-tree-v1-3f9c8346318647058caf3d9cbf15065c3617767322a9eba236662a37a45217c4"
          "/skills/visualize-k12-concepts/scripts/generate_visual_lesson.py")
SPEC_DIR = os.path.join(BASE, "course-specs")
HTML_DIR = os.path.join(BASE, "course-html")
SKEL_DIR = os.path.join(BASE, "course-skeletons")

os.makedirs(HTML_DIR, exist_ok=True)


def render(spec_path):
    cid = os.path.basename(spec_path)[:-5]
    out = os.path.join(HTML_DIR, f"{cid}.html")
    r = subprocess.run([sys.executable, PLUGIN, "--spec", spec_path, "--output", out],
                       capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        return cid, False, (r.stdout + r.stderr).strip().split("\n")[-1][:160]
    # 离线性检查：不得有外部运行时资源
    h = open(out, encoding="utf-8").read()
    import re
    ext = re.findall(r'<(?:script|link|img)[^>]*(?:src|href)="(https?://[^"]+)"', h)
    if ext:
        return cid, False, f"外部运行时依赖: {ext[:2]}"
    return cid, True, f"{len(h.encode()):,} 字节"


def build_index(results):
    skeletons = {}
    for f in glob.glob(os.path.join(SKEL_DIR, "*.json")):
        cid = os.path.basename(f)[:-5]
        if cid.startswith("_"):
            continue
        skeletons[cid] = json.load(open(f, encoding="utf-8"))

    by_area = {}
    for cid, sk in skeletons.items():
        by_area.setdefault(sk["area"]["area_id"], []).append((cid, sk))

    cards = []
    for cid, sk in sorted(skeletons.items()):
        ok = cid in results and results[cid][1]
        cards.append({
            "cid": cid, "name": sk["condition_name"], "area": sk["area"]["name"],
            "dept": sk["area"]["department"], "kind": sk["visual_kind"],
            "kw": sk["keywords"], "scope": sk["competency_scope"],
            "ok": ok, "src": sk["source"].get("title"), "url": sk["source"].get("url"),
            "asof": sk["source"].get("asof_date"),
        })

    # 生成 HTML 索引
    area_cards = []
    for aid, items in sorted(by_area.items()):
        items.sort(key=lambda x: x[1]["condition_name"])
        rows = []
        for cid, sk in items:
            c = next(c for c in cards if c["cid"] == cid)
            badge = "✅" if c["ok"] else "⏳"
            rows.append(
                f'<li class="row"><a class="row-link" href="{cid}.html">'
                f'<span class="cid">{cid}</span>'
                f'<span class="nm">{html.escape(sk["condition_name"])}</span>'
                f'<span class="kw">{html.escape(sk["keywords"] or "")}</span>'
                f'<span class="kind">{c["kind"]}</span>'
                f'<span class="badge">{badge}</span></a></li>')
        area_cards.append(
            f'<section class="area"><h2>{html.escape(items[0][1]["area"]["name"])}'
            f'<span class="cnt">{len(items)} 门</span></h2>'
            f'<p class="core">{html.escape(items[0][1]["area"]["core_competencies"] or "")}</p>'
            f'<ul class="list">{"".join(rows)}</ul></section>')

    ok_n = sum(1 for c in cards if c["ok"])
    page = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>医药代表培训课程库 · 42 门疾病基础课</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#fafaf7;color:#1a1a18;font-family:'PingFang SC','Microsoft YaHei',-apple-system,sans-serif;
font-size:15px;line-height:1.65;padding:0 20px 60px}}
.wrap{{max-width:960px;margin:0 auto}}
header{{padding:48px 0 28px;border-bottom:2px solid #1a1a18;margin-bottom:36px}}
h1{{font-size:30px;font-weight:700;letter-spacing:-.02em;margin-bottom:12px}}
.sub{{color:#5a5a54;font-size:14.5px;max-width:680px}}
.stats{{display:flex;gap:28px;margin-top:22px;flex-wrap:wrap}}
.stat b{{font-size:26px;font-weight:700;display:block;line-height:1.2}}
.stat span{{font-size:12px;color:#78786f}}
.area{{margin-bottom:34px}}
.area h2{{font-size:19px;font-weight:600;padding-bottom:9px;border-bottom:1px solid #dddcd4;
display:flex;align-items:baseline;gap:10px}}
.cnt{{font-size:12px;color:#78786f;font-weight:400}}
.core{{font-size:13px;color:#78786f;margin:9px 0 13px}}
.list{{list-style:none;border:1px solid #e3e2da;border-radius:12px;overflow:hidden;background:#fff}}
.row{{border-bottom:1px solid #efeee8}}
.row:last-child{{border-bottom:none}}
.row-link{{display:grid;grid-template-columns:96px 1fr 190px 108px 22px;gap:12px;align-items:center;
padding:11px 15px;text-decoration:none;color:inherit}}
.row-link:hover{{background:#f4f4ef}}
.cid{{font-family:ui-monospace,Menlo,monospace;font-size:12px;color:#0d7d70}}
.nm{{font-weight:500;font-size:14.5px}}
.kw{{font-size:12px;color:#78786f;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.kind{{font-size:11px;padding:2px 8px;background:#eef4f2;color:#0d7d70;border-radius:5px;text-align:center}}
.badge{{font-size:13px;text-align:center}}
footer{{border-top:1px solid #dddcd4;padding-top:20px;margin-top:40px;color:#78786f;font-size:12.5px}}
.note{{background:#fff;border-left:3px solid #d97706;padding:13px 16px;margin:22px 0;border-radius:0 8px 8px 0;
font-size:13.5px;color:#5a5a54}}
@media(max-width:720px){{.row-link{{grid-template-columns:82px 1fr 22px}}.kw,.kind{{display:none}}}}
</style></head><body><div class="wrap">
<header>
<h1>医药代表培训课程库</h1>
<p class="sub">42 门疾病基础课，全部依据临床知识库的教学范围编写。内容定位为<strong>内部培训课程设计基础数据</strong>，不是经医学事务审批的说明书，也不是临床决策建议。</p>
<div class="stats">
<div class="stat"><b>{len(cards)}</b><span>门课程</span></div>
<div class="stat"><b>{ok_n}</b><span>已渲染</span></div>
<div class="stat"><b>{len(by_area)}</b><span>治疗领域</span></div>
<div class="stat"><b>100%</b><span>离线单文件</span></div>
</div>
</header>
<div class="note"><strong>使用边界：</strong>每门课标注了来源与版本日期（asof_date）。课程中的疾病分型、标志物维度为教学框架；产品与疾病的关联是教学主题关联（educational_topic_not_indication），<strong>不代表该产品已获批该疾病适应症</strong>。在研资产与已获批产品严格区分。涉及具体临床数值与适应症表述，须以最新说明书与医学事务审核为准。</div>
{"".join(area_cards)}
<footer>生成于 {time.strftime('%Y-%m-%d %H:%M')} · 每门课为独立离线 HTML 文件，可直接分发</footer>
</div></body></html>"""
    with open(os.path.join(HTML_DIR, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(page)
    return len(cards), ok_n


def main():
    args = sys.argv[1:]
    specs = sorted(glob.glob(os.path.join(SPEC_DIR, "*.json")))
    if "--only" in args:
        want = args[args.index("--only") + 1]
        specs = [s for s in specs if os.path.basename(s)[:-5] == want]
    if not specs:
        print("无 spec")
        return

    results = {}
    fails = []
    for s in specs:
        cid, ok, msg = render(s)
        results[cid] = (ok, msg)
        print(f"  {'✅' if ok else '❌'} {cid}: {msg}")
        if not ok:
            fails.append((cid, msg))

    total, ok_n = build_index(results)
    print(f"\n渲染完成：{ok_n}/{total} 成功")
    if fails:
        print("失败项：")
        for cid, m in fails:
            print(f"  {cid}: {m}")
    print(f"索引 -> {HTML_DIR}/index.html")


if __name__ == "__main__":
    main()
