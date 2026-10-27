"""单条问答 CLI，供人工抽查与 Streamlit 演示复用。"""
from __future__ import annotations

import argparse
import sys

from ..config import load_settings
from ..generation.llm_client import LLMClient, MockLLMClient
from ..pipeline.qa import GROUPS, LegalQASystem
from ..pipeline.run_experiment import build_runtime


def answer(question: str, group: str = "G2", mock: bool = False, embedding_model: str | None = None) -> dict:
    cfg = load_settings()
    retriever, graph, _ = build_runtime(
        cfg,
        embedding_model,
        need_retrieval=group != "G0",
        need_graph=group == "G2",
    )
    llm = MockLLMClient() if mock else LLMClient(cfg)
    system = LegalQASystem(cfg, retriever, llm, graph)
    result = system.answer(question, group)
    result["prompt_version"] = "1.0"
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="单条法规问答")
    parser.add_argument("question")
    parser.add_argument("--group", default="G2", choices=list(GROUPS))
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--embedding-model", default=None)
    parser.add_argument("--show-evidence", action="store_true")
    args = parser.parse_args()

    result = answer(args.question, args.group, args.mock, args.embedding_model)
    print(result["answer"])
    citations = [item["citation"] for item in result["evidence"] if item["citation"]]
    if citations:
        print("\n检索证据：")
        for idx, item in enumerate(result["evidence"], start=1):
            print(f"  [{idx}] {item['citation']}  rrf={item['score']:.4f}  名次={item['ranks']}")
            if args.show_evidence:
                print("      " + item["text"].replace("\n", " ")[:160])
    if result["graph_context"]:
        print("\n图谱上下文：")
        print(result["graph_context"])
    print(f"\n拒答规则标记：{result['refusal_rule_flag']}；提示词哈希：{result['prompt_hash']}", file=sys.stderr)


if __name__ == "__main__":
    main()
