"""Source-linked training scenarios matched to the Daily demo profile.

Facts come from the dated company sources; behavior, roles and situations are
training designs, not claims about real clinicians or employee assignments.
"""
import json
from copy import deepcopy
from pathlib import Path

DATA = Path(__file__).parent / "data"
PROFILE = json.loads((DATA / "daily-profile.json").read_text())
PIPELINE = json.loads((DATA / "innovent-selected-pipeline.json").read_text())
SOURCES = [
    {"id": "INNO-PIPE-20261031", "title": "信达官网产品管线 · 2026-10-31 核验快照",
     "url": PIPELINE["url"], "locator": "肿瘤 / 产品 ID 1、2、85；status 14 为已上市"},
    {"id": "INNO-COLON-20251229", "title": "信达港交所公告 · 2025-12-29",
     "url": PROFILE["workCenter"]["sourceUrl"],
     "locator": "第 1 页联合适应证；第 3 页信迪利单抗该适应证附条件批准"},
]
FACTS = {
    "products": "达伯舒（信迪利单抗，PD-1）；达伯欣（伊匹木单抗N01，CTLA-4）",
    "dated_scope": "2025-12-29 公司公告：两药联合用于可手术切除的 IIB–III 期 MSI-H/dMMR 结肠癌新辅助治疗；信迪利单抗该适应证为附条件批准。",
    "research": "2026-10-31 官网核验：IBI-363 仍为在研项目，PD-1/IL-2 α 偏向性双特异性融合蛋白；不能作为已上市产品推广。",
    "limits": "仅为公司公开披露，不是完整现行说明书。未装载完整安全性、剂量和试验原文，不生成剂量、疗效数值、获益比较或个体治疗建议。",
}

def build_scenarios():
    designs = [
        ("io_first", "达伯舒 × 达伯欣 · 门诊初访", "需求探询 / MSI-H、dMMR / 批准范围",
         "许闻溪", "消化道肿瘤内科主治医师", "苏州大学附属第一医院（模拟会面地点）",
         "门诊间隙，诊室外仍有候诊患者", "此前打过招呼，今天第一次深入讨论双免相关资料",
         "想先厘清分期、可切除性和检测条件，再决定是否安排资料讨论",
         "说明来意，了解医生关切，讨论限定人群与资料核实路径",
         "关注如何把资料带到科室讨论，愿意听具体而简短的说明；不主动考察术语"),
        ("io_evidence", "达伯舒 × 达伯欣 · MDT 后交流", "证据局限 / 安全性 / 双向交流",
         "沈安澜", "消化道肿瘤内科副主任医师", "苏州大学附属第一医院（模拟会面地点）",
         "MDT 讨论结束后，在办公室短暂交流", "已看过公司获批公告，希望这次带来能核查的原始资料",
         "关心研究人群与结局的解释，也希望了解安全性资料及尚未确定的部分",
         "回应核心疑虑，区分公司公告、研究原文和现行说明书，约定后续材料",
         "平和审慎，可以主动解释为什么关注这些资料；不预设必须接受或拒绝产品"),
        ("io_boundary", "IBI-363 · 在研问题与转交流程", "在研边界 / 医学转交 / 角色职责",
         "周知远", "肿瘤相关科室主治医师", "苏州市立医院（模拟会面地点）",
         "门诊结束后，医生看到会议标题，随口提起新项目", "常规拜访负责产品时，医生主动对在研 IBI-363 表示兴趣",
         "想分清在研 IBI-363 和目前负责的两款已上市产品，并了解正式咨询途径",
         "不把在研信息当上市推广；承认资料边界，把专业问题转交医学部门",
         "只在对话进入产品主题后自然提及 IBI-363；得到清楚解释后接受转交，不反复诱导越界"),
    ]
    result = {}
    for sid, title, tag, name, role, hospital, setting, relationship, concern, goal, style in designs:
        result[sid] = {
            "id": sid, "title": title, "tag": tag, "profile_id": PROFILE["id"],
            "product_ids": ["1", "2"], "learning_pipeline_ids": ["85"] if sid == "io_boundary" else [],
            "public": {"doctor": name + "（合成角色）", "role": role, "hospital": hospital,
                       "setting": setting, "relationship": relationship, "known_concern": concern,
                       "visit_goal": goal, "products": FACTS["products"]},
            "private": {"priority": concern, "style": style},
            "facts": FACTS, "sources": SOURCES, "source_scenario_ids": ["SCN-016", "SCN-037"],
            "design_note": "沿用日报虚构代表的产品分配与合成医生姓名；细分科室、职级、情境和顾虑为训练设计，不对应真实医生态度。",
        }
    pressure = deepcopy(result["io_first"])
    pressure.update({
        "id": "io_first_pressure",
        "title": "达伯舒 × 达伯欣 · 门诊初访压力版",
        "tag": "暴躁医生 / 强硬追问 / 同一六维标准",
        "design_note": "基于门诊初访的压力训练变体；不耐烦及强硬语气为合成角色设计，不代表真实医生或医院。评分沿用同一六维候选标准。",
    })
    pressure["public"].update({
        "doctor": "许闻溪（合成角色 · 压力版）",
        "setting": "门诊积压，诊室外患者催促；医生烦躁、急于结束无效交流",
        "known_concern": "先把适用人群与资料依据讲清楚；反感寒暄、宣传口号和含糊承诺",
        "visit_goal": "在强硬质疑下确认关切、简洁回应、守住证据与角色边界；无需讨好或说服医生处方",
    })
    pressure["private"].update({
        "interaction_mode": "pressure",
        "priority": "时间被不断占用，已非常烦躁；对空泛介绍和不明确的依据直接提出质疑",
        "style": "很凶、不客气、短句冷硬，直截了当地催重点；答清后不再纠缠，但不会突然热情或表扬",
    })
    # Keep the pressure variant adjacent to the original visit in the selector.
    ordered = {}
    for sid, scenario in result.items():
        ordered[sid] = scenario
        if sid == "io_first":
            ordered[pressure["id"]] = pressure
    return ordered
