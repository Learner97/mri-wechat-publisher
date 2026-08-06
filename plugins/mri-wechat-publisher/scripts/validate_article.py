#!/usr/bin/env python3
"""Validate the phase-one MRI WeChat article contract without network access."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


FIXED_SECTIONS = [
    ("abstract", "摘要解读"),
    ("design", "研究设计与数据"),
    ("method", "核心方法解析"),
    ("results", "关键结果与证据链"),
    ("implications", "方法启示与总结"),
]

TEXT_BLOCK_TYPES = {"paragraph", "subheading", "callout"}
VALID_BLOCK_TYPES = TEXT_BLOCK_TYPES | {"list", "image"}
FORBIDDEN_ACTION_KEYS = {
    "publish",
    "freepublish",
    "mass_send",
    "masssend",
    "send_all",
    "delete_draft",
    "delete_material",
}
SECRET_KEYS = {
    "wechat_app_secret",
    "appsecret",
    "app_secret",
    "access_token",
    "cookie",
    "cookies",
    "session_cookie",
}


def load_article(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("文章根节点必须是 JSON 对象。")
    return data


def _walk_keys(value: Any, errors: list[str], location: str = "$") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).strip().lower()
            child_location = f"{location}.{key}"
            if normalized in FORBIDDEN_ACTION_KEYS:
                errors.append(f"禁止的自动动作字段：{child_location}")
            if normalized in SECRET_KEYS and str(child).strip():
                errors.append(f"文章数据中不得包含凭据：{child_location}")
            _walk_keys(child, errors, child_location)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _walk_keys(child, errors, f"{location}[{index}]")


def _plain_text_length(article: dict[str, Any]) -> int:
    chunks: list[str] = []
    for section in article.get("sections", []):
        if not isinstance(section, dict):
            continue
        for block in section.get("blocks", []):
            if not isinstance(block, dict):
                continue
            if isinstance(block.get("text"), str):
                chunks.append(block["text"])
            for item in block.get("items", []):
                if isinstance(item, str):
                    chunks.append(item)
    return len(re.sub(r"\s+", "", "".join(chunks)))


def validate_article(article: dict[str, Any], article_path: Path | None = None) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    if article.get("schema_version") != 1:
        errors.append("schema_version 必须为 1。")

    if article.get("publication_mode") != "draft_only":
        errors.append("publication_mode 必须严格等于 draft_only。")

    for field, maximum in (("article_id", 100), ("title", 64), ("author", 64), ("digest", 120)):
        value = article.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{field} 必须是非空字符串。")
        elif len(value.strip()) > maximum:
            errors.append(f"{field} 超过 {maximum} 个字符。")

    title = article.get("title")
    if isinstance(title, str) and title.strip():
        title_text = title.strip()
        parts = title_text.split(" | ")
        if (
            len(parts) != 2
            or "|" in title_text.replace(" | ", "")
            or not all(part and part == part.strip() for part in parts)
        ):
            errors.append("title 必须使用“期刊全名或公认缩写 | 简短内容题眼”结构。")
        elif len(parts[1].strip()) > 20:
            errors.append("title 的内容主标题（` | ` 之后）超过 20 个字符。")

    source = article.get("source")
    if not isinstance(source, dict):
        errors.append("source 必须是对象。")
    else:
        if not str(source.get("title", "")).strip():
            errors.append("source.title 不能为空。")
        if not str(source.get("source_id", "")).strip():
            errors.append("source.source_id 不能为空；可使用 DOI、PMID 或内部测试标识。")

    sections = article.get("sections")
    if not isinstance(sections, list):
        errors.append("sections 必须是数组。")
        sections = []
    if len(sections) != len(FIXED_SECTIONS):
        errors.append("sections 必须且只能包含五个固定章节。")

    referenced_figures: set[str] = set()
    for index, expected in enumerate(FIXED_SECTIONS):
        if index >= len(sections) or not isinstance(sections[index], dict):
            continue
        section = sections[index]
        expected_id, expected_heading = expected
        if section.get("id") != expected_id or section.get("heading") != expected_heading:
            errors.append(
                f"第 {index + 1} 节必须为 id={expected_id!r}、heading={expected_heading!r}。"
            )
        blocks = section.get("blocks")
        if not isinstance(blocks, list) or not blocks:
            errors.append(f"章节“{expected_heading}”至少需要一个内容块。")
            continue
        for block_index, block in enumerate(blocks):
            location = f"sections[{index}].blocks[{block_index}]"
            if not isinstance(block, dict):
                errors.append(f"{location} 必须是对象。")
                continue
            block_type = block.get("type")
            if block_type not in VALID_BLOCK_TYPES:
                errors.append(f"{location}.type 不受支持：{block_type!r}")
            elif block_type in TEXT_BLOCK_TYPES:
                if not isinstance(block.get("text"), str) or not block["text"].strip():
                    errors.append(f"{location}.text 不能为空。")
            elif block_type == "list":
                items = block.get("items")
                if not isinstance(items, list) or not items or not all(
                    isinstance(item, str) and item.strip() for item in items
                ):
                    errors.append(f"{location}.items 必须是非空字符串数组。")
            elif block_type == "image":
                asset_id = block.get("asset_id")
                if not isinstance(asset_id, str) or not asset_id.strip():
                    errors.append(f"{location}.asset_id 不能为空。")
                else:
                    referenced_figures.add(asset_id)

    figures = article.get("figures")
    if not isinstance(figures, list):
        errors.append("figures 必须是数组。")
        figures = []
    figure_ids: set[str] = set()
    base_dir = article_path.parent if article_path else Path.cwd()
    for index, figure in enumerate(figures):
        location = f"figures[{index}]"
        if not isinstance(figure, dict):
            errors.append(f"{location} 必须是对象。")
            continue
        asset_id = str(figure.get("asset_id", "")).strip()
        if not asset_id:
            errors.append(f"{location}.asset_id 不能为空。")
        elif asset_id in figure_ids:
            errors.append(f"重复的 figure asset_id：{asset_id}")
        else:
            figure_ids.add(asset_id)
        for field in ("path", "alt", "caption", "source", "license_note"):
            if not str(figure.get(field, "")).strip():
                errors.append(f"{location}.{field} 不能为空。")
        figure_path = str(figure.get("path", "")).strip()
        if figure_path and not re.match(r"^https?://", figure_path, re.IGNORECASE):
            resolved = (base_dir / figure_path).resolve()
            if not resolved.is_file():
                errors.append(f"图片文件不存在：{resolved}")

    for asset_id in sorted(referenced_figures - figure_ids):
        errors.append(f"正文引用了未定义的图片：{asset_id}")
    for asset_id in sorted(figure_ids - referenced_figures):
        warnings.append(f"图片已定义但未在正文使用：{asset_id}")

    references = article.get("references")
    if not isinstance(references, list) or not references:
        errors.append("references 至少需要一条可追溯记录。")
        references = []
    for index, reference in enumerate(references):
        if not isinstance(reference, dict):
            errors.append(f"references[{index}] 必须是对象。")
            continue
        if not str(reference.get("id", "")).strip() or not str(reference.get("citation", "")).strip():
            errors.append(f"references[{index}] 缺少 id 或 citation。")
        if reference.get("verified") is not True:
            errors.append(f"references[{index}] 尚未标记为 verified。")

    evidence_map = article.get("evidence_map")
    if not isinstance(evidence_map, list) or not evidence_map:
        errors.append("evidence_map 至少需要一条记录。")
        evidence_map = []
    for index, item in enumerate(evidence_map):
        if not isinstance(item, dict):
            errors.append(f"evidence_map[{index}] 必须是对象。")
            continue
        for field in ("claim_id", "claim", "source_locator"):
            if not str(item.get(field, "")).strip():
                errors.append(f"evidence_map[{index}].{field} 不能为空。")
        if item.get("status") != "verified":
            errors.append(f"evidence_map[{index}] 未通过证据核查。")

    _walk_keys(article, errors)

    body_characters = _plain_text_length(article)
    if body_characters < 100:
        warnings.append("正文少于 100 个非空白字符；仅适合流程测试。")
    if body_characters > 11000:
        warnings.append("正文超过建议的 11,000 个中文字符。")

    return {
        "status": "QA_PASSED" if not errors else "QA_BLOCKED",
        "errors": errors,
        "warnings": warnings,
        "statistics": {
            "title_characters": len(str(article.get("title", "")).strip()),
            "title_hook_characters": (
                len(str(article.get("title", "")).strip().split(" | ", maxsplit=1)[1].strip())
                if " | " in str(article.get("title", "")).strip()
                else 0
            ),
            "digest_characters": len(str(article.get("digest", ""))),
            "body_characters_no_whitespace": body_characters,
            "section_count": len(sections),
            "figure_count": len(figures),
            "reference_count": len(references),
            "evidence_record_count": len(evidence_map),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate an MRI WeChat article JSON file.")
    parser.add_argument("article", type=Path)
    parser.add_argument("--compact", action="store_true", help="Print compact JSON.")
    args = parser.parse_args()

    try:
        article_path = args.article.resolve()
        result = validate_article(load_article(article_path), article_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        result = {
            "status": "QA_BLOCKED",
            "errors": [str(exc)],
            "warnings": [],
            "statistics": {},
        }

    print(json.dumps(result, ensure_ascii=False, indent=None if args.compact else 2))
    return 0 if result["status"] == "QA_PASSED" else 1


if __name__ == "__main__":
    sys.exit(main())
