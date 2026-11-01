#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知识检索层 —— 「LLM 参考数据库」的实现。

为什么必须有这一层
------------------
VLM/文本 LLM **不知道**我们的医学事实。让它自由发挥 = 让它编造。
实测中 VLM 面对「这个药获批了吗」只能给条件式回答，因为它没有事实来源。

所以流程必须是：
    检索事实（带出处）→ 构造受控提示 → LLM 生成 → 事实校验

检索层的硬规则
--------------
1. **运行时只读本地库**：信达临床知识库 v0.5 + 课件语料库。
   公开参考文献经人工整理入库后只供独立参考检索；运行时不做 web 检索。
2. **每条事实带出处**：source_id / 表名 / 行 ID / 效力等级（对齐 D5 的 S1–S7）。
3. **效力低的不能当医学依据**：S5（课件培训材料）只能作沟通训练依据，
   S6（演示道具）/S7（灰色手法）绝不返回。
4. **披露 ≠ 审批**：管线的 reported_status 与 approval_status 必须分列返回。
5. **教学关联 ≠ 适应症**：product_condition_map 的 link_type 一律
   educational_topic_not_indication，不得表述为获批适应症。
"""
import argparse, json, os, re, sqlite3
from collections import defaultdict

# ★ 路径统一来自配置中心
from config import BASE, PATHS

CLIN_DB = PATHS.CLIN_DB
CORPUS_DIR = PATHS.PHASE0
COURSE_DIRS = [PATHS.COURSE_SPECS, PATHS.COURSE_SPECS_TL, PATHS.COURSE_SPECS_CE]

# 效力等级（对齐 D5 §2）
S1, S2, S3, S4, S5, S6, S7 = "S1", "S2", "S3", "S4", "S5", "S6", "S7"

# 课件演示道具 —— 绝不返回（D5 §2.2）
DEMO_PROPS = ["双氢可待因", "智灵通", "傣药", "Ａ产品"]


class KnowledgeBase:
    """只读检索层。加载一次，之后全部走内存索引。"""

    def __init__(self, db_path=CLIN_DB):
        self.db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        self.db.row_factory = sqlite3.Row
        self._load()
        self._load_courses()

    # ---------- 加载 ----------
    def _load(self):
        q = lambda s: [dict(r) for r in self.db.execute(s)]
        self.products = {r["product_id"]: r for r in q("select * from med_products")}
        self.pipeline = {r["asset_id"]: r for r in q("select * from expanded_pipeline")}
        self.conditions = {r["condition_id"]: r for r in q("select * from clinical_conditions")}
        self.clin_sources = {r["source_id"]: r for r in q("select * from clinical_sources")}
        self.sources = {r["source_id"]: r for r in q("select * from sources")}

        # 公开参考资料是候选层，不进入 medical_usable 或自动评分。
        has_external = self.db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='external_reference_documents'"
        ).fetchone()
        if has_external:
            self.external_documents = {
                r["document_id"]: r for r in q("SELECT * FROM external_reference_documents")
            }
            self.external_points = q("SELECT * FROM external_reference_points")
        else:
            self.external_documents = {}
            self.external_points = []

        # 用户提供的书籍仅作可追溯的沟通训练候选，不进入医学事实包。
        has_books = self.db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='local_book_documents'"
        ).fetchone()
        if has_books:
            self.book_documents = {
                r["book_id"]: r for r in q("SELECT * FROM local_book_documents")
            }
            self.book_points = q("SELECT * FROM local_book_points")
        else:
            self.book_documents = {}
            self.book_points = []

        self.prod_cond = defaultdict(list)
        for r in q("select * from product_condition_map"):
            self.prod_cond[r["product_id"]].append(r)
        self.pipe_cond = defaultdict(list)
        for r in q("select * from pipeline_condition_map"):
            self.pipe_cond[r["asset_id"]].append(r)

        self.competency = defaultdict(list)
        for r in q("select * from competency_items"):
            self.competency[(r["subject_type"], r["subject_id"])].append(r)

        # 产品/管线 → 疾病 关键词索引（供检索用）
        self.prod_keywords = defaultdict(set)
        for pid, rows in self.prod_cond.items():
            for r in rows:
                cid = r["condition_id"]
                c = self.conditions.get(cid)
                if c and c.get("keywords"):
                    for kw in str(c["keywords"]).split(";"):
                        if kw.strip():
                            self.prod_keywords[pid].add(kw.strip())

    def _load_courses(self):
        """一期课程 spec —— 作为 S5 级沟通训练依据（不作为医学事实）"""
        self.courses = {}
        for d in COURSE_DIRS:
            if not os.path.isdir(d):
                continue
            for f in sorted(os.listdir(d)):
                if not f.endswith(".json"):
                    continue
                p = os.path.join(d, f)
                try:
                    j = json.load(open(p, encoding="utf-8"))
                except Exception:
                    continue
                cid = os.path.basename(f)[:-5]
                self.courses[cid] = {
                    "spec": j,
                    "title": (j.get("meta") or {}).get("title"),
                    "goal": j.get("goal"),
                    "level": S5,      # 课件 = 培训材料，不是法律依据
                    "kind": "course",
                }

    # ---------- 检索 ----------
    def find_products(self, text, limit=6):
        """按文本找相关产品（已商业化）"""
        hits = []
        t = (text or "")
        for pid, p in self.products.items():
            score = 0
            why = []
            if p.get("brand") and p["brand"] in t:
                score += 10; why.append(f"品牌名「{p['brand']}」")
            if p.get("generic_name") and p["generic_name"] in t:
                score += 8; why.append(f"通用名「{p['generic_name']}」")
            if p.get("mechanism_topic") and p["mechanism_topic"] in t:
                score += 6; why.append(f"靶点「{p['mechanism_topic']}」")
            for kw in self.prod_keywords.get(pid, ()):
                if kw in t:
                    score += 3; why.append(f"关联疾病关键词「{kw}」")
                    break
            if score:
                hits.append((score, pid, why))
        hits.sort(reverse=True)
        return [(pid, why) for _s, pid, why in hits[:limit]]

    def find_pipeline(self, text, limit=6):
        """按文本找相关管线资产"""
        hits = []
        t = (text or "")
        for aid, a in self.pipeline.items():
            score = 0
            why = []
            if aid in t:
                score += 10; why.append(f"资产代号「{aid}」")
            if a.get("mechanism_topic") and a["mechanism_topic"] in t:
                score += 7; why.append(f"机制方向「{a['mechanism_topic']}」")
            for cid in [r["condition_id"] for r in self.pipe_cond.get(aid, [])]:
                c = self.conditions.get(cid)
                if c and c.get("keywords"):
                    for kw in str(c["keywords"]).split(";"):
                        if kw.strip() and kw.strip() in t:
                            score += 3
                            why.append(f"关联疾病关键词「{kw.strip()}」")
                            break
            if score:
                hits.append((score, aid, why))
        hits.sort(reverse=True)
        return [(aid, why) for _s, aid, why in hits[:limit]]

    def find_conditions(self, text, limit=6):
        hits = []
        t = (text or "")
        for cid, c in self.conditions.items():
            score = 0
            why = []
            if c.get("name") and c["name"] in t:
                score += 10; why.append(f"疾病名「{c['name']}」")
            if cid in t:
                score += 10; why.append(f"疾病ID「{cid}」")
            for kw in str(c.get("keywords") or "").split(";"):
                if kw.strip() and kw.strip() in t:
                    score += 4; why.append(f"关键词「{kw.strip()}」")
                    break
            if score:
                hits.append((score, cid, why))
        hits.sort(reverse=True)
        return [(cid, why) for _s, cid, why in hits[:limit]]

    # ---------- 组装事实包 ----------
    def fact_bundle(self, question, condition_id=None, limit_products=4,
                    limit_pipeline=4, limit_conditions=4):
        """
        检索并组装「事实包」——给 LLM 的唯一医学事实来源。

        每条 fact：
          claim      要说的事实
          level      效力等级（S1–S5）
          source     出处（可核对）
          confidence 该事实能否作为医学依据（S5 → 仅沟通训练）
        """
        facts = []

        # ---- 产品 ----
        for pid, why in self.find_products(question, limit_products):
            p = self.products[pid]
            src = self.clin_sources.get(p.get("reference_source"), {})
            facts.append({
                "kind": "product",
                "id": pid,
                "claim": (
                    f"产品「{p.get('brand')}」（通用名 {p.get('generic_name')}），"
                    f"机制方向 {p.get('mechanism_topic')}，领域 {p.get('domain')}。"
                ),
                "level": S2,
                "source": (f"clinical:med_products#{pid} | "
                           f"source_id={p.get('reference_source')}"
                           + (f" | {src.get('title')}" if src.get("title") else "")),
                "confidence": "可核实可讲",
                "matched_by": why,
            })
            # 教学关联 —— 必须带 link_type，不可表述为适应症
            for r in self.prod_cond.get(pid, []):
                c = self.conditions.get(r["condition_id"], {})
                facts.append({
                    "kind": "teaching_link",
                    "id": f"{pid}→{r['condition_id']}",
                    "claim": (
                        f"「{p.get('brand')}」与「{c.get('name', r['condition_id'])}」存在"
                        f"**教学主题关联**（link_type={r.get('link_type')}）——"
                        f"这**不是获批适应症**，不得表述为可用于该疾病。"
                    ),
                    "level": S2,
                    "source": f"clinical:product_condition_map#{pid}→{r['condition_id']}",
                    "confidence": "边界事实，必须原样传达",
                    "matched_by": ["教学关联"],
                })
                break   # 每个产品只给一条关联，避免刷屏

        # ---- 管线 ----
        for aid, why in self.find_pipeline(question, limit_pipeline):
            a = self.pipeline[aid]
            src = self.clin_sources.get(a.get("source_id"), {})
            facts.append({
                "kind": "pipeline",
                "id": aid,
                "claim": (
                    f"管线资产 {aid}，机制方向 {a.get('mechanism_topic')}。"
                    f"研发方披露口径（reported_status）：{a.get('reported_status')}。"
                    f"监管审批状态（approval_status）：{a.get('approval_status')}。"
                    f"**这两个状态不同，必须分开讲**；"
                    f"能否作为可推广信息取决于审批状态，不是披露口径。"
                ),
                "level": S2,
                "source": (f"clinical:expanded_pipeline#{aid} | source_id={a.get('source_id')}"
                           + (f" | {src.get('title')}" if src.get("title") else "")),
                "confidence": "可核实可讲（披露与审批须分列）",
                "matched_by": why,
            })

        # ---- 疾病 ----
        conds = []
        if condition_id and condition_id in self.conditions:
            conds.append((condition_id, "本次训练指定的疾病"))
        for cid, why in self.find_conditions(question, limit_conditions):
            if cid not in [c[0] for c in conds]:
                conds.append((cid, "；".join(why)))
        for cid, why in conds[:limit_conditions + 1]:
            c = self.conditions.get(cid)
            if not c:
                continue
            src = self.clin_sources.get(c.get("source_id"), {})
            facts.append({
                "kind": "condition",
                "id": cid,
                "claim": (
                    f"疾病「{c.get('name')}」（{cid}），领域 {c.get('area_id')}。"
                    f"关键词：{c.get('keywords')}。"
                    f"能力范围：{c.get('competency_scope')}"
                ),
                "level": S3,
                "source": (f"clinical:clinical_conditions#{cid} | source_id={c.get('source_id')}"
                           + (f" | {src.get('title')}" if src.get("title") else "")),
                "confidence": "可核实可讲",
                "matched_by": [why],
            })

        # ---- 课件层级（S5）：仅作沟通训练依据 ----
        for cid, c in list(self.courses.items()):
            if c["title"] and (c["title"].split("：")[0] in question
                               or cid.split("__")[0] in question):
                facts.append({
                    "kind": "course",
                    "id": cid,
                    "claim": f"培训课程《{c['title']}》——教学主线：{str(c.get('goal') or '')[:160]}",
                    "level": S5,
                    "source": f"course_spec:{cid}",
                    "confidence": "仅作沟通训练依据，不得作为医学事实引用",
                    "matched_by": ["课程标题命中"],
                })

        # ---- 过滤：演示道具与灰色手法绝不返回 ----
        facts = [f for f in facts
                 if not any(dp in f["claim"] for dp in DEMO_PROPS)]

        return {
            "question": question,
            "facts": facts,
            "fact_count": len(facts),
            "medical_usable": [f for f in facts if f["level"] in (S2, S3)],
            "note": ("本包为检索所得事实，来源限于信达临床知识库 v0.5 与课件语料；"
                     "未做外部检索。等级 S5 的条目仅作沟通训练依据，不得作为医学事实。"),
        }

    def competency_for(self, subject_type, subject_id, dimension=None):
        """取能力点与检验项（用于训练计划）"""
        items = self.competency.get((subject_type, subject_id), [])
        if dimension:
            items = [i for i in items if i.get("dimension") == dimension]
        return items

    def find_reference_points(self, query="", limit=20):
        """检索带定位符的公开资料候选点；不表示已审核或可用于打分。"""
        query = (query or "").strip().lower()
        hits = []
        for point in self.external_points:
            keywords = [x.strip().lower() for x in point["keywords"].split(";") if x.strip()]
            score = sum(2 for kw in keywords if kw in query or (query and query in kw))
            if query and point["topic"].lower() in query:
                score += 3
            if query and score == 0:
                continue
            doc = self.external_documents[point["document_id"]]
            hits.append((score, {**point, "document": doc}))
        hits.sort(key=lambda hit: (-hit[0], hit[1]["point_id"]))
        return [item for _, item in hits[:limit]]

    def find_book_points(self, query="", limit=20):
        """检索书籍释义与精确页码；L1 候选不能直接当已审核评分规则。"""
        query = (query or "").strip().lower()
        hits = []
        for point in self.book_points:
            haystack = (point["topic"] + " " + point["summary"]).lower()
            if query and query not in haystack:
                continue
            book = self.book_documents[point["book_id"]]
            hits.append({**point, "book": book})
        return hits[:limit]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="本地知识库检索")
    parser.add_argument("--references", metavar="QUERY", help="检索公开参考文献候选点")
    parser.add_argument("--books", metavar="QUERY", help="检索用户提供书籍的候选点")
    args = parser.parse_args()
    kb = KnowledgeBase()
    if args.references is not None:
        for point in kb.find_reference_points(args.references):
            doc = point["document"]
            print(f"[{point['point_id']}] {point['summary']}")
            print(f"  {doc['title']}｜{point['locator']}｜{doc['url']}")
            print(f"  {point['review_status']} / {doc['layer']} / {point['usage_scope']}")
        raise SystemExit(0)
    if args.books is not None:
        for point in kb.find_book_points(args.books):
            book = point["book"]
            print(f"[{point['point_id']}] {point['summary']}")
            print(f"  {book['title']}｜{point['locator']}｜sha256:{book['file_sha256']}")
            print(f"  {point['review_status']} / {book['layer']} / {point['usage_scope']}")
        raise SystemExit(0)
    print(f"✅ 检索层加载：产品 {len(kb.products)} / 管线 {len(kb.pipeline)} / "
          f"疾病 {len(kb.conditions)} / 课程 {len(kb.courses)} / "
          f"公开文献 {len(kb.external_documents)}")
    print()
    for q in ["这个药已经获批用于非小细胞肺癌了吗？",
              "IBI343 现在什么阶段了？",
              "达伯舒的靶点是什么？"]:
        b = kb.fact_bundle(q, condition_id="D-NSCLC")
        print(f"问：{q}")
        print(f"  → {b['fact_count']} 条事实（可作医学依据 {len(b['medical_usable'])} 条）")
        for f in b["facts"][:3]:
            print(f"    [{f['level']}] {f['kind']:14s} {f['claim'][:88]}")
            print(f"           出处：{f['source'][:88]}")
        print()
