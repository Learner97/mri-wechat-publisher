#!/usr/bin/env python3
"""Build a hashed source manifest after an agent verifies paper identity."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_record(path: Path, identity: dict | None = None) -> dict:
    resolved = path.resolve()
    if not resolved.is_file() or resolved.is_symlink():
        raise ValueError(f"文件不存在或不允许使用符号链接：{resolved}")
    if resolved.stat().st_size <= 0:
        raise ValueError(f"文件为空：{resolved}")
    if resolved.suffix.lower() == ".pdf":
        with resolved.open("rb") as handle:
            if handle.read(5) != b"%PDF-":
                raise ValueError(f"PDF签名无效：{resolved}")
    record = {
        "path": str(resolved),
        "size_bytes": resolved.stat().st_size,
        "sha256": sha256(resolved),
    }
    if identity is not None:
        record["identity"] = identity
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cycle-id", required=True)
    parser.add_argument("--source-kind", choices=["USER_UPLOAD", "PUBLIC_FETCH"], required=True)
    parser.add_argument("--main", type=Path, required=True)
    parser.add_argument("--supplement", type=Path, action="append", default=[])
    parser.add_argument("--title", required=True)
    parser.add_argument("--doi", default="")
    parser.add_argument(
        "--matched-by",
        action="append",
        choices=["doi", "title", "pmid", "publisher_link", "filename"],
        required=True,
    )
    parser.add_argument("--verification-evidence", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        identity = {
            "status": "VERIFIED",
            "title": args.title,
            "doi": args.doi,
            "matched_by": args.matched_by,
            "verification_evidence": args.verification_evidence,
        }
        payload = {
            "cycle_id": args.cycle_id,
            "source_kind": args.source_kind,
            "identity": identity,
            "main_file": file_record(args.main),
            "supplements": [
                file_record(path, identity=identity) for path in args.supplement
            ],
        }
        output = args.output.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(output.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(output)
        print(
            json.dumps(
                {
                    "status": "SOURCE_MANIFEST_CREATED",
                    "output": str(output),
                    "main_file": payload["main_file"]["path"],
                    "supplement_count": len(payload["supplements"]),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    except (OSError, ValueError) as exc:
        print(
            json.dumps({"status": "SOURCE_MANIFEST_BLOCKED", "error": str(exc)}, ensure_ascii=False, indent=2),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
