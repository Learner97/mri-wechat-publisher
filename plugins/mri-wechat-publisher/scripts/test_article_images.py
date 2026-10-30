"""Regression tests for original figures, preview delivery and reproducible bundles."""

import copy
import hashlib
import json
import shutil
import unittest
import uuid
import sqlite3
import contextlib
import io
from unittest.mock import patch
from pathlib import Path

from lxml import html
from PIL import Image

from fetch_nature_article import choose_image_url
from prepare_article import prepare
from render_wechat_html import render_article, render_preview
from validate_figure import validate_figure
from wechat_draft_api import WeChatApiError, validate_upload_html
from validate_article import validate_article
from article_artifacts import AssetStore, verify_review, write_approval


class ArticleImageTests(unittest.TestCase):
    def setUp(self):
        test_root = (Path.cwd() / "tmp" / "mri-image-tests").resolve()
        self.root = test_root / uuid.uuid4().hex
        self.root.mkdir(parents=True)
        self.root.relative_to(test_root)
        self.addCleanup(shutil.rmtree, self.root)
        self.original = self.root / "original.png"
        image = Image.new("RGBA", (1000, 700), "white")
        image.putpixel((5, 5), (200, 50, 100, 255))
        image.save(self.original)
        self.asset = {
            "asset_id": "fig1", "figure_id": "Fig. 1", "path": str(self.original),
            "alt": "测试原图", "caption": "图1｜原图", "source": "test fixture",
            "license_note": "CC BY 4.0",
            "image_provenance": {"original_path": str(self.original),
                                 "original_sha256": hashlib.sha256(self.original.read_bytes()).hexdigest(),
                                 "source_locator": "Test fixture, Fig. 1"},
            "mobile_display": {"strategy": "native", "source_figure_id": "Fig. 1",
                               "panel_label": "整图", "review_note": "离线测试素材"},
        }

    def check(self, asset=None, **kwargs):
        return validate_figure(asset or self.asset, self.root, **kwargs)

    def test_original_pixels_pass(self):
        self.assertEqual(self.check()["errors"], [])

    def test_test_covers_cannot_be_relabelled_as_production_sources(self):
        root = Path(__file__).resolve().parents[1] / "assets"
        for name in ("phase1-test-cover.png", "phase2-feature-selection-cover.png"):
            copied = self.root / name
            shutil.copyfile(root / name, copied)
            asset = copy.deepcopy(self.asset)
            asset["path"] = str(copied)
            asset["image_provenance"].update(
                original_path=str(copied),
                original_sha256=hashlib.sha256(copied.read_bytes()).hexdigest(),
            )
            with self.subTest(fixture=name):
                self.assertTrue(any("开发测试图片" in error for error in self.check(asset, cover=True)["errors"]))

    def test_rgb_change_with_unchanged_alpha_is_blocked(self):
        modified = self.root / "modified.png"
        with Image.open(self.original) as image:
            image.putpixel((5, 5), (1, 2, 3, 255))
            image.save(modified)
        self.asset["path"] = str(modified)
        self.assertTrue(self.check()["errors"])

    def test_changed_original_hash_is_blocked(self):
        self.asset["image_provenance"]["original_sha256"] = "0" * 64
        self.assertTrue(self.check()["errors"])

    def test_missing_provenance_is_blocked(self):
        self.asset.pop("image_provenance")
        self.assertTrue(self.check()["errors"])

    def test_renumbered_caption_is_blocked(self):
        self.asset["caption"] = "图2｜被重新编号"
        self.assertTrue(self.check()["errors"])

    def test_html_disguised_as_png_is_blocked(self):
        invalid = self.root / "invalid.png"
        invalid.write_bytes(b"<html>download failed</html>")
        self.asset["path"] = str(invalid)
        self.assertTrue(self.check()["errors"])

    def test_tall_body_original_is_blocked(self):
        Image.new("RGBA", (1000, 1800), "white").save(self.original)
        self.asset["image_provenance"]["original_sha256"] = hashlib.sha256(self.original.read_bytes()).hexdigest()
        self.assertTrue(self.check()["errors"])

    def cropped(self):
        asset = copy.deepcopy(self.asset)
        path = self.root / "cropped.png"
        with Image.open(self.original) as image:
            image.crop((0, 0, 500, 600)).save(path)
        asset["path"] = str(path)
        asset["mobile_display"].update(strategy="selected_panels", crop_box=[0, 0, 500, 600],
                                      crop_reason="dense_composite", annotations_preserved=True)
        screenshot = self.root / "430px-fixture.png"
        Image.new("RGB", (430, 300), "white").save(screenshot)
        capture = {"path": str(screenshot), "sha256": hashlib.sha256(screenshot.read_bytes()).hexdigest()}
        record = {"original_sha256": asset["image_provenance"]["original_sha256"],
                  "before": {**capture, "verdict": "unreadable"}, "after": {**capture, "verdict": "readable"},
                  "problem": "Offline fixture: axis text too small in whole figure.",
                  "alternative": "Offline fixture: larger complete panel group reviewed.",
                  "retained_context": "Offline fixture: full axes, comparison groups and legend retained.",
                  "original_panels": ["A", "B"], "displayed_panels": {"fig1": ["A"]},
                  "omitted_panels": ["B"], "omission_reason": "Offline fixture only: B has no required comparison."}
        decision = self.root / "crop-review.json"
        decision.write_text(json.dumps({"Fig. 1": record, "cover": record}), encoding="utf-8")
        asset["mobile_display"]["crop_review"] = str(decision)
        return asset

    def test_exact_crop_with_review_passes(self):
        self.assertEqual(self.check(self.cropped())["errors"], [])

    def test_crop_without_annotation_confirmation_is_blocked(self):
        asset = self.cropped()
        asset["mobile_display"]["annotations_preserved"] = False
        self.assertTrue(self.check(asset)["errors"])

    def test_false_crop_bounds_are_blocked(self):
        asset = self.cropped()
        asset["mobile_display"]["crop_box"] = [5, 5, 505, 605]
        self.assertTrue(self.check(asset)["errors"])

    def test_nd_crop_is_blocked(self):
        asset = self.cropped()
        asset["license_note"] = "CC BY-NC-ND 4.0"
        self.assertTrue(self.check(asset)["errors"])

    def test_cover_ratio_is_not_a_body_crop_reason(self):
        asset = self.cropped()
        asset["mobile_display"]["crop_reason"] = "cover_ratio"
        self.assertTrue(self.check(asset)["errors"])
        self.assertEqual(self.check(asset, cover=True)["errors"], [])

    def test_nature_uses_full_png_not_last_thumbnail(self):
        figure = html.fromstring('<figure><source srcset="//media.springernature.com/lw1200/springer-static/image/a.png?as=webp"><img src="//media.springernature.com/lw685/springer-static/image/a.png"></figure>')
        self.assertEqual(choose_image_url(figure, "https://www.nature.com"),
                         "https://media.springernature.com/full/springer-static/image/a.png")

    def test_bundle_reproduces_and_upload_rejects_preview(self):
        fixture = Path(__file__).parents[1] / "examples" / "phase1-test-article.json"
        article = json.loads(fixture.read_text(encoding="utf-8"))
        article["cover"]["path"] = str(self.original)
        article["figures"] = [self.asset]
        article["sections"][3]["blocks"].append({"type": "image", "asset_id": "fig1"})
        path = self.root / "article.json"
        path.write_text(json.dumps(article, ensure_ascii=False), encoding="utf-8")
        output = self.root / "bundle"
        first = prepare(path, output)
        self.assertEqual(first["status"], "LOCAL_CHECKS_PASSED", first)
        before = {p.name: p.read_bytes() for p in output.iterdir()}
        self.assertEqual(prepare(path, output), first)
        self.assertEqual({p.name: p.read_bytes() for p in output.iterdir()}, before)
        preview = render_preview(article, path)
        self.assertIn('src="data:image/png;base64,', preview)
        self.assertNotIn("wechat-asset://", preview)
        self.assertLess(len(before["article.html"]), 1024)
        self.assertIn(b'url=preview.html', before["article.html"])
        self.assertNotIn(b'data:image/', before["figure-review.html"])
        validate_upload_html(article, render_article(article))
        with self.assertRaises(WeChatApiError):
            validate_upload_html(article, preview)
        with self.assertRaises(WeChatApiError):
            validate_upload_html(article, render_article(article).replace("wechat-asset://fig1", "https://wrong.example/image.png"))
        with self.assertRaises(WeChatApiError):
            validate_upload_html(article, render_article(article).replace(article["title"], "不对应的标题"))

    def production_bundle(self):
        fixture = Path(__file__).parents[1] / "examples" / "phase1-test-article.json"
        article = json.loads(fixture.read_text(encoding="utf-8"))
        article["source"].update(evidence_level="FULLTEXT", fulltext_verified=True,
                                 source_manifest=str(self.root / "source-manifest.json"))
        source = self.root / "fixture-source.txt"
        source.write_text("Offline fixture evidence only. " + article["sections"][0]["blocks"][0]["text"], encoding="utf-8")
        (self.root / "source-manifest.json").write_text(json.dumps({"main_file": {
            "path": str(source), "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}}), encoding="utf-8")
        article["figures"] = [self.asset]
        article["sections"][3]["blocks"].append({"type": "image", "asset_id": "fig1"})
        article["cover"] = {key: self.asset[key] for key in ("figure_id", "path", "alt", "image_provenance", "mobile_display")}
        article["cover"]["source_note"] = "Internal offline fixture only"
        path = self.root / "article.json"
        path.write_text(json.dumps(article, ensure_ascii=False), encoding="utf-8")
        work = self.root / "work"
        work.mkdir(exist_ok=True)
        text = article["sections"][0]["blocks"][0]["text"]
        facts = {"source_manifest_sha256": AssetStore().digest(self.root / "source-manifest.json"), "facts": [
            {"id": "fixture", "kind": "definition", "importance": "core", "statement": text,
             "anchors": [[text[:8]]], "requires": [[text[8:16]]],
             "source": {"path": str(source), "locator": "Offline fixture sentence", "excerpt": text}}]}
        facts_path = work / "research-facts.json"
        facts_path.write_text(json.dumps(facts), encoding="utf-8")
        (work / "fact-coverage-review.json").write_text(json.dumps({"article_sha256": AssetStore().digest(path),
            "facts_sha256": AssetStore().digest(facts_path), "decisions": [{"fact_id": "fixture", "status": "accurate",
            "article_locations": ["/sections/0/blocks/0/text"], "article_excerpt": text,
            "reason": "Offline fixture source and body match; no real paper approval is asserted."}]}), encoding="utf-8")
        capture = work / "fixture-430.png"
        Image.new("RGB", (430, 300), "white").save(capture)
        (work / "figure-readability.json").write_text(json.dumps({"viewport_css_px": 430, "content_width_css_px": 422,
            "assets": {"fig1": {"asset_sha256": AssetStore().digest(self.original), "screenshot": str(capture),
            "screenshot_sha256": AssetStore().digest(capture), "core_labels": ["Synthetic fixture only"],
            "core_readable": True, "auxiliary_readable": True,
            "reason": "Offline synthetic screenshot contract fixture, not an actual visual approval."}}}), encoding="utf-8")
        self.assertEqual(prepare(path, self.root)["status"], "LOCAL_CHECKS_PASSED")
        review = {"status": "QA_PASSED", "bundle_sha256": AssetStore().digest(self.root / "bundle-manifest.json"),
                  "reviews": {key: "Offline test fixture review" for key in (
                      "scientific_evidence", "reuse_license", "430px_figure_readability")}}
        (self.root / "qa-review.json").write_text(json.dumps(review), encoding="utf-8")
        return path, self.root / "wechat-upload.html"

    def test_schema_unknown_fields_block_before_image_work(self):
        path, _ = self.production_bundle()
        article = json.loads(path.read_text(encoding="utf-8"))
        article["unexpected_typo_field"] = "bad field"
        with patch("article_artifacts.AssetStore.image") as decode:
            result = validate_article(article, path)
        self.assertEqual(result["status"], "QA_BLOCKED")
        decode.assert_not_called()

    def test_review_and_approval_bind_every_input(self):
        path, upload = self.production_bundle()
        hashes = verify_review(path, upload)
        write_approval(json.loads(path.read_text(encoding="utf-8"))["article_id"], upload, hashes)
        self.assertEqual(verify_review(path, upload, require_approval=True), hashes)
        for target in (path, self.original, self.root / "source-manifest.json", upload,
                       self.root / "preview.html", self.root / "qa-review.json"):
            original = target.read_bytes()
            target.write_bytes(original + b" ")
            with self.assertRaises((ValueError, OSError)):
                verify_review(path, upload, require_approval=True)
            target.write_bytes(original)

    def test_rebuilding_after_edit_invalidates_review(self):
        path, upload = self.production_bundle()
        article = json.loads(path.read_text(encoding="utf-8"))
        article["digest"] = "更新后的离线测试导读。"
        path.write_text(json.dumps(article, ensure_ascii=False), encoding="utf-8")
        self.assertEqual(prepare(path, self.root)["status"], "LOCAL_CHECKS_PASSED")
        with self.assertRaises(ValueError):
            verify_review(path, upload)

    def test_assets_are_read_decoded_and_encoded_once(self):
        fixture = Path(__file__).parents[1] / "examples" / "phase1-test-article.json"
        article = json.loads(fixture.read_text(encoding="utf-8"))
        article["cover"]["path"] = str(self.original)
        article["figures"] = [self.asset]
        article["sections"][3]["blocks"].append({"type": "image", "asset_id": "fig1"})
        path = self.root / "article.json"
        path.write_text(json.dumps(article, ensure_ascii=False), encoding="utf-8")
        original_read = Path.read_bytes
        reads = []
        def track_read(path):
            reads.append(path.resolve())
            return original_read(path)
        with patch.object(Path, "read_bytes", track_read), patch("article_artifacts.Image.open", wraps=Image.open) as decode:
            self.assertEqual(prepare(path, self.root)["status"], "LOCAL_CHECKS_PASSED")
        self.assertEqual(reads.count(self.original.resolve()), 1)
        self.assertEqual(decode.call_count, 1)

    def test_state_rejects_stale_qa_and_approval(self):
        import workflow_state_db as store
        path, upload = self.production_bundle()
        article = json.loads(path.read_text(encoding="utf-8"))
        db = sqlite3.connect(":memory:", isolation_level=None)
        db.row_factory = sqlite3.Row
        self.addCleanup(db.close)
        db.executescript(store.SCHEMA_SQL)
        db.execute("INSERT INTO papers(paper_id,canonical_key,doi,title,first_seen_at,updated_at) VALUES(1,'p',?,'Paper','t','t')", (article["source"]["doi"],))
        db.execute("INSERT INTO cycles(cycle_id,status,selected_paper_id,created_at,updated_at) VALUES('test','WRITING',1,'t','t')")
        db.execute("INSERT INTO source_gates(cycle_id,paper_id,access_status,gate_status,access_check_json,input_dir,source_dir,manifest_path,created_at,updated_at) VALUES('test',1,'USER_UPLOAD_REQUIRED','SOURCE_VALIDATED','{}','input','source',?,'t','t')", (str(self.root / "source-manifest.json"),))
        with patch.object(store, "export_compatibility"):
            store.set_artifacts(db, "test", str(path), str(self.root / "preview.html"), "QA_PASSED")
            store.approve_draft(db, "test")
            verify_review(path, upload, require_approval=True)
            review_path = self.root / "qa-review.json"
            review_path.write_text(review_path.read_text(encoding="utf-8") + " ", encoding="utf-8")
            with self.assertRaises(ValueError):
                store.approve_draft(db, "test")
            with self.assertRaises(ValueError):
                verify_review(path, upload, require_approval=True)
            store.set_artifacts(db, "test", str(path), str(self.root / "preview.html"), "QA_PASSED")
            self.assertEqual(db.execute("SELECT user_draft_approval FROM cycles WHERE cycle_id='test'").fetchone()[0], 0)
            store.approve_draft(db, "test")
            verify_review(path, upload, require_approval=True)
            store.set_artifacts(db, "test", str(path), str(self.root / "preview.html"), "QA_PASSED")
            self.assertEqual(db.execute("SELECT user_draft_approval FROM cycles WHERE cycle_id='test'").fetchone()[0], 1)

    def test_api_blocks_stale_approval_before_network(self):
        import wechat_draft_api as api
        path, upload = self.production_bundle()
        article = json.loads(path.read_text(encoding="utf-8"))
        write_approval(article["article_id"], upload, verify_review(path, upload))
        review_path = self.root / "qa-review.json"
        review_path.write_text(review_path.read_text(encoding="utf-8") + " ", encoding="utf-8")
        with patch("sys.argv", ["wechat_draft_api.py", str(path), str(upload), "--execute",
                                "--approval-token", api.APPROVAL_TOKEN]), \
                patch.object(api, "load_env_file"), patch.object(api, "get_stable_token") as network, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(api.main(), 1)
        network.assert_not_called()

    def test_qa_record_requires_actual_notes_before_rebuild(self):
        import prepare_article as builder
        path, upload = self.production_bundle()
        with patch("sys.argv", ["prepare_article.py", str(path), "--record-qa"]), \
                patch.object(builder, "prepare") as rebuild, \
                contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            builder.main()
        rebuild.assert_not_called()
        args = ["prepare_article.py", str(path), "--record-qa", "--scientific-review", "Offline scientific fixture",
                "--license-review", "Offline license fixture", "--visual-review", "Offline visual fixture"]
        with patch("sys.argv", args), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(builder.main(), 0)
        self.assertIn("qa_review", verify_review(path, upload))


if __name__ == "__main__":
    unittest.main()
