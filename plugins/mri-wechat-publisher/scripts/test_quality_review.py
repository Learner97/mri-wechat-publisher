"""Targeted semantic leads, source-bound review, crop necessity and cache tests."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from article_review import review_article, check_resolutions
from article_artifacts import AssetStore, verify_review
import prepare_article as builder
from validate_article import validate_article
import test_article_images as image_fixtures

ROOT = Path(__file__).resolve().parents[1]
CASES = json.loads((ROOT / "examples/quality-risk-cases.json").read_text(encoding="utf-8"))


class ScientificReviewTests(unittest.TestCase):
    def test_risk_and_nonrisk_cases(self):
        for case in CASES:
            article = {"sections": [{"id": "results", "blocks": [{"type": "paragraph", "text": case["text"]}]}]}
            codes = {f["risk"] for f in review_article(article)["risks"]}
            with self.subTest(case=case["name"]):
                if case["expected"]:
                    self.assertIn(case["expected"], codes)
                else:
                    self.assertEqual(codes, set())
                self.assertEqual(article["sections"][0]["blocks"][0]["text"], case["text"])

    def test_essential_null_requires_result_location(self):
        article = {"sections": [{"id": "results", "blocks": [{"type": "paragraph", "text": "总体治疗效应显著。"}]}],
                   "evidence_map": [{"claim_id": "null", "claim": "治疗交互作用不显著。", "essential_result": True}]}
        self.assertTrue(review_article(article)["risks"][0]["blocking"])
        article["sections"][0]["blocks"][0]["text"] = "治疗交互作用不显著。"
        article["evidence_map"][0]["article_locations"] = ["/sections/0/blocks/0/text"]
        self.assertEqual(review_article(article)["risks"], [])
        article["sections"][0]["id"] = "closing"
        self.assertTrue(review_article(article)["risks"][0]["blocking"])

    def test_same_claim_paraphrase_is_a_review_candidate(self):
        article = {"digest": "两种药物在同一亚组中的反应不同，这种差别值得继续检验。",
                   "sections": [{"id": "overview", "blocks": [{"type": "paragraph", "text": "在该亚组，两个治疗条件呈现不同的反应方向与幅度。"}]}],
                   "evidence_map": [{"claim_id": "shared", "claim": "药物亚组反应不同", "article_locations": ["/digest", "/sections/0/blocks/0/text"]}]}
        candidates = review_article(article)["repetition_candidates"]
        self.assertEqual(candidates[0]["shared_claims"], ["shared"])

    def test_verified_flag_alone_cannot_resolve_risk(self):
        article = {"sections": [{"id": "results", "blocks": [{"type": "paragraph", "text": CASES[3]["text"]}]}]}
        report = review_article(article)
        errors = check_resolutions(report, [{"id": report["risks"][0]["id"], "verified": True}], article, Path("article.json"), AssetStore())
        self.assertTrue(errors)

    def test_source_excerpt_and_changed_claim_binding(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "source.txt"
            source.write_text("Synthetic randomized intervention: treatment reduced the endpoint relative to placebo.", encoding="utf-8")
            manifest = {"main_file": {"path": "source.txt"}}
            (root / "source-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            article = {"source": {"source_manifest": "source-manifest.json"}, "sections": [{"id": "results", "blocks": [{"type": "paragraph", "text": "随机干预显示药物导致实验终点下降。"}]}],
                       "evidence_map": [{"claim_id": "intervention", "claim": "药物降低实验终点", "risk_tags": ["association_causality"], "article_locations": ["/sections/0/blocks/0/text"]}]}
            report = review_article(article)
            resolution = {"id": report["risks"][0]["id"], "decision": "supported", "source_path": "source.txt",
                          "source_locator": "Synthetic fixture sentence 1", "source_excerpt": "treatment reduced the endpoint relative to placebo.",
                          "reason": "Synthetic randomized intervention supports this effect direction; excerpt matching alone is not semantic verification."}
            self.assertEqual(check_resolutions(report, [resolution], article, root / "article.json", AssetStore()), [])
            resolution["source_excerpt"] = "Fabricated source evidence must not be accepted."
            self.assertTrue(check_resolutions(report, [resolution], article, root / "article.json", AssetStore()))
            article["sections"][0]["blocks"][0]["text"] = "随机干预显示药物导致另一实验终点下降。"
            self.assertNotEqual(review_article(article)["risks"][0]["id"], report["risks"][0]["id"])

    def test_title_preference_does_not_force_20_character_limit(self):
        path = ROOT / "examples/phase1-test-article.json"
        article = json.loads(path.read_text(encoding="utf-8"))
        article["title"] = "测试期刊 | " + "测" * 25
        result = validate_article(article, path)
        self.assertEqual(result["errors"], [])
        self.assertTrue(any("偏好长度" in w for w in result["warnings"]))
        article["title"] = "测试期刊 | " + "测" * 65
        self.assertTrue(validate_article(article, path)["errors"])

    def test_actual_pdf_excerpt_requires_correct_page(self):
        # Minimal text PDF fixture; exercise real pdfplumber extraction, not a mocked match.
        text = "Synthetic randomized treatment reduced the endpoint."
        stream = f"BT /F1 12 Tf 30 100 Td ({text}) Tj ET".encode()
        objects = [b"<< /Type /Catalog /Pages 2 0 R >>",
                   b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
                   b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 600 200] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
                   b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
                   b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"]
        pdf, offsets = b"%PDF-1.4\n", [0]
        for n, obj in enumerate(objects, 1):
            offsets.append(len(pdf))
            pdf += f"{n} 0 obj\n".encode() + obj + b"\nendobj\n"
        xref = len(pdf)
        pdf += b"xref\n0 6\n0000000000 65535 f \n" + b"".join(f"{n:010d} 00000 n \n".encode() for n in offsets[1:])
        pdf += f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "source.pdf").write_bytes(pdf)
            (root / "manifest.json").write_text(json.dumps({"main_file": {"path": "source.pdf"}}), encoding="utf-8")
            article = {"source": {"source_manifest": "manifest.json"}, "evidence_map": [
                {"claim_id": "trial", "claim": "随机干预降低终点", "risk_tags": ["association_causality"]}]}
            report = review_article(article)
            resolution = {"id": report["risks"][0]["id"], "decision": "supported", "source_path": "source.pdf", "pages": [1],
                          "source_locator": "Synthetic PDF p.1", "source_excerpt": text,
                          "reason": "Synthetic randomized evidence supports the reported endpoint direction."}
            self.assertEqual(check_resolutions(report, [resolution], article, root / "article.json", AssetStore()), [])
            for pages in ([], [0], [2]):
                resolution["pages"] = pages
                self.assertTrue(check_resolutions(report, [resolution], article, root / "article.json", AssetStore()))

    def test_title_validation_claim_uses_actual_method_context(self):
        article = {"title": "期刊 | MRI模型完成独立临床验证", "method_map": [{"name": "预测", "statistics": "内部交叉验证"}]}
        report = review_article(article)
        self.assertEqual(report["risks"][0]["risk"], "validation_scope")
        self.assertEqual(report["risks"][0]["location"], "/title")

    def test_professional_terms_and_null_results_are_retained(self):
        path = ROOT / "examples/phase1-test-article.json"
        article = json.loads(path.read_text(encoding="utf-8"))
        text = "皮层功能层级和结构路径存在空间对应；治疗交互作用不显著。"
        article["sections"][3]["blocks"].append({"type": "paragraph", "text": text})
        result = validate_article(article, path)
        self.assertEqual(result["errors"], [])
        self.assertFalse(any("AI化或评价性用词" in w for w in result["warnings"]))
        self.assertEqual(article["sections"][3]["blocks"][-1]["text"], text)

    def test_revision_growth_is_bounded_and_protected_sections_stay_locked(self):
        path = ROOT / "examples/phase1-test-article.json"
        baseline = json.loads(path.read_text(encoding="utf-8"))
        article = copy.deepcopy(baseline)
        article["sections"][-1]["blocks"].append({"type": "paragraph", "text": "技术定义需要核对。" * 150})
        self.assertTrue(any("净增超过25%" in e for e in validate_article(article, path, baseline_article=baseline)["errors"]))
        reviewed = validate_article(article, path, baseline_article=baseline, technical_revision_reason="Source-supported technical correction fixture.")
        self.assertFalse(any("净增超过25%" in e for e in reviewed["errors"]))
        article["sections"][0]["blocks"][0]["text"] += "改变前置章节。"
        self.assertTrue(any("局部修改越界" in e for e in validate_article(article, path, baseline_article=baseline, technical_revision_reason="Technical fixture")["errors"]))


class CropAndCacheTests(unittest.TestCase):
    def setUp(self):
        self.helper = image_fixtures.ArticleImageTests()
        self.helper.setUp()
        self.addCleanup(self.helper.doCleanups)

    def edit_record(self, asset, change):
        p = Path(asset["mobile_display"]["crop_review"])
        d = json.loads(p.read_text(encoding="utf-8"))
        change(d["Fig. 1"])
        p.write_text(json.dumps(d), encoding="utf-8")

    def test_crop_needs_whole_image_failure_record(self):
        asset = self.helper.cropped()
        asset["mobile_display"].pop("crop_review")
        self.assertTrue(self.helper.check(asset)["errors"])

    def test_readable_whole_image_cannot_be_cropped(self):
        asset = self.helper.cropped()
        self.edit_record(asset, lambda r: r["before"].update(verdict="readable"))
        self.assertTrue(self.helper.check(asset)["errors"])

    def test_partial_selection_is_not_full_split(self):
        asset = self.helper.cropped()
        asset["mobile_display"]["strategy"] = "split_panel"
        self.assertTrue(any("部分选取" in e for e in self.helper.check(asset)["errors"]))

    def test_complete_split_remains_allowed(self):
        asset = self.helper.cropped()
        asset["mobile_display"]["strategy"] = "split_panel"
        self.edit_record(asset, lambda r: r.update(original_panels=["A"], omitted_panels=[]))
        self.assertEqual(self.helper.check(asset)["errors"], [])

    def test_changed_runtime_invalidates_qa(self):
        path, upload = self.helper.production_bundle()
        with patch("article_artifacts.runtime_hashes", return_value={"changed": "validator"}):
            with self.assertRaises(ValueError):
                verify_review(path, upload)

    def test_wrong_screenshot_hash_is_blocked(self):
        asset = self.helper.cropped()
        self.edit_record(asset, lambda r: r["before"].update(sha256="0" * 64))
        self.assertTrue(self.helper.check(asset)["errors"])

    def test_too_tall_reason_must_match_original(self):
        asset = self.helper.cropped()
        asset["mobile_display"]["crop_reason"] = "too_tall"
        self.assertTrue(any("未达到1.8" in e for e in self.helper.check(asset)["errors"]))
        asset["mobile_display"]["crop_reason"] = "dense_composite"
        self.edit_record(asset, lambda r: r["before"].update(verdict="too_tall"))
        self.assertTrue(any("未达到1.8" in e for e in self.helper.check(asset)["errors"]))

    def test_image_review_changes_invalidate_build(self):
        path, _ = self.helper.production_bundle()
        article = json.loads(path.read_text(encoding="utf-8"))
        article["figures"] = [self.helper.cropped()]
        path.write_text(json.dumps(article), encoding="utf-8")
        self.assertEqual(builder.prepare(path, path.parent)["status"], "LOCAL_CHECKS_PASSED")
        self.assertIn("省略面板", (path.parent / "figure-list.md").read_text(encoding="utf-8"))
        self.assertIn("整图检查", (path.parent / "figure-review.html").read_text(encoding="utf-8"))
        with patch.object(builder, "validate_article", wraps=builder.validate_article) as validate:
            self.edit_record(article["figures"][0], lambda r: r.update(problem="Changed concrete whole-image inspection finding."))
            self.assertEqual(builder.prepare(path, path.parent)["status"], "LOCAL_CHECKS_PASSED")
            self.assertEqual(validate.call_count, 1)
        self.edit_record(article["figures"][0], lambda r: r["before"].update(sha256="0" * 64))
        self.assertEqual(builder.prepare(path, path.parent)["status"], "QA_BLOCKED")

    def test_identical_build_reuses_validation_and_rendering(self):
        path, upload = self.helper.production_bundle()
        # Start without an already-built manifest to measure a cold + identical build.
        (path.parent / "bundle-manifest.json").unlink()
        with patch.object(builder, "validate_article", wraps=builder.validate_article) as validate, \
                patch.object(builder, "render_preview", wraps=builder.render_preview) as render:
            first = builder.prepare(path, path.parent)
            mtime = (path.parent / "preview.html").stat().st_mtime_ns
            self.assertEqual(builder.prepare(path, path.parent), first)
            self.assertEqual(validate.call_count, 1)
            self.assertEqual(render.call_count, 1)
            self.assertEqual((path.parent / "preview.html").stat().st_mtime_ns, mtime)
            upload.write_text("tampered", encoding="utf-8")
            builder.prepare(path, path.parent)
            self.assertEqual(validate.call_count, 2)

    def test_source_mutation_invalidates_build_and_review(self):
        path, upload = self.helper.production_bundle()
        source = path.parent / "main.txt"
        source.write_text("Synthetic source identity", encoding="utf-8")
        manifest = {"main_file": {"path": str(source), "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}}
        (path.parent / "source-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        builder.prepare(path, path.parent)
        source.write_text("Changed source identity", encoding="utf-8")
        self.assertEqual(builder.prepare(path, path.parent)["status"], "QA_BLOCKED")
        with self.assertRaises(ValueError):
            verify_review(path, upload)

    def test_record_qa_cannot_bypass_scientific_risk(self):
        path, upload = self.helper.production_bundle()
        article = json.loads(path.read_text(encoding="utf-8"))
        article["sections"][3]["blocks"].append({"type": "paragraph", "text": CASES[3]["text"]})
        path.write_text(json.dumps(article), encoding="utf-8")
        args = ["prepare_article.py", str(path), "--record-qa", "--scientific-review", "Fixture review",
                "--license-review", "Fixture review", "--visual-review", "Fixture review"]
        with patch("sys.argv", args), patch("builtins.print"):
            self.assertEqual(builder.main(), 1)


if __name__ == "__main__":
    unittest.main()
