"""G0/G1/G2 共用提示词模板。

模板本身不随实验组变化，唯一变量是【参考资料】内容：
  G0 无检索内容；G1 为条文切片；G2 为条文切片 + 一跳图谱上下文。
PROMPT_VERSION 变更必须记录到 CHANGELOG.md。
"""
from __future__ import annotations

from typing import Any

PROMPT_VERSION = "1.0"

SYSTEM_PROMPT = """你是国土资源法律法规问答助手，服务对象是基层执法人员与公众。
回答规则：
1. 如果提供了【参考资料】，必须优先依据资料作答，引用格式固定为《法规名称》第X条，并摘录条文原文关键句。
2. 如果资料中没有相关条文，明确回答“现有知识库中没有找到条文依据”，不得编造法规名称、条文号或条文内容。
3. 如果没有提供【参考资料】，依据你已有的知识回答，并说明内容可能存在时效性风险。
4. 如果问题前提与法律冲突、或要求引用不存在的条文，先指出问题，再拒绝按错误前提回答。
5. 使用简体中文，先给结论，再列依据，简洁分点。"""

USER_TEMPLATE = """【参考资料】
{context}

【问题】
{question}"""

NO_CONTEXT_PLACEHOLDER = "（本次未提供检索资料）"


def build_messages(question: str, evidence: list[dict[str, Any]], graph_context: str = "") -> list[dict[str, str]]:
    blocks: list[str] = []
    for idx, item in enumerate(evidence, start=1):
        citation = item.get("citation") or "（未知条文）"
        text = item.get("text") or ""
        graph_line = ""
        if item.get("graph"):
            graph_line = f"\n图谱要素：{item['graph']}"
        blocks.append(f"[{idx}] {citation}\n{text}{graph_line}")
    if graph_context:
        blocks.append(f"【知识图谱关联】\n{graph_context}")
    context = "\n\n".join(blocks) if blocks else NO_CONTEXT_PLACEHOLDER
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": USER_TEMPLATE.format(context=context, question=question)},
    ]


def format_graph_context(subgraph: dict[str, Any]) -> str:
    lines: list[str] = []
    for node in subgraph.get("nodes", []):
        parts = []
        if node.get("subjects"):
            parts.append("主体=" + "、".join(node["subjects"]))
        if node.get("actions"):
            parts.append("行为=" + "、".join(node["actions"]))
        if node.get("penalties"):
            parts.append("处罚=" + "、".join(node["penalties"]))
        if parts:
            lines.append(f"{node['citation']}：{'；'.join(parts)}")
    related = subgraph.get("related", [])
    if related:
        lines.append("关联法条：" + "、".join(node["citation"] for node in related))
    return "\n".join(lines)
