"""离线图谱索引：实体→法条倒排 + 法条一跳邻接。

G2 的图谱一路不依赖 Neo4j 在线服务：同一份 triples.jsonl 既导入 Neo4j
（交付物），也在此构建检索索引（实验可复现）。Neo4j 在线检索为可选增强。
"""
from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


class GraphIndex:
    def __init__(self, triples: list[dict[str, Any]]) -> None:
        self.triples = triples
        self.by_article: dict[str, dict[str, Any]] = {}
        self.entity_articles: dict[str, set[str]] = defaultdict(set)
        self.entity_df: Counter[str] = Counter()
        adjacency: dict[str, Counter[str]] = defaultdict(Counter)

        for triple in triples:
            article_id = triple["article_id"]
            self.by_article[article_id] = triple
            entities = (
                [("S", s) for s in triple.get("subjects", [])]
                + [("A", a) for a in triple.get("actions", [])]
                + [("P", p) for p in triple.get("penalties", [])]
            )
            seen = set()
            for _, entity in entities:
                if entity in seen:
                    continue
                seen.add(entity)
                self.entity_articles[entity].add(article_id)
                self.entity_df[entity] += 1
                # 共享同一实体的法条互为邻居，权重为共享实体数
                for other in sorted(self.entity_articles[entity]):
                    if other != article_id:
                        adjacency[article_id][other] += 1
                        adjacency[other][article_id] += 1

        # 每个法条只保留共享实体最多的 20 个邻居；同分按 article_id 排序，
        # 避免 Python 哈希随机化导致图上下文与 Cypher 导出不可复现。
        self.adjacency: dict[str, list[tuple[str, int]]] = {
            aid: sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:20]
            for aid, counter in adjacency.items()
        }

    @classmethod
    def load(cls, path: Path) -> "GraphIndex":
        with Path(path).open(encoding="utf-8") as fh:
            triples = [json.loads(line) for line in fh if line.strip()]
        return cls(triples)

    @property
    def entity_count(self) -> int:
        return len(self.entity_articles)

    def search(
        self,
        queries: list[str],
        top_k: int,
        seed_ids: list[str] | None = None,
    ) -> list[str]:
        text = " ".join(queries)
        total = max(len(self.by_article), 1)
        scores: dict[str, float] = defaultdict(float)

        for entity, article_ids in self.entity_articles.items():
            if entity not in text:
                continue
            idf = math.log((total + 1) / (self.entity_df[entity] + 1)) + 1.0
            # 实体越长信息量越大（如“县级以上人民政府自然资源主管部门”）
            weight = idf * min(len(entity), 10) / 5.0
            for article_id in sorted(article_ids):
                scores[article_id] += weight

        # 一跳子图：优先从实体命中的法条出发，只取共享 ≥2 个实体的邻居；
        # 无实体命中时退回稠密/BM25 的种子法条。
        seeds = sorted(scores, key=lambda d: (-scores[d], d))[:5] or list(seed_ids or [])
        for seed in seeds:
            for other, shared in self.adjacency.get(seed, [])[:10]:
                if other != seed and shared >= 2:
                    scores[other] += 0.1 * min(shared, 5)

        return sorted(scores, key=lambda d: (-scores[d], d))[:top_k]

    def subgraph(self, article_ids: list[str], max_related: int = 8) -> dict[str, Any]:
        """返回用于拼入提示词的一跳子图三元组。"""
        nodes = [self.by_article[aid] for aid in article_ids if aid in self.by_article]
        related: dict[str, dict[str, Any]] = {}
        for aid in article_ids:
            for other, _ in self.adjacency.get(aid, [])[:5]:
                if other not in article_ids and other in self.by_article:
                    related[other] = self.by_article[other]
                if len(related) >= max_related:
                    break
        return {"nodes": nodes, "related": list(related.values())}
