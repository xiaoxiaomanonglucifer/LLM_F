"""湖南非法占地案件层单元测试（unittest，无需 pytest）。

运行：python -m unittest discover -s tests -v
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from legal_rag.cases.build_case_graph import CaseGraph  # noqa: E402
from legal_rag.cases.case_qa import CaseQASystem, extract_question_facts  # noqa: E402
from legal_rag.cases.extract import (  # noqa: E402
    ArticleResolver,
    _extract_behavior,
    _extract_land_use,
    _mask_pii,
    _sentences,
    _split_citations,
)
from legal_rag.cases.retriever import CaseRetriever  # noqa: E402
from legal_rag.cases.schema import case_text  # noqa: E402


def _article(article_id: str, citation: str, law_title: str, text: str) -> dict:
    return {"article_id": article_id, "citation": citation, "law_title": law_title, "text": text}


def _case(case_id: str, **overrides) -> dict:
    case = {
        "case_id": case_id,
        "decision_no": f"决定书{case_id}",
        "decision_date": "2025-01-01",
        "agency": "某县自然资源局",
        "party": {"type": "单位", "name": "某公司"},
        "behavior": ["未经批准占用土地"],
        "scope_status": "included",
        "facts": "某公司未经批准占用耕地建设厂房。",
        "land_use": [{"type": "耕地", "group": "其他耕地", "area_m2": 100.0}],
        "area_m2": 100.0,
        "project_nature": "非公益",
        "violated_articles": [
            {
                "article_id": "law-land-admin#a0002",
                "article_num": 2,
                "resolved": True,
                "citation": "《中华人民共和国土地管理法》第二条",
            }
        ],
        "penalty_basis_articles": [
            {
                "article_id": "law-land-admin#a0077",
                "article_num": 77,
                "resolved": True,
                "citation": "《中华人民共和国土地管理法》第七十七条",
            }
        ],
        "penalty_types": ["罚款"],
        "fine_amount": 40000.0,
        "fine_rate": [{"land": "耕地", "group": "其他耕地", "yuan_per_m2": 400.0, "area_m2": 100.0}],
        "factors": [],
    }
    case.update(overrides)
    return case


class TestOldArticleMapping(unittest.TestCase):
    def test_land_law_76_maps_to_77(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "articles.jsonl"
            rows = [
                {"doc_id": "law-land-admin", "law_title": "中华人民共和国土地管理法", "article_num": 76, "article_id": "law-land-admin#a0076", "article_no": "第七十六条", "citation": "《中华人民共和国土地管理法》第七十六条"},
                {"doc_id": "law-land-admin", "law_title": "中华人民共和国土地管理法", "article_num": 77, "article_id": "law-land-admin#a0077", "article_no": "第七十七条", "citation": "《中华人民共和国土地管理法》第七十七条"},
                {"doc_id": "reg-land-admin", "law_title": "中华人民共和国土地管理法实施条例", "article_num": 42, "article_id": "reg-land-admin#a0042", "article_no": "第四十二条", "citation": "《中华人民共和国土地管理法实施条例》第四十二条"},
                {"doc_id": "reg-land-admin", "law_title": "中华人民共和国土地管理法实施条例", "article_num": 57, "article_id": "reg-land-admin#a0057", "article_no": "第五十七条", "citation": "《中华人民共和国土地管理法实施条例》第五十七条"},
            ]
            path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows), encoding="utf-8")
            resolver = ArticleResolver(path)
            land = resolver.resolve("中华人民共和国土地管理法", 76, version_year=2004)
            reg = resolver.resolve("中华人民共和国土地管理法实施条例", 42, version_year=2014)
            self.assertEqual(land["article_num"], 77)
            self.assertEqual(land["cited_article_num"], 76)
            self.assertTrue(land["mapped_from_old_version"])
            self.assertEqual(reg["article_num"], 57)
            self.assertEqual(reg["cited_article_num"], 42)
            self.assertTrue(reg["mapped_from_old_version"])


class TestBehaviorAndLand(unittest.TestCase):
    def test_over_approval_not_unauthorized(self):
        behaviors = _extract_behavior("某公司经批准占用土地后，超过批准数量占用园地1062平方米、草地9平方米")
        self.assertIn("超过批准数量占用土地", behaviors)
        self.assertNotIn("未经批准占用土地", behaviors)

    def test_change_of_use_is_excluded_not_unauthorized(self):
        behaviors = _extract_behavior("某公司经批准占用耕地后，未按批准用途使用土地，擅自建设厂房")
        self.assertEqual(behaviors, ["未按批准用途使用土地"])

    def test_subtypes(self):
        self.assertIn("临时用地", _extract_behavior("未经批准占用耕地作为临时用地"))
        self.assertIn("设施农用地", _extract_behavior("未经批准占用耕地作为设施农用地"))

    def test_land_list_and_missing_land(self):
        items = _extract_land_use("耕地722平方米、园地315平方米、林地163平方米、其他土地69平方米")
        self.assertEqual(len(items), 4)
        self.assertEqual(sum(item["area_m2"] for item in items), 1269.0)
        self.assertEqual(_extract_land_use("占用土地13070.5平方米，但未查清地类"), [])

    def test_question_facts_sum_and_explicit_total(self):
        summed = extract_question_facts("2025年，某项目未经批准占用耕地2659平方米、其他土地2527平方米")
        self.assertEqual(summed["area_m2"], 5186.0)
        self.assertEqual(len(summed["land_use"]), 2)
        partial = extract_question_facts(
            "2025年，某项目未经批准占用土地4649平方米，其中永久基本农田238.87平方米、其他土地1111.55平方米"
        )
        self.assertEqual(partial["area_m2"], 4649.0)
        self.assertEqual(len(partial["land_use"]), 2)
        over = extract_question_facts(
            "2025年，某非公益项目经批准占用土地后，超过批准数量占用园地1062平方米、草地9平方米"
        )
        self.assertEqual(over["area_m2"], 1071.0)
        self.assertEqual(len(over["land_use"]), 2)


class TestMaskAndParsing(unittest.TestCase):
    def test_mask_pii(self):
        text = "联系电话13812345678，法定代表人：张三，身份证430102199001011234。"
        masked = _mask_pii(text, {"type": "个人", "name": "张三"})
        self.assertNotIn("13812345678", masked)
        self.assertNotIn("430102199001011234", masked)
        self.assertNotIn("张三", masked)
        self.assertIn("张某", masked)

    def test_mask_third_party_names(self):
        text = (
            "被授权人身份证复印件（康彬）；蒋金芳《身份证现场照片》；"
            "联系人：莫某 王册；被处罚人：祁阳市半岛大酒店有限公司；"
            "法定代表人授权委托书；法定代表人身份证复印件。"
        )
        masked = _mask_pii(text, {"type": "单位", "name": "某公司"})
        self.assertNotIn("康彬", masked)
        self.assertNotIn("蒋金芳", masked)
        self.assertNotIn("王册", masked)
        self.assertIn("康某", masked)
        self.assertIn("蒋某", masked)
        self.assertIn("王某", masked)
        self.assertIn("祁阳市半岛大酒店有限公司", masked)
        self.assertIn("法定代表人授权委托书", masked)

    def test_quote_aware_sentences(self):
        sentences = _sentences("“第一句。第二句。”第三句；第四句。")
        self.assertEqual(len(sentences), 2)
        self.assertIn("第一句。第二句。", sentences[0])
        self.assertEqual(sentences[1], "第四句")

    def test_policy_title_not_article(self):
        mentions = [
            {"law": "中华人民共和国土地管理法", "article_num": 77},
            {"law": "湖南省自然资源行政处罚裁量权基准", "article_num": 1},
        ]
        articles, policies = _split_citations(mentions)
        self.assertEqual([item["article_num"] for item in articles], [77])
        self.assertEqual(policies, ["湖南省自然资源行政处罚裁量权基准"])


class TestCaseViews(unittest.TestCase):
    def test_case_text_excludes_outcome_by_default(self):
        case = _case("c1", fine_amount=999999.0)
        text = case_text(case)
        self.assertNotIn("999999", text)
        self.assertIn("999999", case_text(case, include_outcome=True))

    def test_retriever_and_exclusion(self):
        c1 = _case("c1")
        c2 = _case(
            "c2",
            behavior=["超过批准数量占用土地"],
            facts="某公司超过批准数量占用其他土地建设厂房。",
            land_use=[{"type": "其他土地", "group": "其他土地", "area_m2": 200.0}],
            area_m2=200.0,
        )
        retriever = CaseRetriever([c1, c2])
        hits = retriever.search("未经批准占用耕地", top_k=1)
        self.assertEqual(hits[0].case_id, "c1")
        excluded = retriever.search("未经批准占用耕地", top_k=2, exclude_case_id="c1")
        self.assertNotIn("c1", [hit.case_id for hit in excluded])

    def test_case_graph_related(self):
        c1 = _case("c1")
        c2 = _case("c2")
        graph = CaseGraph([c1, c2])
        self.assertEqual(graph.case_count, 2)
        related = [case_id for case_id, _ in graph.related_cases("c1")]
        self.assertIn("c2", related)
        self.assertIn("未经批准占用土地", graph.stats()["by_behavior"])


class TestCaseQA(unittest.TestCase):
    def setUp(self):
        self.articles = {
            "law-land-admin#a0002": _article("law-land-admin#a0002", "《中华人民共和国土地管理法》第二条", "中华人民共和国土地管理法", "任何单位和个人不得侵占、买卖或者以其他形式非法转让土地。"),
            "law-land-admin#a0044": _article("law-land-admin#a0044", "《中华人民共和国土地管理法》第四十四条", "中华人民共和国土地管理法", "建设占用土地，涉及农用地转为建设用地的，应当办理农用地转用审批手续。"),
            "law-land-admin#a0077": _article("law-land-admin#a0077", "《中华人民共和国土地管理法》第七十七条", "中华人民共和国土地管理法", "未经批准或者采取欺骗手段骗取批准，非法占用土地的，责令退还非法占用的土地，可以并处罚款。"),
            "reg-land-admin#a0057": _article("reg-land-admin#a0057", "《中华人民共和国土地管理法实施条例》第五十七条", "中华人民共和国土地管理法实施条例", "罚款额为非法占用土地每平方米100元以上1000元以下。"),
            "hn-land-admin-implementation#a0055": _article("hn-land-admin-implementation#a0055", "《湖南省实施《中华人民共和国土地管理法》办法》第五十五条", "湖南省实施《中华人民共和国土地管理法》办法", "占用永久基本农田的，处每平方米五百元以上一千元以下罚款。"),
            "law-land-admin#a0057": _article("law-land-admin#a0057", "《中华人民共和国土地管理法》第五十七条", "中华人民共和国土地管理法", "临时用地应当经批准。"),
            "law-land-admin#a0037": _article("law-land-admin#a0037", "《中华人民共和国土地管理法》第三十七条", "中华人民共和国土地管理法", "设施农用地按照有关规定管理。"),
        }
        self.cfg = {"retrieval": {"top_k": 5, "case_top_k": 3}}
        self.system = CaseQASystem(self.cfg, self.articles)

    def test_g0_has_no_law_or_fine_leakage(self):
        result = self.system.analyze(
            "某公司未经批准占用耕地5000平方米建设项目，符合村庄规划，属于非公益项目，应如何处罚？",
            "G0",
        )
        self.assertEqual(result["citations"], [])
        self.assertEqual(result["similar_cases"], [])
        self.assertIsNone(result["steps"]["discretion"]["predicted_fine_range"])
        self.assertIn("未启用条文检索", result["answer"])

    def test_g1_current_standard_calculation(self):
        result = self.system.analyze(
            "某公司未经批准占用耕地5000平方米建设项目，符合村庄规划，属于非公益项目，应如何处罚？",
            "G1",
        )
        self.assertEqual(
            result["steps"]["discretion"]["predicted_fine_range"], [2000000.0, 2500000.0]
        )
        self.assertTrue(any("第七十七条" in item for item in result["citations"]))
        self.assertIn("没收", result["steps"]["conclusion"]["text"])

    def test_legacy_year_does_not_apply_current_bracket(self):
        result = self.system.analyze(
            "2021年7月，某非公益项目未经批准占用耕地723.14平方米建设样板房，应如何处罚？",
            "G1",
        )
        discretion = result["steps"]["discretion"]
        self.assertFalse(discretion["current_standard_applied"])
        self.assertIsNone(discretion["predicted_fine_range"])
        self.assertIn("湘自然资规〔2019〕5号", discretion["version_note"])

    def test_excluded_change_of_use(self):
        result = self.system.analyze(
            "某公司经批准占用耕地后，未按批准用途使用土地，擅自建设厂房，应如何处罚？",
            "G1",
        )
        self.assertEqual(result["steps"]["characterization"]["scope_status"], "excluded")
        self.assertIn("第81条", result["steps"]["conclusion"]["text"])

    def test_partial_land_does_not_give_total(self):
        result = self.system.analyze(
            "2025年，某项目未经批准占用土地4649平方米，其中永久基本农田238.87平方米、其他土地1111.55平方米，其余地类不明，应如何处罚？",
            "G1",
        )
        discretion = result["steps"]["discretion"]
        self.assertTrue(discretion["needs_land_type"])
        self.assertIsNone(discretion["predicted_fine_range"])
        self.assertEqual(discretion["partial_fine_range"], [230590.0, 572335.0])


if __name__ == "__main__":
    unittest.main()
