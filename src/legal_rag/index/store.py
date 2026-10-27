"""Chroma 持久化向量库封装。

集合按语料版本命名（legal_articles_v1），索引目录随 data/v1 版本管理；
检索返回相似度 = 1 - cosine 距离。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np


class ChromaArticleStore:
    def __init__(self, path: Path, collection_name: str) -> None:
        import chromadb

        Path(path).mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(path))
        self.collection_name = collection_name
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def reset(self) -> None:
        try:
            self.client.delete_collection(self.collection_name)
        except Exception:  # 集合不存在时忽略
            pass
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def count(self) -> int:
        return int(self.collection.count())

    def add(
        self,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict[str, Any]],
        embeddings: np.ndarray,
        batch_size: int = 512,
    ) -> None:
        for start in range(0, len(ids), batch_size):
            end = start + batch_size
            self.collection.add(
                ids=ids[start:end],
                documents=documents[start:end],
                metadatas=metadatas[start:end],
                embeddings=embeddings[start:end].tolist(),
            )

    def query(self, embedding: np.ndarray, top_k: int) -> list[dict[str, Any]]:
        result = self.collection.query(
            query_embeddings=[embedding.tolist()],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )
        hits = []
        for article_id, doc, meta, dist in zip(
            result["ids"][0],
            result["documents"][0],
            result["metadatas"][0],
            result["distances"][0],
        ):
            hits.append(
                {
                    "article_id": article_id,
                    "document": doc,
                    "metadata": meta or {},
                    "score": 1.0 - float(dist),
                }
            )
        return hits

    def get_metadatas(self, ids: list[str]) -> list[dict[str, Any]]:
        result = self.collection.get(ids=ids, include=["metadatas"])
        return result["metadatas"]

    def close(self) -> None:
        """显式关闭，确保 HNSW 段落盘；不关闭会导致下次打开时索引文件缺失。"""
        close = getattr(self.client, "close", None)
        if callable(close):
            close()
