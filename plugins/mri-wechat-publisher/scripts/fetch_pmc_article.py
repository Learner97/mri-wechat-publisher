#!/usr/bin/env python3
"""Fetch an open-access PMC package and extract structured article evidence."""

from __future__ import annotations

import argparse
import http.client
import json
import os
import tarfile
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


XLINK = "{http://www.w3.org/1999/xlink}href"
USER_AGENT = "mri-wechat-literature-pilot/1.0 (contact: nature-skills@users.noreply.github.com)"


class FetchError(RuntimeError):
    pass


def fetch(url: str, timeout: int = 90) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
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
    raise FetchError(f"GET failed after 3 attempts for {url}: {last_error}")


def text(node: ET.Element | None) -> str:
    if node is None:
        return ""
    return " ".join("".join(node.itertext()).split())


def find_article_id(root: ET.Element, kind: str) -> str:
    for node in root.findall(".//article-meta/article-id"):
        if node.attrib.get("pub-id-type") == kind:
            return text(node)
    return ""


def safe_extract(archive: tarfile.TarFile, destination: Path) -> None:
    destination = destination.resolve()
    for member in archive.getmembers():
        target = (destination / member.name).resolve()
        if os.path.commonpath([str(destination), str(target)]) != str(destination):
            raise FetchError(f"Unsafe archive member: {member.name}")
    archive.extractall(destination, filter="data")


def collect_sections(root: ET.Element) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    for section in root.findall("./body/sec"):
        sections.append(collect_section(section))
    return sections


def collect_section(section: ET.Element) -> dict[str, Any]:
    paragraphs = [text(node) for node in section.findall("./p") if text(node)]
    return {
        "id": section.attrib.get("id", ""),
        "title": text(section.find("title")),
        "paragraphs": paragraphs,
        "subsections": [collect_section(node) for node in section.findall("./sec")],
    }


def locate_file(source_dir: Path, href: str) -> str:
    name = Path(href).name
    candidates = list(source_dir.rglob(name))
    if not candidates and Path(name).suffix == "":
        candidates = list(source_dir.rglob(name + ".*"))
    return str(candidates[0].resolve()) if candidates else ""


def collect_figures(root: ET.Element, source_dir: Path) -> list[dict[str, Any]]:
    figures: list[dict[str, Any]] = []
    for figure in root.findall(".//fig"):
        hrefs = []
        for graphic in figure.findall(".//graphic"):
            href = graphic.attrib.get(XLINK, "")
            if href:
                hrefs.append({"href": href, "local_path": locate_file(source_dir, href)})
        figures.append({
            "id": figure.attrib.get("id", ""),
            "label": text(figure.find("label")),
            "caption": text(figure.find("caption")),
            "graphics": hrefs,
        })
    return figures


def collect_supplements(root: ET.Element, source_dir: Path) -> list[dict[str, str]]:
    supplements = []
    for node in root.findall(".//supplementary-material"):
        href = ""
        for child in node.iter():
            if child.attrib.get(XLINK):
                href = child.attrib[XLINK]
                break
        supplements.append({
            "id": node.attrib.get("id", ""),
            "label": text(node.find("label")),
            "caption": text(node.find("caption")),
            "href": href,
            "local_path": locate_file(source_dir, href) if href else "",
        })
    return supplements


def fetch_xml_assets(nxml_path: Path, source_dir: Path, pmcid: str) -> dict[str, int]:
    root = ET.parse(nxml_path).getroot()
    hrefs: set[str] = set()
    for node in root.iter():
        href = node.attrib.get(XLINK, "")
        if href and not href.startswith(("http://", "https://", "#")):
            hrefs.add(href)
    downloaded = 0
    failed = 0
    for href in sorted(hrefs):
        filename = Path(href).name
        if not filename:
            continue
        destination = source_dir / filename
        if destination.is_file():
            downloaded += 1
            continue
        quoted = urllib.parse.quote(filename)
        urls = (
            f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/bin/{quoted}",
            f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/bin/{quoted}",
        )
        for url in urls:
            try:
                destination.write_bytes(fetch(url, timeout=90))
                downloaded += 1
                break
            except FetchError:
                continue
        else:
            failed += 1
    return {"downloaded": downloaded, "failed": failed}


