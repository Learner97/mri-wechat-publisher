"""Source-first, topic-independent fixtures; real-paper evaluation stays read-only."""
import copy
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from article_artifacts import AssetStore, verify_review
from article_review import review_article
from fact_coverage import review_coverage, coverage_gate
from validate_figure import readability_report, readability_gate
from validate_article import validate_article
import prepare_article as builder
import test_article_images as fixtures


class FactCoverageTests(unittest.TestCase):
    def setUp(self):
        self.helper = fixtures.ArticleImageTests()
        self.helper.setUp()
        self.addCleanup(self.helper.doCleanups)
        self.path, self.upload = self.helper.production_bundle()
        self.root = self.path.parent
        self.article = json.loads(self.path.read_text(encoding="utf-8"))

    def fact(self, *, text="Four systems contain six between-system and four within-system features.", **kwargs):
        src = self.root / "fixture-source.txt"
        src.write_text(text, encoding="utf-8")
        manifest = self.root / "source-manifest.json"
        manifest.write_text(json.dumps({"main_file": {"path": str(src), "sha256": AssetStore().digest(src)}}), encoding="utf-8")
        record = {"id": "source-first", "kind": "matrix", "importance": "core", "statement": text,
                  "anchors": [["网络特征"]], "requires": [["系统内", "内部项"]],
                  "source": {"path": str(src), "locator": "Synthetic fixture sentence 1", "excerpt": text}}
        record.update(kwargs)
        data = {"source_manifest_sha256": AssetStore().digest(manifest), "facts": [record]}
        (self.root / "work/research-facts.json").write_text(json.dumps(data), encoding="utf-8")
        return record

    def body(self, text):
        self.article["sections"][3]["blocks"].append({"type": "paragraph", "text": text})
        self.path.write_text(json.dumps(self.article, ensure_ascii=False), encoding="utf-8")
        return f"/sections/3/blocks/{len(self.article['sections'][3]['blocks'])-1}/text"

    def review(self):
        return review_coverage(self.article, self.path, AssetStore())

    def decide(self, loc, text, **extra):
        d = {"fact_id": "source-first", "status": "accurate", "article_locations": [loc], "article_excerpt": text,
             "reason": "Synthetic source and this body excerpt support the same definition and scope."}
        d.update(extra)
        (self.root / "work/fact-coverage-review.json").write_text(json.dumps({
            "article_sha256": AssetStore().digest(self.path),
            "facts_sha256": AssetStore().digest(self.root / "work/research-facts.json"), "decisions": [d]}), encoding="utf-8")

    def test_matrix_arithmetic_is_not_hardcoded_to_mind_23(self):
        self.fact(matrix={"nodes": 4, "features": 10, "includes_diagonal": True})
        self.body("网络特征形成4节点矩阵，得到10条系统间连接。")
        r = self.review()
        self.assertTrue(r["findings"])
        self.assertIn("6个非重复", r["findings"][0]["check"])
        self.assertTrue(r["findings"][0]["source_locator"])
        self.assertTrue(r["findings"][0]["location"].startswith("/sections/"))

    def test_terms_present_do_not_automatically_prove_accuracy(self):
        self.fact()
        self.body("网络特征包含系统内与系统间项目。")
        r = self.review()
        self.assertEqual(r["items"][0]["proposed_status"], "accurate")
        self.assertEqual(r["items"][0]["status"], "needs_review")
        self.assertTrue(coverage_gate(r))

    def test_verified_true_cannot_replace_semantic_excerpt(self):
        self.fact()
        loc = self.body("网络特征包含系统内与系统间项目。")
        self.decide(loc, "", verified=True)
        self.assertTrue(coverage_gate(self.review()))

    def test_actual_paraphrase_can_be_semantically_resolved_without_synonym_rewrite(self):
        self.fact()
        text = "网络特征也保留每一群脑区内部的平均关系。"
        loc = self.body(text)
        self.assertTrue(self.review()["findings"])
        self.decide(loc, text)
        self.assertEqual(coverage_gate(self.review()), [])
        self.assertEqual(self.article["sections"][3]["blocks"][-1]["text"], text)

    def test_stale_decision_is_not_reused_after_a_single_sentence_changes(self):
        self.fact()
        text = "网络特征包含系统内项目。"
        loc = self.body(text)
        self.decide(loc, text)
        self.assertEqual(coverage_gate(self.review()), [])
        self.body("新增句子导致输入版本变化。")
        self.assertTrue(coverage_gate(self.review()))

    def test_source_excerpt_and_actual_source_hash_are_checked(self):
        self.fact()
        self.body("网络特征包含系统内项目。")
        (self.root / "fixture-source.txt").write_text("Altered source bytes without registration", encoding="utf-8")
        self.assertEqual(self.review()["items"][0]["status"], "source_insufficient")

    def test_malformed_numeric_fact_stays_unreviewed_instead_of_crashing(self):
        self.fact(analysis_n="24")
        self.assertTrue(coverage_gate(self.review()))

    def test_required_negative_interaction_must_be_present_in_its_result(self):
        self.fact(kind="interaction", text="The four-way interaction for compound A versus B was not significant.",
                  anchors=[["药物甲", "药物乙", "四因素"]], requires=[["四因素"], ["不显著"]],
                  applies_when=[["药物甲"], ["药物乙"]], sections=["results"])
        self.body("药物甲与药物乙的两个单独效应方向不同。")
        self.assertTrue(self.review()["findings"])
        self.body("四因素交互不显著，药物臂内简单效应并非两药差异的交互证明。")
        self.assertEqual(self.review()["items"][0]["automatic_suspicions"], [])

    def test_unrelated_total_n_does_not_cover_a_specific_analysis(self):
        self.fact(kind="sample", text="The endpoint association was computed in 24 participants.",
                  anchors=[["终点相关"]], requires=[], analysis_n=24)
        self.body("全队列24人；另一段将报告分析。")
        self.body("终点相关达到显著。")
        self.assertIn("n=24", self.review()["findings"][0]["check"])

    def test_validation_support_can_span_results_and_interpretation(self):
        self.fact(kind="validation", text="The validation used disjoint samples and depends on assumptions.",
                  requires=[["非重叠"], ["假设"]])
        self.body("网络特征在非重叠样本中复现。")
        self.body("网络特征的方向性解释仍依赖工具变量假设。")
        self.assertEqual(self.review()["findings"], [])
        self.assertTrue(coverage_gate(self.review()))  # Still requires semantic source support.

    def test_reasonable_omission_requires_bound_explanation(self):
        self.fact(applies_when=[["不在本文涉及的分析"]])
        r = self.review()
        self.assertEqual(r["items"][0]["proposed_status"], "reasonable_omission")
        self.assertTrue(coverage_gate(r))
        self.decide("", "", status="reasonable_omission", reason="This source result concerns an analysis not discussed in the present article, so its omission does not change the stated inference.")
        self.assertEqual(coverage_gate(self.review()), [])

    def test_legacy_reading_does_not_require_new_sidecars(self):
        (self.root / "work/research-facts.json").unlink()
        self.article["schema_version"] = 7
        self.assertEqual(self.review()["status"], "NOT_REQUIRED")

    def test_qa_rejects_missing_source_facts_even_with_generic_review_notes(self):
        (self.root / "work/research-facts.json").unlink()
        builder.prepare(self.path, self.root)
        with self.assertRaises(ValueError):
            verify_review(self.path, self.upload)

    def test_review_only_change_reuses_render_but_invalidates_old_qa(self):
        target = self.root / "work/fact-coverage-review.json"
        d = json.loads(target.read_text(encoding="utf-8"))
        d["decisions"][0]["reason"] += " A changed review detail."
        target.write_text(json.dumps(d), encoding="utf-8")
        old = (self.root / "preview.html").stat().st_mtime_ns
        with patch.object(builder, "render_preview", wraps=builder.render_preview) as render, patch("fact_coverage.source_excerpt_errors") as extract:
            builder.prepare(self.path, self.root)
            render.assert_not_called()
            extract.assert_not_called()
        self.assertEqual((self.root / "preview.html").stat().st_mtime_ns, old)
        with self.assertRaises(ValueError):
            verify_review(self.path, self.upload)


