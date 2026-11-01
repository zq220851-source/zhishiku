# SkillTaxonomy 能力树（V1.3 对齐）

> V1.3 把 SkillTaxonomy 列为**共同地基**与核心实体。此前项目产出中该实体缺失，
> 导致知识考察点只是切分出来的短语、没有稳定标识——而 V1.3 §2.3 的差异分析（CoverageMap）
> 恰恰要求按能力点比对。本文件补齐这个地基。

知识技能点 **197** 个 ｜ 沟通技能点 **25** 个 ｜ 合计 **222**

## 一、两棵树与 V1.3 双轨的对应

| 树 | 来源 | 对应 V1.3 轨道 | V1.3 评价项 |
|---|---|---|---|
| knowledge | 临床知识库 `competency_items`（5 维度 × 疾病/产品）| 专业知识运用 | 知识准确性 / 证据运用 / 适用边界 / 专业与合规要求 |
| communication | 课件语料（D0 提取）| 沟通与应变 | 问题理解 / 回答结构 / 表达清晰 / 临场应变 / 情境适应 |

## 二、知识技能树

### 心血管与血脂（心内科）— 11 个能力点

> 领域核心能力：LDL-C与风险分层；PCSK9；血压管理；终点与长期安全性

**射血分数保留型心力衰竭** `D-HFPEF`

- `SK-K-D-HFPEF-108` **诊断框架** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-HFPEF-109` **症状及功能终点** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-HFPEF-110` **研究性适应症** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界

**高胆固醇血症与血脂异常** `D-DYSLIPID`

- `SK-K-D-DYSLIPID-100` **LDL-C** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-DYSLIPID-101` **ApoB** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-DYSLIPID-102` **ASCVD风险** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-DYSLIPID-103` **降脂治疗分类** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界

**高血压** `D-HTN`

- `SK-K-D-HTN-104` **血压指标** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-HTN-105` **药物类别** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-HTN-106` **并发症** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-HTN-107` **研究终点** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界

### 眼科（眼科）— 9 个能力点

> 领域核心能力：OCT/视力；眼眶症状；抗VEGF；TED、nAMD、DME的疾病差异

**新生血管性年龄相关性黄斑变性** `D-NAMD`

- `SK-K-D-NAMD-146` **nAMD** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-NAMD-147` **OCT及视力变化** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-NAMD-148` **眼内抗VEGF治疗概念** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界

**甲状腺眼病** `D-TED`

- `SK-K-D-TED-140` **活动性** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-TED-141` **非活动性** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-TED-142` **眼球突出与眼症状评估** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界

**糖尿病黄斑水肿** `D-DME`

- `SK-K-D-DME-143` **视力与OCT** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-DME-144` **黄斑水肿** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-DME-145` **抗VEGF机制** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界

### 血液肿瘤及细胞治疗（血液科）— 24 个能力点

> 领域核心能力：疾病分型；分子诊断；缓解与复发；MRD；CAR-T与双/三抗安全性

**多发性骨髓瘤** `D-MM`

- `SK-K-D-MM-083` **复发难治定义** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-MM-084` **BCMA** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-MM-085` **细胞治疗** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-MM-086` **CRS** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-MM-087` **神经毒性等风险** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界

**套细胞淋巴瘤** `D-MCL`

- `SK-K-D-MCL-081` **既往治疗线次** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-MCL-082` **BTK抑制剂治疗背景** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界

**弥漫大B细胞淋巴瘤** `D-DLBCL`

- `SK-K-D-DLBCL-071` **CD20** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-DLBCL-072` **分型** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-DLBCL-073` **缓解及复发** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-DLBCL-074` **治疗组合** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界

**急性髓系白血病** `D-AML`

- `SK-K-D-AML-067` **分型** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-AML-068` **FLT3检测** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-AML-069` **诱导与巩固治疗** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-AML-070` **缓解终点** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界

**慢性淋巴细胞白血病/小淋巴细胞淋巴瘤** `D-CLL`

- `SK-K-D-CLL-077` **疾病分型** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-CLL-078` **既往BTK抑制剂** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-CLL-079` **复发** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-CLL-080` **难治定义** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界

**慢性髓系白血病** `D-CML`

- `SK-K-D-CML-064` **BCR-ABL检测** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-CML-065` **耐药变异** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-CML-066` **分子缓解与治疗线次** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界

