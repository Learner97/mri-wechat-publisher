#!/usr/bin/env python3
"""Fetch structured evidence and source figures from a Nature article page."""

from __future__ import annotations

import argparse
import http.client
import http.cookiejar
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from lxml import html


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)


class FetchError(RuntimeError):
    pass


COOKIE_JAR = http.cookiejar.CookieJar()
OPENER = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(COOKIE_JAR))


def fetch(url: str, timeout: int = 90) -> tuple[bytes, str]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with OPENER.open(req, timeout=timeout) as response:
                return response.read(), response.geturl()
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


def clean_text(value: str) -> str:
    return " ".join(value.split())


def node_text(node: Any) -> str:
    return clean_text(" ".join(node.itertext()))


def iter_json_ld(document: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for raw in document.xpath("//script[@type='application/ld+json']/text()"):
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            continue
        values = value if isinstance(value, list) else [value]
        for item in values:
            if isinstance(item, dict):
                items.append(item)
                graph = item.get("@graph")
                if isinstance(graph, list):
                    items.extend(x for x in graph if isinstance(x, dict))
    return items


def choose_article_json(items: list[dict[str, Any]]) -> dict[str, Any]:
    for item in items:
        kind = item.get("@type")
        kinds = kind if isinstance(kind, list) else [kind]
        if any(value in {"ScholarlyArticle", "Article", "NewsArticle"} for value in kinds):
            return item
    return {}


def choose_image_url(figure: Any, base_url: str) -> str:
    candidates: list[str] = []
    for node in figure.xpath(".//source[@srcset] | .//img[@srcset]"):
        for part in node.attrib.get("srcset", "").split(","):
            url = part.strip().split(" ")[0]
            if url:
                candidates.append(url)
    for attr in ("data-src", "src"):
        candidates.extend(figure.xpath(f".//img[@{attr}]/@{attr}"))
    if not candidates:
        return ""
    url = candidates[-1]
    if url.startswith("//"):
        url = "https:" + url
    return urllib.parse.urljoin(base_url, url)


def safe_name(value: str, fallback: str) -> str:
    name = Path(urllib.parse.urlsplit(value).path).name or fallback
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", name)
    return name or fallback


def extract_sections(body: Any) -> list[dict[str, Any]]:
    sections = []
    for section in body.xpath(".//section"):
        heading_nodes = section.xpath("./h2[1] | ./h3[1]")
        heading = node_text(heading_nodes[0]) if heading_nodes else section.attrib.get("data-title", "")
        paragraphs = [
            node_text(node) for node in section.xpath(".//p[not(ancestor::figure) and not(ancestor::figcaption)]")
            if node_text(node)
        ]
        if heading or paragraphs:
            sections.append({"heading": heading, "paragraphs": paragraphs})
    if not sections:
        paragraphs = [node_text(node) for node in body.xpath(".//p") if node_text(node)]
        sections.append({"heading": "Article body", "paragraphs": paragraphs})
    return sections


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    output_dir = args.output_dir.resolve()
    figures_dir = output_dir / "figures"
    supplements_dir = output_dir / "supplements"
    output_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)
    supplements_dir.mkdir(parents=True, exist_ok=True)

    try:
        raw, final_url = fetch(args.url, timeout=120)
        html_path = output_dir / "publisher-fulltext.html"
        html_path.write_bytes(raw)
        document = html.fromstring(raw, base_url=final_url)
        article_json = choose_article_json(iter_json_ld(document))
        body_nodes = document.xpath(
            "//div[contains(concat(' ', normalize-space(@class), ' '), ' c-article-body ')]"
        )
        if not body_nodes:
            body_nodes = document.xpath("//*[@data-test='article-body']")
        if not body_nodes:
            body_nodes = document.xpath("//article")
        body = body_nodes[0] if body_nodes else document
        sections = extract_sections(body)

        license_links = []
        for href in document.xpath("//a[contains(@href, 'creativecommons.org/licenses')]/@href"):
            if href not in license_links:
                license_links.append(href)
        license_texts = [
            node_text(node) for node in document.xpath(
                "//*[contains(translate(@class,'LICENSE','license'),'license') or @data-test='article-license']"
            ) if node_text(node)
        ]

        figures = []
        for index, figure in enumerate(body.xpath(".//figure"), start=1):
            label_nodes = figure.xpath(".//*[self::b or self::strong][starts-with(normalize-space(), 'Fig.') or starts-with(normalize-space(), 'Figure')]")
            caption_nodes = figure.xpath(".//figcaption")
            description_nodes = figure.xpath(".//*[@data-test='bottom-caption']")
            image_url = choose_image_url(figure, final_url)
            local_path = ""
            if image_url:
                filename = safe_name(image_url, f"figure-{index}.jpg")
                destination = figures_dir / filename
                try:
                    if not destination.is_file():
                        data, _ = fetch(image_url, timeout=120)
                        destination.write_bytes(data)
                    local_path = str(destination.resolve())
                except FetchError:
                    local_path = ""
            figures.append({
                "index": index,
                "label": node_text(label_nodes[0]) if label_nodes else f"Figure {index}",
                "caption": " ".join(filter(None, [
                    node_text(caption_nodes[0]) if caption_nodes else "",
                    node_text(description_nodes[0]) if description_nodes else "",
                ])),
                "image_url": image_url,
                "local_path": local_path,
            })

        supplements = []
        links = body.xpath(".//a[@href]")
        for index, link in enumerate(links, start=1):
            href = urllib.parse.urljoin(final_url, link.attrib.get("href", ""))
            label = node_text(link)
            marker = (href + " " + label).lower()
            if not any(term in marker for term in ("supplement", "suppl_file", "additional file")):
                continue
            filename = safe_name(href, f"supplement-{index}")
            destination = supplements_dir / filename
            local_path = ""
            try:
                if not destination.is_file():
                    data, _ = fetch(href, timeout=180)
                    destination.write_bytes(data)
                local_path = str(destination.resolve())
            except FetchError:
                pass
            supplements.append({"label": label, "url": href, "local_path": local_path})

        title = article_json.get("headline") or clean_text(" ".join(document.xpath("//h1//text()")))
        description = article_json.get("description") or article_json.get("abstract") or ""
        payload = {
            "status": "PUBLISHER_FETCHED",
            "source_url": args.url,
            "final_url": final_url,
            "title": title,
            "date_published": article_json.get("datePublished", ""),
            "doi": article_json.get("sameAs", "") or article_json.get("identifier", ""),
            "description": clean_text(str(description)),
            "license_links": license_links,
            "license_text": license_texts[:5],
            "sections": sections,
            "figures": figures,
            "supplements": supplements,
            "html_path": str(html_path.resolve()),
        }
        evidence_path = output_dir / "publisher-evidence.json"
        evidence_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        body_characters = sum(len(paragraph) for section in sections for paragraph in section["paragraphs"])
        print(json.dumps({
            "status": payload["status"],
            "title": title,
            "final_url": final_url,
            "body_characters": body_characters,
            "figure_count": len(figures),
            "downloaded_figures": sum(bool(item["local_path"]) for item in figures),
            "supplement_count": len(supplements),
            "license_links": license_links,
            "output": str(evidence_path),
        }, ensure_ascii=False, indent=2))
        return 0
    except (FetchError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "PUBLISHER_FETCH_BLOCKED", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
