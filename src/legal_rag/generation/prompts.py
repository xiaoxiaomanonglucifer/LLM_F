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


CASE_PROMPT_VERSION = "2.0"

CASE_SYSTEM_PROMPT = """你是湖南省自然资源执法辅助系统，按法官办理非法占地案件的五步顺序作答：
1. 事实：只复述已给出的占地行为、面积、地类、项目性质、规划符合性，不补充未给出的事实。
2. 定性：判断是否属于《土地管理法》第七十七条的非法占用土地，区分未经批准占用与超过批准数量占用。
3. 法条：只引用【已核验法条】中的法规名称、条号和原文，不得引用未给出的条文。
4. 裁量：罚款金额只能使用【已核验计算】中的面积、费率与区间，不得自行改算或另造数字。
5. 结论：按“责令退还—没收或拆除—罚款”的顺序给出处理建议，并说明不确定性。
要求：使用简体中文；先结论后理由；每一步单独成段；类案只作参照，不得把类案结果直接当作本案结论。"""


def build_case_messages(result: dict[str, Any]) -> list[dict[str, str]]:
    steps = result.get("steps", {})
    facts = steps.get("facts", {})
    characterization = steps.get("characterization", {})
    law = steps.get("law_application", {})
    discretion = steps.get("discretion", {})
    evidence_lines = []
    for idx, item in enumerate(law.get("evidence", []), start=1):
        evidence_lines.append(
            f"[{idx}] {item.get('citation')}（{item.get('role')}，来源={item.get('source')}）\n"
            f"{item.get('text', '')[:600]}"
        )
    case_lines = []
    for hit in result.get("similar_cases", [])[:5]:
        case_lines.append(
            f"- {hit.get('decision_no')}（{hit.get('agency')}，{hit.get('decision_date')}）："
            f"行为={'、'.join(hit.get('behavior') or [])}；面积={hit.get('area_m2')}㎡；"
            f"罚款={hit.get('fine_amount')}元；费率={hit.get('fine_rate')}；相似理由={'、'.join(hit.get('reasons') or [])}"
        )
    brackets = discretion.get("brackets") or []
    bracket_lines = [
        f"- {item['land_group']}：面积={item.get('area_m2')}㎡，费率={item.get('yuan_per_m2')}，金额={item.get('fine_range')}"
        for item in brackets
    ]
    context = f"""【问题】
{result.get('question', '')}

【已抽取事实】
行为={facts.get('behavior')}；面积={facts.get('area_m2')}㎡；地类={facts.get('land_use')}；
项目性质={facts.get('project_nature')}；规划符合性={facts.get('plan_conformity')}。

【已核验定性】
{characterization.get('illegal_occupation')}；行为类型={characterization.get('behavior')}；
违反条款={characterization.get('violated_article_ids')}。

【已核验法条】
{chr(10).join(evidence_lines) if evidence_lines else '（本组未启用条文检索）'}

【已核验计算】
{chr(10).join(bracket_lines) if bracket_lines else '（缺少地类面积，无法计算）'}
预测罚款区间={discretion.get('predicted_fine_range')}；类案费率={discretion.get('similar_rates')}；
版本提示={discretion.get('version_note')}

【参考类案】
{chr(10).join(case_lines) if case_lines else '（无相似案例）'}

【确定性草稿】
{result.get('answer', '')}
"""
    return [
        {"role": "system", "content": CASE_SYSTEM_PROMPT},
        {"role": "user", "content": context},
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