**滤泡性淋巴瘤** `D-FL`

- `SK-K-D-FL-075` **惰性淋巴瘤特征** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-FL-076` **治疗指征与复发** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界

### 自身免疫与炎症（风湿免疫/皮肤/消化）— 29 个能力点

> 领域核心能力：炎症通路；疾病活动度；生物制剂选择；感染等风险监测

**克罗恩病** `D-CROHN`

- `SK-K-D-CROHN-126` **诊断证据** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-CROHN-127` **炎症控制** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-CROHN-128` **缓解和复发** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界

**干燥综合征与IgG4相关疾病** `D-SJOGREN`

- `SK-K-D-SJOGREN-138` **自身免疫诊断框架及器官受累** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-SJOGREN-139` **研究性生物靶点** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界

**强直性脊柱炎/轴性脊柱关节炎** `D-AS`

- `SK-K-D-AS-114` **炎症性腰背痛** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-AS-115` **疾病活动度** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-AS-116` **TNF作用** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界

**斑块状银屑病** `D-PSO`

- `SK-K-D-PSO-117` **皮损严重度** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-PSO-118` **PASI** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-PSO-119` **TNF** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-PSO-120` **IL-23通路** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-PSO-121` **复发** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界

**特应性皮炎** `D-AD`

- `SK-K-D-AD-129` **炎症表型** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-AD-130` **疾病严重度** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-AD-131` **生物制剂通路** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界

**痛风与高尿酸血症** `D-GOUT`

- `SK-K-D-GOUT-132` **急性发作与尿酸长期管理** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-GOUT-133` **XO作用机制** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界

**白癜风与斑秃** `D-VITILIGO`

- `SK-K-D-VITILIGO-134` **自身免疫通路** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-VITILIGO-135` **皮损** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-VITILIGO-136` **毛发终点** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-VITILIGO-137` **在研状态** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界

**类风湿关节炎** `D-RA`

- `SK-K-D-RA-111` **疾病活动度** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-RA-112` **炎症指标** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-RA-113` **生物制剂机制和风险** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界

**银屑病关节炎** `D-PSA`

- `SK-K-D-PSA-122` **皮肤与关节双维度** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-PSA-123` **治疗机制** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-PSA-124` **在研** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-PSA-125` **已批边界** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界

### 内分泌与代谢（内分泌科）— 12 个能力点

> 领域核心能力：诊断与合并症；HbA1c；体重百分比；心肾肝风险；GLP-1/GCGR机制与安全性

**2型糖尿病** `D-T2DM`

- `SK-K-D-T2DM-091` **血糖与HbA1c** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-T2DM-092` **并发症** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-T2DM-093` **体重与糖尿病的区别** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界

**代谢功能障碍相关脂肪性肝炎** `D-MASH`

- `SK-K-D-MASH-094` **疾病概念** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-MASH-095` **肝纤维化终点** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-MASH-096` **试验性适应症辨别** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界

**肥胖与体重管理** `D-OBE`

- `SK-K-D-OBE-088` **肥胖诊断框架** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-OBE-089` **体重终点与共病** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-OBE-090` **长期管理** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界

**阻塞性睡眠呼吸暂停** `D-OSA`

- `SK-K-D-OSA-097` **肥胖共病关系** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-OSA-098` **临床终点** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-OSA-099` **研究性证据界限** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界

### 实体瘤与肿瘤免疫（肿瘤学）— 63 个能力点

> 领域核心能力：诊断/分期；组织与基因分型；PD-L1及驱动基因；治疗线次；临床终点；免疫相关安全性

**乳腺癌** `D-BREAST`

- `SK-K-D-BREAST-033` **HR** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-BREAST-034` **HER2分型** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-BREAST-035` **治疗阶段** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-BREAST-036` **内分泌与靶向机制** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界

**卵巢癌** `D-OVARIAN`

- `SK-K-D-OVARIAN-037` **铂敏感** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-OVARIAN-038` **铂耐药** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-OVARIAN-039` **线次** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-OVARIAN-040` **ADC研究与安全性** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界

**子宫内膜癌** `D-ENDO`

- `SK-K-D-ENDO-030` **MMR分型** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-ENDO-031` **治疗线次** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-ENDO-032` **研究人群边界** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界

**宫颈癌** `D-CERVICAL`

- `SK-K-D-CERVICAL-047` **疾病分期** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-CERVICAL-048` **复发** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-CERVICAL-049` **转移背景** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-CERVICAL-050` **研究终点** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界

