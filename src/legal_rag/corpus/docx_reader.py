"""用标准库读取 docx 正文段落（不依赖 python-docx）。"""
from __future__ import annotations

import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


@dataclass
class Paragraph:
    text: str
    style: str = ""


def _paragraph_text(p: ET.Element) -> str:
    parts: list[str] = []
    for node in p.iter():
        if node.tag == W + "t":
            parts.append(node.text or "")
        elif node.tag == W + "tab":
            parts.append("\t")
        elif node.tag in (W + "br", W + "cr"):
            parts.append("\n")
    return "".join(parts)


def _style(p: ET.Element) -> str:
    ppr = p.find(W + "pPr")
    if ppr is None:
        return ""
    pstyle = ppr.find(W + "pStyle")
    return pstyle.get(W + "val", "") if pstyle is not None else ""


def read_docx(path: Path) -> list[Paragraph]:
    with zipfile.ZipFile(path) as zf:
        try:
            xml = zf.read("word/document.xml")
        except KeyError as exc:
            raise ValueError(f"{path} 不是有效的 docx：缺少 word/document.xml") from exc
    root = ET.fromstring(xml)
    body = root.find(W + "body")
    if body is None:
        return []
    paragraphs: list[Paragraph] = []
    for child in body:
        if child.tag == W + "p":
            paragraphs.append(Paragraph(_paragraph_text(child), _style(child)))
        elif child.tag == W + "tbl":
            # 法规正文偶有表格（如附表），按行展开，单元格用制表符分隔
            for tr in child.findall(W + "tr"):
                cells = []
                for tc in tr.findall(W + "tc"):
                    cell_text = "".join(
                        _paragraph_text(p) for p in tc.findall(W + "p")
                    ).strip()
                    cells.append(cell_text)
                line = "\t".join(cells).strip()
                if line:
                    paragraphs.append(Paragraph(line, "Table"))
    return paragraphs
