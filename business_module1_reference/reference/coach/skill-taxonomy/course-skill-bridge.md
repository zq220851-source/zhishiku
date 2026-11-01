# 课程 ↔ 能力点 双向索引

> 把培训课程与陪练 Agent 的知识轨道接上：每门课练哪些能力点，每个能力点由哪门课承载。
> 生成方式：课程考察点与 SkillTaxonomy 能力点按「疾病 + 维度」同名精确匹配。

## 一、覆盖总览

| 项 | 值 |
|---|---|
| 知识能力点总数 | 197 |
| 已被课程覆盖 | 161 |
| **未覆盖** | **36** |
| 覆盖率 | 81.7% |
| 已索引课程 | 71 门 |

## 二、未被课程覆盖的能力点（培训缺口）

这些能力点在陪练 Agent 里会被考到，但目前没有对应课程承载——要么补课，要么在陪练中降级处理。

| 能力点 | 疾病 | 维度 | V1.3 评价项 |
|---|---|---|---|
| `SK-K-DABOHUA-PROD-01` | 达伯华（利妥昔单抗注射液） | product_basics | 知识准确性 |
| `SK-K-DABOTAN-PROD-01` | 达伯坦（佩米替尼片） | product_basics | 知识准确性 |
| `SK-K-FUKESU-PROD-01` | 福可苏（伊基奥仑赛注射液） | product_basics | 知识准确性 |
| `SK-K-IBI115-PIPE-01` | IBI115（DLL3/CD3双特异抗体） | pipeline_literacy | 专业与合规要求 |
| `SK-K-IBI128-PIPE-01` | IBI128（黄嘌呤氧化酶（XO）抑制剂） | pipeline_literacy | 专业与合规要求 |
| `SK-K-IBI3001-PIPE-01` | IBI3001（EGFR/B7H3 ADC） | pipeline_literacy | 专业与合规要求 |
| `SK-K-IBI3002-PIPE-01` | IBI3002（TSLP/IL-4Rα双特异抗体） | pipeline_literacy | 专业与合规要求 |
| `SK-K-IBI3003-PIPE-01` | IBI3003（GPRC5D/BCMA/CD3三抗） | pipeline_literacy | 专业与合规要求 |
| `SK-K-IBI3009-PIPE-01` | IBI3009（DLL3 ADC） | pipeline_literacy | 专业与合规要求 |
| `SK-K-IBI3011-PIPE-01` | IBI3011（IL-1RAP单抗） | pipeline_literacy | 专业与合规要求 |
| `SK-K-IBI3013-PIPE-01` | IBI3013（IL-15单抗） | pipeline_literacy | 专业与合规要求 |
| `SK-K-IBI3014-PIPE-01` | IBI3014（PD-L1/TROP2 ADC） | pipeline_literacy | 专业与合规要求 |
| `SK-K-IBI3016-PIPE-01` | IBI3016（AGT siRNA） | pipeline_literacy | 专业与合规要求 |
| `SK-K-IBI302-PIPE-01` | IBI302（VEGF/补体融合蛋白） | pipeline_literacy | 专业与合规要求 |
| `SK-K-IBI3020-PIPE-01` | IBI3020（CEACAM5 ADC） | pipeline_literacy | 专业与合规要求 |
| `SK-K-IBI3026-PIPE-01` | IBI3026（PD-1/IL-12融合蛋白） | pipeline_literacy | 专业与合规要求 |
| `SK-K-IBI3027-PIPE-01` | IBI3027（IL-4Rα单抗） | pipeline_literacy | 专业与合规要求 |
| `SK-K-IBI3028-PIPE-01` | IBI3028（EGFR/c-Met ADC） | pipeline_literacy | 专业与合规要求 |
| `SK-K-IBI3030-PIPE-01` | IBI3030（月度PCSK9相关候选药） | pipeline_literacy | 专业与合规要求 |
| `SK-K-IBI3031-PIPE-01` | IBI3031（TSHR/IGF-1R双特异抗体） | pipeline_literacy | 专业与合规要求 |
| `SK-K-IBI3032-PIPE-01` | IBI3032（口服日制剂GLP-1R小分子） | pipeline_literacy | 专业与合规要求 |
| `SK-K-IBI3035-PIPE-01` | IBI3035（胰岛素相关多肽） | pipeline_literacy | 专业与合规要求 |
| `SK-K-IBI3038-PIPE-01` | IBI3038（IGF-1R/IL-6相关研发项目） | pipeline_literacy | 专业与合规要求 |
| `SK-K-IBI3040-PIPE-01` | IBI3040（Amylin/Calcitonin相关多肽） | pipeline_literacy | 专业与合规要求 |
| `SK-K-IBI3042-PIPE-01` | IBI3042（口服周制剂GLP-1R小分子） | pipeline_literacy | 专业与合规要求 |
| `SK-K-IBI3046-PIPE-01` | IBI3046（INHBE siRNA） | pipeline_literacy | 专业与合规要求 |
| `SK-K-IBI324-PIPE-01` | IBI324（VEGF-A/ANG2双特异抗体） | pipeline_literacy | 专业与合规要求 |
| `SK-K-IBI355-PIPE-01` | IBI355（CD40L单抗） | pipeline_literacy | 专业与合规要求 |
| `SK-K-JIEPALI-PROD-01` | 捷帕力（匹妥布替尼片） | product_basics | 知识准确性 |
| `SK-K-NAILIKE-PROD-01` | 耐立克（奥雷巴替尼片） | product_basics | 知识准确性 |
| `SK-K-SULIXIN-PROD-01` | 苏立信（阿达木单抗注射液） | product_basics | 知识准确性 |
| `SK-K-WEIFUTAI-PROD-01` | 维复泰（盐酸奎扎替尼片） | product_basics | 知识准确性 |
| `SK-K-XINBILE-PROD-01` | 信必乐（托莱西单抗注射液） | product_basics | 知识准确性 |
| `SK-K-XINBIMIN-PROD-01` | 信必敏（替妥尤单抗N01注射液） | product_basics | 知识准确性 |
| `SK-K-XINERMEI-PROD-01` | 信尔美（玛仕度肽注射液） | product_basics | 知识准确性 |
| `SK-K-XINMEIYUE-PROD-01` | 信美悦（匹康奇拜单抗注射液） | product_basics | 知识准确性 |

