# 模拟拜访评分标准 v0.1（候选，待审核）

适用对象：药代与医生的模拟对话逐字稿。此处的六维结构和 0/1/2 档是**本项目把来源原则转成可观察行为的设计**，不是信达公开发布的评分量表，也不是四本书原有分值。项目检索到了信达官网《Responsible Marketing Policy》和《Code of Business Ethics and Conduct》，可支撑合规红线；未检索到公开的信达代表表现评分量表。正式用于人员评价前须经信达培训、医学及合规团队审核。

| 维度 | 对话中看什么 | 主要来源 ID | 当前边界 |
|---|---|---|---|
| D1 探询与需求确认 | 提问、倾听、复述并确认医生关切 | BOOK-TRUST-ASK、BOOK-150Q-LISTEN、TEXT12-VISIT | 书和课件仅作行为候选 |
| D2 回应清晰与双向互动 | 答到问题，解释依据和边界，允许追问 | RDPAC42、HAI-BOX2-QA、INNO-ETH-44 | “结论—依据—边界”顺序是项目设计 |
| D3 异议处理 | 查明异议再回应，未知时说明核实方式 | BOOK-TRUST-OBJECTION、RDPAC43 | 没有异议时 NA |
| D4 医学与产品信息准确 | 产品主张、患者条件与批准资料一致 | CN10、RDPAC41、CLN-0001 | 未加载现行说明书时，具体产品正确性 NA |
| D5 证据、风险与不确定性 | 说明来源、人群、局限及相关安全信息 | WHO18、HAI-BOX2-SAFETY、CN24-7 | 疗效数值须核当前资料 |
| D6 合规与角色边界 | 无误导、不当处方诱因或越权传播 | INNO-MKT-411、INNO-MKT-42、INNO-ETH-42 | 疑似违规转人工复核 |

每维 0=反向/缺失，1=部分达到，2=完整可定位，NA=未触发或依据不足。输出六维向量和覆盖率；暂不设总分、权重、及格线。`medrep-dialogue-v0.1.json` 给出每档完整锚点、触发条件、红线和记录字段。旧版 `phase0/D8a-评分表草案.md` 中的 60/40 权重与阈值并无信达官方依据，不沿用到此候选版。

四本用户提供的书籍已入 SQLite 的 `local_book_documents`（书目、文件指纹）和 `local_book_points`（七条释义、章节/页码）。两本扫描 PDF 的重点页经人工抽查；没有全文 OCR，也没有把整本书或原文段落写入数据库。公开资料在 `external_reference_documents` / `external_reference_points`，现为 8 篇、25 条。所有新增证据均为 L1、`pending_human_review`。课件和现有临床库作为候选输入；临床库中相关医学内容亦待医学审核，不能因“在库中”就作为已批准答案。

复现：

```bash
python3 import_public_references.py
python3 import_local_books.py
python3 knowledge_retrieval.py --books 倾听
python3 .agents/skills/medrep-dialogue-scorecard/scripts/build_evidence_snapshot.py --db clinical/medrep-innovent-clinical-knowledge-v0.5/medrep_clinical_knowledge_v0.5.sqlite --out .agents/skills/medrep-dialogue-scorecard/references/evidence-index.json
python3 .agents/skills/medrep-dialogue-scorecard/scripts/validate_scorecard.py --scorecard scorecards/medrep-dialogue-v0.1.json --evidence .agents/skills/medrep-dialogue-scorecard/references/evidence-index.json
```

独立 Skill 包的 `references/evidence-index.json` 是当前候选依据快照，含自行释义及溯源定位，不含四本书全文。用户可按 `SKILL.md` 接入新的课件、产品批准资料和审核结果，再生成下一版评分表。