def parse_article(nxml_path: Path, source_dir: Path) -> dict[str, Any]:
    root = ET.parse(nxml_path).getroot()
    license_node = root.find(".//permissions/license")
    article_meta = root.find(".//article-meta")
    authors = []
    if article_meta is not None:
        for contrib in article_meta.findall(".//contrib-group/contrib[@contrib-type='author']"):
            name = contrib.find("name")
            collective = text(contrib.find("collab"))
            if collective:
                authors.append(collective)
            elif name is not None:
                full = " ".join(filter(None, [text(name.find("given-names")), text(name.find("surname"))]))
                if full:
                    authors.append(full)
    abstract_parts = [text(node) for node in root.findall(".//article-meta/abstract") if text(node)]
    return {
        "title": text(root.find(".//article-meta/title-group/article-title")),
        "journal": text(root.find(".//journal-meta/journal-title-group/journal-title")),
        "doi": find_article_id(root, "doi"),
        "pmid": find_article_id(root, "pmid"),
        "pmcid": find_article_id(root, "pmc"),
        "authors": authors,
        "abstract": " ".join(abstract_parts),
        "license": {
            "href": license_node.attrib.get(XLINK, "") if license_node is not None else "",
            "text": text(license_node),
        },
        "sections": collect_sections(root),
        "figures": collect_figures(root, source_dir),
        "supplements": collect_supplements(root, source_dir),
        "nxml_path": str(nxml_path.resolve()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pmcid")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    pmcid = args.pmcid.upper()
    if not pmcid.startswith("PMC") or not pmcid[3:].isdigit():
        raise SystemExit("pmcid must look like PMC123456")
    output_dir = args.output_dir.resolve()
    source_dir = output_dir / "source"
    output_dir.mkdir(parents=True, exist_ok=True)
    source_dir.mkdir(parents=True, exist_ok=True)

    try:
        oa_xml = fetch(f"https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi?id={pmcid}")
        oa_root = ET.fromstring(oa_xml)
        package_link = ""
        for node in oa_root.findall(".//link"):
            if node.attrib.get("format") == "tgz":
                package_link = node.attrib.get("href", "")
                break
        if not package_link:
            raise FetchError(f"PMC OA package link not found for {pmcid}")
        if package_link.startswith("ftp://"):
            package_link = "https://" + package_link[len("ftp://"):]
        package_path = output_dir / f"{pmcid}.tar.gz"
        fetch_mode = "ncbi_oa_package"
        package_error = ""
        try:
            package_path.write_bytes(fetch(package_link, timeout=180))
            with tarfile.open(package_path, "r:gz") as archive:
                safe_extract(archive, source_dir)
            nxml_files = list(source_dir.rglob("*.nxml"))
            if not nxml_files:
                raise FetchError("OA package contains no NXML file")
            asset_status = {"downloaded": 0, "failed": 0}
        except (FetchError, tarfile.TarError, OSError) as exc:
            fetch_mode = "europe_pmc_fulltext_xml"
            package_error = str(exc)
            if package_path.exists() and package_path.stat().st_size == 0:
                package_path.unlink()
            xml_url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML"
            fallback_path = source_dir / f"{pmcid}.xml"
            fallback_path.write_bytes(fetch(xml_url, timeout=180))
            nxml_files = [fallback_path]
            asset_status = fetch_xml_assets(fallback_path, source_dir, pmcid)
        article = parse_article(nxml_files[0], source_dir)
        article["oa_package_url"] = package_link
        article["package_path"] = str(package_path.resolve()) if package_path.is_file() else ""
        article["fetch_mode"] = fetch_mode
        article["package_error"] = package_error
        article["asset_download_status"] = asset_status
        metadata_path = output_dir / "article-evidence.json"
        metadata_path.write_text(json.dumps(article, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({
            "status": "PMC_FETCHED",
            "pmcid": pmcid,
            "title": article["title"],
            "doi": article["doi"],
            "license_href": article["license"]["href"],
            "figure_count": len(article["figures"]),
            "supplement_count": len(article["supplements"]),
            "fetch_mode": fetch_mode,
            "asset_download_status": asset_status,
            "output": str(metadata_path),
        }, ensure_ascii=False, indent=2))
        return 0
    except (FetchError, ET.ParseError, tarfile.TarError, OSError) as exc:
        print(json.dumps({"status": "PMC_FETCH_BLOCKED", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
