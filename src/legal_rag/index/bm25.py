"""BM25 关键词索引：jieba 词 + 中文字符二元组。

二元组的目的是兜住条文号、机构名等专有名词的精确匹配，
与稠密向量召回形成互补。
"""
from __future__ import annotations

import pickle
import re
from pathlib import Path

import jieba
from rank_bm25 import BM25Okapi

_CJK_RUN = re.compile(r"[\u4e00-\u9fff]+")


def tokenize(text: str, use_char_bigram: bool = True) -> list[str]:
    tokens = [t.strip() for t in jieba.lcut(text) if t.strip()]
    if use_char_bigram:
        for run in _CJK_RUN.findall(text):
            tokens.extend(run[i : i + 2] for i in range(len(run) - 1))
    return tokens


class Bm25Index:
    def __init__(self, article_ids: list[str], tokenized: list[list[str]], k1: float, b: float) -> None:
        self.article_ids = article_ids
        self.tokenized = tokenized
        self.k1 = k1
        self.b = b
        self._bm25 = BM25Okapi(tokenized, k1=k1, b=b)

    @classmethod
    def build(
        cls,
        article_ids: list[str],
        texts: list[str],
        k1: float = 1.5,
        b: float = 0.75,
        use_char_bigram: bool = True,
    ) -> "Bm25Index":
        tokenized = [tokenize(t, use_char_bigram) for t in texts]
        return cls(article_ids, tokenized, k1, b)

    def search(self, query: str, top_k: int, use_char_bigram: bool = True) -> list[tuple[str, float]]:
        scores = self._bm25.get_scores(tokenize(query, use_char_bigram))
        order = scores.argsort()[::-1][:top_k]
        return [(self.article_ids[i], float(scores[i])) for i in order if scores[i] > 0]

    def save(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "article_ids": self.article_ids,
            "tokenized": self.tokenized,
            "k1": self.k1,
            "b": self.b,
        }
        tmp = path.with_suffix(path.suffix + ".part")
        with tmp.open("wb") as fh:
            pickle.dump(payload, fh, protocol=pickle.HIGHEST_PROTOCOL)
        tmp.replace(path)

    @classmethod
    def load(cls, path: Path) -> "Bm25Index":
        with Path(path).open("rb") as fh:
            payload = pickle.load(fh)
        return cls(payload["article_ids"], payload["tokenized"], payload["k1"], payload["b"])
