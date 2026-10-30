"""Validate source-image integrity; semantic and phone readability review remains manual."""

from __future__ import annotations

import re
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from article_artifacts import AssetStore


def readability_report(article, base_dir, assets):
    """Validate real selection-stage inspection records, not automatic OCR judgements."""
    figures = article.get("figures", [])
    if not figures:
        return {"status": "NOT_REQUIRED", "items": []}
    path = base_dir / "work/figure-readability.json"
    try:
        data = json.loads(assets.read(path))
        if data.get("viewport_css_px") != 430 or data.get("content_width_css_px") != 422:
            raise ValueError("须在430px视口、422px实际正文图宽度检查候选原图。")
        items = []
        for figure in figures:
            item = data.get("assets", {}).get(figure["asset_id"], {})
            reason = str(item.get("reason", "")).strip()
            capture = base_dir / item.get("screenshot", "")
            if (item.get("asset_sha256") != assets.digest(base_dir / figure["path"])
                    or item.get("screenshot_sha256") != assets.digest(capture)
                    or assets.image(capture).width != 430 or not isinstance(item.get("core_labels"), list)
                    or not item["core_labels"] or not all(isinstance(label, str) and label.strip() for label in item["core_labels"]) or len(reason) < 16):
                raise ValueError(f"{figure['asset_id']}缺少当前图像绑定的真实430px截图、核心标签和具体检查说明。")
            usable = item.get("core_readable") is True
            if item.get("auxiliary_readable") is False:
                usable = usable and item.get("auxiliary_essential") is False and len(str(item.get("auxiliary_reason", ""))) >= 16
            elif item.get("auxiliary_readable") is not True:
                usable = False
            items.append({"asset_id": figure["asset_id"], "status": "USABLE" if usable else "BLOCKED",
                          "reason": reason, "core_labels": item["core_labels"],
                          "auxiliary_readable": item.get("auxiliary_readable"),
                          "auxiliary_reason": item.get("auxiliary_reason", "")})
        return {"status": "REVIEWED" if all(i["status"] == "USABLE" for i in items) else "BLOCKED", "items": items,
                "limitations": "Python核对记录/哈希和失败状态，核心与辅助信息的重要性及可读性由现有视觉QA实际判定。"}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return {"status": "NOT_REVIEWED", "items": [], "reason": str(exc)}


def readability_gate(article, base_dir, assets):
    report = readability_report(article, base_dir, assets)
    if report["status"] in {"REVIEWED", "NOT_REQUIRED"}:
        return []
    return ["选图阶段手机可读性未通过：" + report.get("reason", "; ".join(i["asset_id"] + ":" + i["status"] for i in report["items"]))]


def figure_preview(article, base_dir, output_dir):
    """Shared candidate/final gallery at actual article width; never alters image files."""
    import html
    import os
    lines = ['<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
             '<body style="margin:0;padding:4px;box-sizing:border-box;width:430px;max-width:100%">']
    shown = set()
    for f in article.get("figures", []):
        original = (base_dir / f.get("image_provenance", {}).get("original_path", f["path"])).resolve()
        used = (base_dir / f["path"]).resolve()
        for label, path in [("整图检查（内部）/完整原图", original), ("候选使用图", used)]:
            if path in shown:
                continue
            shown.add(path)
            try:
                url = Path(os.path.relpath(path, output_dir)).as_posix()
            except ValueError:
                url = path.as_uri()
            lines.extend([f"<p>{html.escape(f['asset_id'])} / {label}</p>",
                          f'<img data-asset-id="{html.escape(f["asset_id"], quote=True)}" src="{html.escape(url, quote=True)}" style="display:block;width:100%;height:auto">'])
    return "\n".join(lines + ["</body>"])


