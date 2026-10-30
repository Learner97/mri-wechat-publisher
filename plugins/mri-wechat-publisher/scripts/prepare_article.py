#!/usr/bin/env python3
"""Rebuild a local article bundle from frozen JSON and original images, without network/API writes."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from render_method_map import render_method_map
from render_wechat_html import build_embedded_asset_sources, render_article, render_preview
from validate_article import load_article, validate_article
from article_artifacts import AssetStore, input_hashes, runtime_hashes
from article_review import check_resolutions
from validate_figure import crop_decision, figure_preview, readability_report, readability_gate, validate_figure
from fact_coverage import coverage_gate, render_facts


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(article_path: Path, output_dir: Path) -> dict:
    article_path = article_path.resolve()
    output_dir = output_dir.resolve()
    assets = AssetStore()
    article = json.loads(assets.read(article_path).decode("utf-8-sig"))
    cached, intact, reuse_render = None, False, False
    try:
        inputs = input_hashes(article, article_path, assets)
        runtime = runtime_hashes(assets)
        existing = output_dir / "bundle-manifest.json"
        if existing.is_file():
            cached = json.loads(assets.read(existing))
            intact = bool(cached.get("outputs_sha256")) and all(
                assets.digest(output_dir / name) == digest for name, digest in cached["outputs_sha256"].items())
            if (cached.get("status") == "LOCAL_CHECKS_PASSED"
                    and cached.get("inputs_sha256") == inputs
                    and cached.get("renderer_sha256") == runtime
                    and cached.get("outputs_sha256")
                    and "scientific-review.json" in cached["outputs_sha256"]
                    and intact):
                return cached
            render_inputs = lambda value: {k: v for k, v in value.items()
                                            if k == "article.json" or k.startswith(("asset:", "original:"))}
            reuse_render = intact and cached.get("renderer_sha256") == runtime and render_inputs(cached.get("inputs_sha256", {})) == render_inputs(inputs)
            proof_inputs = lambda value: {k: v for k, v in value.items() if k in {"source_manifest", "review_input:research-facts.json"} or k.startswith("source_file:")}
            old_coverage = cached.get("validation", {}).get("semantic_review", {}).get("fact_coverage", {})
            if (intact and cached.get("renderer_sha256") == runtime and "review_input:research-facts.json" in inputs
                    and proof_inputs(cached.get("inputs_sha256", {})) == proof_inputs(inputs)
                    and old_coverage.get("items") and "source_errors" in old_coverage):
                assets.fact_source_cache = old_coverage  # Literal source proof only; never semantic QA/approval.
    except (OSError, ValueError, KeyError, TypeError):
        # An incomplete/tampered bundle cannot be a cache hit. Validate below.
        inputs = runtime = None
    qa = validate_article(article, article_path, assets=assets)
    if qa["errors"]:
        return {**qa, "status": "QA_BLOCKED"}

    if reuse_render:
        preview = assets.read(output_dir / "preview.html").decode("utf-8")
        upload = assets.read(output_dir / "wechat-upload.html").decode("utf-8")
    else:
        sources = build_embedded_asset_sources(article, article_path, assets)
        preview = render_preview(article, article_path, sources)
        upload = render_article(article)
    figures = article.get("figures", [])
    evidence = ["# 论断—来源映射（内部）", ""]
    for item in article.get("evidence_map", []):
        evidence.extend([f"## {item['claim_id']}", item["claim"], item["source_locator"], ""])
    figure_list = ["# 原图使用与移动端复核清单（内部）", "",
                   "原图完整优先；裁剪只限必要的过密/过高原图，须保留坐标、色条和图例。", ""]
    try:
        inputs = inputs or input_hashes(article, article_path, assets)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return {"status": "QA_BLOCKED", "errors": [str(exc)], "warnings": qa["warnings"]}
    items = [("cover", article.get("cover"), True)] + [(f["asset_id"], f, False) for f in figures]
    for asset_id, asset, is_cover in items:
        if not isinstance(asset, dict):
            continue
        path = (article_path.parent / asset["path"]).resolve()
        provenance = asset.get("image_provenance", {})
        mobile = asset.get("mobile_display", {})
        figure_list.extend([
            f"## {'封面' if is_cover else '正文'}：{asset.get('figure_id', asset_id)}",
            f"- 使用文件：`{asset['path']}`",
            f"- 原图：`{provenance.get('original_path', '')}`",
            f"- 原图SHA-256：`{provenance.get('original_sha256', '')}`",
            f"- 原图定位：{provenance.get('source_locator', '')}",
            f"- 展示策略：{mobile.get('strategy', '')}；面板：{mobile.get('panel_label', '')}",
            f"- 处理说明：{mobile.get('review_note', '')}",
            f"- 许可：{asset.get('license_note', asset.get('source_note', ''))}", "",
        ])
        if mobile.get("crop_review"):
            decision = crop_decision(asset, article_path.parent, assets, cover=is_cover)
            figure_list.extend([f"- 裁剪必要性记录：`{mobile['crop_review']}`",
                                f"- 整图问题与替代方案：{decision['problem']}；{decision['alternative']}",
                                f"- 保留上下文：{decision['retained_context']}"])
            if not is_cover:
                figure_list.extend([f"- 展示面板：{decision['displayed_panels']}",
                                    f"- 省略面板：{decision['omitted_panels']}；{decision.get('omission_reason', '无省略')}", ""])
        if not is_cover:
            image = assets.image(path)
            figure_list.append(f"- 图片像素：{image.width}×{image.height}\n")
    image_review = readability_report(article, article_path.parent, assets)
    outputs = {
        "article.html": ('<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
                         '<meta http-equiv="refresh" content="0;url=preview.html">'
                         '</head><body><a href="preview.html">打开完整预览</a></body></html>'),
        "preview.html": preview,
        "wechat-upload.html": upload,
        "figure-review.html": figure_preview(article, article_path.parent, output_dir),
        "method-map.md": render_method_map(article),
        "evidence-map.md": "\n".join(evidence),
        "figure-list.md": "\n".join(figure_list),
        "scientific-review.json": json.dumps(qa["semantic_review"], ensure_ascii=False, indent=2) + "\n",
        "figure-readability-report.json": json.dumps(image_review, ensure_ascii=False, indent=2) + "\n",
    }
    if qa["semantic_review"]["fact_coverage"].get("items"):
        outputs["work/research-facts.md"] = render_facts(qa["semantic_review"]["fact_coverage"])
    # Deterministic files only: no current timestamps, network requests or random IDs.
    runtime = runtime or runtime_hashes(assets)
    result = {
        "status": "LOCAL_CHECKS_PASSED", "validation": qa,
        "figure_readability": image_review["status"],
        "manual_review_required": ["scientific_evidence", "reuse_license", "430px_figure_readability"],
        "inputs_sha256": inputs, "renderer_sha256": runtime,
        "outputs_sha256": {name: hashlib.sha256(value.encode("utf-8")).hexdigest() for name, value in outputs.items()},
    }
    outputs["bundle-manifest.json"] = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, value in outputs.items():
        target = output_dir / name
        if not target.is_file() or assets.read(target) != value.encode("utf-8"):
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(value, encoding="utf-8", newline="")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("article", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--record-qa", action="store_true", help="Record reviews already completed by a person or agent; does not perform them.")
    parser.add_argument("--figures-only", action="store_true", help="Before writing: inspect original candidates at 430/422px; no body, model call or QA approval.")
    parser.add_argument("--scientific-review")
    parser.add_argument("--license-review")
    parser.add_argument("--visual-review")
    parser.add_argument("--risk-review", type=Path, help="Source-backed resolutions for detected scientific risks (JSON array).")
    parser.add_argument("--verbose", action="store_true", help="Print full hashes/statistics; default output is a compact summary.")
    args = parser.parse_args()
    if args.figures_only:
        if args.record_qa:
            parser.error("选图预检不能登记成稿QA。")
        article = load_article(args.article)
        folder = (args.output_dir or args.article.parent).resolve()
        assets = AssetStore()
        checks = {f["asset_id"]: validate_figure(f, args.article.resolve().parent, assets=assets) for f in article.get("figures", [])}
        result = {"status": "FIGURE_SELECTION_REVIEW", "integrity": checks,
                  "readability": readability_report(article, args.article.resolve().parent, assets)}
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "figure-review.html").write_text(figure_preview(article, args.article.resolve().parent, folder), encoding="utf-8")
        (folder / "figure-preflight.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"status": result["status"], "candidates": len(checks), "readability": result["readability"]["status"], "gallery": str(folder / "figure-review.html")}, ensure_ascii=False))
        return int(any(c["errors"] for c in checks.values()))
    reviews = {"scientific_evidence": args.scientific_review,
               "reuse_license": args.license_review,
               "430px_figure_readability": args.visual_review}
    if args.record_qa and not all(value and value.strip() for value in reviews.values()):
        parser.error("--record-qa requires completed scientific, license and visual review notes")
    result = prepare(args.article, args.output_dir or args.article.parent)
    if args.record_qa and result["status"] == "LOCAL_CHECKS_PASSED":
        folder = (args.output_dir or args.article.parent).resolve()
        article = load_article(args.article)
        try:
            resolutions = json.loads(args.risk_review.read_text(encoding="utf-8")) if args.risk_review else []
        except (OSError, ValueError) as exc:
            print(json.dumps({"status": "QA_BLOCKED", "errors": [str(exc)]}, ensure_ascii=False))
            return 1
        if not isinstance(resolutions, list):
            parser.error("--risk-review must contain a JSON array")
        report = json.loads((folder / "scientific-review.json").read_text(encoding="utf-8"))
        unresolved = check_resolutions(report, resolutions, article, args.article.resolve(), AssetStore())
        if article.get("schema_version") == 8 and article.get("source", {}).get("evidence_level") == "FULLTEXT":
            unresolved += coverage_gate(report.get("fact_coverage", {})) + readability_gate(article, args.article.resolve().parent, AssetStore())
        if unresolved:
            print(json.dumps({"status": "QA_BLOCKED", "errors": unresolved}, ensure_ascii=False))
            return 1
        review = {"status": "QA_PASSED", "bundle_sha256": sha256(folder / "bundle-manifest.json"),
                  "reviews": reviews, "risk_resolutions": resolutions}
        (folder / "qa-review.json").write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="")
        result = {"status": "QA_REVIEW_RECORDED", "review": str(folder / "qa-review.json")}
    if not args.verbose and result["status"] == "LOCAL_CHECKS_PASSED":
        result = {"status": result["status"], "errors": result["validation"]["errors"],
                  "warnings": result["validation"]["warnings"],
                  "scientific_risks": len(result["validation"]["semantic_review"]["risks"]),
                  "fact_coverage": result["validation"]["semantic_review"]["fact_coverage"]["status"],
                  "figure_readability": result["figure_readability"],
                  "bundle_manifest": str((args.output_dir or args.article.parent) / "bundle-manifest.json")}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result["status"] == "QA_BLOCKED" else 0


if __name__ == "__main__":
    sys.exit(main())
