"""混合检索：稠密向量 + BM25 +（可选）图谱子图，RRF 融合。

同一信号内对多条重写查询取并集（按最佳名次合并），再做跨信号融合。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from .fusion import rrf_fuse
from .query_rewrite import rewrite


class EmbedderLike(Protocol):
    def encode(self, texts: list[str], show_progress: bool = False): ...


class GraphLike(Protocol):
    def search(
        self, queries: list[str], top_k: int, seed_ids: list[str] | None = None
    ) -> list[str]: ...


@dataclass
class RetrievalHit:
    article_id: str
    score: float
    ranks: dict[str, int] = field(default_factory=dict)
    record: dict[str, Any] | None = None

    @property
    def citation(self) -> str:
        return (self.record or {}).get("citation", "")

    @property
    def text(self) -> str:
        return (self.record or {}).get("text", "")


def load_articles(path: Path) -> dict[str, dict[str, Any]]:
    with Path(path).open(encoding="utf-8") as fh:
        return {rec["article_id"]: rec for line in fh if line.strip() for rec in [json.loads(line)]}


class HybridRetriever:
    def __init__(
        self,
        embedder: EmbedderLike,
        vector_store,
        bm25,
        articles: dict[str, dict[str, Any]],
        candidate_k: int = 30,
        rrf_k: float = 60,
        use_char_bigram: bool = True,
        graph: GraphLike | None = None,
    ) -> None:
        self.embedder = embedder
        self.vector_store = vector_store
        self.bm25 = bm25
        self.articles = articles
        self.candidate_k = candidate_k
        self.rrf_k = rrf_k
        self.use_char_bigram = use_char_bigram
        self.graph = graph

    def _merge_ranking(self, per_query: list[list[str]]) -> list[str]:
        """同一信号内多查询结果用 RRF 合并，避免不同查询的分数尺度不可比。"""
        rankings = {f"q{idx}": ids for idx, ids in enumerate(per_query) if ids}
        if not rankings:
            return []
        return [aid for aid, _, _ in rrf_fuse(rankings, k=self.rrf_k, top_k=self.candidate_k)]

    def _dense_ranking(self, queries: list[str], k: int) -> list[str]:
        per_query = []
        for query in queries:
            embedding = self.embedder.encode([query], show_progress=False)[0]
            hits = self.vector_store.query(embedding, k)
            per_query.append([h["article_id"] for h in hits])
        return self._merge_ranking(per_query)

    def _bm25_ranking(self, queries: list[str], k: int) -> list[str]:
        per_query = [
            [article_id for article_id, _ in self.bm25.search(q, k, use_char_bigram=self.use_char_bigram)]
            for q in queries
        ]
        return self._merge_ranking(per_query)

    def retrieve(
        self,
        query: str,
        signals: list[str],
        top_k: int = 5,
    ) -> list[RetrievalHit]:
        rw = rewrite(query)
        queries = rw.retrieval_queries()
        rankings: dict[str, list[str]] = {}
        if "dense" in signals:
            rankings["dense"] = self._dense_ranking(queries, self.candidate_k)
        if "bm25" in signals:
            rankings["bm25"] = self._bm25_ranking(queries, self.candidate_k)
        if "graph" in signals:
            if self.graph is None:
                raise RuntimeError("G2 需要图谱检索，但未加载图谱索引")
            seeds = (rankings.get("dense") or rankings.get("bm25") or [])[:5]
            rankings["graph"] = self.graph.search(queries, self.candidate_k, seed_ids=seeds)
        fused = rrf_fuse(rankings, k=self.rrf_k, top_k=top_k)
        return [
            RetrievalHit(
                article_id=article_id,
                score=score,
                ranks=ranks,
                record=self.articles.get(article_id),
            )
            for article_id, score, ranks in fused
        ]
