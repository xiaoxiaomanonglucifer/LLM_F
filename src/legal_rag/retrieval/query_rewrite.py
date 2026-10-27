"""查询重写：口语规范化 + 术语对齐。

重写结果与原查询同时参与检索（多查询并集），避免重写错误导致召回归零。
LLM 重写为可选开关，默认关闭以保证可复现。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# 口语/简称 -> 法规术语。顺序无关，全部叠加为扩展检索式。
TERM_MAP: dict[str, list[str]] = {
    "盖房": ["宅基地", "建房", "审批"],
    "盖房子": ["宅基地", "建房", "审批"],
    "修房子": ["宅基地", "建房", "审批"],
    "村里": ["农村集体经济组织", "村集体"],
    "批地": ["建设用地", "审批", "农用地转用"],
    "占地": ["征收", "占用", "补偿"],
    "拆迁": ["征收", "补偿", "安置"],
    "卖地": ["土地使用权", "出让", "转让"],
    "挖矿": ["矿产资源", "开采", "采矿权"],
    "采矿": ["矿产资源", "采矿权", "开采"],
    "探矿": ["探矿权", "矿产资源", "勘查"],
    "罚款": ["行政处罚", "罚款"],
    "基本农田": ["永久基本农田"],
    "红线": ["生态保护红线", "永久基本农田"],
    "海域": ["海域使用", "海域使用权"],
    "填海": ["海域使用", "围填海"],
    "测绘": ["测绘地理信息", "测绘资质"],
    "土地证": ["不动产登记", "土地权属"],
    "房产证": ["不动产登记"],
    "宅基地证": ["宅基地", "不动产登记"],
}

_WS = re.compile(r"[\s\u3000]+")


@dataclass
class RewrittenQuery:
    original: str
    normalized: str
    expansions: list[str] = field(default_factory=list)

    def retrieval_queries(self) -> list[str]:
        queries = [self.original]
        for q in [self.normalized, *self.expansions]:
            if q and q not in queries:
                queries.append(q)
        return queries


def normalize(text: str) -> str:
    text = text.replace("？", "?").replace("，", " ").replace("。", " ")
    text = text.replace("（", "(").replace("）", ")")
    return _WS.sub(" ", text).strip()


def rewrite(query: str) -> RewrittenQuery:
    normalized = normalize(query)
    expansions: list[str] = []
    for term, legal_terms in TERM_MAP.items():
        if term in query:
            expansions.append(" ".join(legal_terms))
    # 疑问词对检索无贡献，另生成一条去疑问词的版本
    stripped = re.sub(
        r"(请问|我想问一下|想问一下|是什么|有哪些|怎么办|如何|怎么|吗|呢|需要|应当)",
        " ",
        normalized,
    )
    stripped = _WS.sub(" ", stripped).strip()
    if stripped and stripped != normalized:
        expansions.append(stripped)
    return RewrittenQuery(original=query, normalized=normalized, expansions=expansions)