## 三、课程 → 能力点

| 课程 | 覆盖的能力点 |
|---|---|
| D-AD / disease_foundation | `SK-K-D-AD-129`, `SK-K-D-AD-130`, `SK-K-D-AD-131` |
| D-AML / disease_foundation | `SK-K-D-AML-067`, `SK-K-D-AML-068`, `SK-K-D-AML-069`, `SK-K-D-AML-070` |
| D-AS / disease_foundation | `SK-K-D-AS-114`, `SK-K-D-AS-115`, `SK-K-D-AS-116` |
| D-BREAST / clinical_evidence | `SK-K-D-BREAST-033`, `SK-K-D-BREAST-034`, `SK-K-D-BREAST-035`, `SK-K-D-BREAST-036` |
| D-BREAST / disease_foundation | `SK-K-D-BREAST-033`, `SK-K-D-BREAST-034`, `SK-K-D-BREAST-035`, `SK-K-D-BREAST-036` |
| D-BREAST / treatment_landscape | `SK-K-D-BREAST-033`, `SK-K-D-BREAST-034`, `SK-K-D-BREAST-035`, `SK-K-D-BREAST-036` |
| D-CCA / disease_foundation | `SK-K-D-CCA-020`, `SK-K-D-CCA-021`, `SK-K-D-CCA-022`, `SK-K-D-CCA-023` 等 5 个 |
| D-CERVICAL / clinical_evidence | `SK-K-D-CERVICAL-047`, `SK-K-D-CERVICAL-048`, `SK-K-D-CERVICAL-049`, `SK-K-D-CERVICAL-050` |
| D-CERVICAL / disease_foundation | `SK-K-D-CERVICAL-047`, `SK-K-D-CERVICAL-048`, `SK-K-D-CERVICAL-049`, `SK-K-D-CERVICAL-050` |
| D-CERVICAL / treatment_landscape | `SK-K-D-CERVICAL-047`, `SK-K-D-CERVICAL-048`, `SK-K-D-CERVICAL-049`, `SK-K-D-CERVICAL-050` |
| D-CLL / disease_foundation | `SK-K-D-CLL-077`, `SK-K-D-CLL-078`, `SK-K-D-CLL-079`, `SK-K-D-CLL-080` |
| D-CML / disease_foundation | `SK-K-D-CML-064`, `SK-K-D-CML-065`, `SK-K-D-CML-066` |
| D-CRC / clinical_evidence | `SK-K-D-CRC-017`, `SK-K-D-CRC-018`, `SK-K-D-CRC-019` |
| D-CRC / disease_foundation | `SK-K-D-CRC-017`, `SK-K-D-CRC-018`, `SK-K-D-CRC-019` |
| D-CRC / treatment_landscape | `SK-K-D-CRC-017`, `SK-K-D-CRC-018`, `SK-K-D-CRC-019` |
| D-CROHN / disease_foundation | `SK-K-D-CROHN-126`, `SK-K-D-CROHN-127`, `SK-K-D-CROHN-128` |
| D-DLBCL / disease_foundation | `SK-K-D-DLBCL-071`, `SK-K-D-DLBCL-072`, `SK-K-D-DLBCL-073`, `SK-K-D-DLBCL-074` |
| D-DME / disease_foundation | `SK-K-D-DME-143`, `SK-K-D-DME-144`, `SK-K-D-DME-145` |
| D-DYSLIPID / disease_foundation | `SK-K-D-DYSLIPID-100`, `SK-K-D-DYSLIPID-101`, `SK-K-D-DYSLIPID-102`, `SK-K-D-DYSLIPID-103` |
| D-ENDO / disease_foundation | `SK-K-D-ENDO-030`, `SK-K-D-ENDO-031`, `SK-K-D-ENDO-032` |
| D-ESCC / disease_foundation | `SK-K-D-ESCC-027`, `SK-K-D-ESCC-028`, `SK-K-D-ESCC-029` |
| D-FL / disease_foundation | `SK-K-D-FL-075`, `SK-K-D-FL-076` |
| D-GBM / clinical_evidence | `SK-K-D-GBM-051`, `SK-K-D-GBM-052` |
| D-GBM / disease_foundation | `SK-K-D-GBM-051`, `SK-K-D-GBM-052` |
| D-GBM / treatment_landscape | `SK-K-D-GBM-051`, `SK-K-D-GBM-052` |
| D-GC / clinical_evidence | `SK-K-D-GC-012`, `SK-K-D-GC-013`, `SK-K-D-GC-014`, `SK-K-D-GC-015` 等 5 个 |
| D-GC / disease_foundation | `SK-K-D-GC-012`, `SK-K-D-GC-013`, `SK-K-D-GC-014`, `SK-K-D-GC-015` 等 5 个 |
| D-GC / treatment_landscape | `SK-K-D-GC-012`, `SK-K-D-GC-013`, `SK-K-D-GC-014`, `SK-K-D-GC-015` 等 5 个 |
| D-GOUT / disease_foundation | `SK-K-D-GOUT-132`, `SK-K-D-GOUT-133` |
| D-HCC / clinical_evidence | `SK-K-D-HCC-007`, `SK-K-D-HCC-008`, `SK-K-D-HCC-009`, `SK-K-D-HCC-010` 等 5 个 |
| D-HCC / disease_foundation | `SK-K-D-HCC-007`, `SK-K-D-HCC-008`, `SK-K-D-HCC-009`, `SK-K-D-HCC-010` 等 5 个 |
| D-HCC / treatment_landscape | `SK-K-D-HCC-007`, `SK-K-D-HCC-008`, `SK-K-D-HCC-009`, `SK-K-D-HCC-010` 等 5 个 |
| D-HFPEF / disease_foundation | `SK-K-D-HFPEF-108`, `SK-K-D-HFPEF-109`, `SK-K-D-HFPEF-110` |
| D-HTN / disease_foundation | `SK-K-D-HTN-104`, `SK-K-D-HTN-105`, `SK-K-D-HTN-106`, `SK-K-D-HTN-107` |
| D-MASH / disease_foundation | `SK-K-D-MASH-094`, `SK-K-D-MASH-095`, `SK-K-D-MASH-096` |
| D-MCL / disease_foundation | `SK-K-D-MCL-081`, `SK-K-D-MCL-082` |
| D-MEL / disease_foundation | `SK-K-D-MEL-044`, `SK-K-D-MEL-045`, `SK-K-D-MEL-046` |
| D-MESO / disease_foundation | `SK-K-D-MESO-056`, `SK-K-D-MESO-057`, `SK-K-D-MESO-058`, `SK-K-D-MESO-059` 等 8 个 |
| D-MM / disease_foundation | `SK-K-D-MM-083`, `SK-K-D-MM-084`, `SK-K-D-MM-085`, `SK-K-D-MM-086` 等 5 个 |
| D-NAMD / disease_foundation | `SK-K-D-NAMD-146`, `SK-K-D-NAMD-147`, `SK-K-D-NAMD-148` |
| D-NSCLC / clinical_evidence | `SK-K-D-NSCLC-001`, `SK-K-D-NSCLC-002`, `SK-K-D-NSCLC-003`, `SK-K-D-NSCLC-004` 等 6 个 |
| D-NSCLC / disease_foundation | `SK-K-D-NSCLC-001`, `SK-K-D-NSCLC-002`, `SK-K-D-NSCLC-003`, `SK-K-D-NSCLC-004` 等 6 个 |
| D-NSCLC / treatment_landscape | `SK-K-D-NSCLC-001`, `SK-K-D-NSCLC-002`, `SK-K-D-NSCLC-003`, `SK-K-D-NSCLC-004` 等 6 个 |
| D-OBE / disease_foundation | `SK-K-D-OBE-088`, `SK-K-D-OBE-089`, `SK-K-D-OBE-090` |
| D-OSA / disease_foundation | `SK-K-D-OSA-097`, `SK-K-D-OSA-098`, `SK-K-D-OSA-099` |
| D-OVARIAN / clinical_evidence | `SK-K-D-OVARIAN-037`, `SK-K-D-OVARIAN-038`, `SK-K-D-OVARIAN-039`, `SK-K-D-OVARIAN-040` |
| D-OVARIAN / disease_foundation | `SK-K-D-OVARIAN-037`, `SK-K-D-OVARIAN-038`, `SK-K-D-OVARIAN-039`, `SK-K-D-OVARIAN-040` |
| D-OVARIAN / treatment_landscape | `SK-K-D-OVARIAN-037`, `SK-K-D-OVARIAN-038`, `SK-K-D-OVARIAN-039`, `SK-K-D-OVARIAN-040` |
| D-PDAC / disease_foundation | `SK-K-D-PDAC-041`, `SK-K-D-PDAC-042`, `SK-K-D-PDAC-043` |
| D-PSA / disease_foundation | `SK-K-D-PSA-122`, `SK-K-D-PSA-123`, `SK-K-D-PSA-124`, `SK-K-D-PSA-125` |
| D-PSO / disease_foundation | `SK-K-D-PSO-117`, `SK-K-D-PSO-118`, `SK-K-D-PSO-119`, `SK-K-D-PSO-120` 等 5 个 |
| D-RA / disease_foundation | `SK-K-D-RA-111`, `SK-K-D-RA-112`, `SK-K-D-RA-113` |
| D-RCC / disease_foundation | `SK-K-D-RCC-025`, `SK-K-D-RCC-026` |
| D-SJOGREN / disease_foundation | `SK-K-D-SJOGREN-138`, `SK-K-D-SJOGREN-139` |
| D-T2DM / disease_foundation | `SK-K-D-T2DM-091`, `SK-K-D-T2DM-092`, `SK-K-D-T2DM-093` |
| D-TED / disease_foundation | `SK-K-D-TED-140`, `SK-K-D-TED-141`, `SK-K-D-TED-142` |
| D-THYROID / disease_foundation | `SK-K-D-THYROID-053`, `SK-K-D-THYROID-054`, `SK-K-D-THYROID-055` |
| D-VITILIGO / disease_foundation | `SK-K-D-VITILIGO-134`, `SK-K-D-VITILIGO-135`, `SK-K-D-VITILIGO-136`, `SK-K-D-VITILIGO-137` |
| IBI3005 / pipeline_literacy | `SK-K-IBI3005-PIPE-01` |
| IBI343 / pipeline_literacy | `SK-K-IBI343-PIPE-01` |
| IBI354 / pipeline_literacy | `SK-K-IBI354-PIPE-01` |
| IBI363 / pipeline_literacy | `SK-K-IBI363-PIPE-01` |
| aoyixin / product_basics | `SK-K-AOYIXIN-PROD-01` |
| dabole / product_basics | `SK-K-DABOLE-PROD-01` |
| daboshu / product_basics | `SK-K-DABOSHU-PROD-01` |
| dabote / product_basics | `SK-K-DABOTE-PROD-01` |
| daboxin / product_basics | `SK-K-DABOXIN-PROD-01` |
| dayoutong / product_basics | `SK-K-DAYOUTONG-PROD-01` |
| ruituo / product_basics | `SK-K-RUITUO-PROD-01` |
| weize / product_basics | `SK-K-WEIZE-PROD-01` |
| xirangze / product_basics | `SK-K-XIRANGZE-PROD-01` |