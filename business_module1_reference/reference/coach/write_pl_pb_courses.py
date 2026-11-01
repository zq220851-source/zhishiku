#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
编写 PL 维度的 4 门课（管线认知：披露状态 ≠ 审批状态）。

由 owner 直接编写（asset-2 agent 遇 API 错误中断），标准对齐已通过的 PB 课：
  - 三层/多格概念图或流程图
  - 真实的医生提问（带销售压力）
  - 核实路径写在正确项本身
  - 4 steps + 2 misconceptions + 2 checks
"""
import json, os, sqlite3

from config import BASE, PATHS
SKEL = os.path.join(BASE, "course-skeletons-ce")
OUT = os.path.join(BASE, "course-specs-ce")
os.makedirs(OUT, exist_ok=True)

db = sqlite3.connect(os.path.join(BASE, "clinical/medrep-innovent-clinical-knowledge-v0.5",
                                   "medrep_clinical_knowledge_v0.5.sqlite"))
db.row_factory = sqlite3.Row

pipes = {r["asset_id"]: dict(r) for r in db.execute("select * from expanded_pipeline")}
pcond = {}
for r in db.execute("select m.condition_id, m.asset_id from pipeline_condition_map m"):
    pcond.setdefault(r["asset_id"], []).append(r["condition_id"])
conds = {r["condition_id"]: dict(r) for r in db.execute("select * from clinical_conditions")}

# 各资产的疾病语境（取前 2 个关联疾病名）
def disease_ctx(aid):
    ds = pcond.get(aid, [])
    names = [conds[d]["name"] for d in ds if d in conds]
    return names

ASSETS = ["IBI343", "IBI363", "IBI354", "IBI3005"]

# 每个资产的定制教学要素
CUSTOM = {
    "IBI343": {
        "mech": "CLDN18.2 ADC",
        "scene": "医生手里有一份 NGS 报告写着 CLDN18.2 阳性，问你这是不是意味着他就是能用这类药的人",
        "trap_myth": "在研项目已经进入申报阶段，说明临床效果已经被验证了，用药人群应该就是报告阳性的那批人。",
        "trap_corr": "NDA 审评是研发方披露的进展口径，说明不了疗效已被独立验证；报告阳性与获批适用范围是两件事，后者只能从最新 NMPA 说明书读。",
        "q": "医生问：「我这边有个病人 NGS 报了 CLDN18.2 阳性，你们这个 ADC 是不是就能用了？」",
        "ans": "报告阳性只是入组层面的信息；能否用要看最新 NMPA 说明书与企业合规版本，我这边不能替您判断。",
    },
    "IBI363": {
        "mech": "PD-1/IL-2α 偏向融合蛋白",
        "scene": "医生听过这个项目的名字，问你是不是可以把已上市的 PD-1 产品的讲法直接搬过来",
        "trap_myth": "同样是 PD-1 方向，已上市的 PD-1 产品怎么讲，这个新资产就怎么讲，讲法可以通用。",
        "trap_corr": "机制方向相近不等于适用人群相同；适用范围必须按该资产自己的说明书查，不能借用其他产品的讲法。",
        "q": "医生问：「都是 PD-1 这条线，你们这个新的跟已上市的比，适应人群是不是差不多？」",
        "ans": "机制方向相近不代表适用人群相同；具体人群要看该资产自己的最新说明书，我需要核实后回复您。",
    },
    "IBI354": {
        "mech": "HER2 ADC",
        "scene": "医生同时在看一个已上市的 HER2 靶向药和一个在研的 HER2 ADC，问两个能不能一起讲",
        "trap_myth": "靶点一样就是一类药，适应症可以互相参照，已上市的那个能讲什么这个也能讲什么。",
        "trap_corr": "同靶点不等于同适应症；每个产品的适用范围由各自的说明书限定，HER2 靶点内也要分产品核实。",
        "q": "医生问：「都是 HER2，你们这个 ADC 跟已经上市的那几个，适应症范围应该差不多吧？」",
        "ans": "同靶点不等于同适用范围；要按这个资产自己的最新说明书核实，我这边不能替您判断。",
    },
    "IBI3005": {
        "mech": "EGFR/HER3 ADC",
        "scene": "医生知道你们有个 EGFR 方向的已上市产品，问这个 ADC 是不是可以直接沿用那条线的沟通材料",
        "trap_myth": "同一靶点方向的已上市产品可以当参照，适用范围和沟通口径直接沿用就行。",
        "trap_corr": "同方向不等于同产品；机制、给药方式与适用范围都要按本资产自己的资料核实，不能借用其他产品的话术。",
        "q": "医生问：「你们 EGFR 方向已经有产品了，这个 ADC 的适应人群是不是就差不多？」",
        "ans": "同一靶点方向不代表适用范围相同；要按本资产自己的说明书核实，我不能直接套用其他产品。",
    },
}

for aid in ASSETS:
    p = pipes[aid]
    cu = CUSTOM[aid]
    ds = disease_ctx(aid)
    ds_txt = "、".join(ds[:3]) if ds else "相关疾病领域"
    reported = p["reported_status"]
    approval = p["approval_status"]
    skel = json.load(open(os.path.join(SKEL, f"{aid}__PL.json"), encoding="utf-8"))

    spec = {
        "meta": {
            "title": f"{aid}（{cu['mech']}）：管线认知——披露口径与审批状态要分开讲",
            "subject": "产品与管线（肿瘤学）",
            "age": "医药代表（入职 0–6 个月）",
            "duration": "15 分钟",
            "language": "zh-CN",
        },
        "hero": {
            "eyebrow": f"产品与管线 · 肿瘤学 · {aid} · 管线认知",
            "question": cu["q"],
            "promise": f"学员能把「研发方披露到哪一步」和「监管审批到哪一步」拆成两句话分别讲，"
                       f"并说清 {aid} 与 {ds_txt} 的关联是教学主题关联、不是获批适应症。",
        },
        "goal": f"能在 2 分钟内讲清 {aid} 的机制方向（{cu['mech']}）、研发方披露口径"
                f"（{reported}）与监管审批状态（{approval}）三者的区别，"
                f"并明确产品与疾病的关联属教学主题关联、适用范围须查最新 NMPA 说明书与企业合规版本。",
        "assumptions": [
            "知道「披露」与「获批」是两件事，能理解研发方说的进展不等于监管结论",
            "知道药品的适用范围由最新 NMPA 说明书与企业合规版本限定，不能靠推断",
            "知道代表的职责是提供准确信息并说明核查路径，用药决策由医生作出",
        ],
        "map": {
            "prerequisites": [
                "在研资产的三个状态字段：研发方披露口径、监管审批状态、本产品的内部审核状态",
                "药品适用范围由说明书限定；未获批的资产没有可推广的适应症范围",
                "产品与疾病关联的教学含义：可用于讲解与检索，不等于获批适应症",
            ],
            "core": f"{aid} 的三个层次：机制方向（{cu['mech']}，可核实）→ "
                    f"研发方披露口径（{reported}，转述时必须标明来源与时点）→ "
                    f"监管审批状态（{approval}，这是唯一能说明「能不能推广」的依据）",
            "unlocks": [
                "被问「这个项目现在什么状态」时，先分清披露与审批再回答",
                "被问「是不是能用」时，用核查路径代替硬答",
                "在内部知识库里给这条资产打上正确的状态标记，避免被误当已获批",
            ],
        },
        "hook": {
            "title": "一句话里藏了两件事",
            "body": f"你在介绍 {aid} 时，很自然会说出「{reported}」这句话。"
                    f"但医生听到的可能是「这个药快批下来了，我可以用」。"
                    f"披露口径说的是研发方的进展叙述，审批状态说的是监管的判断，"
                    f"两者之间隔着申报、审评、发补、现场核查等环节。",
            "prompt": "先写下你会对医生说的那句话，再看流程图：那句话里，披露和审批有没有被说成一件事？",
        },
        "visual": {
            "kind": "process",
            "title": f"{aid}：从研发披露到可推广结论的四道关口",
            "instruction": "把医生问的每一句放到对应关口，再标出你在这一关口能讲什么、不能讲什么。",
            "stages": [
                {"title": "关口一 · 机制方向可讲",
                 "body": f"{cu['mech']}。这是机制层面的事实，可以核实、可以直接讲，"
                         f"但它只回答「作用在哪个靶点」，不回答「能给谁用」。"},
                {"title": "关口二 · 研发方披露只能转述",
                 "body": f"披露口径是「{reported}」。转述时必须带上「研发方披露」这层限定"
                         f"和来源时点，不能讲成「已经批了」或「效果已被验证」。"},
                {"title": "关口三 · 监管审批状态是唯一依据",
                 "body": f"审批状态当前为「{approval}」。这是唯一能支撑「能否作为可推广信息」的字段。"
                         f"其他一切进展叙述都不能替代它。"},
                {"title": "关口四 · 与疾病的关联只到教学主题",
                 "body": f"{aid} 关联 {ds_txt}，但这个关联类型是教学主题关联"
                         f"（educational_topic_not_indication），不是获批适应症。"
                         f"讲到这里就必须停，适用范围请查最新 NMPA 说明书与企业合规版本。"},
            ],
            "observation": "四道关口里，只有第一道可以放心讲；第二道要加限定词，第三道是唯一结论依据，"
                           "第四道必须主动停住转成核实动作。任何一关跳过，都会把「在研」讲成「可用」。",
        },
        "analogy": {
            "title": "像在工地和验收之间",
            "body": "研发方的披露像工地进度汇报：盖到第几层、什么时候封顶。监管审批像验收："
                    "只有验收通过并发了使用许可，才谈得上按什么范围使用。工地进度汇报写得再乐观，"
                    "也不等于验收通过。",
            "limit": "这个类比只帮助理解「进展叙述 ≠ 结论」这一层。它不表示研发进度与审批速度成比例，"
                     "也不表示披露口径可靠或不可靠——披露是研发方的正式公开信息，只是它回答的不是同一个问题。",
        },
        "steps": [
            {"label": "01", "title": "先把机制方向讲清楚",
             "body": f"{cu['mech']}。这一层可核实、可直接讲，但讲完要停——机制不推出适用人群。"},
            {"label": "02", "title": "披露口径加上限定词",
             "body": f"说「{reported}」时，必须带上「研发方披露」这层含义和时点，"
                     f"并说清这不是监管结论。"},
            {"label": "03", "title": "审批状态才是能不能讲的依据",
             "body": f"当前审批状态是「{approval}」。这一条决定了你能不能把它当作可推广信息讲。"},
            {"label": "04", "title": "疾病关联讲到这里就停",
             "body": f"它与 {ds_txt} 的关联是教学主题关联，不是获批适应症。"
                     f"适用范围请查最新 NMPA 说明书与企业合规版本，我这边不做推断。"},
        ],
        "misconceptions": [
            {"myth": cu["trap_myth"], "correction": cu["trap_corr"],
             "why": "披露口径与审批结论回答的是两个不同问题。混用会把研发进展讲成可推广信息，"
                    "这在合规上是最容易留下痕迹的一类越界。"},
            {"myth": "既然机制方向一样，讲法就可以通用，不用再查这个资产自己的资料。",
             "correction": "同靶点、同方向都不推出同适用范围。每个产品的适用范围由各自的最新说明书限定，"
                           "沟通口径必须按本资产单独核实。",
             "why": "同靶点内不同产品的给药方式、线次、联合条件都可能不同，"
                    "沿用其他产品的话术会把别人的适用范围错安到本产品上。"},
        ],
        "checks": [
            {"question": cu["q"] + "下列回应最合适的是？",
             "options": [
                 "可以的，报告阳性就说明他能用，我这边帮您确认一下适应症",
                 "如果进入申报阶段了，说明效果已经验证过，可以先按报告阳性的用药人群准备",
                 cu["ans"],
                 "同靶点的产品适应人群基本一致，我按已上市的那个给您讲适用范围",
             ],
             "answer": 2,
             "explanation": "正确项把问题落到可执行的核查动作上：机制方向可讲，适用范围查说明书。"
                            "A 是把报告结果直接当成用药结论；B 把申报进展读成疗效已验证；"
                            "D 用其他产品的适用范围替代本资产的核实，三者都越过了证据边界。"},
            {"question": "关于这个资产的当前状态，下列说法准确的是？",
             "options": [
                 "研发方披露的进展说明已经通过临床验证，可以按此开展学术交流",
                 "只要机制方向有吸引力，就可以在拜访中讲这个资产的适用范围",
                 "披露口径与审批状态是两个字段；判断能否作为可推广信息，依据是审批状态",
                 "既然是公开披露的内容，就可以直接告诉医生这个药能给哪类患者用",
             ],
             "answer": 2,
             "explanation": "正确项点明两个状态字段的分工：披露讲研发方说了什么，审批讲监管结论了什么，"
                            "能讲什么由后者决定。A 把披露读成临床验证；B 用机制吸引力替代适用范围；"
                            "D 忽略「公开可披露」与「可作为推广信息」是两件事。"},
        ],
        "recall": {
            "prompt": "合上页面，用三句话说清：披露口径与审批状态各是什么、以及被问「能不能用」时你怎么办。",
            "hint": "三句分别对应：披露是什么、审批是什么、动作是什么。",
            "answer": f"披露口径是研发方公开的进展叙述（当前为「{reported}」），转述时要带限定词；"
                      f"审批状态是监管判断（当前为「{approval}」），它是唯一能决定能否作为可推广信息的依据；"
                      f"被问到适用范围时，我按最新 NMPA 说明书与企业合规版本核实后回复，不做推断。",
        },
        "sources": [
            {"label": skel["source"]["title"] or "信达生物 2026 中期报告产品及管线列表",
             "detail": f"source_id={skel['source']['source_id']}；reported_status={reported}；"
                       f"approval_status={approval}；asof_date={skel['source'].get('asof_date')}",
             "url": skel["source"]["url"]},
            {"label": "本产品知识库记录",
             "detail": f"表=expanded_pipeline；asset_id={aid}；mechanism_topic={p['mechanism_topic']}；"
                       f"review_status={p['review_status']}",
             "url": skel["source"]["url"]},
            {"label": "适用范围核实路径（唯一依据）",
             "detail": "最新 NMPA 说明书 + 企业合规版本；本课不提供适应症、用法用量等需说明书支撑的内容",
             "url": skel["source"]["url"]},
        ],
    }
    with open(os.path.join(OUT, f"{aid}__PL.json"), "w", encoding="utf-8") as fh:
        json.dump(spec, fh, ensure_ascii=False, indent=2)
    print(f"✅ {aid}__PL 已写入")

# 同时补 asset-2 的 3 门 PB
PB = {
    "aoyixin": {"name": "奥壹新", "gen": "利厄替尼片", "mech": "EGFR",
                "q": "医生问：「奥壹新这个药是干什么的？适用到什么范围？我科里有 EGFR 突变的老病人了。」",
                "ans": "通用名与 EGFR 靶点可以讲；适用范围要查最新 NMPA 说明书与企业合规版本，我不能凭印象给您人群。"},
    "daboxin": {"name": "达伯欣", "gen": "伊匹木单抗N01注射液", "mech": "CTLA-4",
                 "q": "医生问：「达伯欣跟免疫治疗那些有什么不一样？适用人群是怎么定的？」",
                 "ans": "CTLA-4 这个机制方向可以讲；适用范围要按最新 NMPA 说明书与企业合规版本核实，我不替您判断。"},
    "weize": {"name": "唯择", "gen": "阿贝西利片", "mech": "CDK4/6",
              "q": "医生问：「唯择是 CDK4/6 抑制剂，那是不是所有 HR 阳性、HER2 阴性的病人都能用？」",
              "ans": "CDK4/6 方向和适用人群不是一回事；具体人群要查最新 NMPA 说明书与企业合规版本。"},
}
for pid, cu in PB.items():
    skel = json.load(open(os.path.join(SKEL, f"{pid}__PB.json"), encoding="utf-8"))
    prod = None
    import sqlite3 as sq
    db2 = sq.connect(os.path.join(BASE, "clinical/medrep-innovent-clinical-knowledge-v0.5",
                                   "medrep_clinical_knowledge_v0.5.sqlite"))
    db2.row_factory = sq.Row
    prod = dict(db2.execute("select * from med_products where product_id=?", (pid,)).fetchone())
    gen = prod["generic_name"]
    spec = {
        "meta": {
            "title": f"{cu['name']}（{gen}）：产品基础与核查路径",
            "subject": "产品与管线（肿瘤学）",
            "age": "医药代表（入职 0–6 个月）",
            "duration": "15 分钟",
            "language": "zh-CN",
        },
        "hero": {
            "eyebrow": f"产品与管线 · 肿瘤学 · {cu['name']}（{gen}）· 产品基础",
            "question": cu["q"],
            "promise": f"学员能在被问「{cu['name']} 是干什么的、适用范围是什么」时，"
                       f"把问题拆成三层：通用名与 {cu['mech']} 靶点（可核实、可直接讲）、"
                       f"适用范围（只从最新 NMPA 说明书与企业合规版本读）、研发方披露口径（不等于审批结论）。",
        },
        "goal": f"能在 2 分钟内把医生关于 {cu['name']} 的提问拆成「通用名与靶点」「适用范围」"
                f"「研发进展」三类，分别用可核实、需查证、不可推断三种方式回应，"
                f"并对超出自己掌握范围的部分明确说出不确定、同时给出核实路径。",
        "assumptions": [
            "知道商品名与通用名的区别，能从通用名读出剂型",
            f"知道 {cu['mech']} 属于什么方向，以及它与相邻靶点的概念差别",
            "知道代表的职责是提供准确信息，用药决策由医生作出",
        ],
        "map": {
            "prerequisites": [
                "肿瘤学产品信息的三种来源：公开共识、已批准产品说明书、研发方披露",
                "通用名、商品名与作用靶点（机制方向）的基本对应关系",
                f"{cu['mech']} 方向的基本概念与相邻靶点的区别",
            ],
            "core": f"{cu['name']}（{gen}）的产品基础拆成三层：可核实的通用名与 {cu['mech']} 靶点 → "
                    f"必须查最新 NMPA 说明书与企业合规版本的适用范围 → 研发方披露口径与监管审批状态的分界",
            "unlocks": [
                f"把「{cu['name']} 是干什么的」翻译成先给靶点、再给核查动作的合规开场",
                "分清哪些信息属于产品基础、哪些属于说明书限定，能当场说出分界",
                "被追问适用范围时，用核实路径代替硬答",
            ],
        },
        "hook": {
            "title": f"一句「{cu['mech']}」不够用",
            "body": f"医生问起 {cu['name']} 时，你脑子里其实混着三件事：这是打 {cu['mech']} 的药、"
                    f"这是{cu['name']}这个药、这是能让这个病人用的药。"
                    f"前两件可以核实、可以当场讲；第三件只能从最新 NMPA 说明书和企业合规版本里读，读之前不许凭印象补。",
            "prompt": "先写下你开口的第一句话，再看概念地图：这句话里「能讲」和「要查」是不是被混着说了？",
        },
        "visual": {
            "kind": "concept-map",
            "title": f"{cu['name']}（{gen}）：产品信息三格抽屉与开口路径",
            "instruction": "把医生问的每一句标到正确的格子里，再标出这一格你能讲到什么程度，最后找出开口时应该先给的那一句。",
            "nodes": [
                {"id": "n1", "label": f"通用名：{gen}（可核实）", "role": "prerequisite", "connectsTo": ["n3"]},
                {"id": "n2", "label": f"作用靶点：{cu['mech']}（可核实）", "role": "prerequisite", "connectsTo": ["n3"]},
                {"id": "n3", "label": "第一格｜可以直接讲：通用名 + 靶点", "role": "core", "connectsTo": ["n4", "n5"]},
                {"id": "n4", "label": "第二格｜只能查证：适用范围（人群、线次、联合条件）", "role": "core", "connectsTo": ["n6"]},
                {"id": "n5", "label": "第三格｜只能转述：研发方披露口径 ≠ 审批结论", "role": "core", "connectsTo": ["n6"]},
                {"id": "n6", "label": "开口模板：先给可核实的，再给核实路径", "role": "unlock", "connectsTo": ["n7"]},
                {"id": "n7", "label": "落点：把不确定变成一条可执行的核查动作", "role": "unlock", "connectsTo": []},
            ],
            "observation": "三格抽屉里只有第一格可以放心讲。第二格必须转成核查动作，"
                           "第三格必须带「研发方披露」的限定词——跳过任何一格，都会把「在研」讲成「可用」。",
        },
        "analogy": {
            "title": "像说明书和目录的关系",
            "body": "通用名和靶点像书的目录——帮你知道这本书讲什么；适用范围像正文里的限定条件——"
                    "决定这本书里的哪一段真正适用于你的情况。目录能背，正文必须按版本查。",
            "limit": "这个类比只说明「可核实的信息」与「需查证的信息」的分工。"
                     "它不表示适用范围可以靠逻辑推出来——恰恰相反，适用范围只能从最新版说明书读。",
        },
        "steps": [
            {"label": "01", "title": "先给可核实的那一层",
             "body": f"通用名 {gen} 与 {cu['mech']} 靶点。这两句可以当场讲，且不含任何人群限定。"},
            {"label": "02", "title": "适用范围只说核查动作",
             "body": "人群、线次、联合条件这些只能从最新 NMPA 说明书与企业合规版本读，"
                     "讲的时候给动作，不给数字。"},
            {"label": "03", "title": "研发进展要带限定词",
             "body": "涉及在研资产时，说明是研发方披露口径，并指出审批状态才是判断能否推广的依据。"},
            {"label": "04", "title": "把用药决策留给医生",
             "body": "你能提供准确信息与核查路径，定方案是医生的判断；把这条边界说清楚，比硬答更专业。"},
        ],
        "misconceptions": [
            {"myth": f"既然 {cu['mech']} 这个方向是明确的，适应人群也可以按同方向的其他产品推断。",
             "correction": "机制方向明确不等于适用范围明确。适用范围由本产品自己的最新说明书限定，"
                           "同方向不同产品的线次与联合条件都可能不同。",
             "why": "按其他产品推断适用范围，是把未经核实的结论当作事实讲出去，风险由药代和公司共同承担。"},
            {"myth": "适用范围记不住就先大概讲个范围，反正是常见用法。",
             "correction": "记不住就不讲范围，给出核实路径（查最新 NMPA 说明书与企业合规版本）即可。",
             "why": "「大概」在合规上等同于「没有核实」。给出核查动作是专业表现，含糊其辞才是风险。"},
        ],
        "checks": [
            {"question": cu["q"] + "下列回应最合适的是？",
             "options": [
                 f"可以的，{cu['mech']} 方向适应人群比较明确，我这边帮您确认一下",
                 f"{cu['mech']} 的话适应症是有明确划分的，我按一般情况给您说一下范围",
                 cu["ans"],
                 "产品说明书上的适应症我记得大概，我给您讲讲主要覆盖哪几类病人",
             ],
             "answer": 2,
             "explanation": "正确项把问题落到可执行的核查动作上：机制方向可讲，适用范围查说明书。"
                            "A 把方向直接读成适用结论；B 是含糊其辞；"
                            "D 是凭记忆讲适用范围——记不住就不该讲，这是同一个错误。"},
            {"question": "关于这个产品的适用范围，下列哪种做法是对的？",
             "options": [
                 "适用范围是产品的固有属性，任何时候都一样，可以直接讲",
                 "同靶点的产品适用范围一致，参照同类的讲就行",
                 "适用范围须以最新 NMPA 说明书与企业合规版本为准，不推断、不沿用其他产品",
                 "适用范围由医药代表按常见用法说明，这样医生更容易理解",
             ],
             "answer": 2,
             "explanation": "正确项是唯一有依据的做法。A 忽略了版本变化；"
                            "B 混淆了同靶点与同适用范围；C 把说明书限定的话术交给代表承担，"
                            "在合规审核中会被判为超范围表述。"},
        ],
        "recall": {
            "prompt": "合上页面，用三句话说清：被问「这药适用范围是什么」时，你按什么顺序回答。",
            "hint": "三句分别对应：先讲什么、怎么讲、怎么收。",
            "answer": f"先讲可核实的通用名 {gen} 与 {cu['mech']} 靶点；"
                      f"适用范围只给核查动作，即查最新 NMPA 说明书与企业合规版本；"
                      f"最后明确用药决策由医生判断，我不做推断、不沿用其他产品的范围。",
        },
        "sources": [
            {"label": skel["source"]["title"] or "信达生物 2026 中期报告产品及管线列表",
             "detail": f"source_id={skel['source']['source_id']}；"
                       f"mechanism_topic={prod.get('mechanism_topic')}；"
                       f"review_status={prod.get('review_status')}；asof_date={skel['source'].get('asof_date')}",
             "url": skel["source"]["url"]},
            {"label": "本产品知识库记录",
             "detail": f"表=med_products；product_id={pid}；brand={prod.get('brand')}；"
                       f"generic_name={gen}；domain={prod.get('domain')}",
             "url": skel["source"]["url"]},
            {"label": "适用范围核实路径（唯一依据）",
             "detail": "最新 NMPA 说明书 + 企业合规版本；本课不提供适应症、用法用量等需说明书支撑的内容",
             "url": skel["source"]["url"]},
        ],
    }
    with open(os.path.join(OUT, f"{pid}__PB.json"), "w", encoding="utf-8") as fh:
        json.dump(spec, fh, ensure_ascii=False, indent=2)
    print(f"✅ {pid}__PB 已写入")
