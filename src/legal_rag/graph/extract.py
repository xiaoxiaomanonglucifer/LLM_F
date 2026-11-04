"""三元组抽取 CLI：默认规则抽取，--method llm 走大模型抽取。"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ..config import ensure_dir, load_settings
from .schema import all_empty, extract_rule_based, iter_articles


def _rule_extract_all(articles_path: Path, out_path: Path) -> dict:
    ensure_dir(out_path.parent)
    total = kept = 0
    with out_path.open("w", encoding="utf-8") as out:
        for article in iter_articles(articles_path):
            total += 1
            triple = extract_rule_based(article)
            if triple is None:
                continue
            out.write(triple.to_json() + "\n")
            kept += 1
    return {"articles_total": total, "triples": kept, **_graph_stats(out_path)}


def _read_progress(path: Path) -> set[str]:
    if not path.exists():
        return set()
    done: set[str] = set()
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                done.add(json.loads(line)["article_id"])
            except (KeyError, json.JSONDecodeError):
                continue
    return done


def _graph_stats(path: Path) -> dict:
    subjects: set[str] = set()
    actions: set[str] = set()
    penalties: set[str] = set()
    applies = regulates = penalty_rel = 0
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            record = json.loads(line)
            subjects.update(record.get("subjects") or [])
            actions.update(record.get("actions") or [])
            penalties.update(record.get("penalties") or [])
            applies += len(record.get("subjects") or [])
            regulates += len(record.get("actions") or [])
            penalty_rel += len(record.get("penalties") or [])
    return {
        "subjects": len(subjects),
        "actions": len(actions),
        "penalties": len(penalties),
        "entities_total": len(subjects) + len(actions) + len(penalties),
        "rel_APPLIES_TO": applies,
        "rel_REGULATES": regulates,
        "rel_PENALTY": penalty_rel,
    }


def _compact_triples(path: Path, articles: list[dict]) -> int:
    """按文章顺序去重写回，避免断点续跑产生重复记录。"""
    if not path.exists():
        return 0
    order = {article["article_id"]: idx for idx, article in enumerate(articles)}
    records: dict[str, dict] = {}
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                records[record["article_id"]] = record
            except (KeyError, json.JSONDecodeError):
                continue
    with path.open("w", encoding="utf-8") as out:
        for article_id in sorted(records, key=lambda x: (order.get(x, len(order)), x)):
            out.write(json.dumps(records[article_id], ensure_ascii=False) + "\n")
    return len(records)


def _llm_extract_all(
    articles_path: Path,
    out_path: Path,
    cfg: dict,
    workers: int = 4,
    limit: int | None = None,
    resume: bool = False,
) -> dict:
    from ..generation.llm_client import LLMClient

    client = LLMClient(cfg)
    articles = list(iter_articles(articles_path))
    if limit is not None:
        articles = articles[:limit]
    ensure_dir(out_path.parent)

    progress_path = out_path.with_suffix(".progress.jsonl")
    can_resume = resume and out_path.exists() and progress_path.exists()
    done = _read_progress(progress_path) if can_resume else set()
    pending = [article for article in articles if article["article_id"] not in done]

    stats = {
        "articles_total": len(articles),
        "processed_now": 0,
        "llm_ok": 0,
        "llm_empty": 0,
        "rule_fallback": 0,
        "error": 0,
        "triples": 0,
        "workers": workers,
        "resume": can_resume,
        "model": client.model,
    }

    def work(article: dict):
        try:
            return article, client.extract_triple(article), None
        except Exception as exc:  # 单条失败不中断全量
            return article, None, exc

    out_mode = "a" if can_resume else "w"
    progress_mode = "a" if can_resume else "w"
    with (
        out_path.open(out_mode, encoding="utf-8") as out,
        progress_path.open(progress_mode, encoding="utf-8") as progress,
        ThreadPoolExecutor(max_workers=max(1, workers)) as pool,
    ):
        for idx, (article, triple, error) in enumerate(pool.map(work, pending), start=1):
            if error is not None:
                status = "error"
                print(f"[LLM抽取失败] {article['article_id']}: {error}", file=sys.stderr)
                triple = extract_rule_based(article)
            elif triple is None:
                status = "rule_fallback"
                triple = extract_rule_based(article)
            elif all_empty(triple):
                status = "llm_empty"
            else:
                status = "llm_ok"
                out.write(triple.to_json() + "\n")

            if status in {"error", "rule_fallback"} and triple is not None:
                out.write(triple.to_json() + "\n")
            progress.write(
                json.dumps({"article_id": article["article_id"], "status": status}, ensure_ascii=False) + "\n"
            )
            stats["processed_now"] += 1
            if idx % 100 == 0 or idx == len(pending):
                print(
                    f"[LLM抽取] {idx}/{len(pending)} 新增完成，"
                    f"累计进度 {len(done) + idx}/{len(articles)}",
                    file=sys.stderr,
                )

    status_counts = Counter()
    for line in progress_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            status_counts[json.loads(line)["status"]] += 1
        except (KeyError, json.JSONDecodeError):
            continue
    stats.update(
        {
            "llm_ok": status_counts["llm_ok"],
            "llm_empty": status_counts["llm_empty"],
            "rule_fallback": status_counts["rule_fallback"],
            "error": status_counts["error"],
            "processed_total": sum(status_counts.values()),
        }
    )
    stats["triples"] = _compact_triples(out_path, articles)
    stats.update(_graph_stats(out_path))
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="抽取法条三元组")
    parser.add_argument("--method", choices=["rule", "llm"], default="rule")
    parser.add_argument("--articles", default=None)
    parser.add_argument("--out", default=None)
    parser.add_argument("--workers", type=int, default=4, help="LLM 并发数，默认 4")
    parser.add_argument("--limit", type=int, default=None, help="只处理前 N 条，用于抽样验证")
    parser.add_argument("--resume", action="store_true", help="按 .progress.jsonl 断点续跑")
    args = parser.parse_args()

    cfg = load_settings()
    articles_path = Path(args.articles or cfg["paths"]["articles_file"])
    default_name = "triples_llm.jsonl" if args.method == "llm" else "triples.jsonl"
    out_path = Path(args.out or (Path(cfg["paths"]["graph_dir"]) / default_name))
    if not articles_path.exists():
        raise SystemExit(f"找不到 {articles_path}，请先构建语料")

    stats = (
        _llm_extract_all(articles_path, out_path, cfg, args.workers, args.limit, args.resume)
        if args.method == "llm"
        else _rule_extract_all(articles_path, out_path)
    )
    stats.update(
        {
            "method": args.method,
            "out": str(out_path),
            "coverage": round(stats["triples"] / max(stats["articles_total"], 1), 4),
        }
    )
    meta_path = out_path.with_suffix(".stats.json")
    meta_path.write_text(json.dumps(stats, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"三元组抽取完成：{stats}")


if __name__ == "__main__":
    main()
