"""三元组抽取 CLI：默认规则抽取，--method llm 走大模型抽取。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ..config import ensure_dir, load_settings
from .schema import Triple, extract_rule_based, iter_articles


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
    return {"articles_total": total, "triples": kept}


def _llm_extract_all(articles_path: Path, out_path: Path, cfg: dict) -> dict:
    from ..generation.llm_client import LLMClient

    client = LLMClient(cfg)
    ensure_dir(out_path.parent)
    total = kept = failed = 0
    with out_path.open("w", encoding="utf-8") as out:
        for article in iter_articles(articles_path):
            total += 1
            triple = None
            try:
                triple = client.extract_triple(article)
            except Exception as exc:  # 单条失败不中断全量
                print(f"[LLM抽取失败] {article['article_id']}: {exc}", file=sys.stderr)
                failed += 1
            if triple is None:
                triple = extract_rule_based(article)
            if triple is None:
                continue
            out.write(triple.to_json() + "\n")
            kept += 1
    return {"articles_total": total, "triples": kept, "llm_failed": failed}


def main() -> None:
    parser = argparse.ArgumentParser(description="抽取法条三元组")
    parser.add_argument("--method", choices=["rule", "llm"], default="rule")
    parser.add_argument("--articles", default=None)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    cfg = load_settings()
    articles_path = Path(args.articles or cfg["paths"]["articles_file"])
    out_path = Path(args.out or (Path(cfg["paths"]["graph_dir"]) / "triples.jsonl"))
    if not articles_path.exists():
        raise SystemExit(f"找不到 {articles_path}，请先构建语料")

    stats = (
        _llm_extract_all(articles_path, out_path, cfg)
        if args.method == "llm"
        else _rule_extract_all(articles_path, out_path)
    )
    stats.update({"method": args.method, "out": str(out_path)})
    meta_path = out_path.with_suffix(".stats.json")
    meta_path.write_text(json.dumps(stats, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"三元组抽取完成：{stats}")


if __name__ == "__main__":
    main()