def crop_decision(asset, base_dir, assets, *, cover=False):
    """Validate the evidence for cropping separately from crop pixel integrity."""
    mobile = asset.get("mobile_display", {})
    path = mobile.get("crop_review", "")
    if not path or re.match(r"https?://", path):
        raise ValueError("裁剪必要性未复核：须引用本地crop_review，先记录430px整图问题及裁后检查。")
    records = json.loads(assets.read(base_dir / path))
    key = "cover" if cover else mobile.get("source_figure_id")
    record = records[key]
    if record.get("original_sha256") != asset["image_provenance"]["original_sha256"]:
        raise ValueError("裁剪必要性记录未绑定当前原图。")
    for stage in ("before", "after"):
        capture = record[stage]
        screenshot = base_dir / capture["path"]
        if (assets.digest(screenshot) != capture["sha256"]
                or assets.image(screenshot).width != 430):
            raise ValueError("裁前/裁后实查截图须为430px且哈希一致。")
    allowed = {"unreadable", "too_tall"} | ({"cover_ratio"} if cover else set())
    if record["before"].get("verdict") not in allowed or record["after"].get("verdict") != "readable":
        raise ValueError("整图可读不能裁剪；须记录具体失败及裁后可读结论。")
    original_image = assets.image(base_dir / asset["image_provenance"]["original_path"])
    if record["before"]["verdict"] == "too_tall" and original_image.height / original_image.width < 1.8:
        raise ValueError("裁前截图声称过高，但原图高/宽未达到1.8。")
    for field in ("problem", "alternative", "retained_context"):
        if len(str(record.get(field, "")).strip()) < 12:
            raise ValueError(f"裁剪必要性记录{field}须具体说明；仅写过密/组合图不充分。")
    if not cover:
        original = set(record["original_panels"])
        retained = {p for panels in record["displayed_panels"].values() for p in panels}
        omitted = set(record["omitted_panels"])
        if not original or retained & omitted or retained | omitted != original:
            raise ValueError("须逐项记录原面板、展示面板及省略面板，不能漏记。")
        if asset["asset_id"] not in record["displayed_panels"]:
            raise ValueError("当前裁图未在展示面板清单中登记。")
        if omitted and mobile.get("strategy") == "split_panel":
            raise ValueError("省略面板属于部分选取，不能登记为完整拆分split_panel。")
        if omitted and len(str(record.get("omission_reason", "")).strip()) < 12:
            raise ValueError("部分选取须说明省略面板为何不损失必要比较，优先保留完整面板组。")
    return record


@lru_cache(maxsize=1)
def internal_fixture_hashes() -> frozenset[str]:
    root = Path(__file__).resolve().parents[1] / "assets"
    assets = AssetStore()
    return frozenset(assets.digest(root / name) for name in (
        "phase1-test-cover.png", "phase2-feature-selection-cover.png",
    ))


