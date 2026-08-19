#!/usr/bin/env python3
"""Validate the phase-one MRI WeChat article contract without network access."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


LEGACY_SECTIONS = [
    ("abstract", "摘要解读"),
    ("design", "研究设计与数据"),
    ("method", "核心方法解析"),
    ("results", "关键结果与证据链"),
    ("implications", "方法启示与总结"),
]

VERSION_2_SECTIONS = [
    ("abstract", "摘要"),
    ("introduction", "引言"),
    ("methods", "方法"),
    ("results", "结果"),
    ("discussion", "讨论与总结"),
]

CURRENT_SECTIONS = [
    ("abstract", "摘要"),
    ("introduction", "引言"),
    ("methods", "方法"),
    ("results", "结果"),
    ("discussion", "讨论"),
    ("summary", "总结"),
]

VERSION_6_SECTIONS = [
    ("abstract", "摘要"),
    ("introduction", "引言"),
    ("methods", "方法"),
    ("results", "结果"),
    ("result_interpretation", "结果解读"),
    ("closing", "结语"),
]

VERSION_6_SECTIONS_WITH_METHOD_INSIGHTS = [
    *VERSION_6_SECTIONS[:-1],
    ("method_insights", "方法启示"),
    VERSION_6_SECTIONS[-1],
]

VERSION_7_SECTIONS = VERSION_6_SECTIONS

VERSION_8_SECTIONS = [
    ("overview", "研究速览"),
    ("introduction", "引言"),
    ("methods", "方法"),
    ("results", "结果"),
    ("result_interpretation", "结果解读"),
    ("closing", "结语"),
]

CURRENT_SCHEMA_VERSION = 8

CLAIM_TYPES = {
    "direct_result",
    "author_interpretation",
    "editorial_explanation",
    "editorial_extension",
}
HARD_BANNED_PHRASES = {
    "30秒读懂",
    "三个关键证据",
    "三条关键证据",
    "关键证据一",
    "证据链",
    "本文只需记住",
    "一句话收束",
    "全文可以收束为",
    "真正值得带走的是",
    "读者",
    "读完后",
}
INTERNAL_PROCESS_PHRASES = {
    "补充方法显示",
    "补充方法记录",
    "补充材料显示",
    "补充材料记录",
    "补充材料未",
    "附录显示",
    "附录记录",
    "proof记录",
    "来源材料未说明",
    "来源材料未提供",
    "研究材料未说明",
    "研究材料未提供",
    "检索显示",
    "核查显示",
    "经核对",
    "核对后",
}
INTERNAL_PROCESS_PATTERNS = (
    re.compile(
        r"(?:正文|补充材料|补充方法|附录|研究材料|来源材料|(?:期刊)?proof)"
        r"(?:中|还|另|则|所)?(?:显示|记录|指出|提到|写道|说明)"
    ),
    re.compile(r"(?:检索|核查|核对)(?:过程|结果|显示|发现|后)"),
)
UNREPORTED_PUBLIC_PHRASES = {
    "未报告",
    "未进一步报告",
    "未进一步说明",
    "未提供具体参数",
}
UNPERFORMED_ANALYSIS_PATTERNS = (
    re.compile(r"(?:未|没有|并未)(?:直接)?(?:测量|纳入|检验|检查|评估|分析|比较|验证|收集|估计)"),
    re.compile(r"(?:没有被|未被)(?:测量|纳入|检验|检查|评估|分析|比较|验证)"),
)
NEGATIVE_SCOPE_PATTERN = re.compile(r"未|没有|不能|无法|不等同于|不代表")
TECHNICAL_META_PHRASES = {
    "该模块",
    "本模块",
    "该步骤输出",
    "分析链",
    "证据链",
}
PAPER_SUBJECT_PATTERN = re.compile(r"论文(?:进行|发现|提出|采用|使用|分析|检验|报告)")
STYLE_WARNING_TERMS = {
    "边界",
    "收束",
    "链条",
    "路径",
    "范式",
    "层级",
    "真正",
    "值得",
}
GENERIC_RESULT_SUBHEADINGS = {
    "关键结果",
    "核心结果",
    "核心发现",
    "主要发现",
    "结果一",
    "结果二",
    "结果三",
}
SUMMARY_EVALUATIVE_PHRASES = {
    "重大创新",
    "突破性",
    "颠覆性",
    "首次证明",
    "非常重要",
    "极具价值",
    "创新性地",
}
CLOSING_RANKING_PHRASES = {
    "最稳定的发现",
    "最可靠的证据",
    "最重要的结果",
    "核心价值在于",
    "核心结论是",
    "最大的价值在于",
}
CLOSING_TEMPLATE_PHRASES = {
    "研究设计上的启发在于",
    "方法学上的启发在于",
    "对MRI研究，较有用的是",
    "对计算神经影像研究",
}
POST_RESULTS_AI_PHRASES = {
    "这些结果共同表明",
    "这一发现进一步说明",
    "值得注意的是",
    "更重要的是",
    "进一步来看",
    "总体而言",
    "综合来看",
    "从某种意义上说",
    "这一发现提示我们",
    "这一结果进一步说明",
    "研究由此表明",
    "真正值得关注的是",
    "尚待检验的是",
    "未来研究需要进一步",
    "这些结果主要限制",
    "这些设计选择主要影响",
    "结论应限于",
    "提供了新的视角",
}
PARAGRAPH_CLOSURE_PATTERNS = (
    re.compile(r"(?:因此|由此可见|这说明|这些结果表明)[^。！？]*[。！？]?$"),
    re.compile(r"(?:未来还需要|尚待检验的是)[^。！？]*[。！？]?$"),
)
METHOD_EVALUATIVE_PHRASES = {
    "真正值得关注的是",
    "真正值得带走的是",
    "关键证据",
    "证据链",
    "意义边界",
    "方法边界",
    "重新理解",
    "从更深层次看",
    "这一结果提醒我们",
    "这套方法真正解决了",
    "最值得借鉴的是",
    "最重要的并不是",
    "对于读者而言",
    "读者需要注意",
    "从科研角度看",
    "从方法学层面来看",
}
EDITORIAL_METHOD_HEADING_PHRASES = {
    "可迁移框架",
    "真正值得",
    "为什么枢纽更脆弱",
    "一个空间成分串起",
    "把疾病效应投向",
    "从平均差异走向",
}
VAGUE_METHOD_PATTERNS = (
    re.compile(r"(?:作者|研究)?(?:使用|采用|进行了?|开展了?)([^。；]{0,24})(?:分析|建模)[。；]"),
    re.compile(r"(?:作者|研究)?(?:构建|建立)了?([^。；]{0,20})(?:模型|网络)[。；]"),
)
STATISTIC_TOKEN_PATTERN = re.compile(
    r"(?:p(?:_[A-Za-z]+)?|q|OR|HR|RR|β|ρ|r|t|F|χ²|z|d|AUC)"
    r"\s*(?:=|<|>|≤|≥)\s*[-+−]?(?:\d+(?:\.\d+)?|\.\d+)"
    r"(?:\s*[×x]\s*10[−⁻^\-]?\d+)?",
    re.IGNORECASE,
)
METHOD_PARAMETER_TOKEN_PATTERN = re.compile(
    r"(?:\b(?:FreeSurfer|MRtrix3|BrainVISA|FSL|SPM|AFNI|ANTs|CAT12|abagen|tckgen|dwi2fod|SIFT2|ACT|SD_STREAM|MSMT-CSD|Dhollander)\b"
    r"|\b\d+(?:\.\d+)?\s*(?:mm3|mm³|mm|ms|Hz|voxels?|streamlines?)\b"
    r"|\d+(?:\.\d+)?\s*(?:万)?条流线"
    r"|(?:步长|流线长度|迭代次数|软件版本|响应函数|球形反卷积|追踪算法))",
    re.IGNORECASE,
)
ASSOCIATION_ANALYSIS_TERMS = {
    "相关",
    "空间关联",
    "空间对应",
    "空间关系",
    "富集",
    "基因表达",
    "PLS",
    "中心性",
}
CAUSAL_OVERCLAIM_PHRASES = {
    "导致",
    "引起",
    "造成",
    "驱动",
    "决定了",
    "证明了",
    "直接机制",
    "机制证据",
}
CORRECTIVE_EDITORIAL_PHRASES = {
    "不等同于",
    "不表示",
    "不能转换为",
    "不能覆盖",
    "不能合并为",
    "不能完全由",
    "不能用于",
}
TRANSITION_MARKERS = {
    "随后",
    "进一步",
    "最后",
    "在确定",
    "在此基础上",
    "接下来",
}

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


def _section_text(section: dict[str, Any]) -> str:
    chunks: list[str] = []
    for block in section.get("blocks", []):
        if not isinstance(block, dict):
            continue
        if isinstance(block.get("text"), str):
            chunks.append(block["text"])
        items = block.get("items", [])
        if isinstance(items, list):
            chunks.extend(item for item in items if isinstance(item, str))
    return "\n".join(chunks)


def _text_length(value: str) -> int:
    return len(re.sub(r"\s+", "", value))


def _long_sentence_summary(value: str) -> tuple[int, int]:
    sentences = [
        re.sub(r"\s+", "", part)
        for part in re.split(r"(?<=[。！？；])|\n+", value)
        if part.strip()
    ]
    lengths = [len(sentence) for sentence in sentences if len(sentence) > 60]
    return len(lengths), max(lengths, default=0)


def _sentences(value: str) -> list[str]:
    return [
        re.sub(r"[\s，。！？；：、,.!?;:]", "", part)
        for part in re.split(r"(?<=[。！？；])|\n+", value)
        if part.strip()
    ]


def _paragraph_closure_locations(sections: list[dict[str, Any]]) -> list[str]:
    locations: list[str] = []
    for section in sections:
        if section.get("id") not in {"result_interpretation", "method_insights", "closing"}:
            continue
        heading = str(section.get("heading") or section.get("id"))
        for index, block in enumerate(section.get("blocks", []), start=1):
            if not isinstance(block, dict) or block.get("type") != "paragraph":
                continue
            text = str(block.get("text") or "").strip()
            if any(pattern.search(text) for pattern in PARAGRAPH_CLOSURE_PATTERNS):
                locations.append(f"{heading}第{index}个内容块")
    return locations


def _unperformed_analysis_locations(section: dict[str, Any]) -> list[str]:
    locations: list[str] = []
    heading = str(section.get("heading") or section.get("id"))
    for index, block in enumerate(section.get("blocks", []), start=1):
        if not isinstance(block, dict) or block.get("type") != "paragraph":
            continue
        text = str(block.get("text") or "").strip()
        hits = sorted(
            {
                match.group(0)
                for pattern in UNPERFORMED_ANALYSIS_PATTERNS
                for match in pattern.finditer(text)
            }
        )
        if hits:
            locations.append(f"{heading}第{index}个内容块（{'、'.join(hits)}）")
    return locations


def _negative_scope_inventory_locations(section: dict[str, Any]) -> list[str]:
    locations: list[str] = []
    heading = str(section.get("heading") or section.get("id"))
    for index, block in enumerate(section.get("blocks", []), start=1):
        if not isinstance(block, dict) or block.get("type") != "paragraph":
            continue
        text = str(block.get("text") or "").strip()
        if len(NEGATIVE_SCOPE_PATTERN.findall(text)) >= 2:
            locations.append(f"{heading}第{index}个内容块")
    return locations


def _paragraph_statistics(
    sections: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, float | int]], list[str], list[str], dict[str, int]]:
    statistics: dict[str, dict[str, float | int]] = {}
    fragmented_runs: list[str] = []
    standalone_transitions: list[str] = []
    opening_counts: dict[str, int] = {}

    for section in sections:
        section_id = str(section.get("id") or "")
        heading = str(section.get("heading") or section_id)
        paragraph_lengths: list[int] = []
        run_lengths: list[int] = []
        run_number = 0

        def finish_run() -> None:
            nonlocal run_lengths, run_number
            if len(run_lengths) >= 4 and sum(length < 120 for length in run_lengths) >= 3:
                run_number += 1
                average = round(sum(run_lengths) / len(run_lengths), 1)
                fragmented_runs.append(
                    f"{heading}第{run_number}组连续{len(run_lengths)}个段落，平均{average}字符"
                )
            run_lengths = []

        for block_index, block in enumerate(section.get("blocks", [])):
            if not isinstance(block, dict) or block.get("type") != "paragraph":
                finish_run()
                continue
            text = str(block.get("text") or "").strip()
            length = _text_length(text)
            paragraph_lengths.append(length)
            run_lengths.append(length)

            for opening in ("研究", "作者", "结果", "论文"):
                if text.startswith(opening):
                    opening_counts[opening] = opening_counts.get(opening, 0) + 1
                    break

            if length <= 70 and any(marker in text for marker in TRANSITION_MARKERS):
                standalone_transitions.append(f"{heading}第{block_index + 1}个内容块")

        finish_run()
        count = len(paragraph_lengths)
        statistics[section_id] = {
            "paragraph_count": count,
            "average_characters": round(sum(paragraph_lengths) / count, 1) if count else 0,
            "short_paragraph_count": sum(length < 80 for length in paragraph_lengths),
        }

    return statistics, fragmented_runs, standalone_transitions, opening_counts


def validate_article(
    article: dict[str, Any],
    article_path: Path | None = None,
    baseline_article: dict[str, Any] | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    schema_version = article.get("schema_version")
    if schema_version not in {1, 2, 3, 4, 5, 6, 7, 8}:
        errors.append("schema_version 必须为 1 至 7（历史兼容）或 8（当前规范）。")
    has_method_insights = any(
        isinstance(section, dict) and section.get("id") == "method_insights"
        for section in article.get("sections", [])
    )
    expected_sections = {
        1: LEGACY_SECTIONS,
        2: VERSION_2_SECTIONS,
        3: CURRENT_SECTIONS,
        4: CURRENT_SECTIONS,
        5: CURRENT_SECTIONS,
        6: (
            VERSION_6_SECTIONS_WITH_METHOD_INSIGHTS
            if has_method_insights
            else VERSION_6_SECTIONS
        ),
        7: VERSION_7_SECTIONS,
        8: VERSION_8_SECTIONS,
    }.get(schema_version, VERSION_8_SECTIONS)
    if schema_version == 1:
        warnings.append("该文章使用历史 schema_version=1；新文章必须使用版本 8。")
    elif schema_version == 2:
        warnings.append("该文章使用历史 schema_version=2 五段式结构；新文章必须使用版本 8。")
    elif schema_version == 3:
        warnings.append("该文章使用历史 schema_version=3；新文章必须使用版本 8。")
    elif schema_version == 4:
        warnings.append("该文章使用历史 schema_version=4；新文章必须使用版本 8。")
    elif schema_version == 5:
        warnings.append("该文章使用历史 schema_version=5；新文章必须使用研究速览、结果解读与结语结构的版本 8。")
    elif schema_version == 6:
        warnings.append("该文章使用历史 schema_version=6；新文章必须使用版本 8。")
    elif schema_version == 7:
        warnings.append("该文章使用历史 schema_version=7；新文章使用以研究速览开头的版本 8。")

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
        if title != title_text:
            errors.append("title 首尾不得包含空白字符。")
        elif "\r" in title_text or "\n" in title_text:
            errors.append("title 不得包含换行。")
        else:
            parts = title_text.split(" | ")
            if (
                len(parts) != 2
                or "|" in title_text.replace(" | ", "")
                or not all(part and part == part.strip() for part in parts)
            ):
                errors.append("title 必须使用“期刊全名或公认缩写 | 简短内容题眼”结构。")
            elif len(parts[1]) > 20:
                errors.append("title 的内容主标题（` | ` 之后）超过 20 个字符。")

    cover = article.get("cover")
    if cover is not None:
        if not isinstance(cover, dict):
            errors.append("cover 必须是对象或 null。")
        else:
            for field in ("path", "alt", "source_note"):
                if not isinstance(cover.get(field), str) or not cover[field].strip():
                    errors.append(f"cover.{field} 不能为空。")
            cover_path = str(cover.get("path", "")).strip()
            if cover_path and not re.match(r"^https?://", cover_path, re.IGNORECASE):
                cover_base = article_path.parent if article_path else Path.cwd()
                resolved_cover = (cover_base / cover_path).resolve()
                if not resolved_cover.is_file():
                    errors.append(f"封面文件不存在：{resolved_cover}")

    source = article.get("source")
    if not isinstance(source, dict):
        errors.append("source 必须是对象。")
    else:
        if not str(source.get("title", "")).strip():
            errors.append("source.title 不能为空。")
        if not str(source.get("source_id", "")).strip():
            errors.append("source.source_id 不能为空；可使用 DOI、PMID 或内部测试标识。")
        evidence_level = str(source.get("evidence_level") or "").strip().upper()
        if evidence_level not in {"FULLTEXT", "TEST_FIXTURE"}:
            errors.append("source.evidence_level 必须为 FULLTEXT 或 TEST_FIXTURE。")
        source_manifest = str(source.get("source_manifest") or "").strip()
        if not source_manifest:
            errors.append("source.source_manifest 不能为空。")
        is_test_fixture = evidence_level == "TEST_FIXTURE"
        if is_test_fixture:
            if not str(article.get("article_id") or "").startswith("phase1-test-"):
                errors.append("TEST_FIXTURE 仅允许用于 phase1-test-* 内部测试文章。")
        else:
            if source.get("fulltext_verified") is not True:
                errors.append("正式文章必须设置 source.fulltext_verified=true。")
            if source_manifest:
                manifest_path = Path(source_manifest)
                if not manifest_path.is_absolute():
                    manifest_base = article_path.parent if article_path else Path.cwd()
                    manifest_path = (manifest_base / manifest_path).resolve()
                if not manifest_path.is_file():
                    errors.append(f"全文来源清单不存在：{manifest_path}")
        if schema_version in {2, 3, 4, 5, 6, 7, 8}:
            for field in ("journal", "published_at", "version_status"):
                if not str(source.get(field, "")).strip():
                    errors.append(f"schema_version={schema_version} 要求 source.{field} 不能为空。")
            authors = source.get("authors")
            if not isinstance(authors, list) or not authors or not all(
                isinstance(author, str) and author.strip() for author in authors
            ):
                errors.append(f"schema_version={schema_version} 要求 source.authors 为非空作者字符串数组。")
            if not str(source.get("doi", "")).strip() and not str(source.get("pmid", "")).strip():
                errors.append(f"schema_version={schema_version} 要求 source.doi 或 source.pmid 至少有一项。")
            version_status = str(source.get("version_status") or "").strip()
            valid_versions = {
                "VERSION_OF_RECORD",
                "PROOF",
                "ACCEPTED_MANUSCRIPT",
                "PREPRINT",
                "OTHER_VERIFIED",
            }
            if version_status and version_status not in valid_versions:
                errors.append(f"source.version_status 不受支持：{version_status!r}")

    sections = article.get("sections")
    if not isinstance(sections, list):
        errors.append("sections 必须是数组。")
        sections = []

    if baseline_article is not None:
        baseline_sections = baseline_article.get("sections")
        if not isinstance(baseline_sections, list) or len(baseline_sections) < 4:
            errors.append("基线文章必须至少包含研究速览或摘要、引言、方法和结果四个章节。")
        elif sections[:4] != baseline_sections[:4]:
            errors.append(
                "局部修改越界：研究速览或摘要、引言、方法或结果与基线文章不一致；"
                "局部修订只能修改用户指定的结果解读和结语。"
            )
    if len(sections) != len(expected_sections):
        errors.append(f"sections 必须且只能包含 {len(expected_sections)} 个固定章节。")

    referenced_figures: set[str] = set()
    for index, expected in enumerate(expected_sections):
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
        if schema_version in {2, 3, 4, 5, 6, 7, 8} and not str(figure.get("figure_id", "")).strip():
            errors.append(f"{location}.figure_id 不能为空；请记录原论文图号或表号。")
        if schema_version == CURRENT_SCHEMA_VERSION:
            mobile_display = figure.get("mobile_display")
            if not isinstance(mobile_display, dict):
                errors.append(f"{location}.mobile_display 必须声明移动端展示策略。")
            else:
                strategy = str(mobile_display.get("strategy") or "").strip()
                valid_strategies = {"native", "cropped", "split_panel", "selected_panels"}
                if strategy not in valid_strategies:
                    errors.append(
                        f"{location}.mobile_display.strategy 不受支持：{strategy!r}"
                    )
                if strategy in {"cropped", "split_panel", "selected_panels"} and not str(
                    mobile_display.get("source_figure_id") or ""
                ).strip():
                    errors.append(
                        f"{location}.mobile_display.source_figure_id 不能为空；"
                        "裁切、拆分或选取面板时必须保留原始组合图编号。"
                    )
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
        claim_type = str(item.get("claim_type") or "").strip()
        if schema_version in {2, 3, 4, 5, 6, 7, 8} and claim_type not in CLAIM_TYPES:
            errors.append(
                f"evidence_map[{index}].claim_type 必须区分直接结果、作者解释或编辑说明。"
            )
        elif claim_type and claim_type not in CLAIM_TYPES:
            errors.append(f"evidence_map[{index}].claim_type 不受支持：{claim_type!r}")
        if item.get("status") != "verified":
            errors.append(f"evidence_map[{index}] 未通过证据核查。")

    method_map = article.get("method_map")
    if schema_version in {4, 5, 6, 7, 8} and (not isinstance(method_map, list) or not method_map):
        errors.append(f"schema_version={schema_version} 要求 method_map 至少包含一个核心分析方法。")
        method_map = []
    elif method_map is None:
        method_map = []
    elif not isinstance(method_map, list):
        errors.append("method_map 必须是数组。")
        method_map = []

    methods_section = next(
        (
            section
            for section in sections
            if isinstance(section, dict) and section.get("id") == "methods"
        ),
        None,
    )
    method_headings = {
        str(block.get("text") or "").strip()
        for block in (methods_section or {}).get("blocks", [])
        if isinstance(block, dict) and block.get("type") == "subheading"
    }
    method_ids: set[str] = set()
    for index, item in enumerate(method_map):
        location = f"method_map[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{location} 必须是对象。")
            continue
        method_id = str(item.get("method_id") or "").strip()
        if not method_id:
            errors.append(f"{location}.method_id 不能为空。")
        elif method_id in method_ids:
            errors.append(f"重复的 method_id：{method_id}")
        else:
            method_ids.add(method_id)
        for field in ("name", "section_heading", "purpose"):
            if not str(item.get(field) or "").strip():
                errors.append(f"{location}.{field} 不能为空。")
        section_heading = str(item.get("section_heading") or "").strip()
        if schema_version in {4, 5, 6, 7, 8} and section_heading and section_heading not in method_headings:
            errors.append(
                f"{location}.section_heading 未对应方法部分小标题：{section_heading}"
            )
        data = item.get("data")
        if not isinstance(data, dict) or not str(data.get("description") or "").strip():
            errors.append(f"{location}.data.description 必须说明输入数据。")
        importance = str(item.get("importance") or "").strip()
        if schema_version in {5, 6, 7, 8} and importance not in {"core", "supporting", "routine"}:
            errors.append(f"{location}.importance 必须为 core、supporting 或 routine。")
        elif importance and importance not in {"core", "supporting", "routine"}:
            errors.append(f"{location}.importance 不受支持：{importance!r}")
        for field, label in (
            ("processing_steps", "数据处理"),
            ("statistics", "统计检验"),
            ("source_locators", "原文定位"),
        ):
            values = item.get(field)
            if not isinstance(values, list) or not values or not all(
                isinstance(value, str) and value.strip() for value in values
            ):
                errors.append(f"{location}.{field} 必须包含至少一项{label}信息。")
        outputs = item.get("outputs")
        if schema_version == 4 and (
            not isinstance(outputs, list)
            or not outputs
            or not all(isinstance(value, str) and value.strip() for value in outputs)
        ):
            errors.append(f"{location}.outputs 必须包含至少一项最终输出信息。")
        elif outputs is not None and (
            not isinstance(outputs, list)
            or not outputs
            or not all(isinstance(value, str) and value.strip() for value in outputs)
        ):
            errors.append(f"{location}.outputs 如存在，必须是非空字符串数组。")
        unreported = item.get("unreported_details", [])
        if schema_version in {5, 6, 7, 8} and "unreported_details" in item:
            errors.append(
                f"{location}.unreported_details 已停用；常规未报告参数应省略，仅将影响主要结论解释的信息写入 critical_missing_details。"
            )
        elif not isinstance(unreported, list) or not all(
            isinstance(value, str) and value.strip() for value in unreported
        ):
            errors.append(f"{location}.unreported_details 必须是字符串数组。")
        critical_missing = item.get("critical_missing_details", [])
        if "critical_missing_details" in item and (
            not isinstance(critical_missing, list)
            or not critical_missing
            or not all(isinstance(value, str) and value.strip() for value in critical_missing)
        ):
            errors.append(f"{location}.critical_missing_details 必须是非空字符串数组。")
        if item.get("status") != "verified":
            errors.append(f"{location} 未通过方法证据核查。")

    _walk_keys(article, errors)

    body_characters = _plain_text_length(article)
    if body_characters < 100:
        warnings.append("正文少于 100 个非空白字符；仅适合流程测试。")

    section_characters: dict[str, int] = {}
    section_shares: dict[str, float] = {}
    paragraph_statistics: dict[str, dict[str, float | int]] = {}
    if isinstance(sections, list):
        for section in sections:
            if not isinstance(section, dict):
                continue
            section_id = str(section.get("id") or "")
            section_characters[section_id] = _text_length(_section_text(section))
        if body_characters:
            section_shares = {
                section_id: round(length / body_characters, 4)
                for section_id, length in section_characters.items()
            }

        valid_sections = [section for section in sections if isinstance(section, dict)]
        (
            paragraph_statistics,
            fragmented_runs,
            standalone_transitions,
            opening_counts,
        ) = _paragraph_statistics(valid_sections)
        if fragmented_runs:
            warnings.append(
                "检测到可能的段落碎片化（仅供语义合并复核，不限制段落数量）："
                + "；".join(fragmented_runs)
            )
        if standalone_transitions:
            warnings.append(
                "检测到可能独立成段的过渡句，请并入其引出的实质段落："
                + "、".join(standalone_transitions)
            )
        repeated_openings = [
            f"{opening}×{count}" for opening, count in opening_counts.items() if count >= 4
        ]
        if repeated_openings:
            warnings.append(
                "段落开头重复较多，请按科学主语人工复核：" + "、".join(repeated_openings)
            )

    if schema_version in {2, 3, 4, 5, 6, 7, 8}:
        visible_text = "\n".join(
            _section_text(section) for section in sections if isinstance(section, dict)
        )
        for phrase in sorted(HARD_BANNED_PHRASES):
            if phrase in visible_text:
                errors.append(f"正文包含模板化或禁用表达：{phrase}")

        if schema_version in {5, 6, 7, 8}:
            for phrase in sorted(INTERNAL_PROCESS_PHRASES):
                if phrase in visible_text:
                    errors.append(f"正文暴露内部材料核查过程：{phrase}")
            for pattern in INTERNAL_PROCESS_PATTERNS:
                match = pattern.search(visible_text)
                if match:
                    errors.append(f"正文暴露内部材料核查过程：{match.group(0)}")
            for phrase in sorted(TECHNICAL_META_PHRASES):
                if phrase in visible_text:
                    errors.append(f"正文包含技术报告式元语言：{phrase}")
            has_critical_missing = any(
                isinstance(item, dict) and item.get("critical_missing_details")
                for item in method_map
            )
            interpretation_ids = (
                {"result_interpretation"} if schema_version in {6, 7, 8} else {"discussion"}
            )
            discussion_text = "\n".join(
                _section_text(section)
                for section in sections
                if isinstance(section, dict) and section.get("id") in interpretation_ids
            )
            non_discussion_text = "\n".join(
                _section_text(section)
                for section in sections
                if isinstance(section, dict) and section.get("id") not in interpretation_ids
            )
            for phrase in sorted(UNREPORTED_PUBLIC_PHRASES):
                if phrase in non_discussion_text:
                    errors.append(
                        f"正文在结果解读之外主动说明缺失信息：{phrase}"
                    )
                elif phrase in discussion_text and not has_critical_missing:
                    errors.append(
                        f"结果解读主动说明常规缺失信息但未登记其对主要结论的影响：{phrase}"
                    )
            paper_subject_hits = PAPER_SUBJECT_PATTERN.findall(visible_text)
            if paper_subject_hits:
                warnings.append(
                    "正文以“论文”作动作主语；优先改为“研究”“作者”或省略主语："
                    + "、".join(sorted(set(paper_subject_hits)))
                )

        warning_hits = sorted(term for term in STYLE_WARNING_TERMS if term in visible_text)
        if warning_hits:
            warnings.append(
                "正文含需人工复核的AI化或评价性用词：" + "、".join(warning_hits)
            )

        contrast_count = len(re.findall(r"不是[^。！？]{0,80}而是", visible_text))
        if contrast_count >= 3:
            warnings.append(f"正文重复使用“不是……而是……”结构 {contrast_count} 次。")

        long_sentence_count, longest_sentence = _long_sentence_summary(visible_text)
        if long_sentence_count:
            warnings.append(
                f"正文有 {long_sentence_count} 个超过60字符的复合句，最长 {longest_sentence} 字符。"
            )

        digest = str(article.get("digest") or "").strip()
        opening_section = next(
            (
                section
                for section in sections
                if isinstance(section, dict)
                and section.get("id") == ("overview" if schema_version == 8 else "abstract")
            ),
            None,
        )
        if digest and isinstance(opening_section, dict) and digest in _section_text(opening_section):
            warnings.append(
                "digest 与研究速览或摘要存在逐句重复，请让导读卡和正文开头承担不同功能。"
            )

        if schema_version == 8 and isinstance(opening_section, dict):
            overview_text = _section_text(opening_section)
            detailed_statistics = STATISTIC_TOKEN_PATTERN.findall(overview_text)
            if detailed_statistics:
                errors.append(
                    "研究速览不得提前罗列具体检验统计量；将 t、p、OR、β 等数值留在结果部分："
                    + "、".join(sorted(set(detailed_statistics))[:6])
                )
            opening_pairs = (
                ("研究速览", opening_section, "引言", next(
                    (section for section in sections if section.get("id") == "introduction"),
                    None,
                )),
                ("研究速览", opening_section, "结果", next(
                    (section for section in sections if section.get("id") == "results"),
                    None,
                )),
            )
            for left_name, left_section, right_name, right_section in opening_pairs:
                if not isinstance(right_section, dict):
                    continue
                left_sentences = {
                    sentence for sentence in _sentences(_section_text(left_section)) if len(sentence) >= 18
                }
                repeated = sorted(
                    sentence
                    for sentence in _sentences(_section_text(right_section))
                    if len(sentence) >= 18 and sentence in left_sentences
                )
                if repeated:
                    warnings.append(
                        f"{left_name}与{right_name}存在完整句重复；同一核心结论只完整陈述一次："
                        + "；".join(repeated[:3])
                    )

        interpretation_ids = (
            {"result_interpretation"} if schema_version in {6, 7, 8} else {"discussion"}
        )
        for section in sections:
            if not isinstance(section, dict) or section.get("id") in interpretation_ids:
                continue
            section_text = _section_text(section)
            hits = sorted(
                phrase for phrase in CORRECTIVE_EDITORIAL_PHRASES if phrase in section_text
            )
            if hits:
                warnings.append(
                    f"{section.get('heading', section.get('id', '未知章节'))}含审稿式限定语："
                    + "、".join(hits)
                    + "；优先改写为数据来源、分析单位或直接结果，并把必要解释集中到结果解读。"
                )

        if isinstance(methods_section, dict):
            methods_text = _section_text(methods_section)
            for phrase in sorted(METHOD_EVALUATIVE_PHRASES):
                if phrase in methods_text:
                    errors.append(f"方法部分包含评价性或读者视角表达：{phrase}")
            for heading in sorted(method_headings):
                heading_hits = sorted(
                    phrase for phrase in EDITORIAL_METHOD_HEADING_PHRASES if phrase in heading
                )
                if heading_hits:
                    errors.append(
                        f"方法小标题应客观描述分析，不使用编辑式措辞：{heading}"
                    )
            vague_hits: list[str] = []
            for pattern in VAGUE_METHOD_PATTERNS:
                vague_hits.extend(match.group(0) for match in pattern.finditer(methods_text))
            if vague_hits:
                warnings.append(
                    "方法部分可能存在过度概括，请结合 method_map 补充必要的数据、处理、统计和有助于理解的输出："
                    + "；".join(sorted(set(vague_hits)))
                )
            parameter_heavy_blocks = []
            for block_index, block in enumerate(methods_section.get("blocks", []), start=1):
                if not isinstance(block, dict) or block.get("type") != "paragraph":
                    continue
                token_count = len(
                    METHOD_PARAMETER_TOKEN_PATTERN.findall(str(block.get("text") or ""))
                )
                if token_count >= 5:
                    parameter_heavy_blocks.append(f"第{block_index}段（{token_count}项）")
            if parameter_heavy_blocks:
                warnings.append(
                    "方法段可能堆积非关键软件或技术参数；保留分析逻辑、关键步骤和决定解释的核心参数即可："
                    + "、".join(parameter_heavy_blocks)
                )

        results_section = next(
            (
                section
                for section in sections
                if isinstance(section, dict) and section.get("id") == "results"
            ),
            None,
        )
        if isinstance(results_section, dict):
            for block in results_section.get("blocks", []):
                if not isinstance(block, dict) or block.get("type") != "subheading":
                    continue
                heading = str(block.get("text") or "").strip()
                if heading in GENERIC_RESULT_SUBHEADINGS or "证据" in heading:
                    errors.append(f"结果小标题必须直接描述发现，不能使用泛化标签：{heading}")
            if "证据" in _section_text(results_section):
                warnings.append("结果部分出现“证据”；请确认是否可改为对原始结果的直接描述。")
            statistic_heavy_blocks = []
            for block_index, block in enumerate(results_section.get("blocks", []), start=1):
                if not isinstance(block, dict) or block.get("type") != "paragraph":
                    continue
                token_count = len(STATISTIC_TOKEN_PATTERN.findall(str(block.get("text") or "")))
                if token_count >= 3:
                    statistic_heavy_blocks.append(f"第{block_index}段（{token_count}项）")
            if statistic_heavy_blocks:
                warnings.append(
                    "结果段统计量可能过度堆积；只保留决定主要结论成立与否的关键统计量："
                    + "、".join(statistic_heavy_blocks)
                )

        causal_locations = []
        for section in sections:
            if not isinstance(section, dict) or section.get("id") not in {
                "results",
                "result_interpretation",
                "closing",
            }:
                continue
            for sentence in _sentences(_section_text(section)):
                if any(term in sentence for term in ASSOCIATION_ANALYSIS_TERMS) and any(
                    phrase in sentence for phrase in CAUSAL_OVERCLAIM_PHRASES
                ):
                    causal_locations.append(
                        f"{section.get('heading', section.get('id'))}：{sentence}"
                    )
        if causal_locations:
            warnings.append(
                "相关、空间对应或富集结果可能被写成因果或机制证据；请按研究设计降低结论强度："
                + "；".join(causal_locations[:4])
            )

        if schema_version in {3, 4, 5, 6, 7, 8}:
            summary_section = next(
                (
                    section
                    for section in sections
                    if isinstance(section, dict)
                    and section.get("id") == ("closing" if schema_version in {6, 7, 8} else "summary")
                ),
                None,
            )
            if isinstance(summary_section, dict):
                summary_text = _section_text(summary_section)
                for phrase in sorted(SUMMARY_EVALUATIVE_PHRASES):
                    if phrase in summary_text:
                        errors.append(f"{'结语' if schema_version in {6, 7, 8} else '总结'}包含评价性创新表述：{phrase}")

        if schema_version in {6, 7, 8}:
            results_section = next(
                (section for section in sections if section.get("id") == "results"), None
            )
            interpretation_section = next(
                (
                    section
                    for section in sections
                    if section.get("id") == "result_interpretation"
                ),
                None,
            )
            if isinstance(results_section, dict) and isinstance(interpretation_section, dict):
                result_sentences = {
                    sentence
                    for sentence in _sentences(_section_text(results_section))
                    if len(sentence) >= 18
                }
                repeated = sorted(
                    sentence
                    for sentence in _sentences(_section_text(interpretation_section))
                    if len(sentence) >= 18 and sentence in result_sentences
                )
                if repeated:
                    errors.append(
                        "结果解读逐句重复结果部分，请删除重复陈述后只保留必要解释："
                        + "；".join(repeated[:3])
                    )

            post_results_ids = (
                {"result_interpretation", "closing"}
                if schema_version in {7, 8}
                else {"result_interpretation", "method_insights", "closing"}
            )
            post_results_sections = [
                section
                for section in sections
                if isinstance(section, dict)
                and section.get("id") in post_results_ids
            ]
            post_results_text = "\n".join(_section_text(section) for section in post_results_sections)
            ai_hits = sorted(phrase for phrase in POST_RESULTS_AI_PHRASES if phrase in visible_text)
            if ai_hits:
                warnings.append(
                    "正文含可能模板化的AI式表达，请优先删除而非同义改写："
                    + "、".join(ai_hits)
                )
            closure_locations = _paragraph_closure_locations(post_results_sections)
            if closure_locations:
                warnings.append(
                    "后半部分段尾可能存在二次概括、升华或展望，请检查删除后信息是否仍完整："
                    + "、".join(closure_locations)
                )
            if schema_version in {7, 8} and isinstance(interpretation_section, dict):
                unperformed_locations = _unperformed_analysis_locations(interpretation_section)
                if unperformed_locations and not has_critical_missing:
                    errors.append(
                        "结果解读默认不得罗列研究未实施的分析；改写为实际数据、变量或分析定义，"
                        "或删除不影响理解的限制：" + "、".join(unperformed_locations)
                    )
                negative_locations = _negative_scope_inventory_locations(interpretation_section)
                if negative_locations:
                    warnings.append(
                        "结果解读可能集中罗列否定或限制性表达，请确认每项都直接影响主要结果解释："
                        + "、".join(negative_locations)
                    )
            closing_section = next(
                (section for section in sections if section.get("id") == "closing"), None
            )
            if isinstance(closing_section, dict):
                closing_text = _section_text(closing_section)
                for phrase in sorted(CLOSING_RANKING_PHRASES):
                    if phrase in closing_text:
                        errors.append(f"结语不得进行证据或价值排名：{phrase}")
                for phrase in sorted(CLOSING_TEMPLATE_PHRASES):
                    if phrase in closing_text:
                        errors.append(
                            f"结语包含固定的方法启示句式：{phrase}；"
                            "方法层内容是可选项，保留时请直接从本研究的具体设计或解释问题写起。"
                        )
                prior_sentences = {
                    sentence
                    for section in sections
                    if isinstance(section, dict) and section.get("id") in {"methods", "results"}
                    for sentence in _sentences(_section_text(section))
                    if len(sentence) >= 18
                }
                closing_repeated = sorted(
                    sentence
                    for sentence in _sentences(closing_text)
                    if len(sentence) >= 18 and sentence in prior_sentences
                )
                if closing_repeated:
                    warnings.append(
                        "结语重复方法或结果完整句；改为说明研究增加的认识，"
                        "仅在确有新增信息时保留具体分析逻辑："
                        + "；".join(closing_repeated[:3])
                    )
                closing_parameter_count = len(
                    METHOD_PARAMETER_TOKEN_PATTERN.findall(closing_text)
                )
                closing_statistic_count = len(STATISTIC_TOKEN_PATTERN.findall(closing_text))
                if closing_parameter_count >= 3 or closing_statistic_count >= 3:
                    warnings.append(
                        "结语可能重复方法流程或统计结果；保留主要认识即可，"
                        "方法层评论不必强制出现。"
                    )

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
            "mobile_optimized_figure_count": sum(
                1
                for figure in figures
                if isinstance(figure, dict)
                and isinstance(figure.get("mobile_display"), dict)
                and figure["mobile_display"].get("strategy")
                in {"cropped", "split_panel", "selected_panels"}
            ),
            "reference_count": len(references),
            "evidence_record_count": len(evidence_map),
            "method_record_count": len(method_map),
            "section_characters": section_characters,
            "section_shares": section_shares,
            "paragraph_statistics": paragraph_statistics,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate an MRI WeChat article JSON file.")
    parser.add_argument("article", type=Path)
    parser.add_argument(
        "--baseline",
        type=Path,
        help="Optional pre-revision article used to enforce identical protected sections.",
    )
    parser.add_argument("--compact", action="store_true", help="Print compact JSON.")
    args = parser.parse_args()

    try:
        article_path = args.article.resolve()
        baseline_article = load_article(args.baseline.resolve()) if args.baseline else None
        result = validate_article(
            load_article(article_path),
            article_path,
            baseline_article=baseline_article,
        )
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