**甲状腺恶性肿瘤** `D-THYROID`

- `SK-K-D-THYROID-053` **分型** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-THYROID-054` **RET基因改变** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-THYROID-055` **检测与靶向治疗** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界

**结直肠癌** `D-CRC`

- `SK-K-D-CRC-017` **MSI-H** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-CRC-018` **dMMR检测** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-CRC-019` **治疗线次与免疫治疗证据边界** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界

**肝细胞癌** `D-HCC`

- `SK-K-D-HCC-007` **分期** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-HCC-008` **肝功能与全身治疗路径** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-HCC-009` **OS** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-HCC-010` **PFS** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-HCC-011` **安全性** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界

**肾细胞癌** `D-RCC`

- `SK-K-D-RCC-025` **既往治疗线次** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-RCC-026` **免疫+TKI方案及证据边界** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界

**肿瘤机制与临床试验** `D-MESO`

- `SK-K-D-MESO-056` **对照组** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-MESO-057` **随机** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-MESO-058` **单臂** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-MESO-059` **ORR** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-MESO-060` **PFS** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-MESO-061` **OS** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-MESO-062` **终点限制** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-MESO-063` **入排标准** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界

**胃癌及胃食管结合部癌** `D-GC`

- `SK-K-D-GC-012` **分期** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-GC-013` **线次** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-GC-014` **CLDN18.2** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-GC-015` **HER2等标志物** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-GC-016` **ADC研究评价** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界

**胆管癌** `D-CCA`

- `SK-K-D-CCA-020` **分子检测** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-CCA-021` **FGFR2融合** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-CCA-022` **重排** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-CCA-023` **人群筛选** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-CCA-024` **单臂研究局限** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界

**胰腺导管腺癌** `D-PDAC`

- `SK-K-D-PDAC-041` **分期** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-PDAC-042` **线次** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-PDAC-043` **ADC在研证据与研究人群** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界

**胶质母细胞瘤** `D-GBM`

- `SK-K-D-GBM-051` **复发性疾病特点** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-GBM-052` **症状与生活质量终点** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界

**非小细胞肺癌** `D-NSCLC`

- `SK-K-D-NSCLC-001` **病理分型** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-NSCLC-002` **分期** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-NSCLC-003` **靶点检测** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-NSCLC-004` **免疫或靶向治疗适用人群** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-NSCLC-005` **PFS** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-NSCLC-006` **OS** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界

**食管鳞癌** `D-ESCC`

- `SK-K-D-ESCC-027` **分期** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-ESCC-028` **局部与全身治疗** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-ESCC-029` **免疫治疗适用范围** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界

**黑色素瘤** `D-MEL`

