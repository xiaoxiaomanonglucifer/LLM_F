"""法规语料采集：精确标题解析 -> 详情 -> docx 下载 -> manifest。"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import REPO_ROOT, ensure_dir, load_catalog, load_settings
from .flk_client import FlkClient, FlkError

COLLECTOR_VERSION = "1.0"


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def collect(
    only: list[str] | None = None,
    force: bool = False,
    min_docs: int = 50,
) -> dict[str, Any]:
    cfg = load_settings()
    catalog = load_catalog()
    paths = cfg["paths"]
    raw_dir = ensure_dir(Path(paths["raw_dir"]))
    meta_dir = ensure_dir(Path(paths["meta_dir"]))
    manifest_path = Path(paths["manifest_file"])

    client = FlkClient(
        interval_sec=float(cfg["corpus"]["request_interval_sec"]),
        timeout_sec=int(cfg["corpus"]["request_timeout_sec"]),
        max_retries=int(cfg["corpus"]["max_retries"]),
        user_agent=cfg["corpus"]["user_agent"],
    )

    entries = catalog["documents"]
    if only:
        wanted = set(only)
        entries = [e for e in entries if e["id"] in wanted]
        unknown = wanted - {e["id"] for e in entries}
        if unknown:
            raise SystemExit(f"--only 中有未知 doc_id: {sorted(unknown)}")

    records: list[dict[str, Any]] = []
    missing: list[dict[str, str]] = []
    errors: list[dict[str, str]] = []

    for i, entry in enumerate(entries, 1):
        doc_id = entry["id"]
        title = entry["title"]
        raw_path = raw_dir / f"{doc_id}.docx"
        meta_path = meta_dir / f"{doc_id}.json"
        prefix = f"[{i:02d}/{len(entries):02d}] {doc_id}"

        if raw_path.exists() and meta_path.exists() and not force:
            meta = _load_json(meta_path)
            records.append(meta)
            print(f"{prefix} 已存在，跳过（sha256={meta['sha256'][:12]}）")
            continue

        try:
            hit = client.resolve_effective(title)
            if hit is None:
                print(f"{prefix} 未找到现行有效版本：{title}")
                missing.append({"doc_id": doc_id, "title": title, "reason": "no_effective_exact_match"})
                continue

            detail = client.detail(hit.bbbs)
            sha256 = client.download_docx(hit.bbbs, raw_path)
            record = {
                "doc_id": doc_id,
                "catalog_title": title,
                "title": hit.title,
                "level": entry["level"],
                "domain": entry["domain"],
                "priority": entry.get("priority", "normal"),
                "flxz": hit.flxz,
                "status_code": hit.sxx,
                "issuing_body": hit.zdjg_name or detail.get("zdjgName", ""),
                "promulgation_date": hit.gbrq or detail.get("gbrq"),
                "effective_date": hit.sxrq or detail.get("sxrq"),
                "bbbs": hit.bbbs,
                "source_url": f"https://flk.npc.gov.cn/detail?id={hit.bbbs}",
                "detail_file": meta_path.relative_to(REPO_ROOT).as_posix(),
                "raw_file": raw_path.relative_to(REPO_ROOT).as_posix(),
                "sha256": sha256,
                "bytes": raw_path.stat().st_size,
                "flk_oss_word_path": (detail.get("ossFile") or {}).get("ossWordPath"),
                "collected_at": _now(),
                "collector_version": COLLECTOR_VERSION,
            }
            _write_json(meta_path, record)
            # 详情单独存档，保留 OSS 路径与目录树，便于复核
            _write_json(meta_dir / f"{doc_id}.detail.json", detail)
            records.append(record)
            print(
                f"{prefix} OK  {hit.title} | {hit.flxz} | 公布 {hit.gbrq} | "
                f"{record['bytes']/1024:.0f} KB | sha={sha256[:12]}"
            )
        except (FlkError, ValueError, OSError) as exc:
            print(f"{prefix} 失败：{exc}")
            errors.append({"doc_id": doc_id, "title": title, "error": str(exc)})
            time.sleep(1.0)

    manifest = {
        "version": catalog.get("version", "v1"),
        "as_of": catalog.get("as_of"),
        "generated_at": _now(),
        "collector_version": COLLECTOR_VERSION,
        "source": catalog.get("source"),
        "catalog_file": "config/corpus_catalog.yaml",
        "catalog_total": len(catalog["documents"]),
        "selected_total": len(entries),
        "collected_total": len(records),
        "missing": missing,
        "errors": errors,
        "documents": sorted(records, key=lambda r: r["doc_id"]),
    }
    _write_json(manifest_path, manifest)

    print(
        f"\n采集完成：成功 {len(records)} / 目标 {len(entries)}，"
        f"缺失 {len(missing)}，错误 {len(errors)}"
    )
    print(f"manifest: {manifest_path}")

    if len(records) < min_docs:
        raise SystemExit(
            f"有效法规只有 {len(records)} 部，低于最低要求 {min_docs} 部；"
            "请检查 catalog 或网络后重跑（已成功的会跳过）。"
        )
    return manifest


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="采集 flk.npc.gov.cn 法规语料")
    parser.add_argument("--only", nargs="*", help="只采集指定 doc_id")
    parser.add_argument("--force", action="store_true", help="忽略已下载文件，重新采集")
    parser.add_argument("--min-docs", type=int, default=50)
    args = parser.parse_args()
    collect(only=args.only, force=args.force, min_docs=args.min_docs)
