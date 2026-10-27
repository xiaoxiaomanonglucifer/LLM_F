"""OpenAI 兼容的生成客户端（Ollama / vLLM 通用）。

解码参数统一从 settings.yaml 读取并写入每条结果记录，保证三组可归因。
"""
from __future__ import annotations

import json
import re
import time
from typing import Any

from ..graph.schema import Triple


class LLMError(RuntimeError):
    pass


class LLMClient:
    def __init__(self, cfg: dict[str, Any]) -> None:
        from openai import OpenAI

        gen = cfg["generation"]
        self.model = gen["model"]
        self.temperature = gen["temperature"]
        self.top_p = gen["top_p"]
        self.seed = gen.get("seed")
        self.max_tokens = gen["max_tokens"]
        self.max_retries = gen.get("max_retries", 2)
        self.seed_supported = True
        self.client = OpenAI(
            base_url=gen["base_url"],
            api_key=gen.get("api_key") or "not-needed",
            timeout=gen.get("timeout_sec", 300),
            max_retries=0,
        )

    @property
    def decoding_params(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "seed": self.seed if self.seed_supported else None,
            "max_tokens": self.max_tokens,
        }

    def chat(self, messages: list[dict[str, str]], max_tokens: int | None = None) -> dict[str, Any]:
        last_error: Exception | None = None
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_tokens": max_tokens or self.max_tokens,
        }
        if self.seed is not None and self.seed_supported:
            kwargs["seed"] = self.seed
        for attempt in range(1, self.max_retries + 2):
            started = time.time()
            try:
                resp = self.client.chat.completions.create(**kwargs)
                text = (resp.choices[0].message.content or "").strip()
                usage = resp.usage.model_dump() if resp.usage else {}
                return {
                    "text": text,
                    "usage": usage,
                    "latency_sec": round(time.time() - started, 2),
                }
            except Exception as exc:
                last_error = exc
                # 部分后端不识别 seed：去掉后用同一参数重试
                if "seed" in str(exc).lower() and "seed" in kwargs:
                    kwargs.pop("seed")
                    self.seed_supported = False
                    continue
                if attempt <= self.max_retries:
                    time.sleep(min(2 ** attempt, 10))
        raise LLMError(f"生成失败：{last_error}")

    def extract_triple(self, article: dict[str, Any]) -> Triple | None:
        prompt = (
            "请从下面法条中抽取知识图谱三元组，只输出一个 JSON 对象，不要解释。\n"
            '格式：{"subjects":["主体"],"actions":["行为"],"penalties":["处罚"]}\n'
            "字段无内容时用空数组。\n\n"
            f"法条：{article['citation']}\n{article['text']}"
        )
        result = self.chat(
            [
                {"role": "system", "content": "你是法律文本信息抽取器，只输出合法 JSON。"},
                {"role": "user", "content": prompt},
            ],
            max_tokens=400,
        )
        data = _parse_json_object(result["text"])
        if data is None:
            return None
        return Triple(
            article_id=article["article_id"],
            citation=article["citation"],
            law_title=article["law_title"],
            subjects=[str(x) for x in data.get("subjects", [])][:8],
            actions=[str(x) for x in data.get("actions", [])][:8],
            penalties=[str(x) for x in data.get("penalties", [])][:8],
            method="llm",
            model=self.model,
        )


def _parse_json_object(text: str) -> dict[str, Any] | None:
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


class MockLLMClient:
    """离线联调用：不调用模型，按上下文返回可预测的固定格式答案。"""

    model = "mock"
    seed = None

    @property
    def decoding_params(self) -> dict[str, Any]:
        return {"model": "mock"}

    def chat(self, messages: list[dict[str, str]], max_tokens: int | None = None) -> dict[str, Any]:
        user = messages[-1]["content"]
        question = user.split("【问题】")[-1].strip()
        citations = re.findall(r"《[^》]+》第[零〇一二三四五六七八九十百千两\d]+条", user)
        if citations:
            text = f"结论（模拟）：{question}\n依据：{citations[0]}（模拟回答，仅用于流程联调）。"
        else:
            text = "现有知识库中没有找到条文依据（模拟回答，仅用于流程联调）。"
        return {"text": text, "usage": {}, "latency_sec": 0.0}

    def extract_triple(self, article: dict[str, Any]) -> Triple | None:
        return None
