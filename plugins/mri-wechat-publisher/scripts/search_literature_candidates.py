#!/usr/bin/env python3
"""Search and rank recent MRI/cognitive-neuroscience papers.

Sources are read-only public APIs: PubMed E-utilities and OpenAlex. Results are
deduplicated by DOI and then normalized title. The output never contains API
credentials.
"""

from __future__ import annotations

import argparse
import http.client
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime
from pathlib import Path
from typing import Any


USER_AGENT = "mri-wechat-literature-pilot/1.0 (contact: nature-skills@users.noreply.github.com)"
PUBMED_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
OPENALEX_BASE = "https://api.openalex.org/works"

JOURNAL_SCORES = {
    "nature": 20,
    "science": 20,
    "cell": 20,
    "nature neuroscience": 20,
    "nature medicine": 20,
    "nature human behaviour": 20,
    "neuron": 20,
    "nature methods": 20,
    "the lancet neurology": 20,
    "lancet neurology": 20,
    "jama neurology": 20,
    "radiology": 20,
    "brain": 20,
    "nature communications": 17,
    "science advances": 17,
    "proceedings of the national academy of sciences": 17,
    "proceedings of the national academy of sciences of the united states of america": 17,
    "biological psychiatry": 17,
    "molecular psychiatry": 17,
    "alzheimer's & dementia": 17,
    "alzheimers & dementia": 17,
    "annals of neurology": 17,
    "neurology": 17,
    "neuropsychopharmacology": 17,
    "cerebral cortex": 17,
    "npj digital medicine": 17,
    "neuroimage": 14,
    "imaging neuroscience": 14,
    "human brain mapping": 14,
    "network neuroscience": 14,
    "communications biology": 14,
}

CORE_TERMS = ("fmri", "functional magnetic resonance", "magnetic resonance imaging", "neuroimaging")
COGNITION_TERMS = (
    "cognit", "memory", "language", "speech", "attention", "emotion", "decision",
    "learning", "conscious", "naturalistic", "social", "behavior", "behaviour",
)
DISEASE_TERMS = (
    "alzheimer", "parkinson", "depression", "schizophrenia", "autism", "epilep",
    "multiple sclerosis", "stroke", "tumor", "dement", "psychiatr", "neurolog",
)
METHOD_TERMS = (
    "benchmark", "foundation model", "multimodal", "deep learning", "machine learning",
    "decod", "connectom", "functional connectivity", "representation", "predict",
    "dynamic", "network", "causal", "individualized", "individualised", "normative",
    "naturalistic", "transformer", "generative", "reconstruct",
)
EXCLUDE_TITLE_TERMS = (
    "systematic review", "scoping review", "narrative review", "meta-analysis",
    "protocol", "editorial", "commentary", "correction", "erratum",
)


class SearchError(RuntimeError):
    pass


