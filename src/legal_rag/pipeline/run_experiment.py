"""G0/G1/G2 对照实验执行器。

输出：results/<run_id>/<group>_r<repeat>.jsonl，每行一题的答案、检索证据与
提示词哈希；run_meta.json 记录配置快照，供 R3 评测与复现检查使用。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
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
from ..generation.llm_client import LLMClient, MockLLMClient
from ..generation.prompts import PROMPT_VERSION
from ..graph.index import GraphIndex
from ..index.bm25 import Bm25Index
from ..index.embedder import build_embedder
from ..index.store import ChromaArticleStore
from ..retrieval.hybrid import HybridRetriever, load_articles
from .qa import GROUPS, LegalQASystem


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_commit() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return out.stdout.strip() or None
    except Exception:
        return None


def load_questions(path: Path) -> list[dict[str, Any]]:
    questions = []
    with Path(path).open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            item = json.loads(line)
            qid = item.get("id") or item.get("question_id")
            if not qid or not item.get("question"):
                raise SystemExit(f"评测题缺少 id/question 字段：{item}")
            item["id"] = qid
            questions.append(item)
    return questions


def build_runtime(
    cfg: dict[str, Any],
    embedding_model: str | None = None,
    need_retrieval: bool = True,
    need_graph: bool = False,
):
    manifest_path = Path(cfg["paths"]["index_dir"]) / "index_manifest.json"
    if need_retrieval and not manifest_path.exists():
        raise SystemExit(f"缺少索引清单 {manifest_path}，请先运行 python -m legal_rag.index.build_index")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    articles = load_articles(Path(cfg["paths"]["articles_file"]))
    embedder = store = bm25 = retriever = graph = None
    if need_retrieval:
        if manifest.get("embedding_model_debug"):
            print(
                "[警告] 当前索引由调试嵌入器（hashing）构建，结果仅供流程联调，"
                "不得作为正式实验数据。",
                file=sys.stderr,
            )
        model_name = resolve_embedding_model(
            cfg, embedding_model or manifest.get("embedding_model")
        )
        if manifest.get("embedding_model") and model_name != manifest["embedding_model"]:
            print(
                f"[警告] 查询嵌入模型 {model_name} 与索引模型 {manifest['embedding_model']} 不一致，"
                "检索结果仅供流程验证，不得作为正式实验数据。",
                file=sys.stderr,
            )
        embedder = build_embedder(
            model_name,
            device=cfg["embedding"]["device"],
            batch_size=cfg["embedding"]["batch_size"],
            normalize=cfg["embedding"]["normalize"],
            max_seq_length=cfg["embedding"]["max_seq_length"],
        )
        store = ChromaArticleStore(resolve_chroma_dir(cfg), cfg["vector_store"]["collection"])
        bm25 = Bm25Index.load(Path(cfg["paths"]["bm25_file"]))
    if need_graph:
        triples_path = Path(cfg["paths"]["graph_dir"]) / "triples.jsonl"
        if not triples_path.exists():
            raise SystemExit(f"缺少 {triples_path}，请先运行 python -m legal_rag.graph.extract")
        graph = GraphIndex.load(triples_path)
        print(f"图谱索引：{len(graph.by_article)} 条三元组，{graph.entity_count} 个实体")
    if need_retrieval:
        retriever = HybridRetriever(
            embedder,
            store,
            bm25,
            articles,
            candidate_k=cfg["retrieval"]["candidate_k"],
            rrf_k=cfg["retrieval"]["rrf_k"],
            use_char_bigram=cfg["bm25"]["use_char_bigram"],
            graph=graph,
        )
    return retriever, graph, manifest


def run(
    groups: list[str],
    questions_path: Path | None = None,
    limit: int | None = None,
    run_id: str | None = None,
    repeats: int = 1,
    mock: bool = False,
    embedding_model: str | None = None,
    model: str | None = None,
    resume: bool = False,
) -> Path:
    cfg = load_settings()
    if model:
        cfg["generation"]["model"] = model
    questions_path = Path(questions_path or cfg["evaluation"]["questions_file"])
    if not questions_path.exists():
        raise SystemExit(f"找不到评测题 {questions_path}；R3 交付前可先用 data/eval/dev/questions.jsonl")
    questions = load_questions(questions_path)
    if limit:
        questions = questions[:limit]
    for group in groups:
        if group not in GROUPS:
            raise SystemExit(f"未知实验组 {group}，可选：{', '.join(GROUPS)}")

    need_retrieval = any(GROUPS[g] for g in groups)
    need_graph = "G2" in groups
    retriever, graph, index_manifest = build_runtime(
        cfg, embedding_model, need_retrieval=need_retrieval, need_graph=need_graph
    )
    llm = MockLLMClient() if mock else LLMClient(cfg)
    system = LegalQASystem(cfg, retriever, llm, graph)

    run_id = run_id or datetime.now().strftime("%Y%m%d-%H%M%S")
    results_dir = ensure_dir(Path(cfg["paths"]["results_dir"]) / run_id)
    meta = {
        "run_id": run_id,
        "started_at": _now(),
        "finished_at": None,
        "git_commit": _git_commit(),
        "groups": groups,
        "repeats": repeats,
        "mock": mock,
        "questions_file": questions_path.relative_to(REPO_ROOT).as_posix()
        if questions_path.is_relative_to(REPO_ROOT)
        else str(questions_path),
        "questions_sha256": _sha256(questions_path),
        "questions_count": len(questions),
        "prompt_version": PROMPT_VERSION,
        "decoding_params": llm.decoding_params,
        "generation_service": {
            key: cfg["generation"].get(key)
            for key in ("base_url", "model", "backend", "quantization")
        },
        "retrieval": {
            "top_k": cfg["retrieval"]["top_k"],
            "candidate_k": cfg["retrieval"]["candidate_k"],
            "rrf_k": cfg["retrieval"]["rrf_k"],
            "signals": GROUPS,
        },
        "index_manifest": index_manifest,
        "python": platform.python_version(),
    }
    (results_dir / "run_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8"
    )

    for repeat in range(1, repeats + 1):
        for group in groups:
            out_path = results_dir / f"{group}_r{repeat}.jsonl"
            done: set[str] = set()
            if resume and out_path.exists():
                done = {
                    json.loads(line)["question_id"]
                    for line in out_path.read_text(encoding="utf-8").splitlines()
                    if line.strip() and "question_id" in json.loads(line)
                }
            mode = "a" if resume and out_path.exists() else "w"
            print(f"[{group} r{repeat}] {len(questions)} 题 -> {out_path}")
            with out_path.open(mode, encoding="utf-8") as fh:
                for idx, item in enumerate(questions, start=1):
                    if item["id"] in done:
                        continue
                    started = time.time()
                    result = system.answer(item["question"], group)
                    record = {
                        "question_id": item["id"],
                        "category": item.get("category"),
                        "question": item["question"],
                        "group": group,
                        "repeat": repeat,
                        "answer": result["answer"],
                        "refusal_rule_flag": result["refusal_rule_flag"],
                        "evidence": result["evidence"],
                        "graph_context": result["graph_context"],
                        "prompt_hash": result["prompt_hash"],
                        "prompt_version": PROMPT_VERSION,
                        "decoding_params": llm.decoding_params,
                        "usage": result["usage"],
                        "latency_sec": result["latency_sec"],
                        "wall_sec": round(time.time() - started, 2),
                        "answered_at": _now(),
                    }
                    fh.write(json.dumps(record, ensure_ascii=False) + "\n")
                    fh.flush()
                    print(f"  {idx}/{len(questions)} {item['id']} 完成")

    meta["finished_at"] = _now()
    (results_dir / "run_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"实验完成：{results_dir}")
    return results_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="运行 G0/G1/G2 对照实验")
    parser.add_argument("--groups", default="G0,G1,G2")
    parser.add_argument("--questions", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--mock", action="store_true", help="使用离线模拟生成器，仅联调")
    parser.add_argument("--embedding-model", default=None, help="覆盖查询嵌入模型")
    parser.add_argument("--model", default=None, help="覆盖生成模型名（仅本机验证，正式实验不要用）")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    run(
        [g.strip() for g in args.groups.split(",") if g.strip()],
        questions_path=args.questions,
        limit=args.limit,
        run_id=args.run_id,
        repeats=args.repeats,
        mock=args.mock,
        embedding_model=args.embedding_model,
        model=args.model,
        resume=args.resume,
    )


if __name__ == "__main__":
    main()
