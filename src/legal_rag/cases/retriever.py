"""相似案例检索：结构化要素 + 案情词面，不读取罚款结果，避免答案泄漏。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..index.bm25 import Bm25Index
from .extract import _extract_area, _extract_behavior, _extract_land_use, _extract_project_nature
from .schema import case_area_by_group, case_land_groups, case_text


@dataclass
class CaseHit:
    case_id: str
    score: float
    reasons: list[str] = field(default_factory=list)
    ranks: dict[str, int] = field(default_factory=dict)
    case: dict[str, Any] | None = None

    @property
    def citation(self) -> str:
        return (self.case or {}).get("decision_no") or self.case_id


class CaseRetriever:
    def __init__(self, cases: list[dict[str, Any]]) -> None:
        self.cases = {
            case["case_id"]: case for case in cases if case.get("scope_status") == "included"
        }
        self.case_ids = sorted(self.cases)
        self.bm25 = Bm25Index.build(
            self.case_ids,
            [case_text(self.cases[case_id], include_outcome=False) for case_id in self.case_ids],
            use_char_bigram=True,
        )

    def _score_case(
        self,
        case: dict[str, Any],
        query_behaviors: set[str],
        query_land: set[str],
        query_nature: str,
        query_area: float | None,
        lexical: float,
    ) -> tuple[float, list[str]]:
        reasons: list[str] = []
        case_behaviors = set(case.get("behavior") or [])
        behavior_overlap = query_behaviors & case_behaviors
        behavior_score = len(behavior_overlap) / len(query_behaviors | case_behaviors) if query_behaviors else 0.0
        if behavior_overlap:
            reasons.append("行为相同：" + "、".join(sorted(behavior_overlap)))

        case_land = set(case_land_groups(case))
        land_overlap = query_land & case_land
        land_score = len(land_overlap) / len(query_land | case_land) if query_land else 0.0
        if land_overlap:
            reasons.append("土地类型相同：" + "、".join(sorted(land_overlap)))

        nature_score = 0.0
        if query_nature != "未知" and case.get("project_nature") not in (None, "未知"):
            nature_score = 1.0 if query_nature == case["project_nature"] else 0.0
            if nature_score:
                reasons.append(f"项目性质相同：{query_nature}")

        area_score = 0.0
        if query_area and case.get("area_m2"):
            denominator = max(query_area, float(case["area_m2"]))
            area_score = max(0.0, 1 - abs(query_area - float(case["area_m2"])) / denominator)
            if area_score >= 0.8:
                reasons.append("面积接近")

        score = (
            0.45 * lexical
            + 0.25 * behavior_score
            + 0.15 * land_score
            + 0.10 * nature_score
            + 0.05 * area_score
        )
        return score, reasons

    def search(
        self,
        query: str,
        top_k: int = 3,
        behaviors: list[str] | None = None,
        land_groups: list[str] | None = None,
        exclude_case_id: str | None = None,
    ) -> list[CaseHit]:
        query_behaviors = set(behaviors if behaviors is not None else _extract_behavior(query))
        query_land = set(
            land_groups
            if land_groups is not None
            else [item["group"] for item in _extract_land_use(query)]
        )
        query_nature = _extract_project_nature(query)
        query_area = _extract_area(query)
        lexical_hits = self.bm25.search(query, top_k=len(self.case_ids))
        lexical = {case_id: score for case_id, score in lexical_hits}
        best = max(lexical.values(), default=0.0)
        hits: list[CaseHit] = []
        for case_id, case in self.cases.items():
            if case_id == exclude_case_id:
                continue
            lex = lexical.get(case_id, 0.0) / best if best > 0 else 0.0
            score, reasons = self._score_case(
                case, query_behaviors, query_land, query_nature, query_area, lex
            )
            if score <= 0:
                continue
            ranks = {}
            if case_id in lexical:
                ranks["bm25"] = sorted(lexical, key=lambda key: lexical[key], reverse=True).index(case_id) + 1
            hits.append(CaseHit(case_id, score, reasons, ranks, case))
        hits.sort(key=lambda hit: (-hit.score, hit.case_id))
        return hits[:top_k]

    def similar(self, case_id: str, top_k: int = 3) -> list[CaseHit]:
        case = self.cases.get(case_id)
        if not case:
            return []
        return self.search(
            case_text(case, include_outcome=False),
            top_k=top_k,
            behaviors=case.get("behavior") or [],
            land_groups=case_land_groups(case),
            exclude_case_id=case_id,
        )

    def aggregate(self, hits: list[CaseHit]) -> dict[str, Any]:
        behavior_counts: dict[str, int] = {}
        land_counts: dict[str, int] = {}
        penalty_counts: dict[str, int] = {}
        rates: list[float] = []
        for hit in hits:
            case = hit.case or {}
            for item in case.get("behavior") or []:
                behavior_counts[item] = behavior_counts.get(item, 0) + 1
            for group in case_land_groups(case):
                land_counts[group] = land_counts.get(group, 0) + 1
            for item in case.get("penalty_types") or []:
                penalty_counts[item] = penalty_counts.get(item, 0) + 1
            for rate in case.get("fine_rate") or []:
                if rate.get("yuan_per_m2"):
                    rates.append(float(rate["yuan_per_m2"]))
        return {
            "behavior_counts": behavior_counts,
            "land_counts": land_counts,
            "penalty_counts": penalty_counts,
            "fine_rates": {
                "min": min(rates) if rates else None,
                "max": max(rates) if rates else None,
                "values": rates,
            },
            "groups": {
                hit.case_id: {
                    "area_by_group": case_area_by_group(hit.case or {}),
                    "fine_rate": (hit.case or {}).get("fine_rate"),
                }
                for hit in hits
            },
        }


def hit_evidence(hit: CaseHit) -> dict[str, Any]:
    case = hit.case or {}
    return {
        "case_id": hit.case_id,
        "decision_no": case.get("decision_no"),
        "agency": case.get("agency"),
        "decision_date": case.get("decision_date"),
        "behavior": case.get("behavior"),
        "land_use": case.get("land_use"),
        "area_m2": case.get("area_m2"),
        "project_nature": case.get("project_nature"),
        "penalty_types": case.get("penalty_types"),
        "fine_amount": case.get("fine_amount"),
        "fine_rate": case.get("fine_rate"),
        "score": round(hit.score, 4),
        "reasons": hit.reasons,
    }