def norm_text(value: str) -> str:
    value = value.lower().replace("–", "-").replace("—", "-")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def norm_doi(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", value)
    return value.rstrip(" .,:;)]")


def request_bytes(url: str, *, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers={"Accept": "application/json, application/xml", "User-Agent": USER_AGENT})
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return response.read()
        except (
            urllib.error.HTTPError,
            urllib.error.URLError,
            http.client.IncompleteRead,
            TimeoutError,
            ConnectionResetError,
            OSError,
        ) as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(2 ** attempt)
    raise SearchError(
        f"GET failed after 3 attempts for {urllib.parse.urlsplit(url).netloc}: {last_error}"
    )


def pubmed_search(date_from: str, retmax: int = 300) -> list[str]:
    journals = " OR ".join(f'"{name}"[Journal]' for name in JOURNAL_SCORES)
    query = (
        '("functional magnetic resonance imaging"[Title/Abstract] OR fMRI[Title/Abstract] '
        'OR "magnetic resonance imaging"[Title/Abstract] OR neuroimaging[Title/Abstract]) '
        'AND (brain[Title/Abstract] OR cognit*[Title/Abstract] OR neurolog*[Title/Abstract] '
        'OR psychiatr*[Title/Abstract]) '
        f'AND ({journals}) '
        f'AND ("{date_from.replace("-", "/")}"[Date - Publication] : "3000"[Date - Publication])'
    )
    params = {
        "db": "pubmed",
        "term": query,
        "retmode": "json",
        "retmax": retmax,
        "sort": "pub date",
        "tool": "mri_wechat_pilot",
        "email": "nature-skills@users.noreply.github.com",
    }
    api_key = os.environ.get("NCBI_API_KEY", "").strip()
    if api_key:
        params["api_key"] = api_key
    url = f"{PUBMED_BASE}/esearch.fcgi?{urllib.parse.urlencode(params)}"
    data = json.loads(request_bytes(url).decode("utf-8"))
    return list(data.get("esearchresult", {}).get("idlist", []))


def element_text(node: ET.Element | None) -> str:
    return "" if node is None else "".join(node.itertext()).strip()


def parse_pub_date(article: ET.Element) -> str:
    article_date = article.find(".//ArticleDate")
    if article_date is not None:
        parts = [element_text(article_date.find(x)) for x in ("Year", "Month", "Day")]
        if all(parts):
            return f"{parts[0]}-{parts[1].zfill(2)}-{parts[2].zfill(2)}"
    pub_date = article.find(".//JournalIssue/PubDate")
    if pub_date is None:
        return ""
    year = element_text(pub_date.find("Year"))
    month = element_text(pub_date.find("Month"))
    day = element_text(pub_date.find("Day")) or "01"
    if not year:
        match = re.search(r"(20\d{2})", element_text(pub_date.find("MedlineDate")))
        return f"{match.group(1)}-01-01" if match else ""
    month_map = {name: i for i, name in enumerate(
        ("", "jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
    )}
    month_num = str(month_map.get(month[:3].lower(), int(month) if month.isdigit() else 1)).zfill(2)
    return f"{year}-{month_num}-{day.zfill(2)}"


def pubmed_fetch(pmids: list[str]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    batch_size = 50
    for offset in range(0, len(pmids), batch_size):
        batch = pmids[offset: offset + batch_size]
        params = {
            "db": "pubmed",
            "id": ",".join(batch),
            "retmode": "xml",
            "tool": "mri_wechat_pilot",
            "email": "nature-skills@users.noreply.github.com",
        }
        api_key = os.environ.get("NCBI_API_KEY", "").strip()
        if api_key:
            params["api_key"] = api_key
        url = f"{PUBMED_BASE}/efetch.fcgi?{urllib.parse.urlencode(params)}"
        root = ET.fromstring(request_bytes(url))
        for item in root.findall(".//PubmedArticle"):
            citation = item.find("MedlineCitation")
            article = item.find(".//Article")
            if citation is None or article is None:
                continue
            title = element_text(article.find("ArticleTitle"))
            abstract_parts = []
            for node in article.findall(".//Abstract/AbstractText"):
                text_value = element_text(node)
                label = node.attrib.get("Label", "").strip()
                abstract_parts.append(f"{label}: {text_value}" if label else text_value)
            doi = ""
            pmcid = ""
            for node in item.findall("./PubmedData/ArticleIdList/ArticleId"):
                kind = node.attrib.get("IdType", "")
                if kind == "doi":
                    doi = norm_doi(element_text(node))
                elif kind == "pmc":
                    pmcid = element_text(node)
            authors = []
            for author in article.findall("./AuthorList/Author")[:8]:
                collective = element_text(author.find("CollectiveName"))
                if collective:
                    authors.append(collective)
                    continue
                name = " ".join(filter(None, [element_text(author.find("ForeName")), element_text(author.find("LastName"))]))
                if name:
                    authors.append(name)
            records.append({
                "title": title,
                "doi": doi,
                "pmid": element_text(citation.find("PMID")),
                "pmcid": pmcid,
                "authors": authors,
                "journal": element_text(article.find(".//Journal/Title")),
                "publication_date": parse_pub_date(article),
                "abstract": " ".join(abstract_parts),
                "cited_by_count": 0,
                "sources": ["PubMed"],
                "publisher_url": f"https://pubmed.ncbi.nlm.nih.gov/{element_text(citation.find('PMID'))}/",
            })
        if offset + batch_size < len(pmids):
            time.sleep(0.4)
    return records


def reconstruct_abstract(index: dict[str, list[int]] | None) -> str:
    if not index:
        return ""
    positions = [(pos, word) for word, values in index.items() for pos in values]
    positions.sort()
    return " ".join(word for _, word in positions)


def openalex_search(date_from: str) -> list[dict[str, Any]]:
    queries = (
        "functional MRI cognitive neuroscience human",
        "MRI neuroimaging neurological psychiatric disease biomarker",
        "fMRI brain decoding naturalistic cognition",
        "functional connectivity neuroimaging method MRI",
    )
    records: list[dict[str, Any]] = []
    for query in queries:
        params = {
            "search": query,
            "filter": f"from_publication_date:{date_from},type:article",
            "per-page": 100,
            "mailto": "nature-skills@users.noreply.github.com",
        }
        url = f"{OPENALEX_BASE}?{urllib.parse.urlencode(params)}"
        data = json.loads(request_bytes(url).decode("utf-8"))
        for work in data.get("results", []):
            location = work.get("primary_location") or {}
            source = location.get("source") or {}
            journal = source.get("display_name", "")
            if norm_text(journal) not in JOURNAL_SCORES:
                continue
            doi = norm_doi(work.get("doi") or "")
            records.append({
                "title": work.get("title", ""),
                "doi": doi,
                "pmid": "",
                "pmcid": "",
                "authors": [
                    (authorship.get("author") or {}).get("display_name", "")
                    for authorship in (work.get("authorships") or [])[:8]
                ],
                "journal": journal,
                "publication_date": work.get("publication_date", ""),
                "abstract": reconstruct_abstract(work.get("abstract_inverted_index")),
                "cited_by_count": work.get("cited_by_count", 0) or 0,
                "sources": ["OpenAlex"],
                "publisher_url": work.get("doi") or work.get("id", ""),
            })
        time.sleep(0.25)
    return records


def merge_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for record in records:
        doi = norm_doi(record.get("doi", ""))
        title_key = norm_text(record.get("title", ""))
        key = f"doi:{doi}" if doi else f"title:{title_key}"
        if key not in merged:
            merged[key] = record
            continue
        target = merged[key]
        for field in ("doi", "pmid", "pmcid", "abstract", "publisher_url", "publication_date"):
            if not target.get(field) and record.get(field):
                target[field] = record[field]
        if len(record.get("authors", [])) > len(target.get("authors", [])):
            target["authors"] = record["authors"]
        target["cited_by_count"] = max(target.get("cited_by_count", 0), record.get("cited_by_count", 0))
        target["sources"] = sorted(set(target.get("sources", [])) | set(record.get("sources", [])))
    return list(merged.values())


def recency_score(publication_date: str, today: date) -> int:
    try:
        published = datetime.strptime(publication_date[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return 4
    age = max(0, (today - published).days)
    if age <= 90:
        return 15
    if age <= 180:
        return 13
    if age <= 365:
        return 10
    if age <= 730:
        return 7
    return 3


def score_record(record: dict[str, Any], today: date) -> dict[str, Any]:
    title = record.get("title", "")
    abstract = record.get("abstract", "")
    text = f"{title} {abstract}".lower()
    title_lower = title.lower()
    if any(term in title_lower for term in EXCLUDE_TITLE_TERMS):
        record["excluded_reason"] = "review_or_non_primary"
    relevance = 0
    relevance += 15 if any(term in text for term in CORE_TERMS) else 0
    relevance += min(8, 2 * sum(term in text for term in COGNITION_TERMS))
    relevance += min(6, 2 * sum(term in text for term in DISEASE_TERMS))
    relevance += min(6, 2 * sum(term in text for term in METHOD_TERMS))
    journal_score = JOURNAL_SCORES.get(norm_text(record.get("journal", "")), 0)
    method_score = min(20, 4 * sum(term in text for term in METHOD_TERMS))
    recent = recency_score(record.get("publication_date", ""), today)
    access = min(10, (4 if abstract else 0) + (3 if record.get("doi") else 0) + (2 if record.get("pmcid") else 0) + (1 if record.get("pmid") else 0))
    categories = []
    if any(term in text for term in COGNITION_TERMS):
        categories.append("cognition")
    if any(term in text for term in DISEASE_TERMS):
        categories.append("disease")
    if any(term in text for term in METHOD_TERMS):
        categories.append("method")
    record["categories"] = categories or ["general_mri"]
    record["score_components"] = {
        "relevance": relevance,
        "journal": journal_score,
        "method_innovation": method_score,
        "recency": recent,
        "verifiability": access,
    }
    record["total_score"] = relevance + journal_score + method_score + recent + access
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date-from", default="2024-08-04")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()

    try:
        pmids = pubmed_search(args.date_from)
        pubmed_records = pubmed_fetch(pmids)
        openalex_records = openalex_search(args.date_from)
        records = merge_records(pubmed_records + openalex_records)
        today = date.today()
        scored = [score_record(record, today) for record in records]
        scored = [
            record for record in scored
            if record["score_components"]["journal"] > 0
            and not record.get("excluded_reason")
            and record.get("publication_date", "") >= args.date_from
        ]
        scored.sort(key=lambda item: (item["total_score"], item.get("publication_date", ""), item.get("cited_by_count", 0)), reverse=True)
        payload = {
            "status": "SEARCH_COMPLETED",
            "date_from": args.date_from,
            "generated_at": datetime.now().astimezone().isoformat(),
            "source_counts": {"pubmed": len(pubmed_records), "openalex": len(openalex_records)},
            "deduplicated_count": len(records),
            "eligible_count": len(scored),
            "records": scored[: args.limit],
        }
        output = args.output.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({
            "status": payload["status"],
            "output": str(output),
            "source_counts": payload["source_counts"],
            "deduplicated_count": payload["deduplicated_count"],
            "eligible_count": payload["eligible_count"],
            "returned_count": len(payload["records"]),
        }, ensure_ascii=False, indent=2))
        return 0
    except (SearchError, ET.ParseError, json.JSONDecodeError, OSError, ValueError) as exc:
        print(json.dumps({"status": "SEARCH_BLOCKED", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
