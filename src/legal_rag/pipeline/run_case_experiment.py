"""案件五步问答实验：G0 / G1 / G2 与案例/图谱消融。

与法规问答实验分开输出，避免混用两套评测口径。每题保存五步中间结果、
相似案例、引用条文与确定性答案，便于逐题复核。
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from ..cases.build_case_graph import CaseGraph
from ..cases.case_qa import CASE_GROUPS, CaseQASystem
from ..cases.retriever import CaseRetriever
from ..cases.schema import load_cases
from ..config import REPO_ROOT, ensure_dir, load_settings
from ..generation.llm_client import LLMClient, MockLLMClient
from ..generation.prompts import CASE_PROMPT_VERSION
from ..retrieval.hybrid import load_articles
from .run_experiment import _git_commit, _now, _sha256, build_runtime, load_questions


def _case_path(cfg: dict[str, Any]) -> Path:
    return Path(cfg["paths"]["cases_dir"]) / "cases.jsonl"


def _case_graph_path(cfg: dict[str, Any]) -> Path:
    return Path(cfg["paths"]["cases_dir"]) / "graph" / "edges.jsonl"


def _build_case_runtime(
    cfg: dict[str, Any], groups: list[str], embedding_model: str | None = None
):
    need_retrieval = any(CASE_GROUPS[group]["law_signals"] for group in groups)
    need_graph = any("graph" in CASE_GROUPS[group]["law_signals"] for group in groups)
    retriever, law_graph, manifest = build_runtime(
        cfg,
        embedding_model=embedding_model,
        need_retrieval=need_retrieval,
        need_graph=need_graph,
    )
    cases = load_cases(_case_path(cfg))
    case_retriever = CaseRetriever(cases)
    case_graph = CaseGraph(cases)
    case_graph_file = _case_graph_path(cfg)
    if case_graph_file.exists():
        print(f"案例图谱文件：{case_graph_file}（离线实例已由 cases.jsonl 重建）")
    return retriever, law_graph, case_retriever, case_graph, manifest


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
    questions_path = Path(
        questions_path
        or cfg["evaluation"].get("case_questions_file")
        or cfg["evaluation"].get("questions_file")
        or "data/eval/dev/questions.jsonl"
    )
    if not questions_path.exists():
        raise SystemExit(f"找不到案件评测题 {questions_path}")
    questions = load_questions(questions_path)
    if limit:
        questions = questions[:limit]
    for group in groups:
        if group not in CASE_GROUPS:
            raise SystemExit(f"未知案件实验组 {group}，可选：{', '.join(CASE_GROUPS)}")

    retriever, law_graph, case_retriever, case_graph, index_manifest = _build_case_runtime(
        cfg, groups, embedding_model
    )
    articles = load_articles(Path(cfg["paths"]["articles_file"]))
    llm = MockLLMClient() if mock else LLMClient(cfg)
    system = CaseQASystem(
        cfg,
        articles,
        case_retriever=case_retriever,
        case_graph=case_graph,
        retriever=retriever,
        llm=llm,
    )

    run_id = run_id or datetime.now().strftime("case-%Y%m%d-%H%M%S")
    results_dir = ensure_dir(Path(cfg["paths"]["results_dir"]) / run_id)
    meta = {
        "run_id": run_id,
        "mode": "case",
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
        "prompt_version": CASE_PROMPT_VERSION,
        "decoding_params": llm.decoding_params,
        "case_count": len(case_retriever.case_ids),
        "case_graph": case_graph.stats(),
        "retrieval": {
            "top_k": cfg["retrieval"]["top_k"],
            "candidate_k": cfg["retrieval"]["candidate_k"],
            "case_top_k": cfg["retrieval"].get("case_top_k", 3),
            "groups": CASE_GROUPS,
        },
        "index_manifest": index_manifest,
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
                    result = system.answer(
                        item["question"],
                        group,
                        exclude_case_id=item.get("exclude_case_id") or item.get("case_id"),
                    )
                    record = {
                        "question_id": item["id"],
                        "category": item.get("category"),
                        "question": item["question"],
                        "group": group,
                        "repeat": repeat,
                        "answer": result.get("llm_answer") or result["answer"],
                        "deterministic_answer": result["answer"],
                        "confidence": result["confidence"],
                        "steps": result["steps"],
                        "similar_cases": result["similar_cases"],
                        "citations": result["citations"],
                        "prompt_hash": result.get("prompt_hash"),
                        "prompt_version": CASE_PROMPT_VERSION,
                        "decoding_params": llm.decoding_params,
                        "usage": result.get("usage", {}),
                        "latency_sec": result.get("latency_sec"),
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
    print(f"案件实验完成：{results_dir}")
    return results_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="运行案件五步问答实验")
    parser.add_argument("--groups", default="G0,G1,G2")
    parser.add_argument("--questions", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--mock", action="store_true", help="使用离线模拟生成器，仅联调")
    parser.add_argument("--embedding-model", default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    run(
        [group.strip() for group in args.groups.split(",") if group.strip()],
        questions_path=Path(args.questions) if args.questions else None,
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
