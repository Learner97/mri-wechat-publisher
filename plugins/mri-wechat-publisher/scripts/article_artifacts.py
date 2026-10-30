"""Shared local asset cache and immutable review/approval snapshots."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import mimetypes
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image


class AssetStore:
    """Read, decode and encode each local asset at most once per operation."""

    def __init__(self):
        self.files = {}
        self.images = {}
        self.uris = {}
        self.hashes = {}
        self.source_pages = {}

    def source_text(self, path: Path, pages: list[int]) -> str:
        """Read only requested evidence pages, once per operation; never dump a PDF."""
        path = path.resolve()
        if path.suffix.lower() == ".pdf":
            if not pages or not all(type(n) is int and n > 0 for n in pages):
                raise ValueError("PDF摘录需给出1起始页码。")
            missing = set(pages) - {n for p, n in self.source_pages if p == path}
            if missing:
                import pdfplumber
                with pdfplumber.open(io.BytesIO(self.read(path))) as document:
                    for n in sorted(missing):
                        self.source_pages[path, n] = document.pages[n - 1].extract_text() or ""
            return " ".join(self.source_pages[path, n] for n in pages)
        if (path, 0) not in self.source_pages:
            raw = self.read(path)
            self.source_pages[path, 0] = (" ".join(ET.fromstring(raw).itertext())
                                         if path.suffix.lower() in {".xml", ".nxml"} else raw.decode("utf-8-sig"))
        return self.source_pages[path, 0]

    def read(self, path: Path) -> bytes:
        path = path.resolve()
        if path not in self.files:
            self.files[path] = path.read_bytes()
        return self.files[path]

    def digest(self, path: Path) -> str:
        path = path.resolve()
        if path not in self.hashes:
            self.hashes[path] = hashlib.sha256(self.read(path)).hexdigest()
        return self.hashes[path]

    def image(self, path: Path):
        path = path.resolve()
        if path not in self.images:
            with Image.open(io.BytesIO(self.read(path))) as image:
                image.load()
                self.images[path] = image.convert("RGBA")
        return self.images[path]

    def data_uri(self, path: Path) -> str:
        path = path.resolve()
        if path not in self.uris:
            mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            self.uris[path] = f"data:{mime};base64," + base64.b64encode(self.read(path)).decode("ascii")
        return self.uris[path]


def input_hashes(article: dict, article_path: Path, assets: AssetStore) -> dict:
    result = {"article.json": assets.digest(article_path)}
    for name in ("research-facts.json", "fact-coverage-review.json", "figure-readability.json"):
        path = article_path.parent / "work" / name
        if path.is_file():
            result[f"review_input:{name}"] = assets.digest(path)
            if name == "figure-readability.json":
                for item in json.loads(assets.read(path)).get("assets", {}).values():
                    if item.get("screenshot"):
                        result[f"readability_capture:{item['screenshot']}"] = assets.digest(article_path.parent / item["screenshot"])
    manifest = article.get("source", {}).get("source_manifest", "")
    if manifest and not manifest.startswith("internal:"):
        result["source_manifest"] = assets.digest(article_path.parent / manifest)
        data = json.loads(assets.read(article_path.parent / manifest))
        for i, record in enumerate([data.get("main_file", {})] + data.get("supplements", [])):
            if record.get("path"):
                digest = assets.digest(article_path.parent / record["path"])
                if record.get("sha256") and record["sha256"] != digest:
                    raise ValueError("来源文件与已登记清单哈希不符，须重新核验登记。")
                result[f"source_file:{i}"] = digest
    items = [("cover", article.get("cover"))] + [(f["asset_id"], f) for f in article.get("figures", [])]
    for asset_id, item in items:
        if not isinstance(item, dict):
            continue
        path = item.get("path", "")
        if path and not path.startswith(("https://", "http://")):
            result[f"asset:{asset_id}"] = assets.digest(article_path.parent / path)
        original = item.get("image_provenance", {}).get("original_path")
        if original:
            result[f"original:{asset_id}"] = assets.digest(article_path.parent / original)
        decision = item.get("mobile_display", {}).get("crop_review")
        if decision:
            result[f"crop_review:{decision}"] = assets.digest(article_path.parent / decision)
            records = json.loads(assets.read(article_path.parent / decision))
            for key, record in records.items():
                for stage in ("before", "after"):
                    capture = record[stage]["path"]
                    result[f"crop_capture:{decision}:{key}:{stage}"] = assets.digest(article_path.parent / capture)
    return result


def runtime_hashes(assets: AssetStore) -> dict:
    root = Path(__file__).resolve().parent
    names = ("prepare_article.py", "validate_article.py", "validate_figure.py", "article_review.py", "fact_coverage.py",
             "render_wechat_html.py", "render_method_map.py", "article_artifacts.py")
    result = {name: assets.digest(root / name) for name in names}
    result["article.schema.json"] = assets.digest(root.parent / "schemas" / "article.schema.json")
    result["editorial-profile.md"] = assets.digest(root.parent / "docs" / "editorial-profile.md")
    return result


def verify_review(article_path: Path, html_path: Path, *, require_approval: bool = False) -> dict:
    """Check the actual bytes reviewed, approved and about to be uploaded."""
    from render_wechat_html import render_article

    article_path, html_path = article_path.resolve(), html_path.resolve()
    assets = AssetStore()
    article = json.loads(assets.read(article_path).decode("utf-8-sig"))
    if assets.read(html_path).decode("utf-8-sig").replace("\r\n", "\n") != render_article(article):
        raise ValueError("上传HTML与当前JSON的标准渲染不一致，请重新生成并复核。")
    inputs = input_hashes(article, article_path, assets)
    hashes = dict(inputs)
    hashes["upload_html"] = assets.digest(html_path)
    if article.get("schema_version") == 8 and article.get("source", {}).get("evidence_level") == "FULLTEXT":
        folder = html_path.parent
        bundle_path, review_path = folder / "bundle-manifest.json", folder / "qa-review.json"
        bundle = json.loads(assets.read(bundle_path).decode("utf-8"))
        review = json.loads(assets.read(review_path).decode("utf-8"))
        if (bundle.get("status") != "LOCAL_CHECKS_PASSED"
                or bundle.get("inputs_sha256") != inputs
                or bundle.get("renderer_sha256") != runtime_hashes(assets)):
            raise ValueError("成稿输入或校验/渲染代码发生变化，需重新生成和复核。")
        for name, digest in bundle["outputs_sha256"].items():
            if assets.digest(folder / name) != digest:
                raise ValueError(f"成稿文件 {name} 在复核后发生变化。")
        if (review.get("status") != "QA_PASSED"
                or review.get("bundle_sha256") != assets.digest(bundle_path)
                or not all(str(review.get("reviews", {}).get(key, "")).strip()
                           for key in ("scientific_evidence", "reuse_license", "430px_figure_readability"))):
            raise ValueError("缺少与当前成稿绑定的科学、许可和手机端QA记录。")
        from article_review import check_resolutions
        report = json.loads(assets.read(folder / "scientific-review.json"))
        unresolved = check_resolutions(report, review.get("risk_resolutions", []), article, article_path, assets)
        if unresolved:
            raise ValueError("高风险科学主张仍待来源复核：" + "; ".join(unresolved))
        from fact_coverage import coverage_gate
        from validate_figure import readability_gate
        blockers = coverage_gate(report.get("fact_coverage", {})) + readability_gate(article, article_path.parent, assets)
        if blockers:
            raise ValueError("来源覆盖或选图尚未完成：" + "; ".join(blockers))
        hashes["bundle"] = assets.digest(bundle_path)
        hashes["qa_review"] = assets.digest(review_path)
        if require_approval:
            approval = json.loads(assets.read(folder / "draft-approval.json").decode("utf-8"))
            if (approval.get("article_id") != article.get("article_id")
                    or approval.get("artifacts_sha256") != hashes):
                raise ValueError("当前稿与用户批准的版本不同，旧批准已失效。")
    return hashes


def write_approval(article_id: str, html_path: Path, hashes: dict) -> None:
    payload = {"article_id": article_id, "artifacts_sha256": hashes}
    (html_path.parent / "draft-approval.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline=""
    )
