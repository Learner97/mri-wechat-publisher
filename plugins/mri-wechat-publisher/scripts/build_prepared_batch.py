#!/usr/bin/env python3
"""Build locally reviewable, evidence-mapped WeChat articles for a prepared batch."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from render_method_map import render_method_map


SECTION_HEADINGS_BY_VERSION = {
    1: [
        ("abstract", "摘要解读"),
        ("design", "研究设计与数据"),
        ("method", "核心方法解析"),
        ("results", "关键结果与证据链"),
        ("implications", "方法启示与总结"),
    ],
    2: [
        ("abstract", "摘要"),
        ("introduction", "引言"),
        ("methods", "方法"),
        ("results", "结果"),
        ("discussion", "讨论与总结"),
    ],
    3: [
        ("abstract", "摘要"),
        ("introduction", "引言"),
        ("methods", "方法"),
        ("results", "结果"),
        ("discussion", "讨论"),
        ("summary", "总结"),
    ],
    4: [
        ("abstract", "摘要"),
        ("introduction", "引言"),
        ("methods", "方法"),
        ("results", "结果"),
        ("discussion", "讨论"),
        ("summary", "总结"),
    ],
    5: [
        ("abstract", "摘要"),
        ("introduction", "引言"),
        ("methods", "方法"),
        ("results", "结果"),
        ("discussion", "讨论"),
        ("summary", "总结"),
    ],
    6: [
        ("abstract", "摘要"),
        ("introduction", "引言"),
        ("methods", "方法"),
        ("results", "结果"),
        ("result_interpretation", "结果解读"),
        ("closing", "结语"),
    ],
    7: [
        ("abstract", "摘要"),
        ("introduction", "引言"),
        ("methods", "方法"),
        ("results", "结果"),
        ("result_interpretation", "结果解读"),
        ("closing", "结语"),
    ],
    8: [
        ("overview", "研究速览"),
        ("introduction", "引言"),
        ("methods", "方法"),
        ("results", "结果"),
        ("result_interpretation", "结果解读"),
        ("closing", "结语"),
    ],
}


def parse_content(path: Path, schema_version: int) -> list[dict]:
    section_headings = SECTION_HEADINGS_BY_VERSION.get(schema_version)
    if section_headings is None:
        raise ValueError(f"Unsupported article schema_version: {schema_version!r}")
    text = path.read_text(encoding="utf-8")
    chunks = re.split(r"^##\s+", text, flags=re.MULTILINE)[1:]
    by_heading: dict[str, list[dict]] = {}
    for chunk in chunks:
        heading, _, body = chunk.partition("\n")
        blocks: list[dict] = []
        for raw in re.split(r"\n\s*\n", body.strip()):
            value = raw.strip()
            if not value:
                continue
            if value.startswith("### "):
                blocks.append({"type": "subheading", "text": value[4:].strip()})
            elif value.startswith("> "):
                blocks.append({"type": "callout", "text": value[2:].strip()})
            elif value.startswith("!FIG:"):
                blocks.append({"type": "image", "asset_id": value[5:].strip()})
            elif value.startswith("- "):
                blocks.append({
                    "type": "list",
                    "items": [line[2:].strip() for line in value.splitlines() if line.startswith("- ")],
                })
            else:
                blocks.append({"type": "paragraph", "text": " ".join(value.splitlines())})
        by_heading[heading.strip()] = blocks
    if schema_version == 6 and "方法启示" in by_heading:
        section_headings = [
            *section_headings[:-1],
            ("method_insights", "方法启示"),
            section_headings[-1],
        ]
    if schema_version in {7, 8} and "方法启示" in by_heading:
        raise ValueError(
            f"schema_version {schema_version} requires method insights to be integrated into 结语"
        )
    missing = [heading for _, heading in section_headings if heading not in by_heading]
    if missing:
        raise ValueError(f"Missing required article-content.md headings: {', '.join(missing)}")
    return [
        {"id": section_id, "heading": heading, "blocks": by_heading[heading]}
        for section_id, heading in section_headings
    ]


def markdown_evidence(items: list[dict]) -> str:
    lines = [
        "# 证据映射",
        "",
        "| ID | 可核查主张 | 类型 | 原文定位 | 状态 |",
        "|---|---|---|---|---|",
    ]
    for item in items:
        lines.append(
            f"| {item['claim_id']} | {item['claim']} | {item.get('claim_type', 'legacy')} | "
            f"{item['source_locator']} | {item['status']} |"
        )
    return "\n".join(lines) + "\n"


def markdown_figures(items: list[dict]) -> str:
    lines = ["# 图片清单", ""]
    for item in items:
        lines.extend([
            f"## {item['asset_id']}",
            "",
            f"- 文件：`{item['path']}`",
            f"- 图注：{item['caption']}",
            f"- 来源：{item['source']}",
            f"- 许可：{item['license_note']}",
            f"- 移动端策略：{item.get('mobile_display', {}).get('strategy', 'legacy')}",
            "",
        ])
    return "\n".join(lines)


def build_one(directory: Path) -> Path:
    manifest = json.loads((directory / "article-manifest.json").read_text(encoding="utf-8"))
    schema_version = manifest.get("schema_version")
    if schema_version not in SECTION_HEADINGS_BY_VERSION:
        raise ValueError(
            "article-manifest.json must declare schema_version 1, 2, 3, 4, 5, 6, 7, or 8"
        )
    if schema_version in {4, 5, 6, 7, 8} and not manifest.get("method_map"):
        raise ValueError(f"schema_version {schema_version} requires a non-empty method_map")
    manifest["sections"] = parse_content(directory / "article-content.md", schema_version)
    manifest.setdefault("settings", {"need_open_comment": 0, "only_fans_can_comment": 0})
    article_path = directory / "article.json"
    article_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (directory / "evidence-map.md").write_text(
        markdown_evidence(manifest["evidence_map"]), encoding="utf-8"
    )
    (directory / "figure-list.md").write_text(
        markdown_figures(manifest["figures"]), encoding="utf-8"
    )
    if manifest.get("method_map"):
        (directory / "method-map.md").write_text(
            render_method_map(manifest), encoding="utf-8"
        )
    return article_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("directories", nargs="+", type=Path)
    args = parser.parse_args()
    for directory in args.directories:
        print(build_one(directory.resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
