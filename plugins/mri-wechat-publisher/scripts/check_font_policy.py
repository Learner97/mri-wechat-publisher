#!/usr/bin/env python3
"""Validate bundled font provenance and plugin-controlled typography."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


SYSTEM_FONT_NAMES = (
    "Microsoft YaHei",
    "Segoe UI",
    "PingFang SC",
    "Hiragino Sans GB",
)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    font_dir = root / "assets" / "fonts"
    manifest_path = font_dir / "font-manifest.json"
    errors: list[str] = []

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "FONT_POLICY_BLOCKED", "errors": [str(exc)]}, indent=2))
        return 1

    font_path = font_dir / str(manifest.get("file", ""))
    license_path = font_dir / str(manifest.get("license_file", ""))
    if not font_path.is_file():
        errors.append(f"Bundled font is missing: {font_path}")
    else:
        digest = hashlib.sha256(font_path.read_bytes()).hexdigest().upper()
        if digest != str(manifest.get("sha256", "")).upper():
            errors.append("Bundled font SHA-256 does not match font-manifest.json")
    if not license_path.is_file() or "SIL OPEN FONT LICENSE Version 1.1" not in license_path.read_text(
        encoding="utf-8"
    ):
        errors.append("Bundled font license is missing or invalid")
    if manifest.get("license") != "SIL Open Font License 1.1":
        errors.append("Font manifest must declare SIL Open Font License 1.1")

    renderer_path = root / "scripts" / "render_wechat_html.py"
    cover_generators = [
        root / "scripts" / "generate_test_cover.ps1",
        root / "scripts" / "generate_phase2_cover.ps1",
    ]
    renderer_text = renderer_path.read_text(encoding="utf-8")
    for name in SYSTEM_FONT_NAMES:
        if name not in renderer_text:
            errors.append(f"Renderer is missing approved device font fallback: {name}")
    cover_text = "\n".join(path.read_text(encoding="utf-8") for path in cover_generators)
    for name in SYSTEM_FONT_NAMES:
        if name in cover_text:
            errors.append(f"Plugin-generated covers must not depend on a system font: {name}")
    if "NotoSansSC-VF.ttf" not in cover_text:
        errors.append("Plugin-generated covers must use the bundled OFL-licensed Noto Sans SC")
    if "@font-face" in renderer_text or "fonts.googleapis.com" in renderer_text:
        errors.append("Renderer must not embed or fetch external fonts")
    bundled_font_files = sorted(
        path.name for path in font_dir.iterdir() if path.suffix.lower() in {".ttf", ".otf", ".woff", ".woff2"}
    )
    if bundled_font_files != [str(manifest.get("file", ""))]:
        errors.append(
            "assets/fonts may contain only the font declared in font-manifest.json: "
            + ", ".join(bundled_font_files)
        )

    result = {
        "status": "FONT_POLICY_PASSED" if not errors else "FONT_POLICY_BLOCKED",
        "errors": errors,
        "font": str(font_path),
        "license": str(license_path),
        "html_font_policy": "device_system_fonts_referenced_only",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