def validate_figure(asset: dict[str, Any], base_dir: Path, *, cover: bool = False, assets: AssetStore | None = None) -> dict:
    assets = assets or AssetStore()
    errors: list[str] = []
    warnings: list[str] = []
    provenance = asset.get("image_provenance")
    mobile = asset.get("mobile_display") or {}
    if not isinstance(mobile, dict):
        return {"errors": ["mobile_display 必须是对象。"], "warnings": []}
    if not isinstance(provenance, dict):
        return {"errors": ["缺少 image_provenance 原图路径、SHA-256 和来源定位。"], "warnings": []}
    if not str(provenance.get("source_locator", "")).strip():
        errors.append("image_provenance.source_locator 不能为空。")
    for field in ("source_figure_id", "panel_label", "review_note"):
        if not str(mobile.get(field, "")).strip():
            errors.append(f"mobile_display.{field} 不能为空。")
    strategy = mobile.get("strategy")
    if strategy not in {"native", "cropped", "split_panel", "selected_panels"}:
        errors.append("mobile_display.strategy 无效。")
    if not str(asset.get("figure_id", "")).strip():
        errors.append("缺少原文 figure_id。")
    expected_number = re.search(r"(?:Fig(?:ure)?\.?\s*|图\s*)(?:S)?(\d+)", str(asset.get("figure_id", "")), re.I)
    caption_number = re.match(r"(?:原文\s*)?(?:补充\s*)?(?:Fig(?:ure)?\.?\s*|图\s*)(?:S)?(\d+)", str(asset.get("caption", "")), re.I)
    if expected_number and caption_number and expected_number[1] != caption_number[1]:
        errors.append("可见图注编号与原文 figure_id 不一致；不得按推文出现顺序重编号。")
    original_path = str(provenance.get("original_path", "")).strip()
    asset_path = str(asset.get("path", "")).strip()
    if not original_path or not asset_path or re.match(r"https?://", original_path + asset_path):
        errors.append("须提供本地原图和实际使用图片，不能只登记远程地址。")
        return {"errors": errors, "warnings": warnings}
    original = (base_dir / original_path).resolve()
    displayed = (base_dir / asset_path).resolve()
    try:
        digest = assets.digest(original)
        if digest in internal_fixture_hashes():
            errors.append("开发测试图片不能作为正式稿原图或封面，即使复制或改名也不允许。")
        if digest != str(provenance.get("original_sha256", "")).lower():
            errors.append("原图 SHA-256 与记录不一致。")
        source, used = assets.image(original), assets.image(displayed)
        source_rgba, used_rgba = source, used
        width, height = used.size
        if not cover and height / width >= 1.8:
            errors.append("正文图片高/宽达到1.8；需换用其他可读原图或合法的完整面板。")
        if width < 860:
            warnings.append(f"图片宽度仅{width}px，需确认已查找高清源，并实查430px手机显示。")
        if strategy == "native":
            if source is not used and (source.size != used.size or source_rgba.tobytes() != used_rgba.tobytes()):
                errors.append("声明 native，但实际图片并非完整原图的相同像素。")
        elif strategy in {"cropped", "split_panel", "selected_panels"}:
            try:
                crop_decision(asset, base_dir, assets, cover=cover)
            except (OSError, ValueError, KeyError, TypeError) as exc:
                errors.append(f"裁剪必要性：{exc}")
            reason = mobile.get("crop_reason")
            allowed = {"dense_composite", "too_tall"} | ({"cover_ratio"} if cover else set())
            if reason not in allowed:
                errors.append("裁剪理由仅限过密组合图、过高原图；封面另允许必要比例适配。")
            if reason == "too_tall" and source.height / source.width < 1.8:
                errors.append("原图高/宽未达到1.8，不能以too_tall替代可读性证据。")
            if mobile.get("annotations_preserved") is not True:
                errors.append("裁剪未确认保留完整坐标、共享色条、图例和必要标签。")
            box = mobile.get("crop_box")
            valid_box = (isinstance(box, list) and len(box) == 4
                         and all(type(v) is int for v in box)
                         and 0 <= box[0] < box[2] <= source.width
                         and 0 <= box[1] < box[3] <= source.height)
            if not valid_box:
                errors.append("裁剪须记录原图像素范围内的 crop_box=[left,top,right,bottom]。")
            else:
                expected = source_rgba.crop(tuple(box))
                if expected.size != used.size or expected.tobytes() != used_rgba.tobytes():
                    errors.append("实际裁图与登记边界不符，或发生了重绘、缩放、改色或有损重编码。")
            license_note = str(asset.get("license_note", asset.get("source_note", "")))
            if re.search(r"BY[\s-]+(?:NC[\s-]+)?ND|by-(?:nc-)?nd", license_note, re.I):
                errors.append("当前许可含ND，不自动放行裁图；请使用完整原图或取得另外的改编授权。")
        return {"errors": errors, "warnings": warnings, "width": width, "height": height,
                "original_sha256": digest}
    except (OSError, ValueError) as exc:
        errors.append(f"图片无法读取或解码：{exc}")
    return {"errors": errors, "warnings": warnings}
