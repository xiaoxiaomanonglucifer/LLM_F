"""从湖南行政处罚决定书/台账中抽取结构化字段（规则版，可复核）。"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from ..config import load_settings

EXTRACTOR_VERSION = "1.0"

_WS = re.compile(r"[ \t\u3000\xa0]+")
_DECISION_NO = re.compile(
    r"[\u4e00-\u9fa5]{0,12}(?:罚字|罚决字?|罚决)\s*[\[\(（〔]?\s*(\d{4})\s*[\]\)）〕]?\s*第?\s*(\d+)\s*号"
)
_DATE_CN = re.compile(r"(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日")
_DATE_ISO = re.compile(r"(20\d{2})-(\d{1,2})-(\d{1,2})")
_AREA = re.compile(r"([\d,]+(?:\.\d+)?)\s*(?:平方米|㎡|m2|m²)")
_LAW = re.compile(r"《((?:[^《》]|《[^》]*》)+)》")
_ARTICLE = re.compile(r"第([一二三四五六七八九十百零〇\d]+)条")
_ARTICLE_LIST = re.compile(r"[、，和及]\s*(?:第)?([一二三四五六七八九十百零〇\d]+)条")

_LAND_TYPES = [
    "永久基本农田", "基本农田", "水田", "旱地", "水浇地", "一般耕地", "耕地",
    "其他园地", "园地", "林地", "其他草地", "草地", "坑塘水面", "村庄",
    "采矿用地", "建设用地", "未利用地", "其他地类", "其他土地", "设施农用地", "宅基地",
]
_LAND_RE = re.compile(
    "(" + "|".join(_LAND_TYPES) + r")(?![）)])([^。；\n、，,]{0,18}?)([\d,]+(?:\.\d+)?)\s*(?:平方米|㎡|m2|m²)"
)
_AREA_LAND_RE = re.compile(
    r"([\d,]+(?:\.\d+)?)\s*(?:平方米|㎡|m2|m²)\s*(?:的)?(" + "|".join(_LAND_TYPES) + ")"
)
_RATE_RES = [
    re.compile(r"每平方米\s*([\d,]+(?:\.\d+)?)\s*元"),
    re.compile(r"([\d,]+(?:\.\d+)?)\s*元\s*/\s*(?:平方米|㎡|m2|m²)"),
    re.compile(r"([\d,]+(?:\.\d+)?)\s*元\s*[×xX*]\s*"),
    re.compile(r"[×xX*]\s*([\d,]+(?:\.\d+)?)\s*元"),
]
_RATE_AREA_PAIR = re.compile(
    r"([\d,]+(?:\.\d+)?)\s*(?:平方米|㎡|m2|m²)?\s*[×xX*]\s*([\d,]+(?:\.\d+)?)\s*元?"
)
_FINE_PATTERNS = [
    re.compile(r"(?:共计|合计|总计)?(?:罚款|处罚款)(?:人民币)?[：:]?\s*([\d,]+(?:\.\d+)?)\s*元"),
    re.compile(r"(?:计|共计|合计)(?:人民币)?[：:]?\s*([\d,]+(?:\.\d+)?)\s*元"),
]
_AMOUNT_YUAN = re.compile(r"([\d,]+(?:\.\d+)?)\s*元")

OLD_ARTICLE_ALIASES = {
    ("law-land-admin", 76): 77,
    ("law-land-admin", 80): 81,
    ("reg-land-admin", 42): 57,
    ("reg-land-admin", 43): 59,
}
OLD_VERSION_CUTOFF = {"law-land-admin": 2004, "reg-land-admin": 2014}

_TITLE_ALIASES = {
    "土地管理法": "law-land-admin",
    "中华人民共和国土地管理法": "law-land-admin",
    "土地管理法实施条例": "reg-land-admin",
    "中华人民共和国土地管理法实施条例": "reg-land-admin",
    "行政处罚法": "law-admin-penalty",
    "中华人民共和国行政处罚法": "law-admin-penalty",
    "城乡规划法": "law-urban-rural-planning",
    "中华人民共和国城乡规划法": "law-urban-rural-planning",
    "基本农田保护条例": "reg-basic-farmland",
    "土地复垦条例": "reg-land-reclamation",
    "湖南省实施中华人民共和国土地管理法办法": "hn-land-admin-implementation",
    "湖南省基本农田保护条例": "hn-basic-farmland",
    "湖南省土地监察条例": "hn-land-supervision",
    "湖南省土地开发整理条例": "hn-land-development-consolidation",
    "湖南省实施中华人民共和国城乡规划法办法": "hn-urban-rural-planning-implementation",
}


def clean_text(text: str) -> str:
    text = text.replace("\xa0", " ").replace("\u3000", " ")
    lines = [_WS.sub(" ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def normalize_title(title: str) -> str:
    title = re.sub(r"[《》〈〉()（）\[\]〔〕\s]", "", title)
    return re.sub(r"（[^）]*）|\([^)]*\)", "", title)


def cn_to_int(text: str) -> int | None:
    if text.isdigit():
        return int(text)
    digits = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
              "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    units = {"十": 10, "百": 100, "千": 1000}
    total, current = 0, 0
    for ch in text:
        if ch in digits:
            current = digits[ch]
        elif ch in units:
            total += (current or 1) * units[ch]
            current = 0
        else:
            return None
    return total + current


def _to_float(text: str) -> float | None:
    try:
        return float(text.replace(",", ""))
    except (TypeError, ValueError):
        return None


def _round2(value: float | None) -> float | None:
    return round(value, 2) if value is not None else None


def _first(patterns: list[str], text: str, flags: int = 0) -> re.Match[str] | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags)
        if match:
            return match
    return None


def _extract_date(text: str, fallback: str | None = None) -> str | None:
    matches = list(_DATE_CN.finditer(text))
    if matches:
        y, m, d = matches[-1].groups()
        return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
    matches = list(_DATE_ISO.finditer(text))
    if matches:
        y, m, d = matches[-1].groups()
        return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
    return fallback


def _extract_decision_no(text: str, hint: str | None = None) -> str | None:
    if hint:
        return hint
    match = _DECISION_NO.search(text)
    if match:
        return re.sub(r"\s+", "", match.group(0))
    return None


def _extract_party(text: str) -> dict[str, Any]:
    patterns = [
        r"被处罚(?:人|单位)[：:]\s*([^\n，。；]{2,60})",
        r"行政相对人[：:]\s*([^\n，。；]{2,60})",
        r"^([\u4e00-\u9fa5]{2,30}(?:公司|管理所|委员会|服务中心|办事处|人民政府|自然资源局|执法局|中心|站|院|厂|场|合作社|村委会|居委会))[：:]",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.M)
        if match:
            name = match.group(1).strip()
            is_unit = bool(re.search(r"公司|管理所|委员会|中心|局|站|院|厂|场|社|村|政府", name))
            return {"type": "单位" if is_unit else "个人", "name": name}
    return {"type": "未知", "name": ""}


def _mask_party(party: dict[str, Any]) -> dict[str, Any]:
    name = party.get("name") or ""
    if party.get("type") == "个人" and name:
        masked = name[0] + "某" if len(name) <= 3 else name[0] + "某" + name[-1]
    elif party.get("type") == "单位" and name:
        masked = name
    else:
        masked = "未知"
    return {**party, "name_masked": masked}


def _extract_area(text: str) -> float | None:
    values = [_to_float(m.group(1)) for m in _AREA.finditer(text)]
    values = [v for v in values if v and v > 0]
    return max(values) if values else None


def _land_group(land_type: str) -> str:
    if "永久基本农田" in land_type or land_type == "基本农田":
        return "永久基本农田"
    if land_type in {"水田", "旱地", "水浇地", "一般耕地", "耕地"}:
        return "其他耕地"
    return "其他土地"


def _extract_land_use(text: str) -> list[dict[str, Any]]:
    seen: set[tuple[str, float]] = set()
    result: list[dict[str, Any]] = []

    def add(land_type: str, area: float | None) -> None:
        if not area or area <= 0:
            return
        key = (land_type, round(area, 2))
        if key in seen:
            return
        seen.add(key)
        result.append({"type": land_type, "group": _land_group(land_type), "area_m2": area})

    for match in _LAND_RE.finditer(text):
        land_type, connector, area_text = match.group(1), match.group(2), match.group(3)
        if "以外" in connector:
            continue
        add(land_type, _to_float(area_text))
    for match in _AREA_LAND_RE.finditer(text):
        add(match.group(2), _to_float(match.group(1)))
    # “园地面积315、林地面积163、其他土地面积69平方米”共用末尾单位
    for sentence in re.split(r"[。；\n]", text):
        items = re.findall(
            "(" + "|".join(_LAND_TYPES) + r")面积([\d,]+(?:\.\d+)?)", sentence
        )
        if len(items) >= 2 and re.search(r"平方米|㎡|m2|m²", sentence):
            for land_type, area_text in items:
                add(land_type, _to_float(area_text))
    # “园地（其他园地）1062㎡”会同时提出园地和其他园地，保留更具体的一项
    return [
        item
        for item in result
        if not any(
            other is not item
            and abs(other["area_m2"] - item["area_m2"]) < 0.005
            and item["type"] != other["type"]
            and item["type"] in other["type"]
            for other in result
        )
    ]


def _extract_fine(text: str) -> float | None:
    candidates: list[float] = []
    for pattern in _FINE_PATTERNS:
        for match in pattern.finditer(text):
            value = _to_float(match.group(1))
            if value and value > 0:
                candidates.append(value)
    if candidates:
        return max(candidates)
    fallback = [_to_float(m.group(1)) for m in _AMOUNT_YUAN.finditer(text)]
    fallback = [v for v in fallback if v and v > 0]
    return max(fallback) if fallback else None


def _extract_rates(text: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, float]] = set()
    for pattern in _RATE_RES:
        for match in pattern.finditer(text):
            rate = _to_float(match.group(1))
            if not rate or rate <= 0:
                continue
            prefix = text[max(0, match.start() - 45):match.start()]
            prefix = re.sub(r"[（(]含[^）)]*[）)]", "", prefix)
            land = "未知"
            best_end = -1
            for candidate in _LAND_TYPES:
                pos = prefix.rfind(candidate)
                if pos < 0:
                    continue
                end = pos + len(candidate)
                if end > best_end or (end == best_end and len(candidate) > len(land)):
                    land = candidate
                    best_end = end
            key = (land, rate)
            if key in seen:
                continue
            seen.add(key)
            result.append({"land": land, "group": _land_group(land) if land != "未知" else "未知", "yuan_per_m2": rate})
    return result


def _extract_behavior(text: str) -> list[str]:
    behaviors: list[str] = []
    if re.search(r"未按(?:照)?批准的?用途|不按照批准的用途", text):
        behaviors.append("未按批准用途使用土地")
    if re.search(r"超过批准|超出批准|超批准|超道路用地红线|批东占西|少批多占|未按(?:照)?批准红线", text):
        behaviors.append("超过批准数量占用土地")
    unauthorized = (
        re.search(r"未经[^。；\n]{0,30}(?:批准|审批)", text)
        or re.search(r"未取得[^。；\n]{0,30}(?:用地手续|批准手续|审批手续|合法用地)", text)
        or re.search(r"未办理[^。；\n]{0,30}(?:审批|批准|用地手续)", text)
    )
    occupation = re.search(r"占用|占地|用地|建设|修建|施工|动工|建成", text)
    if unauthorized and occupation:
        behaviors.append("未经批准占用土地")
    elif (
        "未按批准用途使用土地" not in behaviors
        and re.search(r"擅自[^。；\n]{0,20}(?:占用|占地|建设|修建|施工|动工|建成)", text)
    ):
        behaviors.append("未经批准占用土地")
    if "临时用地" in text:
        behaviors.append("临时用地")
    if "设施农用地" in text:
        behaviors.append("设施农用地")
    return list(dict.fromkeys(behaviors))


def _extract_penalty_types(text: str) -> list[str]:
    result = []
    if re.search(r"责令[^。；\n]{0,60}退还|退还[^。；\n]{0,12}土地", text):
        result.append("责令退还")
    if "拆除" in text:
        result.append("限期拆除")
    if "没收" in text:
        result.append("没收")
    if "罚款" in text:
        result.append("罚款")
    if re.search(r"给予处分|行政处分", text):
        result.append("处分")
    if "移送" in text:
        result.append("移送")
    return result


def _extract_factors(text: str) -> list[str]:
    mapping = {
        "积极配合调查": r"积极配合|主动配合",
        "未造成严重后果": r"未造成严重后果",
        "初次违法": r"初次违法",
        "主动改正": r"及时改正|主动改正|主动消除",
        "占用永久基本农田": r"永久基本农田",
        "面积较大": r"面积较大",
        "从轻或减轻": r"从轻|减轻处罚",
    }
    return [label for label, pattern in mapping.items() if re.search(pattern, text)]


def _extract_project_nature(text: str) -> str:
    if re.search(r"非公益", text):
        return "非公益"
    if re.search(r"公益项目|公益性", text):
        return "公益"
    return "未知"


def _extract_law_version(text: str) -> str:
    match = re.search(r"(20\d{2})\s*(?:年[^）)。；]{0,16})?(?:修正|修订)", text)
    return f"{match.group(1)}年修正/修订" if match else "未知"


def _extract_penalty_section(text: str) -> str:
    decision = re.search(r"(?:作出如下行政处罚(?:决定)?|处罚决定如下|拟责令|现责令)", text)
    if not decision:
        starts = list(re.finditer(r"(?:根据|依据|依照|参照)", text))
        return text[starts[-1].start():] if starts else text
    para_start = text.rfind("\n", 0, decision.start()) + 1
    before = text[para_start:decision.start()]
    starts = list(re.finditer(r"(?:根据|依据|依照|参照)", before))
    start = para_start + starts[0].start() if starts else decision.start()
    tail = text[start:]
    end = len(tail)
    for marker in (
        "行政处罚履行方式", "你公司应自", "你单位应自", "限你公司", "限你单位",
        "缴纳罚款", "到期不缴纳", "本决定送达",
    ):
        pos = tail.find(marker)
        if pos > 0:
            end = min(end, pos)
    return tail[:end]


def _select_land_use(facts_text: str, penalty_text: str, area: float | None) -> list[dict[str, Any]]:
    candidates = [
        items for items in (_extract_land_use(facts_text), _extract_land_use(penalty_text)) if items
    ]
    if not candidates:
        return []
    if area:
        for items in candidates:
            if abs(sum(item["area_m2"] for item in items) - area) / area <= 0.02:
                return items
        return min(
            candidates,
            key=lambda items: abs(sum(item["area_m2"] for item in items) - area) / area,
        )
    return candidates[0]


def _normalize_rate_land(rates: list[dict[str, Any]], land_use: list[dict[str, Any]]) -> None:
    if not land_use:
        return
    groups = {item["group"] for item in land_use}
    for rate in rates:
        if rate.get("land") != "未知":
            continue
        if len(land_use) == 1:
            rate["land"] = land_use[0]["type"]
            rate["group"] = land_use[0]["group"]
        elif len(groups) == 1:
            rate["land"] = next(iter(groups))
            rate["group"] = next(iter(groups))


def _split_citations(
    mentions: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    articles = [
        mention
        for mention in mentions
        if mention.get("article_num") is not None and "裁量" not in mention["law"]
    ]
    policies = [
        mention["law"]
        for mention in mentions
        if mention.get("article_num") is None or "裁量" in mention["law"]
    ]
    return articles, list(dict.fromkeys(policies))


def _article_mentions(sentence: str, include_policies: bool = False) -> list[dict[str, Any]]:
    mentions: list[dict[str, Any]] = []
    for law_match in _LAW.finditer(sentence):
        law = law_match.group(1)
        tail_start = law_match.end()
        next_law = _LAW.search(sentence, tail_start)
        tail = sentence[tail_start: next_law.start() if next_law else len(sentence)]
        version_year = None
        version_match = re.match(r"\s*[（(]([^）)]{0,40}(?:修正|修订|版)[^）)]*)[）)]", tail)
        if version_match:
            year = re.search(r"(20\d{2})", version_match.group(1))
            version_year = int(year.group(1)) if year else None
        articles = list(_ARTICLE.finditer(tail))
        if not articles:
            if include_policies:
                mentions.append(
                    {"law": law, "article_num": None, "article_raw": None, "version_year": version_year}
                )
            continue
        nums = [articles[0].group(1)]
        for extra in _ARTICLE_LIST.finditer(tail[articles[0].end():]):
            if extra.group(1) not in nums:
                nums.append(extra.group(1))
        for num in nums:
            mentions.append(
                {
                    "law": law,
                    "article_num": cn_to_int(num),
                    "article_raw": f"第{num}条",
                    "version_year": version_year,
                }
            )
    return mentions


def _sentences(text: str) -> list[str]:
    sentences: list[str] = []
    buffer: list[str] = []
    quote_depth = 0
    for char in text:
        if char in "“「『":
            quote_depth += 1
        elif char in "”」』":
            quote_depth = max(0, quote_depth - 1)
        if char in "。；\n" and quote_depth == 0:
            sentence = "".join(buffer).strip()
            if sentence:
                sentences.append(sentence)
            buffer = []
        else:
            buffer.append(char)
    sentence = "".join(buffer).strip()
    if sentence:
        sentences.append(sentence)
    return sentences


def _extract_citations(text: str, kind: str, require_keyword: bool = True) -> list[dict[str, Any]]:
    mentions: list[dict[str, Any]] = []
    for sentence in _sentences(text):
        if not require_keyword:
            hit = True
        elif kind == "violated":
            hit = "违反" in sentence or (
                "定性" in sentence and "违法" in sentence and "处罚的法律依据" not in sentence
            )
        else:
            hit = any(key in sentence for key in ("根据", "依据", "依照", "参照", "按照")) and any(
                key in sentence for key in ("处罚", "规定", "基准")
            )
        if not hit:
            continue
        for mention in _article_mentions(sentence, include_policies=kind == "basis"):
            mention["source"] = "cited"
            mentions.append(mention)
    # 同一法条只保留一次
    deduped: dict[tuple[str, int | None], dict[str, Any]] = {}
    for mention in mentions:
        deduped[(normalize_title(mention["law"]), mention["article_num"])] = mention
    return list(deduped.values())


class ArticleResolver:
    def __init__(self, articles_path: Path):
        self.by_key: dict[tuple[str, int], dict[str, Any]] = {}
        self.doc_by_title: dict[str, str] = {}
        for line in articles_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            article = json.loads(line)
            doc_id = article["doc_id"]
            self.doc_by_title.setdefault(normalize_title(article["law_title"]), doc_id)
            self.by_key[(doc_id, int(article["article_num"]))] = {
                "article_id": article["article_id"],
                "article_no": article["article_no"],
                "citation": article["citation"],
            }

    def resolve_doc(self, law: str) -> str | None:
        normalized = normalize_title(law)
        if normalized in _TITLE_ALIASES:
            return _TITLE_ALIASES[normalized]
        if normalized in self.doc_by_title:
            return self.doc_by_title[normalized]
        for title, doc_id in self.doc_by_title.items():
            if normalized and (normalized in title or title in normalized):
                return doc_id
        return None

    def resolve(
        self, law: str, article_num: int | None, version_year: int | None = None
    ) -> dict[str, Any]:
        if article_num is None:
            return {
                "law": law,
                "article_num": None,
                "cited_article_num": None,
                "version_year": version_year,
                "article": None,
                "article_id": None,
                "resolved": False,
            }
        doc_id = self.resolve_doc(law)
        mapped = False
        cited_num = article_num
        if doc_id:
            cutoff = OLD_VERSION_CUTOFF.get(doc_id)
            alias = OLD_ARTICLE_ALIASES.get((doc_id, article_num))
            old_version = version_year is not None and cutoff is not None and version_year <= cutoff
            if alias is not None and (old_version or (doc_id, article_num) not in self.by_key):
                article_num = alias
                mapped = True
        hit = self.by_key.get((doc_id, article_num)) if doc_id else None
        if not hit:
            return {
                "law": law,
                "article_num": article_num,
                "cited_article_num": cited_num,
                "version_year": version_year,
                "article_id": None,
                "resolved": False,
                "mapped_from_old_version": mapped,
            }
        return {
            "law": law,
            "article_num": article_num,
            "cited_article_num": cited_num,
            "version_year": version_year,
            "article": hit["article_no"],
            "article_id": hit["article_id"],
            "citation": hit["citation"],
            "resolved": True,
            "mapped_from_old_version": mapped,
        }


def _resolve_all(mentions: list[dict[str, Any]], resolver: ArticleResolver) -> list[dict[str, Any]]:
    result = []
    for mention in mentions:
        resolved = resolver.resolve(
            mention["law"], mention.get("article_num"), mention.get("version_year")
        )
        resolved["source"] = mention.get("source", "cited")
        result.append(resolved)
    return result


def _extract_facts(text: str) -> str:
    starts = [
        "经查明[，,]",
        "经查[，,]",
        "查明事实如下[：:]",
        "经调查[，,]",
        "你(?:公司|单位)(?=[^。；\\n]{0,20}(?:于|在)20)",
        "被处罚人[^。；\\n]{0,20}(?=(?:于|在)20)",
    ]
    ends = ["上述行为违反", "该行为违反", "以上违法事实", "本案适用的法律", "上述违法事实"]
    start_match = _first(starts, text)
    if not start_match:
        return ""
    tail = text[start_match.end():]
    end_positions = [tail.find(marker) for marker in ends if tail.find(marker) >= 0]
    end = min(end_positions) if end_positions else min(len(tail), 900)
    return clean_text(tail[:end]).strip("　 \n，,")


def _text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


_NAME_STOPWORDS = {
    "某公司",
    "负责人",
    "授权委托",
    "身份证",
    "身份证复",
    "复印件",
    "居民身份",
    "性别",
    "年龄",
    "民族",
    "住址",
    "地址",
    "电话",
    "联系电话",
    "联系",
    "手机",
    "邮箱",
    "传真",
    "邮编",
}


def _mask_name(text: str, person: str) -> str:
    if len(person) < 2 or person in _NAME_STOPWORDS:
        return text
    if any(token in person for token in ("公司", "单位", "身份", "复印", "委托", "负责")):
        return text
    return text.replace(person, person[0] + "某")


def _mask_pii(text: str, party: dict[str, Any]) -> str:
    text = re.sub(r"(?<!\d)1[3-9]\d{9}(?!\d)", "1**********", text)
    text = re.sub(r"(?<!\d)\d{17}[\dXx](?!\d)", "******************", text)
    text = re.sub(r"(?<!\d)\d{16,25}(?!\d)", "****************", text)
    name = party.get("name") or ""
    if party.get("type") == "个人" and len(name) >= 2:
        masked = name[0] + "某" + (name[-1] if len(name) > 3 else "")
        text = text.replace(name, masked)
    for match in re.finditer(
        r"(?:法定代表人|负责人|联系人|被询问人|被授权人|委托代理人|当事人)"
        r"[：:\s]*([\u4e00-\u9fa5]{2,4}(?:[\s　]+[\u4e00-\u9fa5]{2,4})*)"
        r"(?=[\s　，。；、：:]|性别|年龄|民族|住址|地址|电话|联系|$)",
        text,
    ):
        for person in re.split(r"[\s　]+", match.group(1)):
            text = _mask_name(text, person)
    # 第三人姓名常出现在“蒋金芳《身份证》”“身份证复印件（康彬）”等证据清单中
    for match in re.finditer(r"([\u4e00-\u9fa5]{2,3})《身份证", text):
        text = _mask_name(text, match.group(1))
    for match in re.finditer(r"身份证[^，。；\n]{0,8}[（(]([\u4e00-\u9fa5]{2,3})[）)]", text):
        text = _mask_name(text, match.group(1))
    return text


def sanitize_case(case: dict[str, Any]) -> dict[str, Any]:
    raw_party = case.get("party") or {}
    masked = _mask_party(raw_party)
    case["text"] = _mask_pii(case.get("text") or "", raw_party)
    case["facts"] = _mask_pii(case.get("facts") or "", raw_party)
    if masked.get("type") == "个人":
        masked["name"] = masked.get("name_masked")
    case["party"] = masked
    return case


def _check_consistency(case: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    land_sum = sum(item["area_m2"] for item in case.get("land_use") or [])
    area = case.get("area_m2")
    if area and land_sum and abs(land_sum - area) / area > 0.02:
        warnings.append(f"land_use_sum_{land_sum:.2f}_vs_area_{area:.2f}")
    rates = case.get("fine_rate") or []
    fine = case.get("fine_amount")
    if fine and rates:
        calculated = sum(
            item["yuan_per_m2"] * (item.get("area_m2") or 0) for item in rates if item.get("area_m2")
        )
        if calculated and abs(calculated - fine) / fine > 0.02:
            warnings.append(f"fine_rate_product_{calculated:.2f}_vs_fine_{fine:.2f}")
    if not case.get("land_use"):
        warnings.append("land_use_missing")
    if not case.get("violated_articles"):
        warnings.append("violated_articles_missing")
    if not case.get("penalty_basis_articles"):
        warnings.append("penalty_basis_missing")
    if case.get("project_nature") == "未知":
        warnings.append("project_nature_unknown")
    if not (case.get("party") or {}).get("name"):
        warnings.append("party_missing")
    return warnings


def _rate_area_from_text(rate_value: float, text: str) -> float | None:
    number = f"{rate_value:g}"
    for pattern in (
        rf"每平方米\s*{number}\s*元",
        rf"{number}\s*元\s*/\s*(?:平方米|㎡|m2|m²)",
    ):
        for match in re.finditer(pattern, text):
            look = text[max(0, match.start() - 40):match.start()]
            units = list(re.finditer(r"([\d,]+(?:\.\d+)?)\s*(?:平方米|㎡|m2|m²)", look))
            if units:
                return _to_float(units[-1].group(1))
    return None


def _attach_rate_areas(
    rates: list[dict[str, Any]],
    land_use: list[dict[str, Any]],
    area: float | None = None,
    text: str = "",
) -> None:
    for rate in rates:
        if rate.get("area_m2"):
            continue
        candidates = [item for item in land_use if item["type"] == rate["land"]]
        if not candidates:
            candidates = [item for item in land_use if item["group"] == rate["group"]]
        if len(candidates) == 1:
            rate["area_m2"] = candidates[0]["area_m2"]
    # “对非法占用耕地722平方米，按照每平方米350元”就近给出面积
    for rate in rates:
        found = _rate_area_from_text(rate["yuan_per_m2"], text)
        if found:
            rate["area_m2"] = found
    # “2242.92平方米×500元”这类算式直接给出面积，优先于地类匹配
    for match in _RATE_AREA_PAIR.finditer(text):
        pair_area = _to_float(match.group(1))
        pair_rate = _to_float(match.group(2))
        if not pair_area or not pair_rate:
            continue
        for rate in rates:
            if abs(rate["yuan_per_m2"] - pair_rate) < 1e-6:
                rate["area_m2"] = pair_area
                break
    if len(rates) == 1 and not rates[0].get("area_m2") and area:
        rates[0]["area_m2"] = area


def _select_rates(rates: list[dict[str, Any]], fine: float | None) -> list[dict[str, Any]]:
    """处罚段可能引用幅度标准，保留与罚款金额对得上的那一组费率。"""
    if not fine or not rates or len(rates) > 8:
        return rates

    def product(items: list[dict[str, Any]]) -> float:
        return sum(item["yuan_per_m2"] * (item.get("area_m2") or 0) for item in items)

    if any(item.get("area_m2") for item in rates) and abs(product(rates) - fine) / fine <= 0.02:
        return rates
    best: tuple[tuple[float, int], list[dict[str, Any]]] | None = None
    for mask in range(1, 1 << len(rates)):
        subset = [rates[i] for i in range(len(rates)) if mask >> i & 1]
        if any(not item.get("area_m2") for item in subset):
            continue
        value = product(subset)
        if value <= 0:
            continue
        key = (abs(value - fine) / fine, -len(subset))
        if best is None or key < best[0]:
            best = (key, subset)
    if best and best[0][0] <= 0.02:
        return best[1]
    return rates


def _fact_scope(text: str, facts: str) -> str:
    if facts:
        return facts
    for marker in ("本案适用的法律", "以上违法事实", "上述违法事实", "我局于"):
        pos = text.find(marker)
        if pos > 0:
            return text[:pos]
    return text


def parse_decision(text: str, meta: dict[str, Any], resolver: ArticleResolver) -> dict[str, Any]:
    text = clean_text(text)
    decision_no = _extract_decision_no(text, meta.get("decision_no_hint"))
    facts = _extract_facts(text)
    scope = _fact_scope(text, facts)
    penalty_text = _extract_penalty_section(text)
    area = _extract_area(facts) or _extract_area(penalty_text) or _extract_area(text)
    land_use = _select_land_use(facts, penalty_text, area) or _extract_land_use(scope)
    rates = _extract_rates(penalty_text)
    _normalize_rate_land(rates, land_use)
    _attach_rate_areas(rates, land_use, area, penalty_text)
    fine = _round2(_extract_fine(penalty_text) or _extract_fine(text))
    rates = _select_rates(rates, fine)

    party = _mask_party(_extract_party(text))
    behavior = _extract_behavior(scope)
    penalty_at = text.find(penalty_text) if penalty_text else -1
    violated_scope = text[:penalty_at] if penalty_at > 0 else text
    for marker in ("其二、关于本案处罚", "关于本案处罚的法律依据", "本案处罚的法律依据"):
        pos = violated_scope.find(marker)
        if pos > 0:
            violated_scope = violated_scope[:pos]
            break
    violated = _extract_citations(violated_scope, "violated")
    basis_mentions = _extract_citations(penalty_text, "basis", require_keyword=False)
    if not basis_mentions:
        basis_mentions = _extract_citations(text, "basis")
    basis, policy_citations = _split_citations(basis_mentions)

    excluded = "未按批准用途使用土地" in behavior and not any(
        item in behavior for item in ("未经批准占用土地", "超过批准数量占用土地")
    )
    case = {
        "case_id": meta.get("case_id") or _make_case_id(meta.get("region_slug", "hn"), decision_no),
        "source": {
            "url": meta.get("url"),
            "portal": meta.get("portal") or meta.get("agency"),
            "collected_at": meta.get("collected_at"),
            "source_sha256": meta.get("source_sha256"),
            "source_kind": meta.get("kind"),
        },
        "region": meta.get("region"),
        "agency": meta.get("agency"),
        "decision_no": decision_no,
        "decision_date": _extract_date(text),
        "party": party,
        "behavior": behavior,
        "scope_status": "excluded" if excluded else "included",
        "exclusion_reason": "未按批准用途使用土地，不属于非法占地" if excluded else None,
        "facts": facts,
        "land_use": land_use,
        "area_m2": area,
        "project_nature": _extract_project_nature(penalty_text)
        if _extract_project_nature(penalty_text) != "未知"
        else _extract_project_nature(text),
        "violated_articles": _resolve_all(violated, resolver),
        "penalty_basis_articles": _resolve_all(basis, resolver),
        "policy_citations": policy_citations,
        "penalty_types": _extract_penalty_types(penalty_text),
        "fine_amount": fine,
        "fine_rate": rates,
        "factors": _extract_factors(text),
        "law_version": _extract_law_version(text),
        "text": text,
        "extractor": {"method": "rule", "version": EXTRACTOR_VERSION},
    }
    case["warnings"] = _check_consistency(case)
    return case


def _make_case_id(region_slug: str, decision_no: str | None) -> str:
    if decision_no:
        match = re.search(r"[\[\(（〔]?\s*(\d{4})\s*[\]\)）〕]?\s*第?\s*(\d+)\s*号", decision_no)
        if match:
            return f"hn-{region_slug}-{match.group(1)}-{int(match.group(2))}"
    digest = hashlib.sha1((decision_no or "unknown").encode("utf-8")).hexdigest()[:8]
    return f"hn-{region_slug}-{digest}"


def parse_ledger(rows: list[list[str]], meta: dict[str, Any], resolver: ArticleResolver) -> list[dict[str, Any]]:
    header = [cell.replace("\n", "").strip() for cell in rows[0]]
    index = {name: i for i, name in enumerate(header)}

    def cell(row: list[str], *names: str) -> str:
        for name in names:
            for header_name, pos in index.items():
                if name in header_name and pos < len(row):
                    return row[pos].strip()
        return ""

    cases: list[dict[str, Any]] = []
    for row_number, row in enumerate(rows[1:], 1):
        decision_no = cell(row, "行政处罚决定文书号", "文书号")
        if not decision_no or "号" not in decision_no:
            continue
        behavior_type = cell(row, "违法类型")
        facts = cell(row, "违法事实")
        basis_text = cell(row, "处罚依据")
        penalty_text = cell(row, "处罚内容")
        party_name = cell(row, "行政相对人")
        agency = cell(row, "处罚机关") or meta.get("agency")
        date = cell(row, "处罚决定日期")
        fine_wan = _to_float(cell(row, "罚款金额"))
        combined = "\n".join(part for part in (facts, basis_text, penalty_text) if part)

        behavior = _extract_behavior(facts) or _extract_behavior(combined)
        excluded = (
            "非法占用土地" not in behavior_type
            or ("未按批准用途使用土地" in behavior and not any(
                item in behavior for item in ("未经批准占用土地", "超过批准数量占用土地")
            ))
        )
        if excluded:
            continue

        area = _extract_area(facts) or _extract_area(penalty_text)
        land_use = _select_land_use(facts, penalty_text, area)
        rates = _extract_rates(penalty_text)
        _normalize_rate_land(rates, land_use)
        _attach_rate_areas(rates, land_use, area, penalty_text)
        fine = _round2(
            fine_wan * 10000 if fine_wan is not None else _extract_fine(penalty_text)
        )
        rates = _select_rates(rates, fine)
        basis_mentions = _extract_citations(basis_text, "basis", require_keyword=False)
        basis, policy_citations = _split_citations(basis_mentions)
        violated = _extract_citations(facts, "violated")
        inferred = False
        if not violated and behavior:
            violated = _infer_violated(behavior)
            inferred = bool(violated)

        party = _mask_party({"type": "单位", "name": party_name})
        case = {
            "case_id": _make_case_id(meta.get("region_slug", "hn"), decision_no),
            "source": {
                "url": meta.get("url"),
                "portal": meta.get("portal") or meta.get("agency"),
                "collected_at": meta.get("collected_at"),
                "source_sha256": meta.get("source_sha256"),
                "source_kind": meta.get("kind"),
                "ledger_row": row_number,
            },
            "region": meta.get("region"),
            "agency": agency,
            "decision_no": decision_no,
            "decision_date": _extract_date(date) or date or None,
            "party": party,
            "behavior": behavior,
            "scope_status": "included",
            "exclusion_reason": None,
            "facts": facts,
            "land_use": land_use,
            "area_m2": area,
            "project_nature": _extract_project_nature(penalty_text)
            if _extract_project_nature(penalty_text) != "未知"
            else _extract_project_nature(combined),
            "violated_articles": _resolve_all(violated, resolver),
            "penalty_basis_articles": _resolve_all(basis, resolver),
            "policy_citations": policy_citations,
            "penalty_types": _extract_penalty_types(penalty_text),
            "fine_amount": fine,
            "fine_rate": rates,
            "factors": _extract_factors(combined),
            "law_version": _extract_law_version(basis_text),
            "text": combined,
            "extractor": {"method": "rule", "version": EXTRACTOR_VERSION, "violated_inferred": inferred},
        }
        case["warnings"] = _check_consistency(case)
        cases.append(case)
    return cases


def _infer_violated(behavior: list[str]) -> list[dict[str, Any]]:
    if not behavior:
        return []
    return [
        {"law": "中华人民共和国土地管理法", "article_num": 2, "article_raw": "第二条", "source": "inferred_from_behavior"},
        {"law": "中华人民共和国土地管理法", "article_num": 44, "article_raw": "第四十四条", "source": "inferred_from_behavior"},
    ]


def build_resolver() -> ArticleResolver:
    cfg = load_settings()
    path = Path(cfg["paths"]["articles_file"])
    if not path.exists():
        raise SystemExit(f"找不到 v2 法条库：{path}，请先运行 v2 语料构建")
    return ArticleResolver(path)
