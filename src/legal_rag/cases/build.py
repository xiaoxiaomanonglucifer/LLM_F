"""采集湖南处罚决定书/台账并构建 data/cases/v1/cases.jsonl。"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import REPO_ROOT, ensure_dir, load_settings, load_yaml
from .extract import build_resolver, parse_decision, parse_ledger, sanitize_case
from .fetch import fetch_url
from .html_parse import find_table, parse_html

BUILDER_VERSION = "1.0"


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _write_json(path: Path, data: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _rel(path: str | Path) -> str:
    return Path(path).resolve().relative_to(REPO_ROOT).as_posix()


def build(
    only: list[str] | None = None,
    min_cases: int = 10,
) -> dict[str, Any]:
    cfg = load_settings()
    paths = cfg["paths"]
    cases_dir = ensure_dir(Path(paths["cases_dir"]))
    raw_dir = ensure_dir(cases_dir / "raw")
    catalog = load_yaml(Path(paths["case_catalog_file"]))
    resolver = build_resolver()

    sources = catalog.get("sources", [])
    if only:
        wanted = set(only)
        sources = [s for s in sources if s["id"] in wanted]
        unknown = wanted - {s["id"] for s in sources}
        if unknown:
            raise SystemExit(f"--only 中有未知来源: {sorted(unknown)}")

    cases: list[dict[str, Any]] = []
    source_records: list[dict[str, Any]] = []
    duplicates: list[str] = []
    seen: set[str] = set()

    for source in sources:
        if not source.get("enabled", True):
            continue
        print(f"[采集] {source['id']} {source['url']}")
        try:
            fetched = fetch_url(source["url"])
            text, tables = parse_html(fetched["html"])
            meta = {
                **source,
                "collected_at": _now(),
                "source_sha256": fetched["sha256"],
                "final_url": fetched["final_url"],
                "encoding": fetched["encoding"],
            }
            if source["kind"] == "ledger":
                table = find_table(tables, ("行政处罚决定文书号", "违法事实"))
                if table is None:
                    raise RuntimeError("未找到含“行政处罚决定文书号/违法事实”的台账表格")
                parsed_cases = parse_ledger(table, meta, resolver)
            elif source["kind"] == "decision":
                parsed_cases = [parse_decision(text, meta, resolver)]
            else:
                raise RuntimeError(f"未知来源类型：{source['kind']}")
        except Exception as exc:  # 单个来源失败不阻断其他来源
            print(f"  失败：{exc}")
            source_records.append(
                {"id": source["id"], "url": source["url"], "status": "error", "error": str(exc)}
            )
            continue

        kept = 0
        for case in parsed_cases:
            sanitize_case(case)
            case_id = case["case_id"]
            if case_id in seen:
                duplicates.append(case_id)
                continue
            seen.add(case_id)
            text_path = raw_dir / f"{case_id}.txt"
            text_path.write_text(case["text"], encoding="utf-8")
            case["text_path"] = text_path.relative_to(REPO_ROOT).as_posix()
            case["text_sha256"] = _sha256(case["text"])
            case["text_chars"] = len(case["text"])
            case.pop("text", None)
            cases.append(case)
            kept += 1

        source_records.append(
            {
                "id": source["id"],
                "kind": source["kind"],
                "url": source["url"],
                "final_url": fetched["final_url"],
                "status": "ok",
                "http_status": fetched["status_code"],
                "encoding": fetched["encoding"],
                "source_sha256": fetched["sha256"],
                "cases": kept,
                "expected_cases": source.get("expected_cases"),
            }
        )
        print(f"  入库 {kept} 例")

    cases.sort(key=lambda c: (c.get("decision_date") or "", c["case_id"]))
    cases_path = cases_dir / "cases.jsonl"
    with cases_path.open("w", encoding="utf-8") as fh:
        for case in cases:
            fh.write(json.dumps(case, ensure_ascii=False) + "\n")

    included = [c for c in cases if c.get("scope_status") == "included"]
    excluded = [c for c in cases if c.get("scope_status") != "included"]
    warning_counts: Counter[str] = Counter()
    for case in cases:
        for warning in case.get("warnings") or []:
            warning_counts[warning.split("_vs_")[0]] += 1

    stats = {
        "generated_at": _now(),
        "cases_total": len(cases),
        "included": len(included),
        "excluded": len(excluded),
        "duplicates": len(duplicates),
        "by_region": dict(sorted(Counter(c.get("region") or "未知" for c in included).items())),
        "by_year": dict(sorted(Counter((c.get("decision_date") or "未知")[:4] for c in included).items())),
        "by_behavior": dict(
            sorted(Counter(b for c in included for b in c.get("behavior") or []).items())
        ),
        "by_project_nature": dict(sorted(Counter(c.get("project_nature") or "未知" for c in included).items())),
        "missing_fine": sum(1 for c in included if not c.get("fine_amount")),
        "missing_area": sum(1 for c in included if not c.get("area_m2")),
        "missing_violated_articles": sum(1 for c in included if not c.get("violated_articles")),
        "missing_basis_articles": sum(1 for c in included if not c.get("penalty_basis_articles")),
        "warning_counts": dict(warning_counts.most_common()),
    }
    manifest = {
        "version": catalog.get("version", "v1"),
        "as_of": catalog.get("as_of"),
        "generated_at": _now(),
        "builder_version": BUILDER_VERSION,
        "catalog_file": _rel(paths["case_catalog_file"]),
        "articles_file": _rel(paths["articles_file"]),
        "sources": source_records,
        "duplicates": duplicates,
        "stats": stats,
    }
    _write_json(cases_dir / "manifest.json", manifest)
    _write_json(cases_dir / "stats.json", stats)

    print(
        f"\n案例构建完成：总 {stats['cases_total']}，纳入 {stats['included']}，"
        f"排除 {stats['excluded']}，重复 {stats['duplicates']}；"
        f"缺金额 {stats['missing_fine']}，缺面积 {stats['missing_area']}，"
        f"缺违反条款 {stats['missing_violated_articles']}，缺处罚依据 {stats['missing_basis_articles']}"
    )
    print(f"cases   : {cases_path}")
    print(f"manifest: {cases_dir / 'manifest.json'}")

    if len(included) < min_cases:
        raise SystemExit(f"纳入案例只有 {len(included)} 件，低于最低要求 {min_cases} 件")
    return manifest


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="采集湖南非法占地行政处罚案例")
    parser.add_argument("--only", nargs="*", help="只采集指定来源 id")
    parser.add_argument("--min-cases", type=int, default=10)
    args = parser.parse_args()
    build(only=args.only, min_cases=args.min_cases)
