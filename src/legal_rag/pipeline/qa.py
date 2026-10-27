"""问答流水线：检索证据 -> 组装提示词 -> 生成带引用答案。"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from ..generation.prompts import build_messages, format_graph_context
from ..retrieval.hybrid import RetrievalHit

GROUPS: dict[str, list[str]] = {
    "G0": [],
    "G1": ["dense", "bm25"],
    "G2": ["dense", "bm25", "graph"],
}

REFUSAL_PATTERNS = [
    "没有找到条文依据",
    "无条文依据",
    "没有相关条文",
    "未找到相关",
    "无法回答",
    "不能提供",
    "不存在该条文",
    "没有这样的条文",
]
_REFUSAL_RE = re.compile("|".join(REFUSAL_PATTERNS))


def is_refusal(answer: str) -> bool:
    return bool(_REFUSAL_RE.search(answer or ""))


def _evidence_dict(hit: RetrievalHit, triple: dict[str, Any] | None) -> dict[str, Any]:
    record = hit.record or {}
    item = {
        "article_id": hit.article_id,
        "citation": record.get("citation", ""),
        "law_title": record.get("law_title", ""),
        "text": record.get("text", ""),
        "score": round(hit.score, 6),
        "ranks": hit.ranks,
    }
    if triple:
        parts = []
        if triple.get("subjects"):
            parts.append("主体=" + "、".join(triple["subjects"]))
        if triple.get("actions"):
            parts.append("行为=" + "、".join(triple["actions"]))
        if triple.get("penalties"):
            parts.append("处罚=" + "、".join(triple["penalties"]))
        if parts:
            item["graph"] = "；".join(parts)
    return item


class LegalQASystem:
    def __init__(self, cfg: dict[str, Any], retriever, llm, graph_index=None) -> None:
        self.cfg = cfg
        self.retriever = retriever
        self.llm = llm
        self.graph_index = graph_index
        self.top_k = cfg["retrieval"]["top_k"]

    def answer(self, question: str, group: str) -> dict[str, Any]:
        if group not in GROUPS:
            raise ValueError(f"未知实验组：{group}")
        signals = GROUPS[group]
        hits = (
            self.retriever.retrieve(question, signals, top_k=self.top_k) if signals else []
        )
        triples_by_article = self.graph_index.by_article if self.graph_index else {}
        evidence = [_evidence_dict(hit, triples_by_article.get(hit.article_id)) for hit in hits]

        graph_context = ""
        if group == "G2" and self.graph_index and hits:
            graph_context = format_graph_context(
                self.graph_index.subgraph([hit.article_id for hit in hits])
            )

        messages = build_messages(question, evidence, graph_context)
        result = self.llm.chat(messages)
        prompt_hash = hashlib.sha256(
            json.dumps(messages, ensure_ascii=False).encode("utf-8")
        ).hexdigest()[:16]
        return {
            "question": question,
            "group": group,
            "signals": signals,
            "answer": result["text"],
            "refusal_rule_flag": is_refusal(result["text"]),
            "evidence": evidence,
            "graph_context": graph_context,
            "prompt_hash": prompt_hash,
            "prompt_version": None,  # 由 run_experiment 补
            "usage": result.get("usage", {}),
            "latency_sec": result.get("latency_sec"),
        }
