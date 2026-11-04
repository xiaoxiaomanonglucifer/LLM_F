"""校验图谱 Cypher 与 triples.jsonl 一致，可选校验已导入的 Neo4j。

用法：
  python scripts/verify_graph_export.py \
    --triples data/v1/graph/triples.jsonl \
    --cypher data/v1/graph/neo4j_import.cypher

  # 校验嵌入式 / 在线 Neo4j 的计数（原样导入 JSON 或本脚本留档 JSON 均可）
  python scripts/verify_graph_export.py ... --db-counts logs/neo4j_import_v1.json

  NEO4J_PASSWORD=... python scripts/verify_graph_export.py ... \
    --neo4j-uri bolt://127.0.0.1:7687 --neo4j-user neo4j

退出码 0 表示全部通过；1 表示存在不一致。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

STRING = r"'((?:\\.|[^'\\])*)'"
ARTICLE_RE = re.compile(r"MERGE \(a:Article \{article_id: " + STRING + r"\}\)")
SUBJECT_RE = re.compile(r"MERGE \(s:Subject \{name: " + STRING + r"\}\)")
ACTION_RE = re.compile(r"MERGE \(x:Action \{name: " + STRING + r"\}\)")
PENALTY_RE = re.compile(r"MERGE \(p:Penalty \{name: " + STRING + r"\}\)")
CITATION_RE = re.compile(r"MERGE \(a:Article \{article_id: " + STRING + r"\}\) SET a\.citation")
RELATED_ENDPOINT_RE = re.compile(
    r"MATCH \(a:Article \{article_id: " + STRING + r"\}\), "
    r"\(b:Article \{article_id: " + STRING + r"\}\)"
)
REL_COUNTS = ("APPLIES_TO", "REGULATES", "PENALTY", "RELATED_TO")


def cypher_unescape(text: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(text):
        if text[i] == "\\" and i + 1 < len(text):
            nxt = text[i + 1]
            mapped = {"n": "\n", "r": "\r", "t": "\t", "'": "'", "\\": "\\"}.get(nxt)
            if mapped is not None:
                out.append(mapped)
                i += 2
                continue
        out.append(text[i])
        i += 1
    return "".join(out)


def load_triples(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def load_counts(path: Path | None, uri: str | None, user: str, password: str | None) -> dict[str, int] | None:
    if path is not None:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data.get("counts"), dict):
            return data["counts"]
        if isinstance(data.get("db_counts"), dict):
            return data["db_counts"]
        return data
    if not uri:
        return None
    try:
        from neo4j import GraphDatabase
    except ImportError as exc:
        raise SystemExit("未安装 neo4j 驱动：pip install neo4j") from exc
    if not password:
        raise SystemExit("在线校验需要环境变量 NEO4J_PASSWORD")
    queries = {
        "nodes_Article": "MATCH (n:Article) RETURN count(n) AS c",
        "nodes_Subject": "MATCH (n:Subject) RETURN count(n) AS c",
        "nodes_Action": "MATCH (n:Action) RETURN count(n) AS c",
        "nodes_Penalty": "MATCH (n:Penalty) RETURN count(n) AS c",
        "nodes_total": "MATCH (n) RETURN count(n) AS c",
        "rel_APPLIES_TO": "MATCH ()-[r:APPLIES_TO]->() RETURN count(r) AS c",
        "rel_REGULATES": "MATCH ()-[r:REGULATES]->() RETURN count(r) AS c",
        "rel_PENALTY": "MATCH ()-[r:PENALTY]->() RETURN count(r) AS c",
        "rel_RELATED_TO": "MATCH ()-[r:RELATED_TO]->() RETURN count(r) AS c",
        "rel_total": "MATCH ()-[r]->() RETURN count(r) AS c",
    }
    driver = GraphDatabase.driver(uri, auth=(user, password))
    counts: dict[str, int] = {}
    try:
        with driver.session() as session:
            for key, query in queries.items():
                counts[key] = int(session.run(query).single()["c"])
    finally:
        driver.close()
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description="校验图谱 Cypher / Neo4j 导入")
    parser.add_argument("--triples", required=True)
    parser.add_argument("--cypher", required=True)
    parser.add_argument("--db-counts", default=None, help="嵌入导入脚本输出的 JSON")
    parser.add_argument("--neo4j-uri", default=None, help="在线 Neo4j Bolt 地址")
    parser.add_argument("--neo4j-user", default="neo4j")
    parser.add_argument("--json-out", default=None)
    args = parser.parse_args()

    triples_path = Path(args.triples)
    cypher_path = Path(args.cypher)
    triples = load_triples(triples_path)
    text = cypher_path.read_text(encoding="utf-8")

    failures: list[str] = []
    checks = 0

    def check(ok: bool, label: str) -> None:
        nonlocal checks
        checks += 1
        if not ok:
            failures.append(label)

    article_ids = {str(t["article_id"]) for t in triples}
    subjects = {s for t in triples for s in (t.get("subjects") or [])}
    actions = {a for t in triples for a in (t.get("actions") or [])}
    penalties = {p for t in triples for p in (t.get("penalties") or [])}
    expected_rel = {
        "APPLIES_TO": sum(len(t.get("subjects") or []) for t in triples),
        "REGULATES": sum(len(t.get("actions") or []) for t in triples),
        "PENALTY": sum(len(t.get("penalties") or []) for t in triples),
    }

    cypher_articles = {cypher_unescape(x) for x in ARTICLE_RE.findall(text)}
    cypher_subjects = {cypher_unescape(x) for x in SUBJECT_RE.findall(text)}
    cypher_actions = {cypher_unescape(x) for x in ACTION_RE.findall(text)}
    cypher_penalties = {cypher_unescape(x) for x in PENALTY_RE.findall(text)}
    citation_articles = {cypher_unescape(x) for x in CITATION_RE.findall(text)}
    cypher_rel = {name: text.count(f"[:{name}]") for name in REL_COUNTS}

    check(text.count("CREATE CONSTRAINT") == 4, "约束数不是 4")
    check(cypher_articles == article_ids, "Cypher 法条节点与 triples 不一致")
    check(cypher_subjects == subjects, "Cypher 主体节点与 triples 不一致")
    check(cypher_actions == actions, "Cypher 行为节点与 triples 不一致")
    check(cypher_penalties == penalties, "Cypher 处罚节点与 triples 不一致")
    check(len(citation_articles) == len(article_ids), "Cypher 法条 citation 覆盖不完整")
    for name, count in expected_rel.items():
        check(cypher_rel[name] == count, f"Cypher {name} 关系数 {cypher_rel[name]} != {count}")

    bad_lines = []
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("//"):
            continue
        if not line.endswith(";"):
            bad_lines.append(lineno)
    check(not bad_lines, f"Cypher 存在未以分号结尾的行（可能含未转义换行）：{bad_lines[:5]}")

    bad_endpoints = []
    for left, right in RELATED_ENDPOINT_RE.findall(text):
        left = cypher_unescape(left)
        right = cypher_unescape(right)
        if left not in article_ids or right not in article_ids:
            bad_endpoints.append((left, right))
    check(not bad_endpoints, f"RELATED_TO 端点缺失：{bad_endpoints[:3]}")

    counts = load_counts(
        Path(args.db_counts) if args.db_counts else None,
        args.neo4j_uri,
        args.neo4j_user,
        os.environ.get("NEO4J_PASSWORD"),
    )
    if counts is not None:
        expected_counts = {
            "nodes_Article": len(article_ids),
            "nodes_Subject": len(subjects),
            "nodes_Action": len(actions),
            "nodes_Penalty": len(penalties),
            "nodes_total": len(article_ids) + len(subjects) + len(actions) + len(penalties),
            "rel_APPLIES_TO": cypher_rel["APPLIES_TO"],
            "rel_REGULATES": cypher_rel["REGULATES"],
            "rel_PENALTY": cypher_rel["PENALTY"],
            "rel_RELATED_TO": cypher_rel["RELATED_TO"],
            "rel_total": sum(cypher_rel.values()),
        }
        for key, expected in expected_counts.items():
            actual = counts.get(key)
            check(actual == expected, f"Neo4j {key} 计数 {actual} != {expected}")

    summary = {
        "triples": str(triples_path),
        "cypher": str(cypher_path),
        "triples_count": len(triples),
        "cypher_statements": text.count(";"),
        "articles": len(article_ids),
        "subjects": len(subjects),
        "actions": len(actions),
        "penalties": len(penalties),
        "relationships": cypher_rel,
        "db_counts": counts,
        "checks": checks,
        "failures": failures,
        "status": "ok" if not failures else "failed",
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
