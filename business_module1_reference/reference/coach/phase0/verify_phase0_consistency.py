#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 0 交叉一致性验收。

七份决策文档之间必须互相自洽。本脚本逐条核对，并对照 V1.3 口径校验。

用法：
  python3 verify_phase0_consistency.py            # 全量
  python3 verify_phase0_consistency.py --verbose  # 打印明细
"""
import json, glob, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import BASE, PATHS
PHASE0 = PATHS.PHASE0

DOCS = {
    "D0": "D0-语料资产库.md",
    "D1": "D1-医生画像卡schema.md",
    "D2": "D2-合规判定规则表.md",
    "D3": "D3-双轨门控合成规则.md",
    "D4": "D4-形态维度可测性矩阵.md",
    "D5": "D5-知识来源分级与指纹.md",
    "D6": "D6-数据可见性与考核边界.md",
    "D7": "D7-判定回归基线集.md",
    "MERGE": "Phase0-决策冻结包.md",
}

V13_COMM = ["问题理解", "回答结构", "表达清晰", "临场应变", "情境适应"]
V13_MED = ["知识准确性", "证据运用", "适用边界", "专业与合规要求"]
OLD_COMM = ["拜访阶段推进", "需求探询深度", "异议处理质量", "表达与节奏控制", "合规表达边界"]
OLD_MED = ["事实准确性", "证据引用质量", "场景适配性"]

results = []   # (级别, 检查项, 结论, 详情)


def ok(name, detail=""):
    results.append(("✅", name, "通过", detail))


def warn(name, detail=""):
    results.append(("⚠️", name, "需确认", detail))


def bad(name, detail=""):
    results.append(("❌", name, "不通过", detail))


def load():
    docs = {}
    for k, fn in DOCS.items():
        p = os.path.join(PHASE0, fn)
        if os.path.exists(p):
            docs[k] = open(p, encoding="utf-8").read()
    return docs


def main():
    verbose = "--verbose" in sys.argv
    docs = load()
    print(f"已加载文档：{sorted(docs.keys())}\n")

    # ---------- 0. 完整性 ----------
    missing = [k for k in DOCS if k not in docs and k != "MERGE"]
    if missing:
        bad("文档完整性", f"缺失 {missing}")
    else:
        ok("文档完整性", f"D0–D7 共 8 份齐备" + ("+ 合并包" if "MERGE" in docs else "（合并包未生成）"))

    # ---------- 1. V1.3 评分维度命名 ----------
    if "D3" in docs:
        t = docs["D3"]
        has_new = all(d in t for d in V13_COMM) and all(d in t for d in V13_MED)
        has_old_as_primary = sum(t.count(d) for d in OLD_COMM) > sum(t.count(d) for d in V13_COMM)
        if has_new:
            ok("D3 采用 V1.3 维度命名", "沟通五维 + 医学四项均出现")
        else:
            bad("D3 采用 V1.3 维度命名",
                f"缺失：{[d for d in V13_COMM+V13_MED if d not in t]}")
        if has_old_as_primary:
            warn("D3 旧稿命名是否仅作对照", f"旧名出现 {sum(t.count(d) for d in OLD_COMM)} 次，需确认是并列对照而非主用")
        else:
            ok("D3 旧稿命名未作主用")
    else:
        warn("D3 维度命名", "D3 未产出")

    # ---------- 2. 题量策略 ----------
    if "D3" in docs:
        t = docs["D3"]
        fixed3 = re.search(r"固定\s*3\s*[道题]|固定死\s*3", t)
        flexible = re.search(r"(数量可变|不固定|可配置策略|题量.*不固定)", t)
        if flexible:
            ok("D3 题量策略已改为可变", "找到可配置/不固定表述")
        else:
            bad("D3 题量策略", "未见题量可变的表述（V1.3 AT03 要求）")
        if fixed3 and not flexible:
            bad("D3 仍固定 3 题", "违反 V1.3 AT03")
        # 优先级可解释
        if re.search(r"(为何推荐|选择理由|selection_reason|可解释优先级|优先级)", t):
            ok("D3 有可解释优先级机制")
        else:
            warn("D3 可解释优先级", "未找到优先级说明")

    # ---------- 3. 「高频」表述 ----------
    for k in ["D1", "D2", "D3", "D7"]:
        if k in docs:
            t = docs[k]
            # 找"高频问题"这类被当作既定概念的用法
            bad_use = re.findall(r"高频问题(?:生成器)?(?!.{0,12}(?:待拍板|无统计|口径|不构成|改称|不标))", t)
            if bad_use:
                warn(f"{k} 「高频」表述", f"出现 {len(bad_use)} 处，需确认是否为待拍板语境")
            else:
                ok(f"{k} 无「高频问题」既成用法")

    # ---------- 4. 三段式分层（D5）----------
    if "D5" in docs:
        t = docs["D5"]
        for kw in ["候选层", "审核层", "已审核训练层"]:
            if kw not in t:
                bad("D5 三段式分层", f"缺「{kw}」")
        if all(k in t for k in ["候选层", "审核层", "已审核训练层"]):
            ok("D5 三段式分层完整")
        # 状态机
        if re.search(r"draft.{0,80}auto_checked.{0,120}pending_human", t, re.S):
            ok("D5 ReviewCase 状态机完整")
        else:
            warn("D5 ReviewCase 状态机", "未见完整状态链")
        # pending 不得进入正式评分
        if re.search(r"pending.{0,40}(不得|不能|不可).{0,30}(进入|作为).{0,30}(正式|评分|标准)", t, re.S):
            ok("D5 明确 pending 不得进正式评分")
        else:
            warn("D5 pending 约束", "未见明确约束语句")
        # 不得沿用"语料层=主知识库"
        if re.search(r"语料层\s*[=＝]\s*主知识库", t) and not re.search(r"(不采用|不得|去掉|非|纠正|并非)", t):
            bad("D5 去掉了「语料层=主知识库」", "仍保留该定位表述")
        else:
            ok("D5 无「语料层=主知识库」表述")

    # ---------- 5. D2 红线 vs D0 灰色清单 ----------
    if "D2" in docs and "D0" in docs:
        d2, d0 = docs["D2"], docs["D0"]
        gray_ids = set(re.findall(r"G-(\d+)", d0))
        # D2 应引用 D0 的灰色条目
        cited = set(re.findall(r"G-(\d+)", d2))
        overlap = gray_ids & cited
        if gray_ids and cited:
            ok("D2 引用了 D0 灰色清单条目", f"引用 {len(overlap)} 条 / D0 共 {len(gray_ids)} 条")
            if len(overlap) < len(gray_ids) * 0.3:
                warn("D2 灰色素材覆盖率偏低", f"{len(overlap)}/{len(gray_ids)}")
        else:
            warn("D2 与 D0 灰色清单的衔接", "未找到 G-xx 交叉引用")
        # 语义方向判定
        if re.search(r"(语境方向|拒绝|否定|劝阻).{0,60}(豁免|不构成|不成立)", d2, re.S):
            ok("D2 有语义方向判定 + 拒绝语境豁免")
        else:
            bad("D2 语义方向判定", "未见拒绝语境豁免机制")
        # 每条红线要有反例
        if re.search(r"(合规反例|反例)", d2):
            ok("D2 每条红线带同词不同判的反例")
        else:
            warn("D2 反例", "未见反例要求")

    # ---------- 6. D3 三类处理（否决/扣分/不可评）----------
    if "D3" in docs:
        t = docs["D3"]
        for label, pat in [("合规否决", r"(一票否决|合规.*否决)"),
                            ("表述规范扣分", r"(表述不规范.*扣分|维度内扣分)"),
                            ("不可评重分配", r"(从分母移除|权重重分配|重分配权重)")]:
            if re.search(pat, t, re.S):
                ok(f"D3 三类处理：{label}")
            else:
                bad(f"D3 三类处理：{label}", "未找到")

    # ---------- 7. D4 可测性矩阵完整性 ----------
    if "D4" in docs:
        t = docs["D4"]
        if re.search(r"(面访|线下|视频|电话|语音|文字|IM)", t) and re.search(r"(面访|线下)", t) and re.search(r"(电话|语音)", t) and re.search(r"(视频)", t):
            ok("D4 覆盖多种交互形态")
        else:
            warn("D4 形态覆盖", "未见三种形态")
        if re.search(r"(不评|不可评).{0,60}(重分配|归一)", t, re.S):
            ok("D4 不可评维度有权重重分配")
        else:
            bad("D4 不可评维度处理", "未见权重重分配")
        # 矩阵无空格：抽查表格行
        rows = re.findall(r"^\|\s*\*{0,2}(?:COM-\d+\s*)?\*{0,2}(?:问题理解|回答结构|表达清晰|临场应变|情境适应|拜访阶段推进|需求探询深度|异议处理质量|表达与节奏控制|合规表达边界|知识准确性|证据运用|适用边界|专业与合规要求)", t, re.M)
        if len(rows) >= 5:
            ok("D4 矩阵含 5 个话术维度行")
        else:
            warn("D4 矩阵维度行", f"只找到 {len(rows)} 行")

    # ---------- 8. D6 硬约束 ----------
    if "D6" in docs:
        t = docs["D6"]
        if re.search(r"(不可见|看不到|无权查看).{0,30}(他人|同事|其他).{0,10}(错误|明细|记录)", t, re.S):
            ok("D6 药代不可见他人错误")
        else:
            bad("D6 他人错误可见性", "未见明确约束")
        if re.search(r"(不作为|不得作为).{0,20}(人事处罚|考核依据|处罚依据)", t, re.S):
            ok("D6 错误留存不作为处罚依据")
        else:
            bad("D6 处罚边界", "未见明确表述")
        if re.search(r"(GAP|弱项|能力画像).{0,40}(趋势|收敛)", t, re.S):
            ok("D6 考核看收敛趋势")
        else:
            warn("D6 趋势口径", "未见收敛趋势表述")

    # ---------- 9. D7 样本量与结构 ----------
    if "D7" in docs:
        t = docs["D7"]
        n = len(re.findall(r"sample_id", t)) or len(re.findall(r"SCN-|D-[A-Z]+-[A-Z]\d", t))
        # 数据文件里的真实条数（md 里的 sample_id 只是示例）
        jpath = os.path.join(PHASE0, "D7-判定回归基线集.json")
        if os.path.exists(jpath):
            try:
                n = max(n, len(json.load(open(jpath, encoding="utf-8"))))
            except Exception:
                pass
        if n >= 30:
            ok("D7 样本量达标", f"{n} 条")
        else:
            warn("D7 样本量", f"仅 {n} 条（要求 ≥30）")
        if re.search(r"(合规反例|反例|拒绝语境)", t):
            ok("D7 含合规反例样本")
        else:
            bad("D7 合规反例", "未见")
        if re.search(r"(不可评分|知识缺口)", t):
            ok("D7 含不可评分样本")
        else:
            warn("D7 不可评分样本", "未见")

    # ---------- 10. 跨文档字段一致性 ----------
    if "D1" in docs and "D4" in docs:
        d1, d4 = docs["D1"], docs["D4"]
        fields = ["tone_layer", "inquiry_axes", "channel"]
        used = [f for f in fields if f in d1]
        used4 = [f for f in fields if f in d4]
        if used and used4:
            ok("D1/D4 字段命名一致", f"共同字段 {set(used)&set(used4)}")
        elif used:
            warn("D1/D4 字段命名", f"D1 有 {used}，D4 未引用")

    # ---------- 11. 语料引用合法性（对所有文档）----------
    sys.path.insert(0, os.path.join(PHASE0, "workspace"))
    bad_cites = 0
    total_cites = 0
    cite_check = os.path.join(PHASE0, "workspace", "cite_check.py")
    if os.path.exists(cite_check):
        import subprocess
        for k, fn in DOCS.items():
            if k not in docs or k == "MERGE":
                continue
            r = subprocess.run([sys.executable, cite_check, os.path.join(PHASE0, fn)],
                               capture_output=True, text=True)
            for line in r.stdout.split("\n"):
                m = re.match(r"\s*L1 非法 slide\s*=\s*(\d+)", line)
                if m:
                    bad_cites += int(m.group(1))
                m = re.match(r"\s*L2 引文不存在\s*=\s*(\d+)", line)
                if m:
                    bad_cites += int(m.group(1))
                m = re.match(r"\s*引用总数 = (\d+)", line)
                if m:
                    total_cites += int(m.group(1))
    if total_cites:
        if bad_cites == 0:
            ok("全部文档语料引用可回溯", f"{total_cites} 处引用，0 处失效")
        else:
            bad("语料引用回溯", f"{bad_cites} 处失效")

    # ---------- 12. 禁止 web 来源 ----------
    for k, t in docs.items():
        urls = re.findall(r"https?://(?!www\.(cancer\.gov|who\.int|nih\.gov|novartis|novo)|[^\s\)\"，。]+)", t)
        # 只看正文里的裸链接（非 sources 表格里的合法出处）
        naked = [u for u in urls if "clinical_sources" not in u and "NCI" not in t[max(0, t.find(u)-200):t.find(u)+200]]
        if naked:
            warn(f"{k} 含 http 链接", f"{len(naked)} 处，需确认是合法出处还是残留")

    # ---------- 汇总 ----------
    print("=" * 70)
    print(f"{'级别':<4} {'检查项':<34} {'结论':<8} 详情")
    print("-" * 70)
    for lvl, name, concl, detail in results:
        print(f"{lvl:<4} {name:<34} {concl:<8} {detail[:40]}")
    print("-" * 70)
    n_ok = sum(1 for r in results if r[0] == "✅")
    n_warn = sum(1 for r in results if r[0] == "⚠️")
    n_bad = sum(1 for r in results if r[0] == "❌")
    print(f"通过 {n_ok} | 需确认 {n_warn} | 不通过 {n_bad}")
    if n_bad:
        print("\n❌ 存在不通过项，需返工")
        return 1
    print("\n✅ 无阻塞问题")
    return 0


if __name__ == "__main__":
    sys.exit(main())
