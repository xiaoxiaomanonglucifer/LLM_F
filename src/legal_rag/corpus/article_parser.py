"""法规“按条切分”解析器。

设计要点（与开题报告一致）：
  * 以“条”为最小检索与引用单位；
  * 条内的款、项不拆开，完整保留在同一文本块内；
  * 元数据记录 法规名 / 章 / 节 / 条号 / 条序号，支持精确引用；
  * 目录（目　录）整段跳过，避免把目录条目当正文。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable

from .docx_reader import Paragraph

_CN_DIGITS = {
    "零": 0,
    "〇": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}
_CN_UNITS = {"十": 10, "百": 100, "千": 1000}

CHAPTER_RE = re.compile(r"^第([零〇一二三四五六七八九十百千两\d]+)章[\s\u3000]*(.*)$")
SECTION_RE = re.compile(r"^第([零〇一二三四五六七八九十百千两\d]+)节[\s\u3000]*(.*)$")
ARTICLE_RE = re.compile(r"^第([零〇一二三四五六七八九十百千两\d]+)条(?:[\s\u3000]+|$)(.*)$")
TOC_RE = re.compile(r"^目[\s\u3000]*录$")
CLEAN_RE = re.compile(r"[\u200b\ufeff\xa0]")


def cn_to_int(text: str) -> int:
    """中文数字转整数，支持 十二 / 二十 / 一百零二 / 一千二百 等写法。"""
    text = text.strip()
    if text.isdigit():
        return int(text)
    total = 0
    section = 0
    number = 0
    for ch in text:
        if ch in _CN_DIGITS:
            number = _CN_DIGITS[ch]
        elif ch in _CN_UNITS:
            unit = _CN_UNITS[ch]
            if number == 0:
                number = 1
            section += number * unit
            number = 0
        else:
            raise ValueError(f"无法识别的中文数字：{text}")
    return section + number


def normalize_line(text: str) -> str:
    text = CLEAN_RE.sub("", text)
    text = text.replace("\u3000", " ").strip()
    return re.sub(r"[ \t]+", " ", text)


@dataclass
class Article:
    article_no: str
    article_num: int
    text: str
    body: str
    chapter: str | None = None
    section: str | None = None


@dataclass
class ParsedLaw:
    title: str
    preamble: str
    articles: list[Article] = field(default_factory=list)
    tail: str = ""
    structure_issues: list[str] = field(default_factory=list)

    @property
    def article_count(self) -> int:
        return len(self.articles)

    @property
    def char_count(self) -> int:
        return sum(len(a.text) for a in self.articles)


def parse_law(paragraphs: Iterable[Paragraph | str], expected_title: str | None = None) -> ParsedLaw:
    lines: list[str] = []
    for p in paragraphs:
        raw = p.text if isinstance(p, Paragraph) else p
        for piece in raw.split("\n"):
            piece = normalize_line(piece)
            if piece:
                lines.append(piece)

    if expected_title:
        title = expected_title
    else:
        title = lines[0] if lines else ""

    preamble_parts: list[str] = []
    articles: list[Article] = []
    tail_parts: list[str] = []
    chapter: str | None = None
    section: str | None = None
    in_toc = False
    seen_body = False
    current: Article | None = None

    for line in lines:
        if TOC_RE.match(line):
            in_toc = True
            current = None
            continue
        m_chapter = CHAPTER_RE.match(line)
        m_section = SECTION_RE.match(line)
        m_article = ARTICLE_RE.match(line)
        if m_chapter:
            in_toc = False
            seen_body = True
            chapter = line
            section = None
            current = None
            continue
        if m_section:
            in_toc = False
            seen_body = True
            section = line
            current = None
            continue
        if m_article:
            in_toc = False
            seen_body = True
            number_text = m_article.group(1)
            article_no = f"第{number_text}条"
            body_first = m_article.group(2).strip()
            current = Article(
                article_no=article_no,
                article_num=cn_to_int(number_text),
                text=line,
                body=body_first,
                chapter=chapter,
                section=section,
            )
            articles.append(current)
            continue
        if in_toc:
            continue
        if current is not None:
            # 条内续段：款、项、但书等，原样并入本条
            current.text += "\n" + line
            current.body += ("\n" if current.body else "") + line
            continue
        if not seen_body:
            preamble_parts.append(line)
        else:
            tail_parts.append(line)

    issues: list[str] = []
    numbers = [a.article_num for a in articles]
    if not articles:
        issues.append("未解析到任何条文")
    else:
        if numbers != sorted(numbers):
            issues.append("条号非单调递增")
        if len(set(numbers)) != len(numbers):
            issues.append("存在重复条号")
        if numbers[0] != 1:
            issues.append(f"首条编号为 {numbers[0]}，不是 1")
    if any(not a.body for a in articles):
        issues.append("存在正文为空的条文")

    # 标题行如果混进了序言，去掉重复标题与发文数据
    preamble = "\n".join(preamble_parts).strip()
    if preamble.startswith(title):
        preamble = preamble[len(title) :].lstrip()

    return ParsedLaw(
        title=title,
        preamble=preamble,
        articles=articles,
        tail="\n".join(tail_parts).strip(),
        structure_issues=issues,
    )
