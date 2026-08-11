#!/usr/bin/env python3
"""Run deterministic phase-one tests without network or live account writes."""

from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

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

    wrong_mode = copy.deepcopy(article)
    wrong_mode["publication_mode"] = "publish"
    assert_blocked(wrong_mode, article_path, "wrong publication mode")

    missing_section = copy.deepcopy(article)
    missing_section["sections"].pop()
    assert_blocked(missing_section, article_path, "missing fixed section")

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

    print(
        json.dumps(
            {
                "status": "SELF_TEST_PASSED",
                "tests": 18,
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
