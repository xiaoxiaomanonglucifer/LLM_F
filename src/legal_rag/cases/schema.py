"""湖南非法占地案例的结构约定、校验与派生视图。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

BEHAVIORS = [
    "未经批准占用土地",
    "超过批准数量占用土地",
    "临时用地",
    "设施农用地",
    "未按批准用途使用土地",
]

LAND_GROUPS = ["永久基本农田", "其他耕地", "其他土地"]

REQUIRED_FIELDS = [
    "case_id",
    "decision_no",
    "decision_date",
    "agency",
    "party",
    "behavior",
    "scope_status",
    "facts",
    "land_use",
    "area_m2",
    "violated_articles",
    "penalty_basis_articles",
    "penalty_types",
    "fine_amount",
    "fine_rate",
]

ARTICLE_ROLES = {
    ("law-land-admin", 2): "定性依据",
    ("law-land-admin", 44): "定性依据",
    ("law-land-admin", 77): "处罚依据",
    ("reg-land-admin", 57): "罚款幅度",
    ("hn-land-admin-implementation", 55): "湖南裁量幅度",
    ("law-admin-penalty", 37): "从旧兼从轻",
}

# 湘自资规〔2022〕1号公开解读中的裁量档（元/平方米）
DISCRETION_BRACKETS = {
    "永久基本农田": {
        "statute": (500.0, 1000.0),
        "public": (500.0, 600.0),
        "non_public": (600.0, 1000.0),
    },
    "其他耕地": {
        "statute": (300.0, 500.0),
        "public": (300.0, 400.0),
        "non_public": (400.0, 500.0),
    },
    "其他土地": {
        "statute": (100.0, 300.0),
        "public": (100.0, 200.0),
        "non_public": (200.0, 300.0),
    },
}


def load_cases(path: Path) -> list[dict[str, Any]]:
    with Path(path).open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def land_group(land_type: str) -> str:
    if "永久基本农田" in land_type or land_type == "基本农田":
        return "永久基本农田"
    if land_type in {"水田", "旱地", "水浇地", "一般耕地", "耕地"}:
        return "其他耕地"
    return "其他土地"


def case_land_groups(case: dict[str, Any]) -> list[str]:
    groups = {item["group"] for item in case.get("land_use") or []}
    if not groups:
        groups = {
            rate.get("group") for rate in case.get("fine_rate") or [] if rate.get("group") not in (None, "未知")
        }
    return [group for group in LAND_GROUPS if group in groups]


def case_area_by_group(case: dict[str, Any]) -> dict[str, float]:
    totals: dict[str, float] = {}
    for item in case.get("land_use") or []:
        totals[item["group"]] = totals.get(item["group"], 0.0) + float(item["area_m2"])
    if totals:
        return totals
    for rate in case.get("fine_rate") or []:
        group = rate.get("group")
        if group in LAND_GROUPS and rate.get("area_m2"):
            totals[group] = totals.get(group, 0.0) + float(rate["area_m2"])
    return totals


def article_links(case: dict[str, Any]) -> list[dict[str, Any]]:
    links: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for source, items in (
        ("violated", case.get("violated_articles") or []),
        ("basis", case.get("penalty_basis_articles") or []),
    ):
        for item in items:
            if not item.get("resolved") or not item.get("article_id"):
                continue
            key = (source, item["article_id"])
            if key in seen:
                continue
            seen.add(key)
            doc_id = item["article_id"].split("#", 1)[0]
            role = ARTICLE_ROLES.get((doc_id, int(item["article_num"])))
            links.append(
                {
                    "source": source,
                    "article_id": item["article_id"],
                    "citation": item.get("citation"),
                    "article_num": item.get("article_num"),
                    "cited_article_num": item.get("cited_article_num"),
                    "mapped_from_old_version": item.get("mapped_from_old_version", False),
                    "role": role or ("定性依据" if source == "violated" else "处罚依据"),
                }
            )
    return links


def case_text(case: dict[str, Any], include_outcome: bool = False) -> str:
    parts = [
        " ".join(case.get("behavior") or []),
        case.get("facts") or "",
        f"面积{case['area_m2']}平方米" if case.get("area_m2") else "",
        "、".join(f"{item['type']}{item['area_m2']}平方米" for item in case.get("land_use") or []),
        f"项目性质{case['project_nature']}" if case.get("project_nature") not in (None, "未知") else "",
    ]
    if include_outcome:
        parts.extend(
            [
                "、".join(case.get("penalty_types") or []),
                f"罚款{case['fine_amount']}元" if case.get("fine_amount") else "",
            ]
        )
    return " ".join(part for part in parts if part)


def validate_case(case: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    for field in REQUIRED_FIELDS:
        if field not in case or case[field] in (None, "", []):
            if field in {"party"} and case.get("scope_status") == "excluded":
                continue
            issues.append(f"missing:{field}")
    if case.get("scope_status") not in {"included", "excluded"}:
        issues.append("bad_scope_status")
    if not any(item in BEHAVIORS for item in case.get("behavior") or []):
        issues.append("unknown_behavior")
    if case.get("scope_status") == "included":
        for source in ("violated_articles", "penalty_basis_articles"):
            items = case.get(source) or []
            if not items:
                issues.append(f"missing:{source}")
            if any(not item.get("resolved") for item in items):
                issues.append(f"unresolved:{source}")
    area = case.get("area_m2")
    land_sum = sum(float(item["area_m2"]) for item in case.get("land_use") or [])
    if area and land_sum and abs(land_sum - area) / area > 0.02:
        issues.append(f"land_sum:{land_sum:.2f}!={area:.2f}")
    fine = case.get("fine_amount")
    rates = case.get("fine_rate") or []
    if fine and rates:
        product = sum(
            float(item["yuan_per_m2"]) * float(item.get("area_m2") or 0)
            for item in rates
            if item.get("area_m2")
        )
        if product and abs(product - fine) / fine > 0.02:
            issues.append(f"fine_product:{product:.2f}!={fine:.2f}")
    return issues


def summarize_cases(cases: list[dict[str, Any]]) -> dict[str, Any]:
    issue_counts: dict[str, int] = {}
    for case in cases:
        for issue in validate_case(case):
            issue_counts[issue] = issue_counts.get(issue, 0) + 1
    return {
        "total": len(cases),
        "included": sum(case.get("scope_status") == "included" for case in cases),
        "issue_counts": issue_counts,
    }
