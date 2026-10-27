"""句向量封装。

正式实验固定 BGE-M3（1024 维）；无权重时可用 --embedding-model 指向本地
bge-small-zh 等替代模型做流程验证，但该覆盖必须记录在 index_manifest.json，
不得混入正式实验结果。

另提供 hashing 调试嵌入器：中文字符 n-gram 特征哈希，零依赖、确定性，
只用于本机离线联调，manifest 会标记 debug=true。
"""
from __future__ import annotations

import hashlib
import re

import numpy as np

_CJK_RUN = re.compile(r"[\u4e00-\u9fff]+")
_WORD = re.compile(r"[A-Za-z0-9]+")


class Embedder:
    def __init__(
        self,
        model_name: str,
        device: str = "cpu",
        batch_size: int = 16,
        normalize: bool = True,
        max_seq_length: int = 512,
    ) -> None:
        from sentence_transformers import SentenceTransformer

        self.model_name = model_name
        self.batch_size = batch_size
        self.normalize = normalize
        self.model = SentenceTransformer(model_name, device=device)
        if max_seq_length:
            self.model.max_seq_length = max_seq_length

    @property
    def dimension(self) -> int:
        return int(self.model.get_sentence_embedding_dimension())

    def encode(self, texts: list[str], show_progress: bool = True) -> np.ndarray:
        vectors = self.model.encode(
            texts,
            batch_size=self.batch_size,
            normalize_embeddings=self.normalize,
            show_progress_bar=show_progress,
            convert_to_numpy=True,
        )
        return np.asarray(vectors, dtype=np.float32)


def _hash_token(token: str, dim: int) -> tuple[int, float]:
    digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
    value = int.from_bytes(digest, "little")
    return value % dim, 1.0 if (value >> 63) & 1 else -1.0


class HashingEmbedder:
    """调试用特征哈希嵌入器（字符 1~3-gram + 英文/数字词）。"""

    model_name = "hashing-debug"

    def __init__(self, dim: int = 512, normalize: bool = True) -> None:
        self._dim = dim
        self.normalize = normalize

    @property
    def dimension(self) -> int:
        return self._dim

    def _features(self, text: str) -> list[str]:
        feats: list[str] = []
        for run in _CJK_RUN.findall(text):
            feats.extend(run)
            feats.extend(run[i : i + 2] for i in range(len(run) - 1))
            feats.extend(run[i : i + 3] for i in range(len(run) - 2))
        feats.extend(w.lower() for w in _WORD.findall(text))
        return feats

    def encode(self, texts: list[str], show_progress: bool = False) -> np.ndarray:
        matrix = np.zeros((len(texts), self._dim), dtype=np.float32)
        for row, text in enumerate(texts):
            for feat in self._features(text):
                idx, sign = _hash_token(feat, self._dim)
                matrix[row, idx] += sign
            if self.normalize:
                norm = float(np.linalg.norm(matrix[row]))
                if norm > 0:
                    matrix[row] /= norm
        return matrix


def build_embedder(
    model_name: str,
    device: str = "cpu",
    batch_size: int = 16,
    normalize: bool = True,
    max_seq_length: int = 512,
) -> Embedder | HashingEmbedder:
    if model_name.strip().lower() in {"hashing", "hashing-debug"}:
        return HashingEmbedder(normalize=normalize)
    return Embedder(
        model_name,
        device=device,
        batch_size=batch_size,
        normalize=normalize,
        max_seq_length=max_seq_length,
    )

