#!/usr/bin/env python3
"""Render a validated article JSON file to conservative WeChat-compatible HTML."""

from __future__ import annotations

import argparse
import base64
import html
import json
import mimetypes
import re
import sys
from pathlib import Path
from typing import Any

from validate_article import load_article, validate_article


FORBIDDEN_HTML_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"<script\b",
        r"<iframe\b",
        r"<form\b",
        r"<link\b",
        r"\son[a-z]+\s*=",
        r"javascript\s*:",
        r"position\s*:\s*fixed",
    )
]


def inline_text(value: str) -> str:
    escaped = html.escape(value, quote=True)
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)


def render_block(
    block: dict[str, Any],
    figures: dict[str, dict[str, Any]],
    asset_src_overrides: dict[str, str] | None = None,
) -> str:
    block_type = block["type"]
    if block_type == "paragraph":
        return (
            '<p style="margin:0 0 14px;line-height:1.85;font-size:16px;'
            'color:#252525;text-align:justify;letter-spacing:0.02em;">'
            f'{inline_text(block["text"])}</p>'
        )
    if block_type == "subheading":
        return (
            '<h3 style="margin:22px 0 10px;font-size:18px;line-height:1.5;'
            'color:#24567a;font-weight:700;">'
            f'{inline_text(block["text"])}</h3>'
        )
    if block_type == "callout":
        return (
            '<section style="margin:16px 0;padding:14px 16px;border-left:4px solid #3f7fa6;'
            'background:#f3f8fb;border-radius:4px;">'
            '<p style="margin:0;line-height:1.75;font-size:15px;color:#24465d;">'
            f'{inline_text(block["text"])}</p></section>'
        )
    if block_type == "list":
        tag = "ol" if block.get("ordered") else "ul"
        items = "".join(
            '<li style="margin:0 0 8px;line-height:1.75;font-size:16px;color:#252525;">'
            f"{inline_text(item)}</li>" for item in block["items"]
        )
        return f'<{tag} style="margin:8px 0 16px;padding-left:1.6em;">{items}</{tag}>'
    if block_type == "image":
        figure = figures[block["asset_id"]]
        path = figure["path"]
        override = (asset_src_overrides or {}).get(figure["asset_id"])
        src = override or (
            path
            if re.match(r"^https?://", path, re.IGNORECASE)
            else f'wechat-asset://{figure["asset_id"]}'
        )
        return (
            '<section style="margin:20px 0;text-align:center;">'
            f'<img src="{html.escape(src, quote=True)}" alt="{html.escape(figure["alt"], quote=True)}" '
            f'data-asset-id="{html.escape(figure["asset_id"], quote=True)}" '
            'style="display:block;width:100%;max-width:677px;height:auto;margin:0 auto;" />'
            '<p style="margin:8px 0 0;line-height:1.55;font-size:12px;color:#777;text-align:center;">'
            f'{inline_text(figure["caption"])}</p>'
            '<p style="margin:3px 0 0;line-height:1.45;font-size:11px;color:#999;text-align:center;">'
            f'来源：{inline_text(figure["source"])}；{inline_text(figure["license_note"])}</p>'
            '</section>'
        )
    raise ValueError(f"Unsupported block type: {block_type}")


def render_article(
    article: dict[str, Any], asset_src_overrides: dict[str, str] | None = None
) -> str:
    figures = {figure["asset_id"]: figure for figure in article.get("figures", [])}
    parts = [
        '<section data-plugin="mri-wechat-publisher" '
        'style="box-sizing:border-box;max-width:677px;margin:0 auto;padding:8px 4px;'
        'font-family:-apple-system,BlinkMacSystemFont,Segoe UI,PingFang SC,Hiragino Sans GB,'
        'Microsoft YaHei,sans-serif;">',
        '<h1 style="margin:8px 0 14px;font-size:24px;line-height:1.45;color:#173f5f;'
        'font-weight:700;text-align:left;overflow-wrap:anywhere;word-break:break-word;">'
        f'{inline_text(article["title"])}</h1>',
        '<p style="margin:0 0 16px;font-size:13px;line-height:1.6;color:#777;">'
        f'作者：{inline_text(article["author"])}</p>',
        '<section style="margin:0 0 24px;padding:14px 16px;background:#f7f8fa;border-radius:6px;">'
        '<p style="margin:0;font-size:14px;line-height:1.75;color:#555;">'
        f'{inline_text(article["digest"])}</p></section>',
    ]

    for section in article["sections"]:
        parts.append(
            '<h2 style="margin:30px 0 14px;padding-bottom:7px;border-bottom:2px solid #dceaf2;'
            'font-size:21px;line-height:1.5;color:#1f4d78;font-weight:700;">'
            f'{inline_text(section["heading"])}</h2>'
        )
        parts.extend(
            render_block(block, figures, asset_src_overrides) for block in section["blocks"]
        )

    parts.append(
        '<h2 style="margin:30px 0 14px;padding-bottom:7px;border-bottom:2px solid #dceaf2;'
        'font-size:21px;line-height:1.5;color:#1f4d78;font-weight:700;">参考文献</h2>'
    )
    for index, reference in enumerate(article["references"], start=1):
        citation = inline_text(reference["citation"])
        parts.append(
            '<p style="margin:0 0 9px;padding-left:1.6em;text-indent:-1.6em;'
            f'font-size:13px;line-height:1.65;color:#555;">[{index}] {citation}</p>'
        )
    parts.append('</section>')
    rendered = "\n".join(parts)

    hits = [pattern.pattern for pattern in FORBIDDEN_HTML_PATTERNS if pattern.search(rendered)]
    if hits:
        raise ValueError(f"Rendered HTML contains forbidden patterns: {hits}")
    return rendered


def build_embedded_asset_sources(
    article: dict[str, Any], article_path: Path
) -> dict[str, str]:
    """Build data-URI sources for local review without changing article JSON."""
    sources: dict[str, str] = {}
    for figure in article.get("figures", []):
        path = str(figure.get("path", ""))
        if re.match(r"^https?://", path, re.IGNORECASE):
            continue
        resolved = (article_path.parent / path).resolve()
        mime_type = mimetypes.guess_type(resolved.name)[0] or "application/octet-stream"
        encoded = base64.b64encode(resolved.read_bytes()).decode("ascii")
        sources[figure["asset_id"]] = f"data:{mime_type};base64,{encoded}"
    return sources


def main() -> int:
    parser = argparse.ArgumentParser(description="Render WeChat HTML from an article JSON file.")
    parser.add_argument("article", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--embed-local-assets",
        action="store_true",
        help="Embed local figures as data URIs for a self-contained review preview.",
    )
    args = parser.parse_args()

    article_path = args.article.resolve()
    article = load_article(article_path)
    qa = validate_article(article, article_path)
    if qa["status"] != "QA_PASSED":
        print(json.dumps(qa, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1

    asset_sources = (
        build_embedded_asset_sources(article, article_path)
        if args.embed_local_assets
        else None
    )
    rendered = render_article(article, asset_sources)
    if args.embed_local_assets:
        rendered = (
            '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>' + html.escape(article["title"]) + '</title></head>'
            '<body style="margin:0;background:#fff;">' + rendered + '</body></html>'
        )
    output_path = args.output.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered, encoding="utf-8")
    result = {
        "status": "RENDERED",
        "output": str(output_path),
        "html_characters": len(rendered),
        "contains_local_asset_placeholders": "wechat-asset://" in rendered,
        "embedded_local_asset_count": len(asset_sources or {}),
        **qa["statistics"],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
