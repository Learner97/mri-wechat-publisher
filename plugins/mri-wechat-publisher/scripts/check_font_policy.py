#!/usr/bin/env python3
"""Check device-only HTML typography without requiring bundled font files."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


SYSTEM_FONT_NAMES = (
    "-apple-system",
    "BlinkMacSystemFont",
    "Microsoft YaHei",
    "Segoe UI",
    "PingFang SC",
    "Hiragino Sans GB",
    "sans-serif",
)


def validate_font_policy(renderer_text: str) -> list[str]:
    errors: list[str] = []
    for name in SYSTEM_FONT_NAMES:
        if name not in renderer_text:
            errors.append(f"Renderer is missing approved device font fallback: {name}")
    if re.search(
        r"@font-face\b|@import\b|fonts\.(?:googleapis|gstatic)\.com"
        r"|url\s*\([^)]*\.(?:woff2?|[ot]tf|eot)\b"
        r"|data:(?:font/|application/(?:x-font|font))",
        renderer_text, re.IGNORECASE,
    ):
        errors.append("Renderer must not embed or fetch external fonts")
    return errors


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    renderer_path = root / "scripts" / "render_wechat_html.py"
    errors = validate_font_policy(renderer_path.read_text(encoding="utf-8"))

    result = {
        "status": "FONT_POLICY_PASSED" if not errors else "FONT_POLICY_BLOCKED",
        "errors": errors,
        "html_font_policy": "device_system_fonts_referenced_only",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