class PolarityAndFigureTests(unittest.TestCase):
    def test_negative_conditional_and_unrelated_negative_scopes(self):
        safe = ["空间相关仍不足以指定确定的疾病机制。", "若相关能通过随机干预实验验证，才能讨论导致疾病的机制。",
                "未检出显著遗传相关，不能据此认为完全独立。", "随机对照试验显示药物导致终点降低。",
                "变量筛选使用全样本，因此这不是完全独立的无偏外部评估。"]
        unsafe = ["空间相关不代表全部机制，但该相关证明了确定的因果机制。",
                  "相关结果证明了因果机制，不能用于临床诊断。", "未发现显著遗传相关，因此证明两者完全独立。"]
        for text in safe + unsafe:
            report = review_article({"sections": [{"id": "results", "blocks": [{"type": "paragraph", "text": text}]}]})
            with self.subTest(text=text): self.assertEqual(bool(report["risks"]), text in unsafe)

    def test_normal_scientific_evidence_heading_is_allowed(self):
        p = Path(__file__).resolve().parents[1] / "examples/phase1-test-article.json"
        a = json.loads(p.read_text(encoding="utf-8"))
        a["title"] = "Nat Commun | 纵向证据与横断面关联"
        a["sections"][3]["blocks"].append({"type": "subheading", "text": "纵向证据与横断面关联的对应"})
        self.assertEqual(validate_article(a, p)["errors"], [])

    def test_core_and_auxiliary_readability_are_separate(self):
        helper = fixtures.ArticleImageTests(); helper.setUp(); self.addCleanup(helper.doCleanups)
        p, _ = helper.production_bundle()
        article = json.loads(p.read_text(encoding="utf-8")); path = p.parent / "work/figure-readability.json"
        data = json.loads(path.read_text(encoding="utf-8")); row = data["assets"]["fig1"]
        row.update(auxiliary_readable=False, auxiliary_essential=False,
                   auxiliary_reason="Auxiliary ROI abbreviations are not used for the stated core comparison.")
        path.write_text(json.dumps(data), encoding="utf-8")
        self.assertEqual(readability_gate(article, p.parent, AssetStore()), [])
        row["core_readable"] = False; path.write_text(json.dumps(data), encoding="utf-8")
        self.assertTrue(readability_gate(article, p.parent, AssetStore()))
        row.update(core_readable=True, auxiliary_essential=True); path.write_text(json.dumps(data), encoding="utf-8")
        self.assertTrue(readability_gate(article, p.parent, AssetStore()))

    def test_cli_json_is_utf8_even_with_cp1252_environment(self):
        helper = fixtures.ArticleImageTests(); helper.setUp(); self.addCleanup(helper.doCleanups)
        path, _ = helper.production_bundle()
        article = json.loads(path.read_text(encoding="utf-8"))
        article["title"] = "Nat Commun | " + "矩阵计算与核心阴性结果的准确解释" * 2
        path.write_text(json.dumps(article, ensure_ascii=False), encoding="utf-8")
        env = dict(os.environ, PYTHONIOENCODING="cp1252")
        for script in ("validate_article.py", "prepare_article.py"):
            with self.subTest(script=script):
                result = subprocess.run([sys.executable, str(Path(__file__).with_name(script)), str(path)],
                                        env=env, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", errors="replace"))
                output = result.stdout.decode("utf-8")
                self.assertIn("标题题眼", output)
                self.assertTrue(json.loads(output)["warnings"])

    def test_selection_preview_does_not_require_a_generated_article(self):
        helper = fixtures.ArticleImageTests(); helper.setUp(); self.addCleanup(helper.doCleanups)
        path = helper.root / "candidates.json"
        path.write_text(json.dumps({"figures": [helper.asset]}), encoding="utf-8")
        with patch("sys.argv", ["prepare_article.py", str(path), "--figures-only"]), patch("builtins.print"):
            self.assertEqual(builder.main(), 0)
        self.assertTrue((helper.root / "figure-review.html").is_file())
        self.assertFalse((helper.root / "qa-review.json").exists())


if __name__ == "__main__":
    unittest.main()
