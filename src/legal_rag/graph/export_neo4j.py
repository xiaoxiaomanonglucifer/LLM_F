"""把 triples.jsonl 导出为 Neo4j Cypher，或直接导入运行中的 Neo4j。

节点：Article / Subject / Action / Penalty
关系：APPLIES_TO（法条→主体）、REGULATES（法条→行为）、
      PENALTY（法条→处罚）、RELATED_TO（共享实体的一跳关联）
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ..config import REPO_ROOT, ensure_dir, env_password, load_settings
from .index import GraphIndex


def _q(text: str) -> str:
    escaped = (
        str(text)
        .replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace("\r", "\\r")
        .replace("\n", "\\n")
        .replace("\t", "\\t")
    )
    return "'" + escaped + "'"


def build_statements(triples: list[dict], adjacency: dict[str, list[str]], with_related: bool) -> list[str]:
    stmts = [
        "CREATE CONSTRAINT article_id IF NOT EXISTS FOR (a:Article) REQUIRE a.article_id IS UNIQUE",
        "CREATE CONSTRAINT subject_name IF NOT EXISTS FOR (s:Subject) REQUIRE s.name IS UNIQUE",
        "CREATE CONSTRAINT action_name IF NOT EXISTS FOR (a:Action) REQUIRE a.name IS UNIQUE",
        "CREATE CONSTRAINT penalty_name IF NOT EXISTS FOR (p:Penalty) REQUIRE p.name IS UNIQUE",
    ]
    for t in triples:
        aid = _q(t["article_id"])
        stmts.append(
            f"MERGE (a:Article {{article_id: {aid}}}) "
            f"SET a.citation = {_q(t['citation'])}, a.law_title = {_q(t['law_title'])}"
        )
        for subject in t.get("subjects", []):
            stmts.append(
                f"MERGE (a:Article {{article_id: {aid}}}) "
                f"MERGE (s:Subject {{name: {_q(subject)}}}) "
                "MERGE (a)-[:APPLIES_TO]->(s)"
            )
        for action in t.get("actions", []):
            stmts.append(
                f"MERGE (a:Article {{article_id: {aid}}}) "
                f"MERGE (x:Action {{name: {_q(action)}}}) "
                "MERGE (a)-[:REGULATES]->(x)"
            )
        for penalty in t.get("penalties", []):
            stmts.append(
                f"MERGE (a:Article {{article_id: {aid}}}) "
                f"MERGE (p:Penalty {{name: {_q(penalty)}}}) "
                "MERGE (a)-[:PENALTY]->(p)"
            )
    if with_related:
        seen: set[tuple[str, str]] = set()
        for aid, neighbours in adjacency.items():
            for other, _shared in neighbours[:5]:
                key = tuple(sorted((aid, other)))
                if key in seen:
                    continue
                seen.add(key)
                stmts.append(
                    f"MATCH (a:Article {{article_id: {_q(key[0])}}}), "
                    f"(b:Article {{article_id: {_q(key[1])}}}) "
                    "MERGE (a)-[:RELATED_TO]->(b)"
                )
    return stmts


def import_statements(uri: str, user: str, database: str, password: str, statements: list[str]) -> int:
    try:
        from neo4j import GraphDatabase
    except ImportError as exc:
        raise SystemExit("未安装 neo4j 驱动：pip install neo4j") from exc
    driver = GraphDatabase.driver(uri, auth=(user, password))
    count = 0
    with driver.session(database=database) as session:
        for stmt in statements:
            session.run(stmt).consume()
            count += 1
    driver.close()
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="导出/导入 Neo4j 图谱")
    parser.add_argument("--triples", default=None)
    parser.add_argument("--out", default=None)
    parser.add_argument("--import", action="store_true", dest="do_import")
    parser.add_argument("--no-related", action="store_true")
    args = parser.parse_args()

    cfg = load_settings()
    triples_path = Path(args.triples or (Path(cfg["paths"]["graph_dir"]) / "triples.jsonl"))
    if not triples_path.exists():
        raise SystemExit(f"找不到 {triples_path}，请先运行 python -m legal_rag.graph.extract")
    with triples_path.open(encoding="utf-8") as fh:
        triples = [json.loads(line) for line in fh if line.strip()]

    graph = GraphIndex(triples)
    statements = build_statements(triples, graph.adjacency, with_related=not args.no_related)

    out_path = Path(args.out or (Path(cfg["paths"]["graph_dir"]) / "neo4j_import.cypher"))
    ensure_dir(out_path.parent)
    header = (
        f"// generated from {triples_path.relative_to(REPO_ROOT).as_posix()}\n"
        f"// triples={len(triples)} statements={len(statements)}\n"
        "// 执行：cypher-shell -f neo4j_import.cypher 或在 Neo4j Browser 中逐段运行\n"
    )
    out_path.write_text(header + ";\n".join(statements) + ";\n", encoding="utf-8")
    print(f"Cypher 导出完成：{out_path}（{len(statements)} 条语句）")

    if args.do_import:
        password = env_password()
        if not password:
            raise SystemExit("导入需要环境变量 NEO4J_PASSWORD")
        gcfg = cfg["graph"]
        count = import_statements(
            gcfg["uri"], gcfg["user"], gcfg["database"], password, statements
        )
        print(f"Neo4j 导入完成：{count} 条语句", file=sys.stdout)


if __name__ == "__main__":
    main()
