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

PENALTY_TYPES = [
    ("没收违法所得", ("没收违法所得",)),
    ("没收实物", ("没收实物",)),
    ("责令退还", ("责令退还",)),
    ("限期拆除", ("限期拆除",)),
    ("责令改正", ("责令改正",)),
    ("责令停止", ("责令停止",)),
    ("吊销许可证", ("吊销",)),
    ("追究刑事责任", ("刑事责任",)),
    ("行政处分", ("行政处分", "处分")),
    ("罚款", ("罚款",)),
    ("没收", ("没收",)),
    ("警告", ("警告",)),
    ("记过", ("记过",)),
    ("记大过", ("记大过",)),
    ("降级", ("降级",)),
    ("撤职", ("撤职",)),
    ("开除", ("开除",)),
]

_PENALTY_ONLY_ACTIONS = {"罚款", "没收", "没收违法所得", "吊销", "行政处分", "追究刑事责任"}

_SUBJECT_SUFFIXES = (
    "政府", "部门", "机构", "单位", "组织", "企业", "公司", "权利人", "当事人",
    "人", "委员会", "银行", "村", "组", "机关", "院", "者", "中心", "站", "所",
)

_ACTION_PREFIXES = ("不得", "禁止", "可以", "应当", "必须", "予以", "依法")
_NEGATIVE_PREFIXES = ("未", "不", "没有", "无")
_ACTION_PENALTY_TERMS = ("罚款", "没收", "吊销", "处分", "刑事责任")

_PENALTY_HINTS = (
    "罚款", "责令", "没收", "拆除", "吊销", "处分", "刑事责任", "警告",
    "记过", "降级", "撤职", "开除", "追责", "赔偿", "改正", "停止",
)


def _looks_like_subject(value: str) -> bool:
    if value in SUBJECTS:
        return True
    if value.endswith("的") or value.endswith("时") or value.endswith("间"):
        return False
    return any(value.endswith(suffix) for suffix in _SUBJECT_SUFFIXES)


def _normalize_action(value: str) -> str:
    for prefix in _ACTION_PREFIXES:
        if value.startswith(prefix) and len(value) > len(prefix):
            return value[len(prefix):]
    return value


def _canonical_actions(value: str) -> list[str]:
    return [action for action in ACTIONS if action in value and action not in _PENALTY_ONLY_ACTIONS]


def _looks_like_penalty(value: str) -> bool:
    if value.startswith(("不得", "禁止", "应当", "可以")):
        return False
    return any(hint in value for hint in _PENALTY_HINTS)


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


def _squash(text: str) -> str:
    return re.sub(r"\s+", "", text)


def _present(value: str, text: str) -> bool:
    return value in text or _squash(value) in _squash(text)


def _clean_values(values: Any, limit: int = 8) -> list[str]:
    if not isinstance(values, list):
        return []
    cleaned: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        item = re.sub(r"\s+", " ", value).strip(" \t\r\n,，;；。[]{}'\"")
        if not item or item.lower() in {"none", "null", "n/a", "无", "[]", "{}"}:
            continue
        if len(item) > 60:
            continue
        if item not in cleaned:
            cleaned.append(item)
        if len(cleaned) >= limit:
            break
    return cleaned


def _dedupe_present(items: list[str], text: str) -> list[str]:
    matched = sorted({s for s in items if _present(s, text)}, key=len, reverse=True)
    kept: list[str] = []
    for item in matched:
        if not any(item in longer for longer in kept):
            kept.append(item)
    return kept


def _dedupe_subsumed(items: list[str]) -> list[str]:
    kept: list[str] = []
    for item in sorted(dict.fromkeys(items), key=len, reverse=True):
        if not any(item in longer for longer in kept):
            kept.append(item)
    return kept


def sanitize_llm_triple(article: dict[str, Any], data: dict[str, Any], model: str = "") -> Triple:
    """把模型输出回验到原文，丢弃示例泄漏和原文没有的实体。"""
    text = article["text"]
    if article.get("article_num") == 1 and "为了" in text[:30]:
        return Triple(
            article_id=article["article_id"],
            citation=article["citation"],
            law_title=article["law_title"],
            method="llm",
            model=model,
            extracted_at=_now(),
        )

    subjects = _dedupe_present(
        [item for item in _clean_values(data.get("subjects"), 8) if _looks_like_subject(item)],
        text,
    )

    actions: list[str] = []
    for raw in _clean_values(data.get("actions"), 8):
        if raw.startswith(_NEGATIVE_PREFIXES):
            actions.extend(_canonical_actions(raw))
            continue
        item = _normalize_action(raw)
        if len(item) > 10:
            actions.extend(_canonical_actions(item))
            continue
        if any(term in item for term in _ACTION_PENALTY_TERMS) or item in _PENALTY_ONLY_ACTIONS:
            continue
        actions.append(item)
    actions = _dedupe_present(actions, text)

    penalties: list[str] = []
    for item in _clean_values(data.get("penalties"), 8):
        matched = [
            name
            for name, keys in PENALTY_TYPES
            if any(key in item and key in text for key in keys)
        ]
        if matched:
            penalties.extend(matched)
        elif len(item) <= 30 and _looks_like_penalty(item) and _present(item, text):
            penalties.append(item)
    if any(item != "行政处分" for item in penalties):
        penalties = [item for item in penalties if item != "行政处分"]
    penalties = _dedupe_subsumed(penalties)

    return Triple(
        article_id=article["article_id"],
        citation=article["citation"],
        law_title=article["law_title"],
        subjects=subjects,
        actions=actions,
        penalties=penalties,
        method="llm",
        model=model,
        extracted_at=_now(),
    )


def all_empty(triple: Triple) -> bool:
    return not (triple.subjects or triple.actions or triple.penalties)


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
