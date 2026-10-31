"""抓取湖南行政处罚公开页面；TLS 校验失败时仅对公开政府站点降级重试。"""
from __future__ import annotations

import hashlib
import time
from typing import Any

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124 Safari/537.36"
)


def fetch_url(url: str, timeout: int = 40, retries: int = 3) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(
                url,
                headers={"User-Agent": USER_AGENT, "Accept-Language": "zh-CN,zh;q=0.9"},
                timeout=timeout,
                verify=True,
            )
            resp.raise_for_status()
            break
        except requests.exceptions.SSLError as exc:
            last_error = exc
            if attempt == retries:
                resp = requests.get(
                    url,
                    headers={"User-Agent": USER_AGENT, "Accept-Language": "zh-CN,zh;q=0.9"},
                    timeout=timeout,
                    verify=False,
                )
                resp.raise_for_status()
                break
        except requests.RequestException as exc:
            last_error = exc
            if attempt == retries:
                raise
            time.sleep(1.5 * attempt)

    encoding = resp.apparent_encoding or resp.encoding or "utf-8"
    html = resp.content.decode(encoding, errors="replace")
    return {
        "html": html,
        "content": resp.content,
        "encoding": encoding,
        "status_code": resp.status_code,
        "final_url": resp.url,
        "sha256": hashlib.sha256(resp.content).hexdigest(),
    }
