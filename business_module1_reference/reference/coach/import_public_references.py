#!/usr/bin/env python3
"""Import reviewed-as-sources, not approved-as-scoring-rules, public MR references.

The records below are concise paraphrases with locators. Full copyrighted PDFs
remain at their publishers' URLs. Re-running this script is idempotent.
"""

from __future__ import annotations

import hashlib
import sqlite3

from config import PATHS

ACCESSED_ON = "2026-10-31"

# id, title, issuer, kind, edition, jurisdiction, URL, source level, scope, note
DOCUMENTS = [
    (
        "MRDOC-INNOVENT-MKT", "Responsible Marketing Policy", "Innovent Biologics",
        "company_policy", "官网公开版；访问于2026-10-31", "信达生物及子公司",
        "https://img.innoventbio.com/ESG/Responsible_Marketing_Policy.pdf",
        "S4", "信达员工的负责任营销行为", "信达官方政策；不是公开的医药代表评分量表。",
    ),
    (
        "MRDOC-INNOVENT-ETHICS", "Code of Business Ethics and Conduct", "Innovent Biologics",
        "company_policy", "官网公开版；访问于2026-10-31", "信达生物及子公司",
        "https://img.innoventbio.com/ESG/Code_Of_Business_Ethics_And_Conduct.pdf",
        "S4", "信达员工的商业道德行为", "信达官方政策；不是公开的医药代表评分量表。",
    ),
    (
        "MRDOC-CN-2026", "医药代表管理办法", "国家药监局等七部门", "regulation",
        "2026年第42号；2026-08-01施行", "中国",
        "https://sft.xinjiang.gov.cn/xjsft/flfggz/202607/c6889ead6f3843a9a59dba7eeff5b373.shtml",
        "S1", "中国境内医药代表", "政府网站转载的法规全文；旧《备案管理办法（试行）》已废止。",
    ),
    (
        "MRDOC-WHO-1988", "Ethical criteria for medicinal drug promotion", "World Health Organization",
        "international_principles", "WHA41.17 / 1988", "国际",
        "https://iris.who.int/bitstream/handle/10665/38125/924154239X_eng.pdf",
        "S1", "伦理原则；需按所在法域适配", "WHO 原始 PDF；不是中国法律。",
    ),
    (
        "MRDOC-RDPAC-2022", "RDPAC 行业行为准则", "RDPAC", "industry_code",
        "2022年修订版；2023-04-01生效", "中国",
        "https://cnadmin.rdpac.org/upload/upload_file/1689938526.pdf",
        "S1", "RDPAC 会员公司", "协会原始 PDF；行业自律准则，不等同于普遍适用的法律。",
    ),
    (
        "MRDOC-TEXTBOOK-MKT", "医药市场营销：项目十二 临床医药代表工作实务", "高等教育出版社教材资源",
        "textbook_chapter", "ISBN 9787040538625；公开章节", "中国",
        "https://oss0.changxianggu.com/book/chapter/269_9787040538625.pdf",
        "S5", "教学和情境设计", "只取岗位能力与对话结构；产品、剂量、临床数据例子不得用作医学事实。",
    ),
    (
        "MRDOC-HAI-WHO-GUIDE", "Understanding and Responding to Pharmaceutical Promotion: A Practical Guide",
        "WHO / Health Action International", "teaching_manual", "First edition; working draft for pilot field testing",
        "国际", "https://haiweb.org/storage/2015/05/Pharma-Promotion-Guide-English.pdf",
        "S5", "医生视角的药代拜访观察；教学参考", "公开试用稿；第4章清单可作候选观察项，不能直接当中国法规。",
    ),
    (
        "MRDOC-YYHG-DRAFT", "医药代表职业化培养规范", "广东省医药合规促进会",
        "draft_training_standard", "T/YYHG 0001-2019；征求意见稿", "中国",
        "https://www.ttbz.org.cn/upload/file/20190213/6368565538440529817379300.pdf",
        "S5", "培训科目参考", "封面明确标示征求意见稿；不得称为已生效标准。",
    ),
]

