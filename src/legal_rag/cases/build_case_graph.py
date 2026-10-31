"""构建“案件—行为—法条—裁量—土地类型”离线图谱，并导出 Neo4j Cypher。

图谱使用与法规图谱相同的 JSONL 三元组思路：同一份数据既供离线检索，
也可直接导入 Neo4j。边只记录案件材料能支撑的事实，不写入推测值。
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from ..config import ensure_dir, load_settings
from .schema import article_links, case_land_groups, load_cases, validate_case

PRESCRIBES = {
    ("law-land-admin", 77): ["责令退还", "限期拆除", "没收", "罚款", "处分"],
    ("reg-land-admin", 57): ["罚款"],
    ("hn-land-admin-implementation", 55): ["罚款"],
}


def _node(node_id: str, node_type: str, label: str, **props: Any) -> dict[str, Any]:
    return {"id": node_id, "type": node_type, "label": label, "props": props}


def _edge(source: str, predicate: str, target: str, **props: Any) -> dict[str, Any]:
    return {"source": source, "predicate": predicate, "target": target, "props": props}


class CaseGraph:
    def __init__(self, cases: list[dict[str, Any]]) -> None:
        self.cases = {case["case_id"]: case for case in cases}
        self.nodes: dict[str, dict[str, Any]] = {}
        self.edges: list[dict[str, Any]] = []
        self.by_behavior: dict[str, set[str]] = defaultdict(set)
        self.by_article: dict[str, set[str]] = defaultdict(set)
        self.by_land_group: dict[str, set[str]] = defaultdict(set)
        self.by_penalty: dict[str, set[str]] = defaultdict(set)
        self.by_factor: dict[str, set[str]] = defaultdict(set)
        self._build()

    def _add_node(self, node: dict[str, Any]) -> None:
        self.nodes.setdefault(node["id"], node)

    def _add_edge(self, edge: dict[str, Any]) -> None:
        self.edges.append(edge)

    def _build(self) -> None:
        behavior_articles: dict[str, set[str]] = defaultdict(set)
        for case in self.cases.values():
            case_id = case["case_id"]
            case_node = f"case:{case_id}"
            self._add_node(
                _node(
                    case_node,
                    "Case",
                    case.get("decision_no") or case_id,
                    case_id=case_id,
                    region=case.get("region"),
                    agency=case.get("agency"),
                    decision_date=case.get("decision_date"),
                    scope_status=case.get("scope_status"),
                    area_m2=case.get("area_m2"),
                    fine_amount=case.get("fine_amount"),
                )
            )
            for behavior in case.get("behavior") or []:
                behavior_node = f"behavior:{behavior}"
                self._add_node(_node(behavior_node, "Behavior", behavior))
                self._add_edge(_edge(case_node, "ALLEGED_BEHAVIOR", behavior_node))
                self.by_behavior[behavior].add(case_id)
            for link in article_links(case):
                article_id = link["article_id"]
                article_node = f"article:{article_id}"
                self._add_node(
                    _node(
                        article_node,
                        "Article",
                        link.get("citation") or article_id,
                        article_id=article_id,
                        article_num=link.get("article_num"),
                        cited_article_num=link.get("cited_article_num"),
                        mapped_from_old_version=link.get("mapped_from_old_version", False),
                        role=link.get("role"),
                    )
                )
                predicate = "VIOLATES" if link["source"] == "violated" else "CITES_BASIS"
                self._add_edge(_edge(case_node, predicate, article_node))
                self.by_article[article_id].add(case_id)
                if link["source"] == "violated":
                    for behavior in case.get("behavior") or []:
                        behavior_articles[behavior].add(article_id)
                doc_id = article_id.split("#", 1)[0]
                for penalty in PRESCRIBES.get((doc_id, int(link["article_num"])), []):
                    penalty_node = f"penalty:{penalty}"
                    self._add_node(_node(penalty_node, "PenaltyType", penalty))
                    self._add_edge(_edge(article_node, "PRESCRIBES", penalty_node))
            for group in case_land_groups(case):
                land_node = f"land:{group}"
                self._add_node(_node(land_node, "LandType", group))
                areas = [
                    item["area_m2"]
                    for item in case.get("land_use") or []
                    if item["group"] == group
                ]
                self._add_edge(
                    _edge(
                        case_node,
                        "HAS_LAND_TYPE",
                        land_node,
                        area_m2=round(sum(areas), 2) if areas else None,
                    )
                )
                self.by_land_group[group].add(case_id)
            for penalty in case.get("penalty_types") or []:
                penalty_node = f"penalty:{penalty}"
                self._add_node(_node(penalty_node, "PenaltyType", penalty))
                self._add_edge(
                    _edge(
                        case_node,
                        "SANCTIONED_WITH",
                        penalty_node,
                        fine_amount=case.get("fine_amount") if penalty == "罚款" else None,
                    )
                )
                self.by_penalty[penalty].add(case_id)
            for factor in case.get("factors") or []:
                factor_node = f"factor:{factor}"
                self._add_node(_node(factor_node, "Factor", factor))
                self._add_edge(_edge(case_node, "HAS_FACTOR", factor_node))
                self.by_factor[factor].add(case_id)
        for behavior, article_ids in behavior_articles.items():
            behavior_node = f"behavior:{behavior}"
            for article_id in sorted(article_ids):
                self._add_edge(_edge(behavior_node, "VIOLATES", f"article:{article_id}"))

    @property
    def case_count(self) -> int:
        return len(self.cases)

    def neighbors(self, case_id: str, predicate: str | None = None) -> list[dict[str, Any]]:
        node_id = f"case:{case_id}"
        return [
            edge
            for edge in self.edges
            if edge["source"] == node_id and (predicate is None or edge["predicate"] == predicate)
        ]

    def related_cases(self, case_id: str, top_k: int = 5) -> list[tuple[str, int]]:
        case = self.cases.get(case_id)
        if not case:
            return []
        my_behavior = set(case.get("behavior") or [])
        my_land = set(case_land_groups(case))
        my_articles = {link["article_id"] for link in article_links(case)}
        scores: Counter[str] = Counter()
        for other_id, other in self.cases.items():
            if other_id == case_id:
                continue
            score = 0
            score += 3 * len(my_behavior & set(other.get("behavior") or []))
            score += 2 * len(my_land & set(case_land_groups(other)))
            score += len(my_articles & {link["article_id"] for link in article_links(other)})
            if score:
                scores[other_id] = score
        return scores.most_common(top_k)

    def subgraph(self, case_ids: list[str]) -> dict[str, Any]:
        allowed_nodes = set()
        edges = []
        for case_id in case_ids:
            node_id = f"case:{case_id}"
            allowed_nodes.add(node_id)
            for edge in self.edges:
                if edge["source"] == node_id:
                    edges.append(edge)
                    allowed_nodes.add(edge["target"])
        return {
            "nodes": [self.nodes[node_id] for node_id in sorted(allowed_nodes) if node_id in self.nodes],
            "edges": edges,
        }

    def stats(self) -> dict[str, Any]:
        return {
            "cases": self.case_count,
            "nodes": len(self.nodes),
            "edges": len(self.edges),
            "by_behavior": {key: len(value) for key, value in sorted(self.by_behavior.items())},
            "by_land_group": {key: len(value) for key, value in sorted(self.by_land_group.items())},
            "by_penalty": {key: len(value) for key, value in sorted(self.by_penalty.items())},
            "articles": len(self.by_article),
        }


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _cypher_value(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return json.dumps(value)
    return json.dumps(str(value), ensure_ascii=False)


def export_cypher(graph: CaseGraph, path: Path) -> None:
    lines = ["// 湖南非法占地案例图谱（自动生成）", "CREATE CONSTRAINT case_id IF NOT EXISTS FOR (n:Case) REQUIRE n.id IS UNIQUE;", ""]
    for node in graph.nodes.values():
        props = {"id": node["id"], "label": node["label"], **node["props"]}
        assignments = ", ".join(f"{key}: {_cypher_value(value)}" for key, value in props.items())
        lines.append(f"MERGE (n:{node['type']} {{id: {_cypher_value(node['id'])}}}) SET n += {{{assignments}}};")
    lines.append("")
    for edge in graph.edges:
        props = {"source": edge["source"], **edge["props"]}
        assignments = ", ".join(f"{key}: {_cypher_value(value)}" for key, value in props.items())
        lines.append(
            f"MATCH (a {{id: {_cypher_value(edge['source'])}}}), (b {{id: {_cypher_value(edge['target'])}}}) "
            f"MERGE (a)-[r:{edge['predicate']}]->(b) SET r += {{{assignments}}};"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build(cases_path: Path | None = None, out_dir: Path | None = None) -> Path:
    cfg = load_settings()
    cases_path = Path(cases_path or Path(cfg["paths"]["cases_dir"]) / "cases.jsonl")
    out_dir = ensure_dir(Path(out_dir or Path(cfg["paths"]["cases_dir"]) / "graph"))
    cases = load_cases(cases_path)
    issues = {case["case_id"]: validate_case(case) for case in cases}
    graph = CaseGraph(cases)
    nodes = sorted(graph.nodes.values(), key=lambda node: (node["type"], node["id"]))
    edges = sorted(graph.edges, key=lambda edge: (edge["source"], edge["predicate"], edge["target"]))
    _write_jsonl(out_dir / "nodes.jsonl", nodes)
    _write_jsonl(out_dir / "edges.jsonl", edges)
    triples = [
        {
            "case_id": edge["source"].split(":", 1)[1] if edge["source"].startswith("case:") else None,
            "subject": edge["source"],
            "predicate": edge["predicate"],
            "object": edge["target"],
            "properties": edge["props"],
        }
        for edge in edges
    ]
    _write_jsonl(out_dir / "case_triples.jsonl", triples)
    export_cypher(graph, out_dir / "neo4j.cypher")
    stats = graph.stats()
    stats["validation"] = {
        "cases_with_issues": {case_id: items for case_id, items in issues.items() if items},
        "clean_cases": sum(not items for items in issues.values()),
    }
    (out_dir / "stats.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"案例图谱：{graph.case_count} 案，{len(nodes)} 节点，{len(edges)} 边 -> {out_dir}")
    return out_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="构建湖南非法占地案例图谱")
    parser.add_argument("--cases", default=None)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()
    build(
        Path(args.cases) if args.cases else None,
        Path(args.out) if args.out else None,
    )


if __name__ == "__main__":
    main()
