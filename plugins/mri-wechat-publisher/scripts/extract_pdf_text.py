#!/usr/bin/env python3
"""Extract page-delimited text from a PDF for evidence review."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pdfplumber


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    pdf_path = args.pdf.resolve()
    output_path = args.output.resolve()
    pages = []
    with pdfplumber.open(pdf_path) as document:
        for index, page in enumerate(document.pages, start=1):
            content = page.extract_text(x_tolerance=2, y_tolerance=3) or ""
            pages.append(f"\n===== PAGE {index} =====\n{content.strip()}\n")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("".join(pages), encoding="utf-8")
    print(json.dumps({
        "status": "PDF_TEXT_EXTRACTED",
        "pages": len(pages),
        "characters": sum(len(page) for page in pages),
        "output": str(output_path),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