- `SK-K-D-MEL-044` **免疫治疗基础** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-MEL-045` **耐药与既往用药背景** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界
- `SK-K-D-MEL-046` **研究对照** — 维度：disease_foundation/treatment_landscape/clinical_evidence ｜ V1.3 评价项：知识准确性/证据运用/适用边界

### 产品与管线视角

**ASSET-commercial_product**（20 项）

- `SK-K-DABOSHU-PROD-01` 达伯舒（信迪利单抗注射液） — product_basics
- `SK-K-DAYOUTONG-PROD-01` 达攸同（贝伐珠单抗注射液） — product_basics
- `SK-K-SULIXIN-PROD-01` 苏立信（阿达木单抗注射液） — product_basics
- `SK-K-DABOHUA-PROD-01` 达伯华（利妥昔单抗注射液） — product_basics
- `SK-K-DABOTAN-PROD-01` 达伯坦（佩米替尼片） — product_basics
- `SK-K-NAILIKE-PROD-01` 耐立克（奥雷巴替尼片） — product_basics
- `SK-K-XIRANGZE-PROD-01` 希冉择（雷莫西尤单抗注射液） — product_basics
- `SK-K-RUITUO-PROD-01` 睿妥（塞普替尼胶囊） — product_basics
- `SK-K-FUKESU-PROD-01` 福可苏（伊基奥仑赛注射液） — product_basics
- `SK-K-XINBILE-PROD-01` 信必乐（托莱西单抗注射液） — product_basics
- `SK-K-DABOTE-PROD-01` 达伯特（氟泽雷塞片） — product_basics
- `SK-K-JIEPALI-PROD-01` 捷帕力（匹妥布替尼片） — product_basics
- `SK-K-DABOLE-PROD-01` 达伯乐（己二酸他雷替尼胶囊） — product_basics
- `SK-K-AOYIXIN-PROD-01` 奥壹新（利厄替尼片） — product_basics
- `SK-K-XINBIMIN-PROD-01` 信必敏（替妥尤单抗N01注射液） — product_basics
- `SK-K-XINERMEI-PROD-01` 信尔美（玛仕度肽注射液） — product_basics
- `SK-K-XINMEIYUE-PROD-01` 信美悦（匹康奇拜单抗注射液） — product_basics
- `SK-K-DABOXIN-PROD-01` 达伯欣（伊匹木单抗N01注射液） — product_basics
- `SK-K-WEIZE-PROD-01` 唯择（阿贝西利片） — product_basics
- `SK-K-WEIFUTAI-PROD-01` 维复泰（盐酸奎扎替尼片） — product_basics

**ASSET-research_asset**（29 项）

- `SK-K-IBI343-PIPE-01` IBI343（CLDN18.2 ADC） — pipeline_literacy
- `SK-K-IBI363-PIPE-01` IBI363（PD-1/IL-2α偏向融合蛋白） — pipeline_literacy
- `SK-K-IBI354-PIPE-01` IBI354（HER2 ADC） — pipeline_literacy
- `SK-K-IBI3003-PIPE-01` IBI3003（GPRC5D/BCMA/CD3三抗） — pipeline_literacy
- `SK-K-IBI3005-PIPE-01` IBI3005（EGFR/HER3 ADC） — pipeline_literacy
- `SK-K-IBI3009-PIPE-01` IBI3009（DLL3 ADC） — pipeline_literacy
- `SK-K-IBI3001-PIPE-01` IBI3001（EGFR/B7H3 ADC） — pipeline_literacy
- `SK-K-IBI3014-PIPE-01` IBI3014（PD-L1/TROP2 ADC） — pipeline_literacy
- `SK-K-IBI3020-PIPE-01` IBI3020（CEACAM5 ADC） — pipeline_literacy
- `SK-K-IBI3026-PIPE-01` IBI3026（PD-1/IL-12融合蛋白） — pipeline_literacy
- `SK-K-IBI3028-PIPE-01` IBI3028（EGFR/c-Met ADC） — pipeline_literacy
- `SK-K-IBI115-PIPE-01` IBI115（DLL3/CD3双特异抗体） — pipeline_literacy
- `SK-K-IBI302-PIPE-01` IBI302（VEGF/补体融合蛋白） — pipeline_literacy
- `SK-K-IBI128-PIPE-01` IBI128（黄嘌呤氧化酶（XO）抑制剂） — pipeline_literacy
- `SK-K-IBI324-PIPE-01` IBI324（VEGF-A/ANG2双特异抗体） — pipeline_literacy
- `SK-K-IBI3002-PIPE-01` IBI3002（TSLP/IL-4Rα双特异抗体） — pipeline_literacy
- `SK-K-IBI3016-PIPE-01` IBI3016（AGT siRNA） — pipeline_literacy
- `SK-K-IBI355-PIPE-01` IBI355（CD40L单抗） — pipeline_literacy
- `SK-K-IBI3032-PIPE-01` IBI3032（口服日制剂GLP-1R小分子） — pipeline_literacy
- `SK-K-IBI3040-PIPE-01` IBI3040（Amylin/Calcitonin相关多肽） — pipeline_literacy
- `SK-K-IBI3042-PIPE-01` IBI3042（口服周制剂GLP-1R小分子） — pipeline_literacy
- `SK-K-IBI3035-PIPE-01` IBI3035（胰岛素相关多肽） — pipeline_literacy
- `SK-K-IBI3011-PIPE-01` IBI3011（IL-1RAP单抗） — pipeline_literacy
- `SK-K-IBI3013-PIPE-01` IBI3013（IL-15单抗） — pipeline_literacy
- `SK-K-IBI3027-PIPE-01` IBI3027（IL-4Rα单抗） — pipeline_literacy
- `SK-K-IBI3031-PIPE-01` IBI3031（TSHR/IGF-1R双特异抗体） — pipeline_literacy
- `SK-K-IBI3046-PIPE-01` IBI3046（INHBE siRNA） — pipeline_literacy
- `SK-K-IBI3030-PIPE-01` IBI3030（月度PCSK9相关候选药） — pipeline_literacy
- `SK-K-IBI3038-PIPE-01` IBI3038（IGF-1R/IL-6相关研发项目） — pipeline_literacy

## 三、沟通技能树

### 3.1 五个通用沟通能力（V1.3 §1.5 五维）

- `SK-C-GEN-01` **问题理解** — 准确识别医生真正在问什么（含转问、追问、质疑） ｜ V1.3 评价项：问题理解
- `SK-C-GEN-02` **回答结构** — 给出可跟随的回答结构（结论先行、分层、留核查口） ｜ V1.3 评价项：回答结构
- `SK-C-GEN-03` **表达清晰** — 口语可懂、无黑话、术语即时解释 ｜ V1.3 评价项：表达清晰
- `SK-C-GEN-04` **临场应变** — 被拒绝/被打断/被质疑时的即时调整 ｜ V1.3 评价项：临场应变
- `SK-C-GEN-05` **情境适应** — 同一知识在不同医生风格与场合下的表达适配 ｜ V1.3 评价项：情境适应

### 3.2 拜访阶段能力点


### 3.3 异议类型能力点（7 类实质类型）

- `SK-C-OBJ-01` 处理「价格异议」  `[A36 S162]`  ｜ 价格异议类异议的处理
- `SK-C-OBJ-02` 处理「需求异议」  `[A36 S163]`  ｜ 需求异议类异议的处理
- `SK-C-OBJ-03` 处理「权力异议」  `[A36 S164]`  ｜ 权力异议类异议的处理
- `SK-C-OBJ-04` 处理「产品异议」  `[A36 S164]`  ｜ 产品异议类异议的处理
- `SK-C-OBJ-05` 处理「货源异议」  `[A36 S165]`  ｜ 货源异议类异议的处理
- `SK-C-OBJ-06` 处理「医药代表异议」  `[A36 S165]`  ｜ 医药代表异议类异议的处理
- `SK-C-OBJ-07` 处理「购买时间异议」  `[A36 S166]`  ｜ 购买时间异议类异议的处理

### 3.4 抗拒形态能力点

- `SK-C-STAGE-RESIST-01` 应对「拖延的抗拒」  `[A71 S56]`  ｜ 抗拒形态下的临场应变
- `SK-C-STAGE-RESIST-02` 应对「假借理由的抗拒」  `[A71 S56]`  ｜ 抗拒形态下的临场应变
- `SK-C-STAGE-RESIST-03` 应对「沉默的抗拒」  `[A71 S56]`  ｜ 抗拒形态下的临场应变
- `SK-C-STAGE-RESIST-04` 应对「转换话题的抗拒」  `[A71 S56]`  ｜ 抗拒形态下的临场应变
- `SK-C-STAGE-RESIST-05` 应对「反对层出不穷」  `[A71 S56]`  ｜ 抗拒形态下的临场应变
- `SK-C-STAGE-RESIST-06` 应对「倦态的抗拒」  `[A71 S56]`  ｜ 抗拒形态下的临场应变

## 四、这份能力树解锁了什么

| V1.3 需求 | 本文件如何满足 |
|---|---|
| §2.3 CoverageMap 按能力点比对 | 每个 skill 有稳定 ID，预测考点与复盘问题都映射到同一 ID |
| §2.5 EmployeeSkillState 按 skill 记录 | skill_id 可直接作为 EmployeeSkillState.skill_id |
| §1.3 QuestionCandidate 必须关联 skill_ids[] | 每门课的 148 个知识考察点已有稳定 ID 形态 |
| §1.5 Rubric 跨情境比较 | 沟通树与知识树分离，两轨各用自己的 skill 空间 |

**仍缺的**：SkillTaxonomy 目前覆盖 42 个疾病 + 49 个产品/管线 + 沟通树。
V1.3 §1.2 要求的 `ExpertRef`/`TopicAffinity`（真实专家的公开学术线索）尚未建——
那部分必须来自公开可核验来源，不能从课件语料推断。
