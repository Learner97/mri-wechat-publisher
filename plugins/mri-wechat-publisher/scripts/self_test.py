#!/usr/bin/env python3
"""Run deterministic phase-one tests without network or live account writes."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

from render_wechat_html import FORBIDDEN_HTML_PATTERNS, render_article
from validate_article import load_article, validate_article


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

    missing_journal_separator = copy.deepcopy(article)
    missing_journal_separator["title"] = "没有期刊分隔符"
    assert_blocked(missing_journal_separator, article_path, "title journal separator")

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
                "tests": 7,
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
