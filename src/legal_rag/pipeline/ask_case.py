"""v2 案件单题问答 CLI：输出五步中间结果、引用与类案。

用法：
  export LEGAL_RAG_SETTINGS=config/settings_v2.yaml
  python -m legal_rag.pipeline.ask_case "未经批准占用永久基本农田建厂房会怎么罚" --group G2
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ..cases.case_qa import CASE_GROUPS, CaseQASystem
from ..config import load_settings
from ..generation.llm_client import LLMClient, MockLLMClient
from ..retrieval.hybrid import load_articles
from .run_case_experiment import _build_case_runtime


def answer(
    question: str,
    group: str = "G2",
    mock: bool = False,
    embedding_model: str | None = None,
    exclude_case_id: str | None = None,
) -> dict:
    cfg = load_settings()
    if "cases_dir" not in cfg["paths"]:
        raise SystemExit("当前配置没有案例层，请设置 LEGAL_RAG_SETTINGS=config/settings_v2.yaml")
    retriever, _law_graph, case_retriever, case_graph, _manifest = _build_case_runtime(
        cfg, [group], embedding_model
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
    return system.answer(question, group, exclude_case_id=exclude_case_id)


def main() -> None:
    parser = argparse.ArgumentParser(description="v2 案件五步问答单题入口")
    parser.add_argument("question")
    parser.add_argument("--group", default="G2", choices=list(CASE_GROUPS))
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--embedding-model", default=None)
    parser.add_argument("--exclude-case-id", default=None)
    parser.add_argument("--json", action="store_true", help="输出完整 JSON 结果")
    args = parser.parse_args()

    result = answer(args.question, args.group, args.mock, args.embedding_model, args.exclude_case_id)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=1))
        return

    print(result.get("llm_answer") or result["answer"])
    print("\n===== 五步中间结果 =====")
    for key in ("facts", "characterization", "law_application", "discretion", "conclusion"):
        print(f"\n## {key}")
        print(json.dumps(result["steps"][key], ensure_ascii=False, indent=1))
    print("\n===== 引用 =====")
    for item in result["steps"]["law_application"]["evidence"]:
        print(f"- {item.get('citation')}（{item.get('role')}，来源={item.get('source')}）")
    if not result["steps"]["law_application"]["evidence"]:
        print("- 本组未启用条文检索")
    print("\n===== 类案 =====")
    for hit in result["similar_cases"]:
        print(f"- {hit.get('case_id')} {hit.get('decision_no')}（score={hit.get('score')}）")
    if not result["similar_cases"]:
        print("- 无")
    print(
        f"\n置信度：{result['confidence']}；提示词哈希：{result.get('prompt_hash')}；"
        f"耗时：{result.get('latency_sec')}s",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
