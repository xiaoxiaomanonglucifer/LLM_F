"""不依赖第三方库的 HTML 正文与表格抽取。"""
from __future__ import annotations

import re
from html.parser import HTMLParser

_BLOCK_TAGS = {
    "p", "div", "br", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6",
    "section", "article", "header", "footer", "title",
}
_SKIP_TAGS = {"script", "style", "noscript"}
_WS = re.compile(r"[ \t\u3000\xa0]+")


class _Extractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.chunks: list[str] = []
        self.tables: list[list[list[str]]] = []
        self._skip = 0
        self._table_stack: list[list[list[str]]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs) -> None:  # type: ignore[no-untyped-def]
        tag = tag.lower()
        if tag in _SKIP_TAGS:
            self._skip += 1
            return
        if self._skip:
            return
        if tag == "table":
            table: list[list[str]] = []
            self._table_stack.append(table)
            self.tables.append(table)
        elif tag == "tr" and self._table_stack:
            self._row = []
            self._table_stack[-1].append(self._row)
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []
        elif tag in _BLOCK_TAGS:
            self.chunks.append("\n")
        if tag == "br":
            self.chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in _SKIP_TAGS:
            self._skip = max(0, self._skip - 1)
            return
        if self._skip:
            return
        if tag in ("td", "th") and self._cell is not None and self._row is not None:
            self._row.append(_clean("".join(self._cell)))
            self._cell = None
            self.chunks.append("\t")
        elif tag == "tr" and self._row is not None:
            self._row = None
            self.chunks.append("\n")
        elif tag == "table" and self._table_stack:
            self._table_stack.pop()
            self.chunks.append("\n")
        elif tag in _BLOCK_TAGS:
            self.chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        if self._cell is not None:
            self._cell.append(data)
        else:
            self.chunks.append(data)


def _clean(text: str) -> str:
    text = text.replace("\xa0", " ").replace("\u3000", " ")
    return _WS.sub(" ", text).strip()


def parse_html(html: str) -> tuple[str, list[list[list[str]]]]:
    parser = _Extractor()
    parser.feed(html)
    parser.close()

    lines = []
    for raw in "".join(parser.chunks).splitlines():
        line = _clean(raw)
        if line:
            lines.append(line)
    text = "\n".join(lines)

    tables: list[list[list[str]]] = []
    for table in parser.tables:
        rows = [row for row in table if any(cell for cell in row)]
        if len(rows) >= 2:
            tables.append(rows)
    return text, tables


def find_table(tables: list[list[list[str]]], required: tuple[str, ...]) -> list[list[str]] | None:
    for rows in tables:
        header = " ".join(rows[0])
        if all(key in header for key in required):
            return rows
    return None
