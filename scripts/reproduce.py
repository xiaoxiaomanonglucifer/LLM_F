"""一键复现脚本：采集 -> 切分 -> 三元组 -> 索引 -> 测试 -> 联调实验。

用法：
  python scripts/reproduce.py --embedding-model hashing --mock
  python scripts/reproduce.py --skip-collect --embedding-model models/bge-small-zh-v1.5
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description="R2 全流程一键复现")
    parser.add_argument("--skip-collect", action="store_true", help="跳过联网采集，复用 data/v1/raw")
    parser.add_argument("--skip-index", action="store_true", help="跳过索引重建")
    parser.add_argument("--embedding-model", default=None)
    parser.add_argument("--mock", action="store_true", help="实验阶段使用模拟生成器")
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args()

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_id = args.run_id or f"repro-{stamp}"
    log_dir = REPO_ROOT / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"reproduce_{stamp}.log"
    summary_path = log_dir / f"reproduce_{stamp}.json"

    steps: list[tuple[str, list[str]]] = []
    if not args.skip_collect:
        steps.append(("collect", [sys.executable, "-m", "legal_rag.corpus.collect", "--min-docs", "50"]))
    steps.append(("build_corpus", [sys.executable, "-m", "legal_rag.corpus.build"]))
    steps.append(("extract_triples", [sys.executable, "-m", "legal_rag.graph.extract"]))
    if not args.skip_index:
        cmd = [sys.executable, "-m", "legal_rag.index.build_index"]
        if args.embedding_model:
            cmd += ["--embedding-model", args.embedding_model]
        steps.append(("build_index", cmd))
    steps.append(("unit_tests", [sys.executable, "-m", "unittest", "discover", "-s", "tests"]))
    exp_cmd = [
        sys.executable,
        "-m",
        "legal_rag.pipeline.run_experiment",
        "--questions",
        "data/eval/dev/questions.jsonl",
        "--groups",
        "G0,G1,G2",
        "--run-id",
        run_id,
    ]
    if args.embedding_model:
        exp_cmd += ["--embedding-model", args.embedding_model]
    if args.mock:
        exp_cmd.append("--mock")
    steps.append(("dev_experiment", exp_cmd))

    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT / "src")
    env["PYTHONIOENCODING"] = "utf-8"

    results = []
    started_all = time.time()
    with log_path.open("w", encoding="utf-8") as log:
        for name, cmd in steps:
            print(f"[reproduce] {name}: {' '.join(cmd)}")
            log.write(f"\n===== {name} =====\n{' '.join(cmd)}\n")
            log.flush()
            started = time.time()
            proc = subprocess.run(cmd, cwd=REPO_ROOT, env=env, capture_output=True, text=True, encoding="utf-8")
            log.write(proc.stdout or "")
            if proc.stderr:
                log.write("\n[stderr]\n" + proc.stderr)
            log.flush()
            status = "ok" if proc.returncode == 0 else f"failed({proc.returncode})"
            results.append(
                {"step": name, "status": status, "returncode": proc.returncode, "elapsed_sec": round(time.time() - started, 1)}
            )
            print(f"[reproduce] {name}: {status} ({results[-1]['elapsed_sec']}s)")
            if proc.returncode != 0:
                print(f"[reproduce] 失败，详见 {log_path}", file=sys.stderr)
                break

    summary = {
        "started_at": stamp,
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "elapsed_sec": round(time.time() - started_all, 1),
        "run_id": run_id,
        "embedding_model": args.embedding_model,
        "mock": args.mock,
        "steps": results,
        "log": str(log_path),
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[reproduce] 汇总：{summary_path}")
    if any(item["status"] != "ok" for item in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
