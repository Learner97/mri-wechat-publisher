#!/usr/bin/env python3
"""Metadata-only full-text and supplement availability checks.

The checker queries bibliographic metadata only. It never downloads or stores a
PDF, full-text HTML/XML body, or supplement. Scientific ranking must remain
independent from the access result.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable


USER_AGENT = "mri-wechat-source-readiness/1.0"
EUROPE_PMC_SEARCH = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
OPENALEX_WORKS = "https://api.openalex.org/works"

ACCESS_STATUSES = {
    "PUBLIC_FULLTEXT_CONFIRMED",
    "PUBLIC_HTML_CONFIRMED",
    "USER_UPLOAD_REQUIRED",
    "ACCESS_UNKNOWN",
}
SUPPLEMENT_STATUSES = {
    "PUBLIC_AVAILABLE",
    "DETECTED_RESTRICTED",
    "NOT_FOUND",
    "UNKNOWN",
}


def normalize_doi(value: Any) -> str:
    text = str(value or "").strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if text.startswith(prefix):
            text = text[len(prefix) :]
    return text.rstrip(" .,:;)]")


def truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def request_json(url: str, timeout: int = 12) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _first_result(payload: dict[str, Any]) -> dict[str, Any]:
    result_list = payload.get("resultList") or {}
    results = result_list.get("result") or []
    return results[0] if results and isinstance(results[0], dict) else {}


def _fulltext_urls(result: dict[str, Any]) -> list[dict[str, Any]]:
    container = result.get("fullTextUrlList") or {}
    values = container.get("fullTextUrl") or []
    return [value for value in values if isinstance(value, dict)]


def _openalex_result(payload: dict[str, Any]) -> dict[str, Any]:
    results = payload.get("results") or []
    return results[0] if results and isinstance(results[0], dict) else {}


def _openalex_access(candidate: dict[str, Any], work: dict[str, Any]) -> tuple[bool, str, str, str]:
    open_access = work.get("open_access") or candidate.get("open_access") or {}
    best = work.get("best_oa_location") or candidate.get("best_oa_location") or {}
    is_oa = bool(open_access.get("is_oa") or best.get("is_oa"))
    oa_status = str(open_access.get("oa_status") or "").lower()
    pdf_url = str(best.get("pdf_url") or "").strip()
    landing_url = str(
        best.get("landing_page_url")
        or open_access.get("oa_url")
        or ""
    ).strip()
    return is_oa, oa_status, pdf_url, landing_url


def probe_candidate(
    candidate: dict[str, Any],
    *,
    fetch_json: Callable[[str, int], dict[str, Any]] = request_json,
    timeout: int = 12,
    checked_at: str | None = None,
) -> dict[str, Any]:
    """Return an access assessment without fetching any full-text content."""

    doi = normalize_doi(candidate.get("doi"))
    pmid = str(candidate.get("pmid") or "").strip()
    pmcid = str(candidate.get("pmcid") or "").strip()
    timestamp = checked_at or datetime.now().astimezone().isoformat(timespec="seconds")
    evidence: list[dict[str, Any]] = []
    errors: list[str] = []
    public_pdf_or_xml = False
    public_html = False
    explicit_closed = False
    public_url = ""
    supplement_status = "UNKNOWN"
    supplement_url = ""

    if pmcid:
        public_pdf_or_xml = True
        public_url = f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/"
        evidence.append(
            {
                "source": "PubMed",
                "signal": "pmcid_present",
                "value": pmcid,
            }
        )

    embedded_is_oa, embedded_oa_status, embedded_pdf, embedded_landing = _openalex_access(
        candidate, {}
    )
    if embedded_is_oa and embedded_pdf:
        public_pdf_or_xml = True
        public_url = public_url or embedded_pdf
        evidence.append(
            {"source": "OpenAlex", "signal": "embedded_public_pdf", "value": embedded_pdf}
        )
    elif embedded_is_oa and embedded_landing:
        public_html = True
        public_url = public_url or embedded_landing
        evidence.append(
            {
                "source": "OpenAlex",
                "signal": "embedded_oa_landing_page",
                "value": embedded_landing,
            }
        )
    if embedded_oa_status == "closed":
        explicit_closed = True

    europe_pmc_result: dict[str, Any] = {}
    if pmid or doi:
        query = f"EXT_ID:{pmid} AND SRC:MED" if pmid else f'DOI:"{doi}"'
        url = (
            f"{EUROPE_PMC_SEARCH}?"
            + urllib.parse.urlencode(
                {"query": query, "format": "json", "resultType": "core", "pageSize": 1}
            )
        )
        try:
            europe_pmc_result = _first_result(fetch_json(url, timeout))
            if europe_pmc_result:
                evidence.append(
                    {
                        "source": "Europe PMC",
                        "signal": "metadata_record",
                        "value": str(europe_pmc_result.get("id") or pmid or doi),
                    }
                )
                epmc_pmcid = str(europe_pmc_result.get("pmcid") or "").strip()
                urls = _fulltext_urls(europe_pmc_result)
                for item in urls:
                    value = str(item.get("url") or "").strip()
                    style = str(item.get("documentStyle") or item.get("availability") or "").lower()
                    if not value:
                        continue
                    if any(token in style or token in value.lower() for token in ("pdf", "xml")):
                        public_pdf_or_xml = True
                        public_url = public_url or value
                    elif truthy(europe_pmc_result.get("isOpenAccess")):
                        public_html = True
                        public_url = public_url or value
                if epmc_pmcid and (
                    truthy(europe_pmc_result.get("isOpenAccess"))
                    or truthy(europe_pmc_result.get("inPMC"))
                ):
                    public_pdf_or_xml = True
                    public_url = public_url or f"https://pmc.ncbi.nlm.nih.gov/articles/{epmc_pmcid}/"
                if str(europe_pmc_result.get("isOpenAccess") or "").upper() == "N":
                    explicit_closed = True
                if truthy(europe_pmc_result.get("hasSuppl")):
                    supplement_status = (
                        "PUBLIC_AVAILABLE"
                        if public_pdf_or_xml or public_html
                        else "DETECTED_RESTRICTED"
                    )
                    supplement_url = public_url
                elif "hasSuppl" in europe_pmc_result:
                    supplement_status = "NOT_FOUND"
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"Europe PMC metadata check failed: {exc}")

    if doi and not public_pdf_or_xml:
        url = (
            f"{OPENALEX_WORKS}?"
            + urllib.parse.urlencode(
                {
                    "filter": f"doi:https://doi.org/{doi}",
                    "per-page": 1,
                    "select": "id,doi,open_access,best_oa_location",
                }
            )
        )
        try:
            work = _openalex_result(fetch_json(url, timeout))
            if work:
                is_oa, oa_status, pdf_url, landing_url = _openalex_access(candidate, work)
                evidence.append(
                    {
                        "source": "OpenAlex",
                        "signal": "metadata_record",
                        "value": str(work.get("id") or doi),
                    }
                )
                if is_oa and pdf_url:
                    public_pdf_or_xml = True
                    public_url = public_url or pdf_url
                elif is_oa and landing_url:
                    public_html = True
                    public_url = public_url or landing_url
                if oa_status == "closed":
                    explicit_closed = True
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"OpenAlex metadata check failed: {exc}")

    if public_pdf_or_xml:
        status = "PUBLIC_FULLTEXT_CONFIRMED"
        confidence = "high"
        user_action = "可在成稿任务中获取并核验公开全文"
    elif public_html:
        status = "PUBLIC_HTML_CONFIRMED"
        confidence = "medium"
        user_action = "可在成稿任务中获取并核验公开全文HTML"
    elif explicit_closed:
        status = "USER_UPLOAD_REQUIRED"
        confidence = "medium"
        user_action = "选择后请上传合法取得的全文PDF；如有补充材料请一并上传"
    else:
        status = "ACCESS_UNKNOWN"
        confidence = "low"
        user_action = "选择后需重新核验；若仍无法确认，请上传全文PDF"

    return {
        "status": status,
        "checked_at": timestamp,
        "check_mode": "metadata_only",
        "downloaded_content": False,
        "confidence": confidence,
        "public_fulltext_url": public_url or None,
        "evidence": evidence,
        "errors": errors,
        "user_action": user_action,
        "supplement": {
            "status": supplement_status,
            "url": supplement_url or None,
        },
    }


def enrich_payload(
    payload: dict[str, Any],
    *,
    limit: int | None = None,
    fetch_json: Callable[[str, int], dict[str, Any]] = request_json,
    timeout: int = 12,
) -> dict[str, Any]:
    enriched = copy.deepcopy(payload)
    key = "candidates" if isinstance(enriched.get("candidates"), list) else "records"
    records = enriched.get(key)
    if not isinstance(records, list):
        raise ValueError("输入JSON必须包含 candidates 或 records 数组。")
    count = len(records) if limit is None or limit <= 0 else min(limit, len(records))
    for index, candidate in enumerate(records[:count]):
        if not isinstance(candidate, dict):
            raise ValueError(f"{key}[{index}] 必须是对象。")
        candidate["fulltext_access"] = probe_candidate(
            candidate, fetch_json=fetch_json, timeout=timeout
        )
    enriched["fulltext_check_policy"] = {
        "mode": "metadata_only",
        "content_downloaded": False,
        "scientific_score_independent": True,
        "checked_record_count": count,
        "allowed_statuses": sorted(ACCESS_STATUSES),
    }
    return enriched


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=0, help="0 checks every record")
    parser.add_argument("--timeout", type=int, default=12)
    args = parser.parse_args()
    try:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("输入JSON根节点必须是对象。")
        enriched = enrich_payload(payload, limit=args.limit, timeout=args.timeout)
        atomic_write_json(args.output.resolve(), enriched)
        records = enriched.get("candidates") or enriched.get("records") or []
        print(
            json.dumps(
                {
                    "status": "ACCESS_CHECK_COMPLETED",
                    "output": str(args.output.resolve()),
                    "checked_count": enriched["fulltext_check_policy"]["checked_record_count"],
                    "access_statuses": [
                        (record.get("fulltext_access") or {}).get("status")
                        for record in records
                        if isinstance(record, dict) and record.get("fulltext_access")
                    ],
                    "content_downloaded": False,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(
            json.dumps({"status": "ACCESS_CHECK_BLOCKED", "error": str(exc)}, ensure_ascii=False, indent=2),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
