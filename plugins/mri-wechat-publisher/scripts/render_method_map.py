#!/usr/bin/env python3
"""Render an article's internal method map as reviewable Markdown."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def clean(value: Any) -> str:
    return str(value or "").replace("|", "\\|").strip()


def append_values(lines: list[str], label: str, values: list[str], *, ordered: bool = False) -> None:
    lines.append(f"- {label}：")
    for index, value in enumerate(values, start=1):
        marker = f"{index}." if ordered else "-"
        lines.append(f"  {marker} {clean(value)}")


def render_method_map(article: dict[str, Any]) -> str:
    items = article.get("method_map")
    if not isinstance(items, list) or not items:
        raise ValueError("article.method_map must contain at least one method")

    lines = [
        "# Method Map",
        "",
        "该文件用于内部方法证据核查，不进入公众号正文。方法按重要性记录数据、处理、统计、必要输出和研究材料定位。",
        "",
    ]
    for item in items:
        data = item["data"]
        lines.extend(
            [
                f"## {clean(item['method_id'])}｜{clean(item['name'])}",
                "",
                f"- 正文小标题：{clean(item['section_heading'])}",
                f"- 分析目的：{clean(item['purpose'])}",
                f"- 方法重要性：{clean(item.get('importance', 'legacy'))}",
                f"- 数据概述：{clean(data['description'])}",
            ]
        )
        for field, label in (
            ("sample", "样本"),
            ("source", "来源"),
            ("modality", "模态"),
            ("groups", "数据划分"),
            ("analysis_unit", "分析单元"),
            ("dimensions", "维度"),
        ):
            value = clean(data.get(field))
            if value:
                lines.append(f"- {label}：{value}")
        append_values(lines, "处理步骤", item["processing_steps"], ordered=True)
        append_values(lines, "统计检验", item["statistics"])
        outputs = item.get("outputs", [])
        if outputs:
            append_values(lines, "有助于后续理解的输出", outputs)
        append_values(lines, "原文定位", item["source_locators"])
        unreported = item.get("unreported_details", [])
        if unreported:
            append_values(lines, "原文未报告", unreported)
        critical_missing = item.get("critical_missing_details", [])
        if critical_missing:
            append_values(lines, "影响主要结论解释的缺失信息", critical_missing)
        lines.extend([f"- 状态：{clean(item['status'])}", ""])
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("article", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    article_path = args.article.resolve()
    output_path = args.output.resolve()
    article = json.loads(article_path.read_text(encoding="utf-8"))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_method_map(article), encoding="utf-8")
    print(json.dumps({
        "status": "METHOD_MAP_RENDERED",
        "methods": len(article.get("method_map", [])),
        "output": str(output_path),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
