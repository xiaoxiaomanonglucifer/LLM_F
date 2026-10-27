"""图谱三元组 schema 与规则抽取。

三元组粒度：一条法条对应一条记录，字段为 主体（subjects）、行为（actions）、
处罚（penalties）。规则抽取是确定性兜底；GPU 环境可用 --method llm 切换为
大模型抽取，两者都写入同一格式，供 Neo4j 导入与离线图谱检索共用。
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SUBJECTS = [
    "县级以上地方人民政府自然资源主管部门",
    "县级以上人民政府自然资源主管部门",
    "县级以上人民政府农业农村主管部门",
    "县级以上人民政府水行政主管部门",
    "县级以上人民政府生态环境主管部门",
    "县级以上人民政府林业草原主管部门",
    "县级以上人民政府",
    "省级以上人民政府",
    "国务院自然资源主管部门",
    "国务院农业农村主管部门",
    "国务院",
    "自然资源主管部门",
    "农业农村主管部门",
    "水行政主管部门",
    "生态环境主管部门",
    "林业草原主管部门",
    "乡镇人民政府",
    "村民委员会",
    "农村集体经济组织",
    "不动产登记机构",
    "建设单位",
    "施工单位",
    "采矿权人",
    "探矿权人",
    "海域使用权人",
    "土地使用者",
    "承包方",
    "发包方",
    "任何单位和个人",
]

ACTIONS = [
    "审批", "批准", "审核", "征收", "征用", "补偿", "安置", "登记", "确权",
    "出让", "转让", "出租", "抵押", "划拨", "许可", "规划", "开采", "勘查",
    "保护", "监督", "检查", "查处", "处罚", "强制执行", "收回", "拆除",
    "没收", "复垦", "占用", "转用", "使用", "备案", "公告", "听证", "复议",
]

PENALTY_PATTERNS = [
    r"(?:罚款|处以罚款)[^。；]{0,24}?\d[\d,.]*\s*(?:万元|元)",
    r"责令[^。；]{0,32}",
    r"没收[^。；]{0,32}",
    r"吊销[^。；]{0,24}",
    r"依法追究刑事责任",
    r"给予[^。；]{0,16}处分",
]

_PENALTY_RE = [re.compile(p) for p in PENALTY_PATTERNS]


@dataclass
class Triple:
    article_id: str
    citation: str
    law_title: str
    subjects: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    penalties: list[str] = field(default_factory=list)
    method: str = "rule"
    model: str = ""
    extracted_at: str = ""

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _dedupe_longest(items: list[str], text: str) -> list[str]:
    matched = sorted({s for s in items if s in text}, key=len, reverse=True)
    kept: list[str] = []
    for s in matched:
        if not any(s in longer for longer in kept):
            kept.append(s)
    return kept


def extract_rule_based(article: dict[str, Any]) -> Triple | None:
    text = article["text"]
    subjects = _dedupe_longest(SUBJECTS, text)
    actions = _dedupe_longest(ACTIONS, text)
    penalties: list[str] = []
    for pattern in _PENALTY_RE:
        for match in pattern.finditer(text):
            snippet = match.group(0).strip()
            if snippet and snippet not in penalties:
                penalties.append(snippet)
    if not subjects and not actions and not penalties:
        return None
    return Triple(
        article_id=article["article_id"],
        citation=article["citation"],
        law_title=article["law_title"],
        subjects=subjects,
        actions=actions,
        penalties=penalties,
        method="rule",
        extracted_at=_now(),
    )


def iter_articles(path: Path):
    with Path(path).open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                yield json.loads(line)
