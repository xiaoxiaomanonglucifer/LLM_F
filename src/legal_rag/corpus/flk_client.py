"""国家法律法规数据库（flk.npc.gov.cn）客户端。

只依赖 requests。接口于 2026-10 实测：
  POST /law-search/search/list   {searchType:1(精确), searchContent:标题,...}
  GET  /law-search/search/flfgDetails?bbbs=...
  GET  /law-search/download/pc?bbbs=...&format=docx  -> data.url 为 OSS 签名地址
"""
from __future__ import annotations

import html
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests

BASE_URL = "https://flk.npc.gov.cn"
_EM_TAG = re.compile(r"</?em[^>]*>")
_WS = re.compile(r"[\s\u3000]+")


class FlkError(RuntimeError):
    pass


def strip_highlight(text: str) -> str:
    return html.unescape(_EM_TAG.sub("", text or "")).strip()


def normalize_title(text: str) -> str:
    text = strip_highlight(text).replace("《", "").replace("》", "")
    return _WS.sub("", text)


@dataclass
class SearchHit:
    bbbs: str
    title: str
    flxz: str
    sxx: int
    gbrq: str | None
    sxrq: str | None
    zdjg_name: str
    raw: dict[str, Any] = field(default_factory=dict)


class FlkClient:
    def __init__(
        self,
        interval_sec: float = 0.6,
        timeout_sec: int = 60,
        max_retries: int = 4,
        user_agent: str = "legal-rag-course-project/1.0",
        session: requests.Session | None = None,
    ) -> None:
        self.interval_sec = interval_sec
        self.timeout_sec = timeout_sec
        self.max_retries = max_retries
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "User-Agent": user_agent,
                "Referer": f"{BASE_URL}/search",
                "Origin": BASE_URL,
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Content-Type": "application/json",
            }
        )
        self._last_request = 0.0

    def _wait(self) -> None:
        delta = time.monotonic() - self._last_request
        if delta < self.interval_sec:
            time.sleep(self.interval_sec - delta)
        self._last_request = time.monotonic()

    def _request(
        self, method: str, url: str, json_expected: bool = True, **kwargs: Any
    ) -> requests.Response:
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            self._wait()
            try:
                resp = self.session.request(method, url, timeout=self.timeout_sec, **kwargs)
                if resp.status_code == 200:
                    content_type = resp.headers.get("Content-Type", "")
                    if not json_expected or "json" in content_type:
                        return resp
                    # 站点 WAF 会返回 JS 挑战页；此时冷却后重试
                    last_error = FlkError(
                        f"返回非 JSON（疑似 WAF 挑战）：{content_type} {resp.text[:80]!r}"
                    )
                    time.sleep(min(15 * attempt, 60))
                    continue
                last_error = FlkError(f"HTTP {resp.status_code}: {resp.text[:200]}")
            except requests.RequestException as exc:  # 网络抖动重试
                last_error = exc
            time.sleep(min(2 ** attempt * 0.5, 8))
        raise FlkError(f"{method} {url} 失败（重试 {self.max_retries} 次）：{last_error}")

    def search_title(self, title: str, page_size: int = 20) -> list[SearchHit]:
        """按标题精确检索；返回所有同名条目（含历史版本），由调用方选有效版本。"""
        body = {
            "searchRange": 1,
            "sxrq": [],
            "gbrq": [],
            "searchType": 1,
            "sxx": [],
            "gbrqYear": [],
            "flfgCodeId": [],
            "zdjgCodeId": [],
            "searchContent": title,
            "xgzlSearch": False,
            "orderByParam": {"order": "-1", "sort": ""},
            "pageNum": 1,
            "pageSize": page_size,
        }
        resp = self._request("POST", f"{BASE_URL}/law-search/search/list", json=body)
        payload = resp.json()
        if payload.get("code") != 200:
            raise FlkError(f"检索失败：{payload}")
        hits = []
        for row in payload.get("rows") or []:
            hits.append(
                SearchHit(
                    bbbs=row["bbbs"],
                    title=strip_highlight(row.get("title", "")),
                    flxz=row.get("flxz", ""),
                    sxx=int(row.get("sxx") or 0),
                    gbrq=row.get("gbrq"),
                    sxrq=row.get("sxrq"),
                    zdjg_name=row.get("zdjgName", ""),
                    raw=row,
                )
            )
        return hits

    def resolve_effective(self, title: str) -> SearchHit | None:
        """返回与 title 精确同名且现行有效（sxx=3）的条目；多版本取公布日期最新者。"""
        target = normalize_title(title)
        hits = [h for h in self.search_title(title) if normalize_title(h.title) == target]
        valid = [h for h in hits if h.sxx == 3]
        if not valid:
            return None
        valid.sort(key=lambda h: h.gbrq or "", reverse=True)
        return valid[0]

    def detail(self, bbbs: str) -> dict[str, Any]:
        resp = self._request(
            "GET", f"{BASE_URL}/law-search/search/flfgDetails", params={"bbbs": bbbs}
        )
        payload = resp.json()
        if payload.get("code") != 200 or not payload.get("data"):
            raise FlkError(f"详情获取失败 bbbs={bbbs}: {payload}")
        return payload["data"]

    def docx_url(self, bbbs: str) -> str:
        resp = self._request(
            "GET",
            f"{BASE_URL}/law-search/download/pc",
            params={"bbbs": bbbs, "format": "docx"},
        )
        payload = resp.json()
        if payload.get("code") != 200 or not payload.get("data", {}).get("url"):
            raise FlkError(f"下载地址获取失败 bbbs={bbbs}: {payload}")
        return payload["data"]["url"]

    def download_docx(self, bbbs: str, dest: Path) -> str:
        """下载 docx 到 dest，返回 sha256。校验 ZIP 魔数，避免把错误页存成法规。"""
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        url = self.docx_url(bbbs)
        resp = self._request("GET", url, json_expected=False)
        content = resp.content
        if not content.startswith(b"PK\x03\x04"):
            raise FlkError(f"下载内容不是 docx（bbbs={bbbs}, {len(content)} bytes）")
        tmp = dest.with_suffix(dest.suffix + ".part")
        tmp.write_bytes(content)
        tmp.replace(dest)
        import hashlib

        return hashlib.sha256(content).hexdigest()
