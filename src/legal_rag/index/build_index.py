"""从 articles.jsonl 构建 Chroma 向量索引与 BM25 索引。

用法：
  python -m legal_rag.index.build_index
  python -m legal_rag.index.build_index --embedding-model /path/to/bge-small-zh
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import (
    REPO_ROOT,
    ensure_dir,
    load_settings,
    resolve_chroma_dir,
    resolve_embedding_model,
)
from .bm25 import Bm25Index
from .embedder import build_embedder
from .store import ChromaArticleStore

INDEX_VERSION = "1.0"


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_articles(path: Path) -> list[dict[str, Any]]:
    with Path(path).open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def embed_text(article: dict[str, Any]) -> str:
    return f"{article['citation']}\n{article['text']}"


def to_metadata(article: dict[str, Any]) -> dict[str, Any]:
    meta = {
        "doc_id": article["doc_id"],
        "law_title": article["law_title"],
        "level": article["level"],
        "domain": article["domain"],
        "article_no": article["article_no"],
        "article_num": int(article["article_num"]),
        "citation": article["citation"],
        "chapter": article.get("chapter") or "",
        "section": article.get("section") or "",
        "effective_date": article.get("effective_date") or "",
        "source_url": article.get("source_url") or "",
    }
    return meta


def build_index(
    embedding_model: str | None = None,
    device: str | None = None,
    batch_size: int | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    cfg = load_settings()
    paths = cfg["paths"]
    articles_path = Path(paths["articles_file"])
    if not articles_path.exists():
        raise SystemExit("找不到 articles.jsonl，请先运行：python -m legal_rag.corpus.build")

    articles = read_articles(articles_path)
    if limit:
        articles = articles[:limit]
    if not articles:
        raise SystemExit("articles.jsonl 为空")

    model_name = resolve_embedding_model(cfg, embedding_model)
    device = device or cfg["embedding"]["device"]
    batch_size = batch_size or cfg["embedding"]["batch_size"]
    started = time.time()

    print(f"载入 {len(articles)} 条文本块；嵌入模型：{model_name}（device={device}）")
    embedder = build_embedder(
        model_name,
        device=device,
        batch_size=batch_size,
        normalize=cfg["embedding"]["normalize"],
        max_seq_length=cfg["embedding"]["max_seq_length"],
    )
    texts = [article["text"] for article in articles]
    vectors = embedder.encode([embed_text(article) for article in articles])
    print(f"向量化完成：shape={vectors.shape}，耗时 {time.time() - started:.1f}s")

    store_path = resolve_chroma_dir(cfg)
    store = ChromaArticleStore(store_path, cfg["vector_store"]["collection"])
    store.reset()
    ids = [article["article_id"] for article in articles]
    store.add(ids, texts, [to_metadata(a) for a in articles], vectors)
    count = store.count()
    if count != len(articles):
        raise SystemExit(f"Chroma 写入数量不一致：{count} != {len(articles)}")
    # 预热一次查询，确保 HNSW 段落在进程退出前完成构建与落盘
    store.query(vectors[0], 1)
    store.close()
    print(f"Chroma 写入完成：{count} 条，集合 {cfg['vector_store']['collection']}")

    bm25 = Bm25Index.build(
        ids,
        texts,
        k1=cfg["bm25"]["k1"],
        b=cfg["bm25"]["b"],
        use_char_bigram=cfg["bm25"]["use_char_bigram"],
    )
    bm25_path = Path(paths["bm25_file"])
    bm25.save(bm25_path)
    print(f"BM25 写入完成：{bm25_path}")

    manifest = {
        "index_version": INDEX_VERSION,
        "built_at": _now(),
        "articles_file": articles_path.relative_to(REPO_ROOT).as_posix(),
        "articles_sha256": _sha256(articles_path),
        "article_count": len(articles),
        "embedding_model": model_name,
        "embedding_model_debug": model_name.strip().lower() in {"hashing", "hashing-debug"},
        "embedding_dim": embedder.dimension,
        "embedding_normalized": cfg["embedding"]["normalize"],
        "embedding_max_seq_length": cfg["embedding"]["max_seq_length"],
        "device": device,
        "vector_store": {
            "provider": "chroma",
            "collection": cfg["vector_store"]["collection"],
            "distance": cfg["vector_store"]["distance"],
            "path": str(store_path),
            "configured_path": paths["chroma_dir"],
        },
        "bm25": {"k1": cfg["bm25"]["k1"], "b": cfg["bm25"]["b"], "char_bigram": cfg["bm25"]["use_char_bigram"]},
        "debug_limit": limit,
        "elapsed_sec": round(time.time() - started, 1),
    }
    manifest_path = Path(paths["index_dir"]) / "index_manifest.json"
    ensure_dir(manifest_path.parent)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"索引清单：{manifest_path}")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="构建 Chroma + BM25 索引")
    parser.add_argument("--embedding-model", default=None, help="覆盖嵌入模型（本地路径或 HF 名称）")
    parser.add_argument("--device", default=None, help="cpu / cuda")
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument("--limit", type=int, default=None, help="仅索引前 N 条，用于流程验证")
    args = parser.parse_args()
    build_index(args.embedding_model, args.device, args.batch_size, args.limit)


if __name__ == "__main__":
    main()
