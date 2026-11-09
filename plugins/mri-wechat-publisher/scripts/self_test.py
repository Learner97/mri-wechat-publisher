#!/usr/bin/env python3
"""Run deterministic phase-one tests without network or live account writes."""

from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

from render_method_map import render_method_map
from render_wechat_html import FORBIDDEN_HTML_PATTERNS, render_article
from validate_article import load_article, validate_article
from wechat_draft_api import WeChatApiError, resolve_required_cover


def assert_blocked(article: dict, article_path: Path, label: str) -> None:
    result = validate_article(article, article_path)
    if result["status"] != "QA_BLOCKED":
        raise AssertionError(f"{label} should be blocked: {result}")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    article_path = root / "examples" / "phase1-test-article.json"
    article = load_article(article_path)

    baseline = validate_article(article, article_path)
    if baseline["status"] != "QA_PASSED":
        raise AssertionError(f"baseline failed: {baseline}")

    schema_path = root / "schemas" / "article.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    schema_errors = sorted(
        Draft202012Validator(schema).iter_errors(article),
        key=lambda error: list(error.absolute_path),
    )
    if schema_errors:
        raise AssertionError(f"example schema validation failed: {schema_errors}")

    version_5_template = copy.deepcopy(article)
    version_5_template["schema_version"] = 5
    version_5_template["sections"][0]["id"] = "abstract"
    version_5_template["sections"][0]["heading"] = "摘要"
    version_5_template["sections"][4]["id"] = "discussion"
    version_5_template["sections"][4]["heading"] = "讨论"
    version_5_template["sections"][5]["id"] = "summary"
    version_5_template["sections"][5]["heading"] = "总结"

    legacy_article = copy.deepcopy(version_5_template)
    legacy_article["schema_version"] = 1
    legacy_article.pop("method_map")
    legacy_article["source"].pop("authors")
    legacy_article["source"].pop("version_status")
    for evidence_item in legacy_article["evidence_map"]:
        evidence_item.pop("claim_type")
    legacy_article["sections"] = legacy_article["sections"][:5]
    legacy_headings = [
        ("abstract", "摘要解读"),
        ("design", "研究设计与数据"),
        ("method", "核心方法解析"),
        ("results", "关键结果与证据链"),
        ("implications", "方法启示与总结"),
    ]
    for section, (section_id, heading) in zip(legacy_article["sections"], legacy_headings):
        section["id"] = section_id
        section["heading"] = heading
    legacy_result = validate_article(legacy_article, article_path)
    if legacy_result["status"] != "QA_PASSED":
        raise AssertionError(f"legacy schema compatibility failed: {legacy_result}")
    legacy_schema_errors = list(Draft202012Validator(schema).iter_errors(legacy_article))
    if legacy_schema_errors:
        raise AssertionError(f"legacy schema validation failed: {legacy_schema_errors}")

    version_2_article = copy.deepcopy(version_5_template)
    version_2_article["schema_version"] = 2
    version_2_article.pop("method_map")
    version_2_article["sections"] = version_2_article["sections"][:5]
    version_2_article["sections"][4]["heading"] = "讨论与总结"
    version_2_result = validate_article(version_2_article, article_path)
    if version_2_result["status"] != "QA_PASSED":
        raise AssertionError(f"version 2 compatibility failed: {version_2_result}")
    version_2_schema_errors = list(Draft202012Validator(schema).iter_errors(version_2_article))
    if version_2_schema_errors:
        raise AssertionError(f"version 2 schema validation failed: {version_2_schema_errors}")

    version_3_article = copy.deepcopy(version_5_template)
    version_3_article["schema_version"] = 3
    version_3_article.pop("method_map")
    version_3_result = validate_article(version_3_article, article_path)
    if version_3_result["status"] != "QA_PASSED" or not any(
        "历史 schema_version=3" in warning for warning in version_3_result["warnings"]
    ):
        raise AssertionError(f"version 3 compatibility failed: {version_3_result}")
    version_3_schema_errors = list(Draft202012Validator(schema).iter_errors(version_3_article))
    if version_3_schema_errors:
        raise AssertionError(f"version 3 schema validation failed: {version_3_schema_errors}")

    version_4_article = copy.deepcopy(version_5_template)
    version_4_article["schema_version"] = 4
    for method in version_4_article["method_map"]:
        method.pop("importance")
    version_4_result = validate_article(version_4_article, article_path)
    if version_4_result["status"] != "QA_PASSED" or not any(
        "历史 schema_version=4" in warning for warning in version_4_result["warnings"]
    ):
        raise AssertionError(f"version 4 compatibility failed: {version_4_result}")
    version_4_schema_errors = list(Draft202012Validator(schema).iter_errors(version_4_article))
    if version_4_schema_errors:
        raise AssertionError(f"version 4 schema validation failed: {version_4_schema_errors}")

    version_5_result = validate_article(version_5_template, article_path)
    if version_5_result["status"] != "QA_PASSED" or not any(
        "历史 schema_version=5" in warning for warning in version_5_result["warnings"]
    ):
        raise AssertionError(f"version 5 compatibility failed: {version_5_result}")
    version_5_schema_errors = list(
        Draft202012Validator(schema).iter_errors(version_5_template)
    )
    if version_5_schema_errors:
        raise AssertionError(f"version 5 schema validation failed: {version_5_schema_errors}")

    version_6_article = copy.deepcopy(article)
    version_6_article["schema_version"] = 6
    version_6_article["sections"][0]["id"] = "abstract"
    version_6_article["sections"][0]["heading"] = "摘要"
    version_6_result = validate_article(version_6_article, article_path)
    if version_6_result["status"] != "QA_PASSED" or not any(
        "历史 schema_version=6" in warning for warning in version_6_result["warnings"]
    ):
        raise AssertionError(f"version 6 compatibility failed: {version_6_result}")
    version_6_schema_errors = list(
        Draft202012Validator(schema).iter_errors(version_6_article)
    )
    if version_6_schema_errors:
        raise AssertionError(f"version 6 schema validation failed: {version_6_schema_errors}")

    version_7_article = copy.deepcopy(article)
    version_7_article["schema_version"] = 7
    version_7_article["sections"][0]["id"] = "abstract"
    version_7_article["sections"][0]["heading"] = "摘要"
    version_7_result = validate_article(version_7_article, article_path)
    if version_7_result["status"] != "QA_PASSED" or not any(
        "历史 schema_version=7" in warning for warning in version_7_result["warnings"]
    ):
        raise AssertionError(f"version 7 compatibility failed: {version_7_result}")
    version_7_schema_errors = list(
        Draft202012Validator(schema).iter_errors(version_7_article)
    )
    if version_7_schema_errors:
        raise AssertionError(f"version 7 schema validation failed: {version_7_schema_errors}")

    optional_method_insights = copy.deepcopy(version_6_article)
    optional_method_insights["sections"].insert(
        5,
        {
            "id": "method_insights",
            "heading": "方法启示",
            "blocks": [
                {
                    "type": "paragraph",
                    "text": "先验证结构再转换HTML，使内容错误与排版错误能够分别检查。",
                }
            ],
        },
    )
    optional_result = validate_article(optional_method_insights, article_path)
    if optional_result["status"] != "QA_PASSED":
        raise AssertionError(f"optional method insights failed: {optional_result}")
    optional_schema_errors = list(
        Draft202012Validator(schema).iter_errors(optional_method_insights)
    )
    if optional_schema_errors:
        raise AssertionError(f"optional method insights schema failed: {optional_schema_errors}")

    wrong_mode = copy.deepcopy(article)
    wrong_mode["publication_mode"] = "publish"
    assert_blocked(wrong_mode, article_path, "wrong publication mode")

    missing_section = copy.deepcopy(article)
    missing_section["sections"].pop()
    assert_blocked(missing_section, article_path, "missing fixed section")

    legacy_heading_in_current = copy.deepcopy(article)
    legacy_heading_in_current["sections"][0]["id"] = "abstract"
    legacy_heading_in_current["sections"][0]["heading"] = "摘要"
    assert_blocked(legacy_heading_in_current, article_path, "legacy heading in schema version 8")
    if not list(Draft202012Validator(schema).iter_errors(legacy_heading_in_current)):
        raise AssertionError("schema should reject legacy headings in schema version 8")

    missing_claim_type = copy.deepcopy(article)
    missing_claim_type["evidence_map"][0].pop("claim_type")
    assert_blocked(missing_claim_type, article_path, "missing claim type")
    if not list(Draft202012Validator(schema).iter_errors(missing_claim_type)):
        raise AssertionError("schema should reject missing claim_type in schema version 8")

    missing_source_authors = copy.deepcopy(article)
    missing_source_authors["source"].pop("authors")
    assert_blocked(missing_source_authors, article_path, "missing source authors")
    if not list(Draft202012Validator(schema).iter_errors(missing_source_authors)):
        raise AssertionError("schema should reject missing source authors in schema version 8")

    missing_method_map = copy.deepcopy(article)
    missing_method_map.pop("method_map")
    assert_blocked(missing_method_map, article_path, "missing method map")
    if not list(Draft202012Validator(schema).iter_errors(missing_method_map)):
        raise AssertionError("schema should reject a missing method_map in schema version 8")

    optional_method_output = copy.deepcopy(article)
    optional_method_output["method_map"][0].pop("outputs")
    if validate_article(optional_method_output, article_path)["status"] != "QA_PASSED":
        raise AssertionError("schema version 8 must allow a method record without outputs")
    if list(Draft202012Validator(schema).iter_errors(optional_method_output)):
        raise AssertionError("schema should allow a method record without outputs in schema version 8")

    missing_method_importance = copy.deepcopy(article)
    missing_method_importance["method_map"][0].pop("importance")
    assert_blocked(missing_method_importance, article_path, "missing method importance")
    if not list(Draft202012Validator(schema).iter_errors(missing_method_importance)):
        raise AssertionError("schema should reject a method record without importance in schema version 8")

    retired_unreported_details = copy.deepcopy(article)
    retired_unreported_details["method_map"][0]["unreported_details"] = ["内部夹具未报告参数。"]
    assert_blocked(retired_unreported_details, article_path, "retired unreported details")
    if not list(Draft202012Validator(schema).iter_errors(retired_unreported_details)):
        raise AssertionError("schema should reject unreported_details in schema version 8")

    overview_statistics = copy.deepcopy(article)
    overview_statistics["sections"][0]["blocks"][0]["text"] += " t=2.40，p=0.02。"
    assert_blocked(overview_statistics, article_path, "detailed statistics in Research Overview")

    repeated_opening = copy.deepcopy(article)
    repeated_opening["sections"][1]["blocks"][0]["text"] = (
        repeated_opening["sections"][0]["blocks"][0]["text"]
    )
    repeated_opening_result = validate_article(repeated_opening, article_path)
    if not any("研究速览与引言存在完整句重复" in warning for warning in repeated_opening_result["warnings"]):
        raise AssertionError("opening-section duplication should trigger a review warning")

    empty_critical_missing = copy.deepcopy(article)
    empty_critical_missing["method_map"][0]["critical_missing_details"] = []
    assert_blocked(empty_critical_missing, article_path, "empty critical missing details")
    if not list(Draft202012Validator(schema).iter_errors(empty_critical_missing)):
        raise AssertionError("schema should reject an empty critical_missing_details array")

    mismatched_method_heading = copy.deepcopy(article)
    mismatched_method_heading["method_map"][0]["section_heading"] = "不存在的小标题"
    assert_blocked(mismatched_method_heading, article_path, "mismatched method heading")

    evaluative_method = copy.deepcopy(article)
    evaluative_method["sections"][2]["blocks"][1]["text"] = "真正值得关注的是这套方法。"
    assert_blocked(evaluative_method, article_path, "evaluative method prose")

    vague_method = copy.deepcopy(article)
    vague_method["sections"][2]["blocks"][1]["text"] = "作者进行了结构连接分析。"
    vague_result = validate_article(vague_method, article_path)
    if not any("方法部分可能存在过度概括" in warning for warning in vague_result["warnings"]):
        raise AssertionError("vague method prose should trigger a review warning")

    parameter_heavy_method = copy.deepcopy(article)
    parameter_heavy_method["sections"][2]["blocks"][1]["text"] = (
        "MRtrix3 dwi2fod采用MSMT-CSD和Dhollander响应函数，"
        "tckgen使用SD_STREAM与ACT，追踪步长0.5 mm，每人生成1000万条流线。"
    )
    parameter_result = validate_article(parameter_heavy_method, article_path)
    if not any("堆积非关键软件或技术参数" in warning for warning in parameter_result["warnings"]):
        raise AssertionError("parameter-list method prose should trigger a review warning")

    method_markdown = render_method_map(article)
    for marker in ("方法重要性", "数据概述", "处理步骤", "统计检验", "有助于后续理解的输出", "原文定位"):
        if marker not in method_markdown:
            raise AssertionError(f"method map renderer omitted {marker}")

    output_free_method = copy.deepcopy(article)
    output_free_method["method_map"][0].pop("outputs")
    output_free_markdown = render_method_map(output_free_method)
    if "有助于后续理解的输出" in output_free_markdown:
        raise AssertionError("method map renderer should omit an absent optional output field")

    canned_prose = copy.deepcopy(article)
    canned_prose["sections"][0]["blocks"][0]["text"] = "本文只需记住三点。"
    assert_blocked(canned_prose, article_path, "canned prose")

    for label, digest in {
        "declarative digest": "两个影像指标在同一空间尺度上呈现不同分布。",
        "open-question digest": "同一空间模式在独立样本中还能保持吗？",
        "question-answer digest": "差异出现在哪里？结果集中在预先定义的区域。",
    }.items():
        digest_form = copy.deepcopy(article)
        digest_form["digest"] = digest
        if validate_article(digest_form, article_path)["status"] != "QA_PASSED":
            raise AssertionError(f"{label} should be accepted when source-grounded")

    reader_address = copy.deepcopy(article)
    reader_address["sections"][0]["blocks"][0]["text"] = "读者可以据此判断。"
    assert_blocked(reader_address, article_path, "reader address")

    generic_result_heading = copy.deepcopy(article)
    generic_result_heading["sections"][3]["blocks"][0]["text"] = "关键结果"
    assert_blocked(generic_result_heading, article_path, "generic result heading")

    statistic_heavy_result = copy.deepcopy(article)
    statistic_heavy_result["sections"][3]["blocks"][1]["text"] = (
        "主要关系达到p=0.001，扩展分析OR=2.10，另一项比较β=0.30。"
    )
    statistic_result = validate_article(statistic_heavy_result, article_path)
    if not any("统计量可能过度堆积" in warning for warning in statistic_result["warnings"]):
        raise AssertionError("statistic-list result prose should trigger a review warning")

    causal_overclaim = copy.deepcopy(article)
    causal_overclaim["sections"][4]["blocks"][0]["text"] = (
        "空间相关证明了区域基因表达直接驱动影像变化。"
    )
    causal_result = validate_article(causal_overclaim, article_path)
    if not any("可能被写成因果或机制证据" in warning for warning in causal_result["warnings"]):
        raise AssertionError("association-to-causation wording should trigger a review warning")

    variable_result_count = copy.deepcopy(article)
    variable_result_count["sections"][3]["blocks"].extend(
        {"type": "subheading", "text": f"离线检查项目{i}通过"}
        for i in range(2, 7)
    )
    if validate_article(variable_result_count, article_path)["status"] != "QA_PASSED":
        raise AssertionError("result subsection count must remain evidence-driven")

    long_article = copy.deepcopy(article)
    long_article["sections"][4]["blocks"][0]["text"] += "测" * 12000
    long_result = validate_article(long_article, article_path)
    if long_result["status"] != "QA_PASSED" or any(
        "11,000" in warning for warning in long_result["warnings"]
    ):
        raise AssertionError("current schema must not enforce the legacy 11,000-character target")

    introduction_too_long = copy.deepcopy(article)
    introduction_too_long["sections"][1]["blocks"][0]["text"] = "研究背景。" * 80
    if validate_article(introduction_too_long, article_path)["status"] != "QA_PASSED":
        raise AssertionError("section length relationships must not block evidence-driven writing")

    summary_too_long = copy.deepcopy(article)
    summary_too_long["sections"][5]["blocks"][0]["text"] = "研究采用统一数据结构。结果通过离线检查。" * 12
    summary_result = validate_article(summary_too_long, article_path)
    if summary_result["status"] != "QA_PASSED" or any(
        "总结明显长于摘要" in warning or "总结不足摘要" in warning
        for warning in summary_result["warnings"]
    ):
        raise AssertionError("abstract/summary ratios must not control validation")

    result_share_article = copy.deepcopy(article)
    result_share_article["sections"][2]["blocks"][1]["text"] += "方法说明。" * 150
    result_share_result = validate_article(result_share_article, article_path)
    if result_share_result["status"] != "QA_PASSED" or any(
        "结果部分仅占正文" in warning or "结果篇幅少于方法" in warning
        for warning in result_share_result["warnings"]
    ):
        raise AssertionError("section shares must remain descriptive statistics only")

    evaluative_summary = copy.deepcopy(article)
    evaluative_summary["sections"][5]["blocks"][0]["text"] = "这是一项突破性研究。"
    assert_blocked(evaluative_summary, article_path, "evaluative summary")

    ranked_closing = copy.deepcopy(article)
    ranked_closing["sections"][5]["blocks"][0]["text"] = "最稳定的发现是结构检查通过。"
    assert_blocked(ranked_closing, article_path, "ranked closing")

    templated_closing = copy.deepcopy(article)
    templated_closing["sections"][5]["blocks"][0]["text"] = (
        "研究设计上的启发在于，先定位再验证。"
    )
    assert_blocked(templated_closing, article_path, "templated closing opener")

    one_paragraph_closing = copy.deepcopy(article)
    one_paragraph_closing["sections"][5]["blocks"] = [
        {"type": "paragraph", "text": "测试表明结构和排版检查均可完成。"}
    ]
    if validate_article(one_paragraph_closing, article_path)["status"] != "QA_PASSED":
        raise AssertionError("version 8 closing must not require a second method-insight paragraph")

    repeated_result_sentence = copy.deepcopy(article)
    repeated_text = repeated_result_sentence["sections"][3]["blocks"][1]["text"]
    repeated_result_sentence["sections"][4]["blocks"].append(
        {"type": "paragraph", "text": repeated_text}
    )
    assert_blocked(repeated_result_sentence, article_path, "duplicated Results sentence")

    ai_scaffolding = copy.deepcopy(article)
    ai_scaffolding["sections"][4]["blocks"][0]["text"] = (
        "总体而言，测试只覆盖结构和排版。"
    )
    ai_result = validate_article(ai_scaffolding, article_path)
    if not any("模板化的AI式表达" in warning for warning in ai_result["warnings"]):
        raise AssertionError("AI-style scaffolding should trigger a review warning")

    terminal_closure = copy.deepcopy(article)
    terminal_closure["sections"][4]["blocks"][0]["text"] = (
        "测试只覆盖结构和排版。因此，测试已经完成。"
    )
    terminal_result = validate_article(terminal_closure, article_path)
    if not any("段尾可能存在二次概括" in warning for warning in terminal_result["warnings"]):
        raise AssertionError("formulaic paragraph closure should trigger a review warning")

    misplaced_method_insights = copy.deepcopy(article)
    misplaced_method_insights["sections"].append(
        {
            "id": "method_insights",
            "heading": "方法启示",
            "blocks": [{"type": "paragraph", "text": "测试分析顺序。"}],
        }
    )
    assert_blocked(misplaced_method_insights, article_path, "misplaced method insights")

    unperformed_inventory = copy.deepcopy(article)
    unperformed_inventory["sections"][4]["blocks"][0]["text"] = (
        "研究没有纳入介数中心性，也未测量患者自身连接。"
    )
    assert_blocked(unperformed_inventory, article_path, "unperformed analysis inventory")

    negative_inventory = copy.deepcopy(article)
    negative_inventory["sections"][4]["blocks"][0]["text"] = (
        "该空间关系不能解释个体变化，也无法判断长期变化。"
    )
    negative_result = validate_article(negative_inventory, article_path)
    if not any("集中罗列否定或限制性表达" in warning for warning in negative_result["warnings"]):
        raise AssertionError("stacked negative scope statements should trigger a review warning")

    protected_revision = copy.deepcopy(article)
    protected_revision["sections"][0]["blocks"][0]["text"] += "不应改动。"
    protected_result = validate_article(
        protected_revision,
        article_path,
        baseline_article=article,
    )
    if not any("局部修改越界" in error for error in protected_result["errors"]):
        raise AssertionError("a scoped revision must block changes to the first four sections")

    ending_only_revision = copy.deepcopy(article)
    ending_only_revision["sections"][4]["blocks"][0]["text"] = (
        "测试结果只用于验证结构、来源和草稿安全规则。"
    )
    ending_result = validate_article(
        ending_only_revision,
        article_path,
        baseline_article=article,
    )
    if ending_result["status"] != "QA_PASSED":
        raise AssertionError(f"an ending-only scoped revision should pass: {ending_result}")

    leaked_secret = copy.deepcopy(article)
    leaked_secret["access_token"] = "do-not-store-this"
    assert_blocked(leaked_secret, article_path, "credential leakage")

    too_long_title = copy.deepcopy(article)
    too_long_title["title"] = "测试期刊 | " + "测" * 21
    assert_blocked(too_long_title, article_path, "title hook length")

    full_title_over_limit = copy.deepcopy(article)
    full_title_over_limit["title"] = "超长测试期刊名称" * 8 + " | 合法题眼"
    assert_blocked(full_title_over_limit, article_path, "full title length")

    missing_journal_separator = copy.deepcopy(article)
    missing_journal_separator["title"] = "没有期刊分隔符"
    assert_blocked(missing_journal_separator, article_path, "title journal separator")

    multiple_journal_separators = copy.deepcopy(article)
    multiple_journal_separators["title"] = "测试期刊 | 方法 | 结果"
    assert_blocked(multiple_journal_separators, article_path, "multiple title separators")

    padded_title = copy.deepcopy(article)
    padded_title["title"] = f" {article['title']} "
    assert_blocked(padded_title, article_path, "title outer whitespace")

    multiline_title = copy.deepcopy(article)
    multiline_title["title"] = "测试期刊 | MRI\n排版"
    assert_blocked(multiline_title, article_path, "title newline")

    missing_cover = copy.deepcopy(article)
    missing_cover["cover"] = None
    try:
        resolve_required_cover(missing_cover, article_path)
    except WeChatApiError:
        pass
    else:
        raise AssertionError("missing cover should block dry-run readiness")

    incomplete_cover = copy.deepcopy(article)
    incomplete_cover["cover"] = {"path": article["cover"]["path"]}
    assert_blocked(incomplete_cover, article_path, "incomplete cover metadata")

    cover_path = resolve_required_cover(article, article_path)
    if not cover_path.is_file():
        raise AssertionError(f"example cover was not resolved: {cover_path}")

    missing_evidence_level = copy.deepcopy(article)
    missing_evidence_level["source"].pop("evidence_level")
    assert_blocked(missing_evidence_level, article_path, "missing evidence level")

    unverified_fulltext = copy.deepcopy(article)
    unverified_fulltext["article_id"] = "real-article"
    unverified_fulltext["source"]["evidence_level"] = "FULLTEXT"
    unverified_fulltext["source"]["fulltext_verified"] = False
    unverified_fulltext["source"]["source_manifest"] = "missing-source-manifest.json"
    assert_blocked(unverified_fulltext, article_path, "unverified fulltext")

    title_schema = schema["properties"]["title"]
    title_pattern = re.compile(title_schema["pattern"])
    title_contract_cases = {
        "测试期刊 | MRI排版": True,
        "测试期刊 | " + "测" * 20: True,
        " 测试期刊 | 合法题眼": False,
        "测试期刊 | 合法题眼 ": False,
        "测试\n期刊 | 合法题眼": False,
        "测试期刊 | 合法\n题眼": False,
        "测试期刊 | 方法 | 结果": False,
        "测试期刊 | " + "测" * 21: False,
    }
    for candidate_title, expected in title_contract_cases.items():
        candidate = copy.deepcopy(article)
        candidate["title"] = candidate_title
        runtime_passed = validate_article(candidate, article_path)["status"] == "QA_PASSED"
        schema_passed = (
            title_schema["minLength"] <= len(candidate_title) <= title_schema["maxLength"]
            and title_pattern.fullmatch(candidate_title) is not None
        )
        if runtime_passed != expected or schema_passed != expected:
            raise AssertionError(
                "title validator/schema mismatch: "
                f"{candidate_title!r}, runtime={runtime_passed}, schema={schema_passed}"
            )

    cover_required = set(schema["properties"]["cover"]["required"])
    if not cover_required.issubset(article["cover"]):
        raise AssertionError("example cover does not satisfy the JSON Schema required fields")

    rendered = render_article(article)
    if any(pattern.search(rendered) for pattern in FORBIDDEN_HTML_PATTERNS):
        raise AssertionError("renderer emitted forbidden HTML")
    for heading in (section["heading"] for section in article["sections"]):
        if heading not in rendered:
            raise AssertionError(f"missing heading in HTML: {heading}")
    for system_font in (
        "Microsoft YaHei",
        "Segoe UI",
        "PingFang SC",
        "Hiragino Sans GB",
    ):
        if system_font not in rendered:
            raise AssertionError(f"renderer omitted approved system font fallback: {system_font}")
    if rendered.count(article["digest"]) != 1 or 'data-role="digest"' not in rendered:
        raise AssertionError("renderer must show the digest exactly once in the grey introduction card")

    corrective_results = copy.deepcopy(article)
    corrective_results["sections"][3]["blocks"][1]["text"] += "这一结果不能转换为个体表达变化。"
    corrective_result = validate_article(corrective_results, article_path)
    if not any("结果含审稿式限定语" in warning for warning in corrective_result["warnings"]):
        raise AssertionError("corrective editorial phrasing outside Result Interpretation should be flagged")

    fragmented_methods = copy.deepcopy(article)
    fragmented_methods["sections"][2]["blocks"] = [
        {"type": "subheading", "text": "离线流程"},
        *(
            {"type": "paragraph", "text": f"步骤{i}完成离线处理。"}
            for i in range(1, 6)
        ),
    ]
    fragmented_result = validate_article(fragmented_methods, article_path)
    if not any("段落碎片化" in warning for warning in fragmented_result["warnings"]):
        raise AssertionError("a long run of short paragraphs should trigger a non-blocking review warning")

    standalone_transition = copy.deepcopy(article)
    standalone_transition["sections"][3]["blocks"].insert(
        1, {"type": "paragraph", "text": "随后，研究进一步检查另一项分析。"}
    )
    transition_result = validate_article(standalone_transition, article_path)
    if not any("独立成段的过渡句" in warning for warning in transition_result["warnings"]):
        raise AssertionError("standalone transition paragraphs should trigger a review warning")

    exposed_review_process = copy.deepcopy(article)
    exposed_review_process["sections"][2]["blocks"][1]["text"] = "补充方法显示研究使用统一JSON。"
    assert_blocked(exposed_review_process, article_path, "exposed material review process")

    exposed_review_process_variant = copy.deepcopy(article)
    exposed_review_process_variant["sections"][2]["blocks"][1]["text"] = "补充材料指出研究使用统一JSON。"
    assert_blocked(exposed_review_process_variant, article_path, "exposed material review process variant")

    substantive_version_difference = copy.deepcopy(article)
    substantive_version_difference["sections"][4]["blocks"][0]["text"] = (
        "预印本样本量为100人，proof样本量为102人；该差异改变了最终分析样本。"
    )
    if validate_article(substantive_version_difference, article_path)["status"] != "QA_PASSED":
        raise AssertionError("a substantive version difference may be stated without review-process language")

    exposed_missing_parameter = copy.deepcopy(article)
    exposed_missing_parameter["sections"][2]["blocks"][1]["text"] = "来源材料未提供具体参数。"
    assert_blocked(exposed_missing_parameter, article_path, "exposed ordinary missing parameter")

    critical_missing_in_methods = copy.deepcopy(article)
    critical_missing_in_methods["method_map"][0]["critical_missing_details"] = [
        "缺失信息直接影响主要结论解释。"
    ]
    critical_missing_in_methods["sections"][2]["blocks"][1]["text"] = "研究未报告具体参数。"
    assert_blocked(critical_missing_in_methods, article_path, "critical missing detail outside result interpretation")

    critical_missing_in_discussion = copy.deepcopy(article)
    critical_missing_in_discussion["method_map"][0]["critical_missing_details"] = [
        "缺失信息直接影响主要结论解释。"
    ]
    critical_missing_in_discussion["sections"][4]["blocks"][0]["text"] = (
        "研究未报告直接影响主要结论解释的参数。"
    )
    if validate_article(critical_missing_in_discussion, article_path)["status"] != "QA_PASSED":
        raise AssertionError("a registered conclusion-critical omission may be stated in Result Interpretation")

    technical_report_meta = copy.deepcopy(article)
    technical_report_meta["sections"][2]["blocks"][1]["text"] = "该模块读取统一JSON并生成HTML。"
    assert_blocked(technical_report_meta, article_path, "technical report meta-language")

    paper_subject = copy.deepcopy(article)
    paper_subject["sections"][2]["blocks"][1]["text"] = "论文进行了结构校验并转换HTML。"
    paper_subject_result = validate_article(paper_subject, article_path)
    if not any("以“论文”作动作主语" in warning for warning in paper_subject_result["warnings"]):
        raise AssertionError("paper-as-subject phrasing should trigger a review warning")

    figure_article = copy.deepcopy(article)
    figure_article["figures"] = [
        {
            "asset_id": "fig-test",
            "figure_id": "Figure test",
            "path": "../assets/phase1-test-cover.png",
            "alt": "测试图片",
            "caption": "图1｜只显示简洁图注。",
            "source": "内部测试来源，不应公开显示",
            "license_note": "内部测试许可，不应公开显示",
            "mobile_display": {"strategy": "native"},
        }
    ]
    figure_article["sections"][2]["blocks"].append(
        {"type": "image", "asset_id": "fig-test"}
    )
    figure_rendered = render_article(figure_article)
    if "图1｜只显示简洁图注。" not in figure_rendered:
        raise AssertionError("renderer omitted the concise figure caption")
    if "内部测试来源" in figure_rendered or "内部测试许可" in figure_rendered or "来源：" in figure_rendered:
        raise AssertionError("renderer exposed internal figure provenance in public HTML")

    missing_mobile_strategy = copy.deepcopy(figure_article)
    missing_mobile_strategy["figures"][0].pop("mobile_display")
    assert_blocked(missing_mobile_strategy, article_path, "missing mobile figure strategy")

    print(
        json.dumps(
            {
                "status": "SELF_TEST_PASSED",
                "tests": 83,
                "network_calls": 0,
                "live_draft_writes": 0,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
