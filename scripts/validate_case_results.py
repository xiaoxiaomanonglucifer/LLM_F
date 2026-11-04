"""按 docs/handoff_gpu_server.md §5 验收清单校验案件实验结果。

用法：
  python scripts/validate_case_results.py --run-dir results/case-main-v1
  python scripts/validate_case_results.py --run-dir results/smoke-server --allow-debug

退出码 0 表示全部通过；1 表示存在失败项。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_QUESTIONS = REPO_ROOT / "data/cases/v1/questions.jsonl"
DEFAULT_CASES = REPO_ROOT / "data/cases/v1/cases.jsonl"

GROUPS = ["G0", "G1", "G2", "G2-case", "G2-graph"]
RETRIEVAL_GROUPS = {"G1", "G2", "G2-case", "G2-graph"}
CASE_GROUPS = {"G2", "G2-graph"}
REQUIRED_FIELDS = [
    "question_id", "category", "question", "group", "repeat", "answer",
    "steps", "similar_cases", "citations", "prompt_hash", "prompt_version",
    "decoding_params", "usage", "latency_sec",
]
STEP_KEYS = {"facts", "characterization", "law_application", "discretion", "conclusion"}
DECODING = {"temperature": 0.1, "top_p": 0.9, "seed": 42, "max_tokens": 1024}


def load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def close(a, b, tol: float = 0.01) -> bool:
    return a is not None and b is not None and abs(float(a) - float(b)) <= tol


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


class Report:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.checks = 0

    def check(self, ok: bool, label: str) -> None:
        self.checks += 1
        if not ok:
            self.failures.append(label)

    def section(self, name: str) -> None:
        print(f"\n[{name}]")

    def summarize(self) -> int:
        print(f"\n共 {self.checks} 项检查，失败 {len(self.failures)} 项")
        for item in self.failures:
            print(f"  ✗ {item}")
        return 0 if not self.failures else 1


def citation_items(record: dict) -> list[dict]:
    items = record.get("citations") or []
    if items and isinstance(items[0], str):
        return [{"article_id": None, "citation": text, "score": None, "ranks": {}} for text in items]
    return items


def validate_meta(
    report: Report,
    meta: dict,
    allow_debug: bool,
    expected_questions: int,
    expected_cases: int,
    expected_graph: dict | None,
    expected_index_articles: int | None,
    questions_sha256: str | None,
) -> None:
    report.section("run_meta")
    report.check(bool(meta.get("git_commit")), "git_commit 为空")
    report.check(
        meta.get("questions_count") == expected_questions,
        f"questions_count {meta.get('questions_count')} != {expected_questions}",
    )
    report.check(
        meta.get("case_count") == expected_cases,
        f"case_count {meta.get('case_count')} != {expected_cases}",
    )
    if questions_sha256 and meta.get("questions_sha256"):
        report.check(
            meta.get("questions_sha256") == questions_sha256,
            "questions_sha256 与当前题库不一致",
        )
    graph = meta.get("case_graph") or {}
    if expected_graph:
        for key in ("cases", "nodes", "edges"):
            if expected_graph.get(key) is not None:
                report.check(
                    graph.get(key) == expected_graph[key],
                    f"案件图谱 {key}={graph.get(key)} != {expected_graph[key]}",
                )
    else:
        report.check(graph.get("cases") == expected_cases, f"案件图谱 cases != {expected_cases}")
        report.check(isinstance(graph.get("nodes"), int) and graph["nodes"] > 0, "案件图谱 nodes 非法")
        report.check(isinstance(graph.get("edges"), int) and graph["edges"] >= 0, "案件图谱 edges 非法")
    report.check(meta.get("prompt_version") == "2.0", "prompt_version != 2.0")
    if not allow_debug:
        report.check(meta.get("mock") is False, "mock != false")
        params = meta.get("decoding_params") or {}
        for key, value in DECODING.items():
            report.check(params.get(key) == value, f"decoding_params.{key} != {value}")
        report.check(params.get("model") not in {None, "", "mock"}, "decoding_params.model 不是真实模型")
        manifest = meta.get("index_manifest") or {}
        report.check(manifest.get("embedding_model") == "BAAI/bge-m3", "索引嵌入模型不是 BAAI/bge-m3")
        report.check(manifest.get("embedding_model_debug") is False, "索引仍为调试嵌入器")
        report.check(manifest.get("embedding_dim") == 1024, "索引维数不是 1024")
        if expected_index_articles is not None:
            report.check(
                manifest.get("article_count") == expected_index_articles,
                f"索引条数不是 {expected_index_articles}",
            )
        else:
            report.check(
                isinstance(manifest.get("article_count"), int) and manifest["article_count"] > 0,
                "索引条数非法",
            )
    else:
        print("  (--allow-debug：跳过 mock / 嵌入模型 / 解码参数检查)")


def validate_record(report: Report, record: dict, question: dict, cases: dict[str, dict]) -> None:
    qid, group = record.get("question_id"), record.get("group")
    tag = f"{group}/{qid}"
    for field in REQUIRED_FIELDS:
        if field not in record:
            report.failures.append(f"{tag} 缺少字段 {field}")
    steps = record.get("steps") or {}
    report.check(set(steps) == STEP_KEYS, f"{tag} steps 不是五步")
    if set(steps) != STEP_KEYS:
        return
    facts = steps["facts"]
    char = steps["characterization"]
    discretion = steps["discretion"]
    law = steps["law_application"]
    expected = question.get("expected") or {}

    items = citation_items(record)
    for item in items:
        if any(key not in item for key in ("article_id", "citation", "score", "ranks")):
            report.failures.append(f"{tag} citations 缺少 article_id/citation/score/ranks")
            break

    if not record.get("prompt_hash") or not record.get("prompt_version"):
        report.failures.append(f"{tag} prompt_hash/prompt_version 为空")
    if record.get("latency_sec") is None:
        report.failures.append(f"{tag} latency_sec 为空")

    if group == "G0":
        report.check(items == [], f"{tag} G0 不应有引用")
        report.check(record.get("similar_cases") == [], f"{tag} G0 不应有类案")
        report.check(discretion.get("predicted_fine_range") is None, f"{tag} G0 不应计算罚款区间")
        report.check(law.get("evidence") == [], f"{tag} G0 不应有法条证据")
        return

    report.check(record.get("similar_cases") == [] if group == "G1" else True, f"{tag} G1 不应有类案")
    if group == "G2-case":
        report.check(record.get("similar_cases") == [], f"{tag} G2-case 不应有类案")
    if group in CASE_GROUPS:
        similar = record.get("similar_cases") or []
        report.check(len(similar) <= 3, f"{tag} 类案超过 3 条")
        query_case = question.get("exclude_case_id") or question.get("case_id")
        report.check(
            not query_case or all(hit.get("case_id") != query_case for hit in similar),
            f"{tag} 类案包含查询案自身 {query_case}",
        )

    report.check(char.get("scope_status") == expected.get("scope_status"), f"{tag} scope_status 不符")
    if expected.get("behavior"):
        report.check(
            set(char.get("behavior") or []) == set(expected["behavior"]),
            f"{tag} behavior 不符：{char.get('behavior')}",
        )
    if expected.get("land_groups"):
        report.check(
            set(discretion.get("land_groups") or []) == set(expected["land_groups"]),
            f"{tag} land_groups 不符：{discretion.get('land_groups')}",
        )
    if expected.get("area_m2") is not None:
        report.check(close(facts.get("area_m2"), expected["area_m2"]), f"{tag} area_m2 不符")
    if "fine_range" in expected:
        target = expected["fine_range"]
        actual = discretion.get("predicted_fine_range")
        if target is None:
            report.check(actual is None, f"{tag} fine_range 应为 null，实际 {actual}")
        else:
            report.check(
                actual is not None and close(actual[0], target[0]) and close(actual[1], target[1]),
                f"{tag} fine_range 不符：{actual} != {target}",
            )
    if "partial_fine_range" in expected:
        target = expected["partial_fine_range"]
        actual = discretion.get("partial_fine_range")
        report.check(
            actual is not None and close(actual[0], target[0]) and close(actual[1], target[1]),
            f"{tag} partial_fine_range 不符：{actual}",
        )
    if expected.get("needs_land_type"):
        report.check(discretion.get("needs_land_type") is True, f"{tag} needs_land_type 应为 true")
    if "current_standard_applied" in expected:
        report.check(
            discretion.get("current_standard_applied") == expected["current_standard_applied"],
            f"{tag} current_standard_applied 不符",
        )
    for needle in expected.get("version_note_contains") or []:
        report.check(needle in (discretion.get("version_note") or ""), f"{tag} version_note 缺少「{needle}」")
    citations = [item.get("citation") or "" for item in items]
    for needle in expected.get("required_citations") or []:
        report.check(any(needle in text for text in citations), f"{tag} 引用缺少「{needle}」")
    if expected.get("required_text"):
        text = record.get("deterministic_answer") or ""
        report.check(expected["required_text"] in text, f"{tag} 确定性答案缺少「{expected['required_text']}」")

    if "actual_fine" in expected:
        case = cases.get(question.get("case_id") or "")
        if case is not None:
            report.check(close(case.get("fine_amount"), expected["actual_fine"]), f"{tag} 案卷罚款额与 expected 不符")
        if "fine_contained" in expected:
            actual_range = discretion.get("predicted_fine_range")
            contained = bool(
                actual_range
                and actual_range[0] <= expected["actual_fine"] <= actual_range[1]
            )
            report.check(contained == expected["fine_contained"], f"{tag} fine_contained 不符")


def main() -> None:
    parser = argparse.ArgumentParser(description="校验案件实验结果")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--questions", default=str(DEFAULT_QUESTIONS))
    parser.add_argument("--cases", default=str(DEFAULT_CASES))
    parser.add_argument("--graph-stats", default=None, help="案件图谱 stats.json；默认取 cases 同级的 graph/stats.json")
    parser.add_argument("--index-manifest", default=str(REPO_ROOT / "data/v2/index/index_manifest.json"))
    parser.add_argument("--expect-questions", type=int, default=None)
    parser.add_argument("--expect-cases", type=int, default=None)
    parser.add_argument("--expect-index-articles", type=int, default=None)
    parser.add_argument("--allow-debug", action="store_true", help="允许 mock / 调试索引（仅流程验证）")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    if not run_dir.is_absolute():
        run_dir = REPO_ROOT / run_dir
    questions_path = Path(args.questions)
    cases_path = Path(args.cases)
    meta = json.loads((run_dir / "run_meta.json").read_text(encoding="utf-8"))
    questions = {item["id"]: item for item in load_jsonl(questions_path)}
    cases = {item["case_id"]: item for item in load_jsonl(cases_path)}

    expected_questions = args.expect_questions or len(questions)
    expected_cases = args.expect_cases or len(cases)
    expected_graph = None
    graph_stats_path = Path(args.graph_stats) if args.graph_stats else cases_path.parent / "graph" / "stats.json"
    if graph_stats_path.exists():
        graph_stats = json.loads(graph_stats_path.read_text(encoding="utf-8"))
        expected_graph = {key: graph_stats.get(key) for key in ("cases", "nodes", "edges")}

    expected_index_articles = args.expect_index_articles
    if expected_index_articles is None:
        index_manifest_path = Path(args.index_manifest)
        if index_manifest_path.exists():
            expected_index_articles = json.loads(index_manifest_path.read_text(encoding="utf-8")).get("article_count")

    report = Report()
    validate_meta(
        report,
        meta,
        args.allow_debug,
        expected_questions,
        expected_cases,
        expected_graph,
        expected_index_articles,
        sha256_file(questions_path),
    )

    for group in meta.get("groups") or GROUPS:
        report.section(group)
        files = sorted(run_dir.glob(f"{group}_r*.jsonl"))
        report.check(bool(files), f"{group} 缺少结果文件")
        for path in files:
            records = load_jsonl(path)
            report.check(len(records) == len(questions), f"{path.name} 题目数 {len(records)} != {len(questions)}")
            for record in records:
                question = questions.get(record.get("question_id"))
                if question is None:
                    report.failures.append(f"{path.name} 未知题目 {record.get('question_id')}")
                    continue
                validate_record(report, record, question, cases)
        print(f"  已检查 {len(files)} 个文件")

    sys.exit(report.summarize())


if __name__ == "__main__":
    main()
