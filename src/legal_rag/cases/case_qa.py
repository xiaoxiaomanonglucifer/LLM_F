"""五步案件问答：事实抽取 → 行为定性 → 法条适用 → 裁量计算 → 结论。

确定性部分先给出可复核的数字与引用；大模型只负责在给定证据内组织语言，
不参与事实认定、条文选择或罚款计算。
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from typing import Any

from ..generation.prompts import build_case_messages
from ..retrieval.hybrid import HybridRetriever
from .extract import (
    _extract_area,
    _extract_behavior,
    _extract_land_use,
    _extract_project_nature,
)
from .retriever import CaseHit, CaseRetriever, hit_evidence
from .schema import DISCRETION_BRACKETS, article_links

CASE_GROUPS: dict[str, dict[str, Any]] = {
    "G0": {"law_signals": [], "cases": False, "case_graph": False, "curated": False},
    "G1": {"law_signals": ["dense", "bm25"], "cases": False, "case_graph": False, "curated": True},
    "G2": {
        "law_signals": ["dense", "bm25", "graph"],
        "cases": True,
        "case_graph": True,
        "curated": True,
    },
    "G2-case": {
        "law_signals": ["dense", "bm25", "graph"],
        "cases": False,
        "case_graph": False,
        "curated": True,
    },
    "G2-graph": {
        "law_signals": ["dense", "bm25"],
        "cases": True,
        "case_graph": True,
        "curated": True,
    },
}

CURATED_ARTICLES = [
    ("law-land-admin#a0002", "定性依据"),
    ("law-land-admin#a0044", "定性依据"),
    ("law-land-admin#a0077", "处罚依据"),
    ("reg-land-admin#a0057", "罚款幅度"),
    ("hn-land-admin-implementation#a0055", "湖南裁量幅度"),
]

SUBTYPE_ARTICLES = {
    "临时用地": ("law-land-admin#a0057", "临时用地审批"),
    "设施农用地": ("law-land-admin#a0037", "设施农用地管制"),
}

LAW_SUPPLEMENT_LIMIT = 3
SUPPLEMENT_KEYWORDS = ("未经批准", "责令退还", "罚款", "裁量基准", "超出批准", "超过批准")


def _fmt(value: float | None) -> str:
    if value is None:
        return "未知"
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _article_evidence(
    articles: dict[str, dict[str, Any]], article_id: str, role: str, source: str
) -> dict[str, Any] | None:
    record = articles.get(article_id)
    if not record:
        return None
    return {
        "article_id": article_id,
        "citation": record.get("citation", ""),
        "law_title": record.get("law_title", ""),
        "text": record.get("text", ""),
        "role": role,
        "source": source,
    }


def _dedupe_evidence(items: list[dict[str, Any]], limit: int = 10) -> list[dict[str, Any]]:
    seen: set[str] = set()
    kept: list[dict[str, Any]] = []
    for item in items:
        article_id = item.get("article_id")
        if not article_id or article_id in seen:
            continue
        seen.add(article_id)
        kept.append(item)
    return kept[:limit]


_TOTAL_AREA_RE = re.compile(
    r"(?:总面积|合计|共计|共占用|占用土地|占地总面积)[^。；\n\d]{0,6}?"
    r"([\d,]+(?:\.\d+)?)\s*(?:平方米|㎡|m2|m²)"
)


def _extract_total_area(text: str) -> float | None:
    match = _TOTAL_AREA_RE.search(text)
    return float(match.group(1).replace(",", "")) if match else None


def extract_question_facts(question: str) -> dict[str, Any]:
    land_use = _extract_land_use(question)
    explicit_total = _extract_total_area(question)
    area = explicit_total or _extract_area(question)
    if land_use and explicit_total is None and len(land_use) >= 2:
        area = round(sum(item["area_m2"] for item in land_use), 2)
    behavior = _extract_behavior(question)
    nature = _extract_project_nature(question)
    plan = "未知"
    if re.search(r"不符合[^。；\n]{0,12}(?:规划|土地利用总体规划)", question):
        plan = "不符合规划"
    elif re.search(r"符合[^。；\n]{0,12}(?:规划|土地利用总体规划)", question):
        plan = "符合规划"
    return {
        "area_m2": area,
        "land_use": land_use,
        "behavior": behavior,
        "project_nature": nature,
        "plan_conformity": plan,
        "source": "问题原文",
    }


def _characterize(
    facts: dict[str, Any], similar: list[CaseHit], use_law: bool = True
) -> dict[str, Any]:
    behaviors = list(facts["behavior"])
    inferred = False
    if not behaviors and similar:
        counts: Counter[str] = Counter()
        for hit in similar:
            for behavior in (hit.case or {}).get("behavior") or []:
                counts[behavior] += 1
        if counts:
            behaviors = [counts.most_common(1)[0][0]]
            inferred = True
    excluded = "未按批准用途使用土地" in behaviors and not any(
        item in behaviors for item in ("未经批准占用土地", "超过批准数量占用土地")
    )
    in_scope = any(
        item in behaviors for item in ("未经批准占用土地", "超过批准数量占用土地")
    )
    if excluded:
        status = "不属于非法占地（未按批准用途使用土地）"
        violated = []
    elif in_scope:
        status = "非法占用土地" if use_law else "疑似非法占用土地（未作条文定性）"
        violated = ["law-land-admin#a0002", "law-land-admin#a0044"] if use_law else []
    else:
        status = "待定"
        violated = []
    return {
        "behavior": behaviors,
        "behavior_inferred": inferred,
        "illegal_occupation": status,
        "violated_article_ids": violated,
        "scope_status": "excluded" if excluded else ("included" if in_scope else "unknown"),
        "law_basis_enabled": use_law,
    }


def _law_application(
    question: str,
    facts: dict[str, Any],
    characterization: dict[str, Any],
    articles: dict[str, dict[str, Any]],
    retriever: HybridRetriever | None,
    signals: list[str],
    similar: list[CaseHit],
    use_curated: bool,
    top_k: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    evidence: list[dict[str, Any]] = []
    if use_curated:
        for article_id, role in CURATED_ARTICLES:
            item = _article_evidence(articles, article_id, role, "法条链")
            if item:
                evidence.append(item)
        for behavior in characterization["behavior"]:
            if behavior in SUBTYPE_ARTICLES:
                article_id, role = SUBTYPE_ARTICLES[behavior]
                item = _article_evidence(articles, article_id, role, "法条链")
                if item:
                    evidence.append(item)
    retrieved_hits = []
    if retriever is not None and signals:
        query = " ".join(
            part
            for part in (
                question,
                "非法占用土地 行政处罚 罚款 裁量基准 湖南",
                " ".join(characterization["behavior"]),
                " ".join(item["type"] for item in facts["land_use"]),
            )
            if part
        )
        retrieved_hits = retriever.retrieve(query, signals, top_k=top_k)
        for hit in retrieved_hits[:LAW_SUPPLEMENT_LIMIT]:
            record = hit.record or {}
            if not any(keyword in record.get("text", "") for keyword in SUPPLEMENT_KEYWORDS):
                continue
            evidence.append(
                {
                    "article_id": hit.article_id,
                    "citation": record.get("citation", ""),
                    "law_title": record.get("law_title", ""),
                    "text": record.get("text", ""),
                    "role": "检索补充",
                    "source": "检索",
                    "score": round(hit.score, 6),
                }
            )
    for hit in similar:
        for link in article_links(hit.case or {}):
            record = articles.get(link["article_id"])
            if not record:
                continue
            evidence.append(
                {
                    "article_id": link["article_id"],
                    "citation": record.get("citation", ""),
                    "law_title": record.get("law_title", ""),
                    "text": record.get("text", ""),
                    "role": link.get("role") or "类案引用",
                    "source": "类案",
                    "case_id": hit.case_id,
                }
            )
    return _dedupe_evidence(evidence), [
        {
            "article_id": hit.article_id,
            "citation": (hit.record or {}).get("citation", ""),
            "score": round(hit.score, 6),
            "ranks": hit.ranks,
        }
        for hit in retrieved_hits
    ]


def _conduct_year(question: str) -> int | None:
    match = re.search(r"(?:19|20)\d{2}", question)
    return int(match.group(0)) if match else None


def _discretion(
    facts: dict[str, Any],
    similar: list[CaseHit],
    question: str,
    use_law: bool = True,
    scope_status: str = "included",
) -> dict[str, Any]:
    groups = list(dict.fromkeys(item["group"] for item in facts["land_use"]))
    area_by_group: dict[str, float] = {}
    for item in facts["land_use"]:
        area_by_group[item["group"]] = area_by_group.get(item["group"], 0.0) + item["area_m2"]
    if not area_by_group and facts.get("area_m2") and len(groups) == 1:
        area_by_group[groups[0]] = float(facts["area_m2"])

    nature = facts.get("project_nature")
    conduct_year = _conduct_year(question)
    current_standard = conduct_year is None or conduct_year >= 2022
    classified_area = round(sum(area_by_group.values()), 2)
    area_total = facts.get("area_m2")
    area_gap = (
        round(float(area_total) - classified_area, 2)
        if area_total and area_by_group
        else None
    )
    fully_classified = bool(area_by_group) and (
        area_gap is None or abs(area_gap) <= max(float(area_total) * 0.02, 0.01)
    )
    needs_land_type = bool(area_total) and not fully_classified
    applicable = use_law and scope_status == "included"
    if not applicable:
        return {
            "land_groups": groups,
            "area_by_group": area_by_group,
            "project_nature": nature,
            "brackets": [],
            "predicted_fine_range": None,
            "partial_fine_range": None,
            "calculation_complete": False,
            "similar_rates": [],
            "similar_fines": [],
            "version_note": "",
            "conduct_year": conduct_year,
            "current_standard_applied": False,
            "classified_area_m2": classified_area,
            "area_gap_m2": area_gap,
            "fully_classified": fully_classified,
            "needs_land_type": needs_land_type,
            "law_basis_enabled": use_law,
            "applicable": False,
            "inapplicable_reason": "no_law" if not use_law else scope_status,
        }

    nature_key = "public" if nature == "公益" else ("non_public" if nature == "非公益" else "statute")
    brackets = []
    predicted_low = 0.0
    predicted_high = 0.0
    complete = False
    if current_standard:
        for group in groups:
            lower, upper = DISCRETION_BRACKETS[group][nature_key]
            area = area_by_group.get(group)
            brackets.append(
                {
                    "land_group": group,
                    "area_m2": area,
                    "yuan_per_m2": [lower, upper],
                    "fine_range": [round(lower * area, 2), round(upper * area, 2)] if area else None,
                    "basis": "湘自资规〔2022〕1号" if nature_key != "statute" else "实施条例第57条 + 湖南办法第55条",
                }
            )
        predicted_low = sum(item["fine_range"][0] for item in brackets if item["fine_range"])
        predicted_high = sum(item["fine_range"][1] for item in brackets if item["fine_range"])
        complete = (
            bool(brackets)
            and all(item["fine_range"] for item in brackets)
            and fully_classified
        )
    partial_fine_range = (
        [round(predicted_low, 2), round(predicted_high, 2)]
        if brackets and all(item["fine_range"] for item in brackets) and not complete
        else None
    )

    similar_rates = [
        float(rate["yuan_per_m2"])
        for hit in similar
        for rate in (hit.case or {}).get("fine_rate") or []
        if rate.get("yuan_per_m2")
    ]
    similar_fines = [
        float(hit.case["fine_amount"])
        for hit in similar
        if (hit.case or {}).get("fine_amount")
    ]
    version_note = ""
    if conduct_year is not None and conduct_year <= 2019:
        version_note = (
            f"问题涉及{conduct_year}年的占地行为，行为时适用2004年土地管理法第76条、"
            "2014年实施条例第42条；现行法已改为第77条、第57条。"
            "本回答不套用现行罚款幅度，金额应按行为时标准核定。"
        )
    elif conduct_year in (2020, 2021):
        version_note = (
            f"问题涉及{conduct_year}年的占地行为，土地管理法适用2019年修正后的第77条；"
            "实施条例在2021年9月前仍为2014年版第42条，湖南省裁量标准应核对行为时版本"
            "（湘自然资规〔2019〕5号）。本回答不套用现行罚款幅度。"
        )
    return {
        "land_groups": groups,
        "area_by_group": area_by_group,
        "project_nature": nature,
        "brackets": brackets,
        "predicted_fine_range": [round(predicted_low, 2), round(predicted_high, 2)] if complete else None,
        "partial_fine_range": partial_fine_range,
        "calculation_complete": complete,
        "similar_rates": similar_rates,
        "similar_fines": similar_fines,
        "version_note": version_note,
        "conduct_year": conduct_year,
        "current_standard_applied": current_standard,
        "classified_area_m2": classified_area,
        "area_gap_m2": area_gap,
        "fully_classified": fully_classified,
        "needs_land_type": needs_land_type,
        "law_basis_enabled": True,
        "applicable": True,
        "inapplicable_reason": None,
    }


def _conclusion(
    characterization: dict[str, Any],
    facts: dict[str, Any],
    discretion: dict[str, Any],
    use_law: bool = True,
) -> dict[str, Any]:
    if not use_law:
        return {
            "penalty_types": [],
            "fine_range": None,
            "text": "本组未启用条文检索与裁量基准，无法依据现行法给出处罚种类和罚款幅度。",
        }
    if characterization["scope_status"] == "excluded":
        return {
            "penalty_types": [],
            "fine_range": None,
            "text": "该行为属于未按批准用途使用土地，不属于《土地管理法》第77条非法占地，"
            "应另按第81条等规定处理。",
        }
    if characterization["scope_status"] != "included":
        return {
            "penalty_types": [],
            "fine_range": None,
            "text": "现有事实不足以认定非法占用土地，需补充占地位置、地类、面积和审批情况。",
        }
    penalties = ["责令退还"]
    if facts.get("plan_conformity") == "符合规划":
        penalties.append("没收")
    elif facts.get("plan_conformity") == "不符合规划":
        penalties.append("限期拆除")
    else:
        penalties.append("没收或限期拆除（取决于是否符合国土空间规划）")
    penalties.append("罚款")
    fine_range = discretion.get("predicted_fine_range")
    if not discretion.get("current_standard_applied", True):
        text = (
            "应责令退还非法占用的土地，"
            + ("没收" if facts.get("plan_conformity") == "符合规划" else "没收或限期拆除")
            + "，并处罚款；罚款幅度应按行为时有效的裁量标准核定，不能直接套用现行标准。"
        )
    elif fine_range:
        text = (
            "应责令退还非法占用的土地，"
            + ("没收" if facts.get("plan_conformity") == "符合规划" else "没收或限期拆除")
            + f"，并处罚款；按已查明的面积和地类，罚款区间为 {_fmt(fine_range[0])}–{_fmt(fine_range[1])} 元。"
        )
    elif discretion.get("partial_fine_range"):
        partial = discretion["partial_fine_range"]
        text = (
            "应责令退还非法占用的土地，"
            + ("没收" if facts.get("plan_conformity") == "符合规划" else "没收或限期拆除")
            + f"，并处罚款；已查明地类部分为 {_fmt(partial[0])}–{_fmt(partial[1])} 元，"
            + f"但总面积中尚有 {_fmt(discretion.get('area_gap_m2'))}㎡ 地类未查明，"
            "罚款总额需补充调查后确定。"
        )
    else:
        text = "应责令退还非法占用的土地，并视规划符合情况没收或限期拆除，可以并处罚款；"
        text += "因问题未给出完整的地类面积，罚款金额暂不能精确计算。"
    return {"penalty_types": penalties, "fine_range": fine_range, "text": text}


def _render_answer(
    question: str,
    facts: dict[str, Any],
    characterization: dict[str, Any],
    discretion: dict[str, Any],
    conclusion: dict[str, Any],
    evidence: list[dict[str, Any]],
    similar: list[CaseHit],
    use_law: bool = True,
) -> str:
    if facts["land_use"]:
        land_text = "、".join(f"{item['type']} {_fmt(item['area_m2'])}㎡" for item in facts["land_use"])
    elif discretion["land_groups"]:
        land_text = "、".join(discretion["land_groups"])
    else:
        land_text = "地类未载明"
    lines = [
        "一、事实",
        f"占地行为：{'、'.join(facts['behavior']) or '未载明'}；面积：{_fmt(facts['area_m2'])}㎡；地类：{land_text}；"
        f"项目性质：{facts['project_nature']}；规划符合性：{facts['plan_conformity']}。",
        "",
        "二、行为定性",
    ]
    if characterization["scope_status"] == "included" and use_law:
        lines.append(
            "未经批准（或超过批准数量）占用土地，违反《土地管理法》第二条第三款、第四十四条第一款，"
            "属于非法占用土地。"
        )
    elif characterization["scope_status"] == "included":
        lines.append(
            "从事实看疑似未经批准（或超过批准数量）占用土地；本组未启用条文检索，不作条文定性。"
        )
    elif characterization["scope_status"] == "excluded":
        lines.append("属于未按批准用途使用土地，不属于非法占地。")
    else:
        lines.append("现有事实不足以完成定性，需要补充审批与地类信息。")
    if characterization["behavior_inferred"]:
        lines.append("（行为类型由相似案例推断，待原始材料确认。）")
    lines += ["", "三、法条适用"]
    for item in evidence[:6]:
        role = item.get("role") or ""
        lines.append(f"- {item['citation']}（{role}）：{item['text'][:120]}…")
    if not evidence:
        lines.append("- 本组未启用条文检索。")
    lines += ["", "四、裁量计算"]
    if not use_law:
        lines.append("- 本组未启用条文检索与裁量基准，未计算罚款区间。")
    elif discretion.get("inapplicable_reason") == "excluded":
        lines.append("- 该行为不属于非法占地，不适用第77条罚款幅度。")
    elif discretion.get("inapplicable_reason"):
        lines.append("- 现有事实尚不足以认定非法占地，未计算第77条罚款幅度。")
    elif not discretion.get("current_standard_applied", True):
        lines.append("- 行为发生在现行裁量标准生效前，本回答未套用现行罚款幅度。")
    elif discretion["brackets"]:
        for bracket in discretion["brackets"]:
            if bracket["fine_range"]:
                lines.append(
                    f"- {bracket['land_group']} {_fmt(bracket['area_m2'])}㎡ × "
                    f"{_fmt(bracket['yuan_per_m2'][0])}–{_fmt(bracket['yuan_per_m2'][1])} 元/㎡ = "
                    f"{_fmt(bracket['fine_range'][0])}–{_fmt(bracket['fine_range'][1])} 元。"
                )
            else:
                lines.append(f"- {bracket['land_group']}：面积缺失，无法计算金额。")
        if not discretion.get("fully_classified", True):
            lines.append(
                f"- 已查明地类面积 {_fmt(discretion.get('classified_area_m2'))}㎡，"
                f"总面积 {_fmt(facts.get('area_m2'))}㎡，差额 "
                f"{_fmt(discretion.get('area_gap_m2'))}㎡ 的地类待查，不能给出罚款总额区间。"
            )
    else:
        lines.append("- 未取得可计算的地类与面积。")
    if discretion["similar_rates"]:
        lines.append(
            f"- 类案适用费率：{_fmt(min(discretion['similar_rates']))}–"
            f"{_fmt(max(discretion['similar_rates']))} 元/㎡。"
        )
    if discretion["version_note"]:
        lines.append(f"- 版本提示：{discretion['version_note']}")
    lines += ["", "五、结论", conclusion["text"]]
    if similar:
        lines.append("")
        lines.append("参考类案：")
        for hit in similar[:3]:
            case = hit.case or {}
            lines.append(
                f"- {case.get('decision_no')}（{case.get('agency')}，{case.get('decision_date')}）："
                f"{'、'.join(case.get('behavior') or [])}，"
                f"罚款 {_fmt(case.get('fine_amount'))} 元。"
            )
    if any(item["role"] == "检索补充" for item in evidence):
        lines.append("")
        lines.append("注：条文检索结果仅作补充，正式适用前应核对现行有效版本。")
    return "\n".join(lines)


class CaseQASystem:
    def __init__(
        self,
        cfg: dict[str, Any],
        articles: dict[str, dict[str, Any]],
        case_retriever: CaseRetriever | None = None,
        case_graph=None,
        retriever: HybridRetriever | None = None,
        llm=None,
    ) -> None:
        self.cfg = cfg
        self.articles = articles
        self.case_retriever = case_retriever
        self.case_graph = case_graph
        self.retriever = retriever
        self.llm = llm

    def _similar_cases(
        self, question: str, spec: dict[str, Any], exclude_case_id: str | None
    ) -> list[CaseHit]:
        """直接检索占满名额；启用案件图谱时预留一个关联位，且关联案排在直接命中之后。"""
        top_k = int(self.cfg["retrieval"].get("case_top_k", 3))
        if not spec["cases"] or self.case_retriever is None:
            return []
        direct_k = top_k
        if spec["case_graph"] and self.case_graph is not None and top_k >= 2:
            direct_k = top_k - 1
        similar = self.case_retriever.search(
            question, top_k=direct_k, exclude_case_id=exclude_case_id
        )
        if not spec["case_graph"] or self.case_graph is None:
            return similar

        existing = {hit.case_id for hit in similar}
        graph_hits: list[CaseHit] = []
        for hit in similar:
            for rank, (case_id, score) in enumerate(
                self.case_graph.related_cases(hit.case_id, top_k=2), start=1
            ):
                if case_id in existing or case_id == exclude_case_id:
                    continue
                case = self.case_graph.cases.get(case_id)
                if case:
                    graph_hits.append(
                        CaseHit(case_id, 0.0, ["案件图谱关联"], {"graph": rank}, case)
                    )
                    existing.add(case_id)
        if graph_hits and similar:
            floor = min(hit.score for hit in similar)
            for hit in graph_hits:
                hit.score = round(floor * 0.5, 6)
        similar.extend(graph_hits[: max(0, top_k - len(similar))])

        if len(similar) < top_k:
            for hit in self.case_retriever.search(
                question, top_k=top_k, exclude_case_id=exclude_case_id
            ):
                if hit.case_id in existing:
                    continue
                similar.append(hit)
                existing.add(hit.case_id)
                if len(similar) >= top_k:
                    break
        return similar[:top_k]

    def analyze(
        self, question: str, group: str = "G2", exclude_case_id: str | None = None
    ) -> dict[str, Any]:
        if group not in CASE_GROUPS:
            raise ValueError(f"未知案件实验组：{group}")
        spec = CASE_GROUPS[group]
        use_law = bool(spec["law_signals"]) or bool(spec["curated"])
        facts = extract_question_facts(question)
        similar = self._similar_cases(question, spec, exclude_case_id)
        characterization = _characterize(facts, similar, use_law)
        evidence, retrieved = _law_application(
            question,
            facts,
            characterization,
            self.articles,
            self.retriever,
            spec["law_signals"],
            similar,
            spec["curated"],
            int(self.cfg["retrieval"]["top_k"]),
        )
        discretion = _discretion(
            facts, similar, question, use_law, characterization["scope_status"]
        )
        conclusion = _conclusion(characterization, facts, discretion, use_law)
        answer = _render_answer(
            question, facts, characterization, discretion, conclusion, evidence, similar, use_law
        )
        result = {
            "question": question,
            "group": group,
            "signals": spec,
            "law_basis_enabled": use_law,
            "steps": {
                "facts": facts,
                "characterization": characterization,
                "law_application": {"evidence": evidence, "retrieved": retrieved},
                "discretion": discretion,
                "conclusion": conclusion,
            },
            "similar_cases": [hit_evidence(hit) for hit in similar],
            "citations": [item["citation"] for item in evidence],
            "answer": answer,
            "confidence": self._confidence(facts, characterization, similar),
        }
        return result

    def answer(self, question: str, group: str = "G2", exclude_case_id: str | None = None) -> dict[str, Any]:
        result = self.analyze(question, group, exclude_case_id)
        if self.llm is not None:
            messages = build_case_messages(result)
            generation = self.llm.chat(messages)
            result["llm_answer"] = generation["text"]
            result["usage"] = generation.get("usage", {})
            result["latency_sec"] = generation.get("latency_sec")
            result["prompt_hash"] = hashlib.sha256(
                json.dumps(messages, ensure_ascii=False).encode("utf-8")
            ).hexdigest()[:16]
        return result

    @staticmethod
    def _confidence(
        facts: dict[str, Any], characterization: dict[str, Any], similar: list[CaseHit]
    ) -> str:
        has_core = bool(characterization["behavior"]) and bool(facts.get("area_m2")) and bool(
            facts.get("land_use")
        )
        if has_core and len(similar) >= 2:
            return "high"
        if characterization["behavior"] and (facts.get("area_m2") or facts.get("land_use")):
            return "medium"
        return "low"
