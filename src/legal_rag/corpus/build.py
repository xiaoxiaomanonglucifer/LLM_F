"""把 data/v1/raw 下的 docx 解析成按条文本块，产出 documents.jsonl / articles.jsonl。"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import ensure_dir, load_settings
from .article_parser import parse_law
from .docx_reader import read_docx

PARSER_VERSION = "1.0"


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _write_json(path: Path, data: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


def build(min_articles_per_doc: int = 3) -> dict[str, Any]:
    cfg = load_settings()
    paths = cfg["paths"]
    data_dir = Path(paths["data_dir"])
    manifest_path = Path(paths["manifest_file"])
    if not manifest_path.exists():
        raise SystemExit("找不到 manifest.json，请先运行采集：python -m legal_rag.corpus.collect")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    documents: list[dict[str, Any]] = []
    articles: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []

    for rec in manifest["documents"]:
        doc_id = rec["doc_id"]
        raw_path = Path(cfg["paths"]["raw_dir"]) / f"{doc_id}.docx"
        if not raw_path.exists():
            raise SystemExit(f"缺少原始文件：{raw_path}")

        parsed = parse_law(read_docx(raw_path), expected_title=rec["title"])
        indexed = parsed.article_count >= min_articles_per_doc
        doc_record = {
            "doc_id": doc_id,
            "title": rec["title"],
            "level": rec["level"],
            "domain": rec["domain"],
            "priority": rec.get("priority", "normal"),
            "flxz": rec.get("flxz"),
            "issuing_body": rec.get("issuing_body"),
            "promulgation_date": rec.get("promulgation_date"),
            "effective_date": rec.get("effective_date"),
            "bbbs": rec.get("bbbs"),
            "source_url": rec.get("source_url"),
            "raw_file": rec.get("raw_file"),
            "sha256": rec.get("sha256"),
            "article_count": parsed.article_count,
            "char_count": parsed.char_count,
            "preamble_chars": len(parsed.preamble),
            "tail_chars": len(parsed.tail),
            "structure_issues": parsed.structure_issues,
            "indexed": indexed,
            "parser_version": PARSER_VERSION,
            "parsed_at": _now(),
        }
        documents.append(doc_record)
        if parsed.structure_issues:
            issues.append(
                {
                    "doc_id": doc_id,
                    "title": rec["title"],
                    "article_count": parsed.article_count,
                    "issues": parsed.structure_issues,
                }
            )
        if not indexed:
            print(f"[跳过] {doc_id} 仅解析到 {parsed.article_count} 条：{rec['title']}")
            continue

        seen: Counter[int] = Counter()
        for art in parsed.articles:
            seen[art.article_num] += 1
            suffix = "" if seen[art.article_num] == 1 else f"-{seen[art.article_num]}"
            articles.append(
                {
                    "article_id": f"{doc_id}#a{art.article_num:04d}{suffix}",
                    "doc_id": doc_id,
                    "law_title": rec["title"],
                    "level": rec["level"],
                    "domain": rec["domain"],
                    "priority": rec.get("priority", "normal"),
                    "article_no": art.article_no,
                    "article_num": art.article_num,
                    "chapter": art.chapter,
                    "section": art.section,
                    "text": art.text,
                    "body": art.body,
                    "citation": f"《{rec['title']}》{art.article_no}",
                    "effective_date": rec.get("effective_date"),
                    "promulgation_date": rec.get("promulgation_date"),
                    "source_url": rec.get("source_url"),
                    "sha256": rec.get("sha256"),
                }
            )

    articles.sort(key=lambda a: (a["doc_id"], a["article_num"], a["article_id"]))

    documents_path = Path(paths["documents_file"])
    articles_path = Path(paths["articles_file"])
    ensure_dir(documents_path.parent)
    with documents_path.open("w", encoding="utf-8") as f:
        for d in sorted(documents, key=lambda x: x["doc_id"]):
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    with articles_path.open("w", encoding="utf-8") as f:
        for a in articles:
            f.write(json.dumps(a, ensure_ascii=False) + "\n")

    indexed_docs = [d for d in documents if d["indexed"]]
    by_level = Counter(d["level"] for d in indexed_docs)
    by_domain = Counter(d["domain"] for d in indexed_docs)
    lengths = [len(a["text"]) for a in articles]
    stats = {
        "generated_at": _now(),
        "parser_version": PARSER_VERSION,
        "documents_total": len(documents),
        "documents_indexed": len(indexed_docs),
        "documents_below_min_articles": len(documents) - len(indexed_docs),
        "articles_total": len(articles),
        "chars_total": sum(lengths),
        "article_chars_avg": round(sum(lengths) / len(lengths), 1) if lengths else 0,
        "article_chars_min": min(lengths) if lengths else 0,
        "article_chars_max": max(lengths) if lengths else 0,
        "articles_per_doc_avg": round(len(articles) / len(indexed_docs), 1) if indexed_docs else 0,
        "documents_by_level": dict(sorted(by_level.items())),
        "documents_by_domain": dict(sorted(by_domain.items())),
        "structure_issues": len(issues),
        "issue_details": issues,
    }
    _write_json(Path(paths["corpus_stats_file"]), stats)

    print(
        f"语料构建完成：可索引法规 {stats['documents_indexed']} 部，"
        f"按条切分 {stats['articles_total']} 条，"
        f"共 {stats['chars_total']/10000:.1f} 万字；"
        f"条均 {stats['article_chars_avg']} 字；结构告警 {stats['structure_issues']} 部。"
    )
    print(f"documents: {documents_path}")
    print(f"articles : {articles_path}")
    print(f"stats    : {paths['corpus_stats_file']}")
    return stats


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="构建按条切分语料")
    parser.add_argument("--min-articles-per-doc", type=int, default=3)
    args = parser.parse_args()
    build(min_articles_per_doc=args.min_articles_per_doc)