# id, document id, precise locator, paraphrase, topic, searchable keywords, use
POINTS = [
    ("INNO-MKT-411", "MRDOC-INNOVENT-MKT", "§4.1.1–4.1.2", "不得对产品作虚假或误导性表述，也不得误导性地描述竞争产品。", "合规红线", "虚假;误导;产品;竞争", "compliance_reference"),
    ("INNO-MKT-413", "MRDOC-INNOVENT-MKT", "§4.1.3", "比较性营销主张应有可核验依据，并经过相应审查。", "证据运用", "比较;证据;审查", "compliance_reference"),
    ("INNO-MKT-42", "MRDOC-INNOVENT-MKT", "§4.2", "营销资料使用前应取得公司授权和批准。", "材料边界", "材料;批准;授权", "compliance_reference"),
    ("INNO-ETH-42", "MRDOC-INNOVENT-ETHICS", "§4.2–4.3", "禁止贿赂，不得以金钱或有价物诱导医疗专业人员处方。", "合规红线", "贿赂;处方;利益;诱导", "compliance_reference"),
    ("INNO-ETH-44", "MRDOC-INNOVENT-ETHICS", "§4.4", "对外沟通应真实、透明、公平。", "专业沟通", "真实;透明;公平;沟通", "candidate_scoring_basis"),
    ("INNO-ETH-11", "MRDOC-INNOVENT-ETHICS", "§11", "应妥善保护工作中接触的个人信息和隐私。", "隐私边界", "隐私;个人信息", "compliance_reference"),
    ("CN10", "MRDOC-CN-2026", "第十条（二）（三）", "医药代表需掌握所推广药品的药理毒理、适应症、联合用药、不良反应、禁忌症及注意事项等，并经持有人培训考核合格。", "专业知识", "药理;适应症;联合用药;不良反应;禁忌症;注意事项;培训", "candidate_scoring_basis"),
    ("CN21", "MRDOC-CN-2026", "第二十一条（一）至（三）", "学术推广职责包括传递药品信息、沟通协助合理用药，以及收集反馈临床使用情况、不良反应和临床需求。", "岗位职责", "信息传递;沟通;合理用药;不良反应;反馈", "candidate_scoring_basis"),
    ("CN24-7", "MRDOC-CN-2026", "第二十四条（七）", "禁止误导医生用药、夸大或误导疗效、隐匿已知或医生反馈的不良反应，以及干预合理用药。", "合规红线", "夸大;疗效;不良反应;误导;合理用药", "compliance_reference"),
    ("CN24-1", "MRDOC-CN-2026", "第二十条、第二十四条（一）（二）（九）", "开展学术推广须符合备案、医疗机构同意及持有人授权的药品类别、治疗领域和区域。", "拜访边界", "备案;同意;授权;拜访;领域", "compliance_reference"),
    ("WHO17", "MRDOC-WHO-1988", "Medical representatives §17", "医药代表应接受充分训练，并具备足够的医学及技术知识和诚信，以便传递药品信息。", "专业能力", "培训;医学知识;诚信;专业", "candidate_scoring_basis"),
    ("WHO18", "MRDOC-WHO-1988", "Medical representatives §18", "向处方者或调剂者提供所讨论产品完整、无偏的信息及获批科学资料或同等资料。", "信息完整性", "完整;无偏;说明书;证据;资料", "candidate_scoring_basis"),
    ("WHO19", "MRDOC-WHO-1988", "Medical representatives §19", "代表不应向处方者或调剂者提供不当诱因；雇主对代表的陈述和行为负责。", "合规红线", "诱因;礼品;回扣;贿赂", "compliance_reference"),
    ("RDPAC3", "MRDOC-RDPAC-2022", "第三条及注释7；印刷页15", "会员公司不得把未获中国上市许可的药品作上市推广；获批前或说明书外的科学交流应由医学专业人员开展或监督。", "适用边界", "获批;上市;说明书外;适应症;医学", "candidate_scoring_basis"),
    ("RDPAC41", "MRDOC-RDPAC-2022", "第四条4.1；印刷页16", "会员公司的推广内容应与中国药品主管部门批准的药品信息保持一致。", "信息准确性", "批准;说明书;推广;适应症", "candidate_scoring_basis"),
    ("RDPAC42", "MRDOC-RDPAC-2022", "第四条4.2；印刷页17", "会员公司的推广信息应清楚、准确、平衡且充分，避免通过夸大、省略或绝对化表述造成误导。", "表达与证据", "清楚;准确;平衡;夸大;省略;绝对化", "candidate_scoring_basis"),
    ("RDPAC43", "MRDOC-RDPAC-2022", "第四条4.3；印刷页18", "会员公司应能用获批说明书或科学证据支持推广主张，并客观回应专业人士的资料请求。", "证据运用", "证据;说明书;资料;回答问题", "candidate_scoring_basis"),
    ("TEXT12-SKILLS", "MRDOC-TEXTBOOK-MKT", "项目十二 任务二；印刷页279-280", "教材把学术推广、客户筛选、时间管理、问题分析和学术活动列为临床医药代表的岗位能力。", "岗位能力", "学术推广;客户;时间管理;问题分析", "scenario_design_only"),
    ("TEXT12-VISIT", "MRDOC-TEXTBOOK-MKT", "项目十二 任务二；印刷页280-281", "教材将专业拜访拆成开场、探询聆听、产品信息介绍和异议处理等环节。", "沟通能力", "开场;探询;聆听;异议;沟通;拜访", "scenario_design_only"),
    ("HAI-BOX2-APPROVAL", "MRDOC-HAI-WHO-GUIDE", "第4章 Box 2；印刷页69-70；问题1-2", "从医生视角核查代表所述适应症和给药方案是否与监管批准资料一致。", "信息准确性", "适应症;剂量;给药;批准;说明书", "candidate_observation_item"),
    ("HAI-BOX2-SAFETY", "MRDOC-HAI-WHO-GUIDE", "第4章 Box 2；印刷页69-70；问题3-6", "观察代表是否主动谈及相关不良反应、禁忌症和药物相互作用，而非只在追问后披露。", "安全信息", "不良反应;禁忌症;相互作用;主动", "candidate_observation_item"),
    ("HAI-BOX2-QA", "MRDOC-HAI-WHO-GUIDE", "第4章 Box 2；印刷页69-70；问题7", "观察代表是否愿意正面回答医疗专业人士提出的问题。", "沟通能力", "回答问题;异议;沟通;回应", "candidate_observation_item"),
    ("HAI-BOX2-INDUCEMENT", "MRDOC-HAI-WHO-GUIDE", "第4章 Box 2；印刷页69-70；问题9", "观察拜访中是否存在促使处方的不当诱因。", "合规红线", "诱因;礼品;回扣;处方", "candidate_observation_item"),
    ("YYHG33", "MRDOC-YYHG-DRAFT", "3.3.1-3.3.5；印刷页4", "征求意见稿建议培训覆盖法规、职业道德、药剂药理知识及拜访和沟通等职业技能。", "培训框架", "法规;职业道德;药理;拜访;沟通", "scenario_design_only"),
    ("YYHG92", "MRDOC-YYHG-DRAFT", "9.2；印刷页7", "征求意见稿建议评估客观、实用、系统且连续，强调对培训后行为的观察。", "评估原则", "客观;行为;评估;培训", "scenario_design_only"),
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS external_reference_documents (
    document_id TEXT PRIMARY KEY, title TEXT NOT NULL, issuer TEXT NOT NULL,
    document_kind TEXT NOT NULL, edition TEXT NOT NULL, jurisdiction TEXT NOT NULL,
    url TEXT NOT NULL, source_level TEXT NOT NULL, authority_scope TEXT NOT NULL,
    note TEXT NOT NULL, accessed_on TEXT NOT NULL, layer TEXT NOT NULL,
    review_status TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS external_reference_points (
    point_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES external_reference_documents(document_id),
    locator TEXT NOT NULL, summary TEXT NOT NULL, topic TEXT NOT NULL,
    keywords TEXT NOT NULL, usage_scope TEXT NOT NULL,
    fingerprint TEXT NOT NULL, summary_sha256 TEXT NOT NULL,
    review_status TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_external_reference_points_topic
    ON external_reference_points(topic);
"""


def import_references(db_path=PATHS.CLIN_DB):
    with sqlite3.connect(db_path) as db:
        db.execute("PRAGMA foreign_keys=ON")
        db.executescript(SCHEMA)
        for doc in DOCUMENTS:
            db.execute("""INSERT INTO external_reference_documents VALUES
                (?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(document_id) DO UPDATE SET
                title=excluded.title, issuer=excluded.issuer,
                document_kind=excluded.document_kind, edition=excluded.edition,
                jurisdiction=excluded.jurisdiction, url=excluded.url,
                source_level=excluded.source_level,
                authority_scope=excluded.authority_scope, note=excluded.note,
                accessed_on=excluded.accessed_on, layer=excluded.layer,
                review_status=CASE
                    WHEN external_reference_documents.url != excluded.url
                      OR external_reference_documents.edition != excluded.edition
                    THEN 'pending_human_review'
                    ELSE external_reference_documents.review_status END""",
                (*doc[:8], doc[8], doc[9], ACCESSED_ON, "L1", "pending_human_review"))
        for pid, doc_id, locator, summary, topic, keywords, usage in POINTS:
            fingerprint = f"web:{doc_id}#{locator}@{ACCESSED_ON}"
            summary_hash = "sha256:" + hashlib.sha256(summary.encode("utf-8")).hexdigest()
            db.execute("""INSERT INTO external_reference_points VALUES (?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(point_id) DO UPDATE SET
                document_id=excluded.document_id, locator=excluded.locator,
                summary=excluded.summary, topic=excluded.topic,
                keywords=excluded.keywords, usage_scope=excluded.usage_scope,
                fingerprint=excluded.fingerprint,
                summary_sha256=excluded.summary_sha256,
                review_status=CASE
                    WHEN external_reference_points.summary_sha256 != excluded.summary_sha256
                      OR external_reference_points.locator != excluded.locator
                    THEN 'pending_human_review'
                    ELSE external_reference_points.review_status END""",
                (pid, doc_id, locator, summary, topic, keywords, usage,
                 fingerprint, summary_hash, "pending_human_review"))
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    return len(DOCUMENTS), len(POINTS)


if __name__ == "__main__":
    documents, points = import_references()
    print(f"Imported {documents} documents and {points} reference points into {PATHS.CLIN_DB}")
