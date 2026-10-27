"""Reciprocal Rank Fusion（RRF）。

按名次倒数求和：score(d) = Σ 1/(k + rank_i(d))。
对分数尺度不敏感，不需要人工调各路权重。
"""
from __future__ import annotations

from collections import defaultdict


def rrf_fuse(
    rankings: dict[str, list[str]], k: int = 60, top_k: int = 5
) -> list[tuple[str, float, dict[str, int]]]:
    scores: dict[str, float] = defaultdict(float)
    ranks: dict[str, dict[str, int]] = defaultdict(dict)
    for signal, ids in rankings.items():
        for rank, article_id in enumerate(ids, start=1):
            scores[article_id] += 1.0 / (k + rank)
            ranks[article_id][signal] = rank
    ordered = sorted(scores, key=lambda d: (-scores[d], d))
    return [(d, scores[d], ranks[d]) for d in ordered[:top_k]]
