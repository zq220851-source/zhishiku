"""API-based behavior review with local quote and provenance validation.

No local model or rule-based dimension ratings are used. Product factual accuracy
remains NA until current approved labeling and medical review are available.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from remote_provider import RemoteDoctorProvider, RemoteAPIError

ROOT = Path(__file__).resolve().parents[1]
SCORECARD = json.loads((ROOT / "scorecards/medrep-dialogue-v0.1.json").read_text(encoding="utf-8"))
EVIDENCE = json.loads((ROOT / ".agents/skills/medrep-dialogue-scorecard/references/evidence-index.json").read_text(encoding="utf-8"))["records"]


def suspected_flags(transcript: list[dict]) -> list[dict]:
    """Queue only obvious phrases for human review; never convict automatically."""
    flags = []
    for i, item in enumerate(transcript):
        if item.get("role") != "药代":
            continue
        text = item.get("text", "")
        claim = re.search(r"(我(?:给|安排|提供).{0,8}(回扣|红包|礼品)|保证.*(处方|疗效)|所有患者.*(适用|有效)|绝对(?:安全|有效))", text)
        refused = re.search(r"(不能|不得|不应|不可以|不保证|不提供|不安排|不等于)", text)
        if claim and not refused:
            flags.append({"turn_index": i, "quote": text[:220],
                          "status": "待人工合规复核",
                          "source_ids": ["CN24-7", "INNO-MKT-411", "INNO-ETH-42"]})
    return flags


def assess_with_api(transcript: list[dict], scenario_id: str, scenario_facts: dict | None = None) -> dict:
    """Ask an external model for behavior ratings, then verify every quote locally."""
    provider = RemoteDoctorProvider()
    compact_rubric = [{k: d[k] for k in ("id", "name", "trigger", "anchors", "design_note")}
                      for d in SCORECARD["dimensions"]]
    numbered = [{"turn_index": i, "role": m["role"], "text": m["text"]}
                for i, m in enumerate(transcript)]
    system = (
        "你是医药代表模拟拜访的培训评审助手。只根据给定逐字稿和行为锚点评价"
        "药代可观察的行为，不能凭印象推断。输出严格 JSON，不要 Markdown。"
        "每个维度给 0、1、2 或 NA；情境没触发则 NA。"
        "每个非 NA 维度必须提供药代发言的原文连续子串 quote 和对应 turn_index。"
        "why 用一句中文说明判定；不引用逐字稿之外的事实。"
        "D4 医学与产品准确性必须为 NA，因为未提供现行获批说明书和医学审核。"
        "不要输出总分、权重或及格线；合规疑点只能提示人工复核，不作最终认定。"
        "返回结构：{\"ratings\":[{\"id\":\"D1\",\"rating\":1,\"why\":\"...\",\"quote\":\"...\",\"turn_index\":1},...]}，六维各一条。"
    )
    user = "评分标准：\n" + json.dumps(compact_rubric, ensure_ascii=False) + "\n逐字稿：\n" + json.dumps(numbered, ensure_ascii=False)
    user += "\n有来源的情境背景（不是医学审核依据，D4仍须NA）：\n" + json.dumps(scenario_facts or {}, ensure_ascii=False)
    if any(m["role"] == "药代" for m in transcript):
        raw = provider.chat(system, user, max_tokens=6000, temperature=0.1)
    else:
        raw = json.dumps({"ratings": [{"id": d["id"], "rating": "NA", "why": "本次没有已提交的药代发言，无法评分。"} for d in SCORECARD["dimensions"]]})
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        raise RemoteAPIError("评分 API 未返回 JSON，请重试评分")
    try:
        data = json.loads(raw[start:end + 1])
    except json.JSONDecodeError as exc:
        raise RemoteAPIError("评分 API 返回的 JSON 无法解析，请重试评分") from exc
    ratings = data.get("ratings")
    if not isinstance(ratings, list) or len(ratings) != 6:
        raise RemoteAPIError("评分 API 未完整返回六个维度，请重试评分")
    by_id = {r.get("id"): r for r in ratings if isinstance(r, dict)}
    if len(by_id) != 6:
        raise RemoteAPIError("评分 API 维度不完整或重复，请重试评分")
    dimensions = []
    for dim in SCORECARD["dimensions"]:
        did = dim["id"]
        if did not in by_id:
            raise RemoteAPIError(f"评分 API 缺少 {did}，请重试评分")
        item = by_id[did]
        rating = item.get("rating", "NA")
        if rating in ("0", "1", "2"):
            rating = int(rating)
        if rating not in (0, 1, 2, "NA"):
            rating = "NA"
        why = str(item.get("why", ""))[:240]
        spans = []
        if did == "D4":
            rating = "NA"
            why = "缺少对应产品现行中国批准说明书及医学审核，具体医学/产品事实不能自动判对错。"
        elif rating != "NA":
            quote = str(item.get("quote", "")).strip()
            try:
                index = int(item.get("turn_index"))
            except (TypeError, ValueError):
                index = -1
            if not quote or index < 0 or index >= len(transcript) or transcript[index]["role"] != "药代" or quote not in transcript[index]["text"]:
                rating = "NA"
                why = "模型引用的药代原话无法在逐字稿定位，本维度已转待复核。"
            else:
                spans = [{"turn_index": index, "quote": quote}]
        source_ids = dim["source_ids"]
        dimensions.append({
            "id": did, "name": dim["name"], "domain": dim["domain"],
            "rating": rating, "why": why, "transcript_spans": spans,
            "anchors": dim["anchors"], "trigger": dim["trigger"],
            "source_ids": source_ids,
            "sources": [{"id": sid, "title": EVIDENCE.get(sid, {}).get("title", sid),
                         "locator": EVIDENCE.get(sid, {}).get("locator", ""),
                         "url": EVIDENCE.get(sid, {}).get("url", "")}
                        for sid in source_ids],
            "review_status": "api_suggestion_pending_human_review",
        })
    rated = sum(d["rating"] != "NA" for d in dimensions)
    return {
        "scenario_id": scenario_id,
        "scorecard_id": SCORECARD["id"],
        "scorecard_status": SCORECARD["status"],
        "official_innovent_scorecard": False,
        "method": "远程模型按六维锚点给出行为初评；引用须逐字匹配药代发言。医学事实和合规结论待人工审核。",
        "dimensions": dimensions,
        "coverage": {"rated": rated, "total": len(dimensions)},
        "hard_gate_review": suspected_flags(transcript),
        "overall_score": None,
        "note": "不设总分、权重或及格线。修改转写后可重算。",
    }
