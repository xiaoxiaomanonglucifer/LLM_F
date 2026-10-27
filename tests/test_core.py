"""核心逻辑单元测试（unittest，无需 pytest）。

运行：python -m unittest discover -s tests -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from legal_rag.corpus.article_parser import cn_to_int, parse_law  # noqa: E402
from legal_rag.graph.index import GraphIndex  # noqa: E402
from legal_rag.index.bm25 import Bm25Index, tokenize  # noqa: E402
from legal_rag.pipeline.qa import is_refusal  # noqa: E402
from legal_rag.retrieval.fusion import rrf_fuse  # noqa: E402
from legal_rag.retrieval.query_rewrite import rewrite  # noqa: E402


class TestChineseNumbers(unittest.TestCase):
    def test_basic(self):
        cases = {"一": 1, "十": 10, "十二": 12, "二十": 20, "四十四": 44, "一百": 100, "一百零二": 102, "一百二十": 120}
        for text, expected in cases.items():
            self.assertEqual(cn_to_int(text), expected, text)

    def test_digits(self):
        self.assertEqual(cn_to_int("7"), 7)


class TestArticleParser(unittest.TestCase):
    LINES = [
        "中华人民共和国测试法",
        "（2020年1月1日通过）",
        "目　录",
        "第一章　总则",
        "第二章　管理",
        "第一章　总则",
        "第一条　为了测试，制定本法。",
        "第二条　本法适用于测试。",
        "第一款内容。",
        "（一）第一项；",
        "第二章　管理",
        "第三条　管理部门负责管理。",
    ]

    def test_split_and_metadata(self):
        parsed = parse_law(self.LINES, expected_title="中华人民共和国测试法")
        self.assertEqual(parsed.article_count, 3)
        self.assertEqual([a.article_no for a in parsed.articles], ["第一条", "第二条", "第三条"])
        self.assertEqual(parsed.articles[0].chapter, "第一章 总则")
        self.assertEqual(parsed.articles[2].chapter, "第二章 管理")
        self.assertIn("（一）第一项；", parsed.articles[1].text)
        self.assertIn("为了测试", parsed.articles[0].body)
        self.assertIn("2020年1月1日", parsed.preamble)
        self.assertEqual(parsed.structure_issues, [])

    def test_toc_skipped(self):
        parsed = parse_law(self.LINES[2:5] + self.LINES[5:])
        self.assertNotIn("第一章　总则", parsed.preamble)


class TestRrf(unittest.TestCase):
    def test_order_and_ranks(self):
        fused = rrf_fuse({"dense": ["a", "b", "c"], "bm25": ["b", "a", "d"]}, k=60, top_k=3)
        ids = [item[0] for item in fused]
        self.assertEqual(ids[:2], ["a", "b"])
        self.assertEqual(fused[0][2], {"dense": 1, "bm25": 2})
        self.assertAlmostEqual(fused[0][1], 1 / 61 + 1 / 62)


class TestBm25(unittest.TestCase):
    def test_tokenize_has_words_and_bigrams(self):
        tokens = tokenize("宅基地审批", use_char_bigram=True)
        self.assertIn("宅基地", tokens)
        self.assertIn("宅基", tokens)

    def test_search_ranks_relevant_first(self):
        ids = ["a1", "a2", "a3"]
        texts = ["农村村民住宅用地由乡镇人民政府审核批准", "矿产资源开采实行采矿许可证制度", "海域使用需取得海域使用权"]
        index = Bm25Index.build(ids, texts)
        hits = index.search("宅基地审批由谁批准", top_k=2)
        self.assertEqual(hits[0][0], "a1")


class TestGraphIndex(unittest.TestCase):
    TRIPLES = [
        {"article_id": "a1", "citation": "《测试法》第一条", "law_title": "测试法", "subjects": ["乡镇人民政府"], "actions": ["审批", "登记"], "penalties": []},
        {"article_id": "a2", "citation": "《测试法》第二条", "law_title": "测试法", "subjects": ["乡镇人民政府"], "actions": ["登记"], "penalties": ["责令改正"]},
        {"article_id": "a3", "citation": "《测试法》第三条", "law_title": "测试法", "subjects": ["采矿权人"], "actions": ["开采"], "penalties": []},
    ]

    def test_search_and_subgraph(self):
        graph = GraphIndex(self.TRIPLES)
        self.assertEqual(graph.entity_count, 6)
        ranked = graph.search(["乡镇人民政府审批"], top_k=3)
        self.assertEqual(ranked[0], "a1")
        self.assertIn("a2", ranked)
        sub = graph.subgraph(["a1"])
        self.assertEqual(sub["nodes"][0]["article_id"], "a1")
        self.assertEqual([n["article_id"] for n in sub["related"]], ["a2"])

    def test_seed_expansion(self):
        graph = GraphIndex(self.TRIPLES)
        ranked = graph.search(["完全无关的查询"], top_k=3, seed_ids=["a1"])
        self.assertIn("a2", ranked)


class TestQueryRewrite(unittest.TestCase):
    def test_colloquial_expansion(self):
        rw = rewrite("村里盖房子要办什么手续？")
        queries = rw.retrieval_queries()
        self.assertGreaterEqual(len(queries), 2)
        joined = " ".join(queries)
        self.assertIn("宅基地", joined)
        self.assertEqual(queries[0], "村里盖房子要办什么手续？")


class TestRefusal(unittest.TestCase):
    def test_detect(self):
        self.assertTrue(is_refusal("现有知识库中没有找到条文依据。"))
        self.assertTrue(is_refusal("土地管理法不存在该条文。"))
        self.assertFalse(is_refusal("依据《土地管理法》第四十四条，应办理农用地转用审批。"))


if __name__ == "__main__":
    unittest.main()
