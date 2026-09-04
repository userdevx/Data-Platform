from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import requests
from bs4 import BeautifulSoup


class InternetSearchError(Exception):
    pass


PROJECT_ROOT = Path(__file__).resolve().parents[2]
VAULT_WEB_DIR = PROJECT_ROOT / "data" / "vault" / "web"

SEARCH_URL = "https://html.duckduckgo.com/html/"

FORBIDDEN_HOSTS = {
    "169.254.169.254",
    "metadata.google.internal",
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
}

FORBIDDEN_HOST_PREFIXES = (
    "10.",
    "172.16.",
    "172.17.",
    "172.18.",
    "172.19.",
    "172.20.",
    "172.21.",
    "172.22.",
    "172.23.",
    "172.24.",
    "172.25.",
    "172.26.",
    "172.27.",
    "172.28.",
    "172.29.",
    "172.30.",
    "172.31.",
    "192.168.",
)

HIGH_QUALITY_DOMAINS = (
    "github.com",
    "raw.githubusercontent.com",
    "docs.github.com",
    "github.blog",
    "learn.microsoft.com",
    "microsoft.com",
    "azure.microsoft.com",
    "visualstudio.microsoft.com",
    "code.visualstudio.com",
    "python.org",
    "docs.python.org",
    "developer.mozilla.org",
    "nodejs.org",
    "npmjs.com",
    "pypi.org",
    "rust-lang.org",
    "doc.rust-lang.org",
    "tauri.app",
    "vite.dev",
    "react.dev",
    "typescriptlang.org",
    "sqlite.org",
    "stackoverflow.com",
    "britannica.com",
    "wikipedia.org",
    ".gov",
    ".edu",
)

TOP_SOFTWARE_SOURCES = (
    "github.com",
    "raw.githubusercontent.com",
    "docs.github.com",
    "learn.microsoft.com",
    "microsoft.com",
    "azure.microsoft.com",
    "visualstudio.microsoft.com",
    "code.visualstudio.com",
    "python.org",
    "docs.python.org",
    "developer.mozilla.org",
    "nodejs.org",
    "npmjs.com",
    "pypi.org",
    "rust-lang.org",
    "doc.rust-lang.org",
    "tauri.app",
    "vite.dev",
    "react.dev",
    "typescriptlang.org",
    "sqlite.org",
    "stackoverflow.com",
)

REQUEST_HEADERS = {
    "User-Agent": "ApplicationIntelligence/0.1 local source reader; no persistent cookies",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,text/plain;q=0.8,*/*;q=0.7",
    "Accept-Language": "en-US,en;q=0.9",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def normalize_url(url: str) -> str:
    parsed = urlparse(url)

    if parsed.netloc.endswith("duckduckgo.com") and parsed.path.startswith("/l/"):
        query = parse_qs(parsed.query)
        uddg = query.get("uddg", [""])[0]

        if uddg:
            return unquote(uddg)

    return url


def validate_public_url(url: str) -> None:
    parsed = urlparse(url)
    host = parsed.hostname or ""

    if parsed.scheme not in {"http", "https"}:
        raise InternetSearchError("Only HTTP and HTTPS URLs are allowed.")

    if not host:
        raise InternetSearchError("URL host is missing.")

    host = host.lower()

    if host in FORBIDDEN_HOSTS:
        raise InternetSearchError(f"Forbidden host: {host}")

    if any(host.startswith(prefix) for prefix in FORBIDDEN_HOST_PREFIXES):
        raise InternetSearchError(f"Private network host is blocked: {host}")


def classify_source_quality(host: str) -> tuple[str, int]:
    clean_host = host.lower()

    if any(domain in clean_host for domain in TOP_SOFTWARE_SOURCES):
        return "high", 110

    if any(domain in clean_host for domain in HIGH_QUALITY_DOMAINS):
        return "high", 100

    if clean_host.endswith(".org"):
        return "medium", 70

    if clean_host.endswith(".com"):
        return "medium", 60

    return "unknown", 40


def extract_search_results(html: str, limit: int) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    results: list[dict[str, Any]] = []

    for result_node in soup.select(".result"):
        title_node = result_node.select_one(".result__title a")

        if not title_node:
            continue

        title = clean_text(title_node.get_text(" ", strip=True))
        url = normalize_url(title_node.get("href", ""))

        if not title or not url:
            continue

        try:
            validate_public_url(url)
        except InternetSearchError:
            continue

        parsed = urlparse(url)
        host = parsed.hostname or ""
        quality, score = classify_source_quality(host)

        results.append(
            {
                "title": title,
                "url": url,
                "host": host,
                "source_quality": quality,
                "source_score": score,
            }
        )

        if len(results) >= limit:
            break

    results.sort(key=lambda item: item.get("source_score", 0), reverse=True)
    return results[:limit]


def search_web(query: str, limit: int = 5) -> dict[str, Any]:
    clean_query = query.strip()

    if not clean_query:
        raise InternetSearchError("Search query is required.")

    limit = max(1, min(limit, 10))

    response = requests.post(
        SEARCH_URL,
        data={"q": clean_query},
        headers=REQUEST_HEADERS,
        timeout=20,
    )
    response.raise_for_status()

    results = extract_search_results(response.text, limit)

    return {
        "source": "internet",
        "category": "search",
        "data_type": "internet_search_results",
        "value": clean_query,
        "unit": "query",
        "status": "complete",
        "result_count": len(results),
        "results": results,
        "created_at": utc_now(),
    }


def remove_unwanted_nodes(soup: BeautifulSoup) -> None:
    for selector in [
        "script",
        "style",
        "noscript",
        "iframe",
        "svg",
        "canvas",
        "form",
        "button",
        "nav",
        "footer",
        "header",
        "aside",
        "[aria-hidden='true']",
    ]:
        for node in soup.select(selector):
            node.decompose()


def extract_page_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    remove_unwanted_nodes(soup)

    main_node = soup.find("main") or soup.find("article") or soup.find("body") or soup
    raw_text = main_node.get_text("\n", strip=True)

    lines = []

    for line in raw_text.splitlines():
        clean_line = clean_text(line)

        if len(clean_line) >= 3:
            lines.append(clean_line)

    return "\n".join(lines).strip()


def save_web_page_to_vault(
    *,
    url: str,
    title: str,
    host: str,
    text: str,
) -> str:
    VAULT_WEB_DIR.mkdir(parents=True, exist_ok=True)

    url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    safe_host = re.sub(r"[^a-zA-Z0-9_.-]+", "_", host)[:80]
    file_path = VAULT_WEB_DIR / f"{safe_host}_{url_hash}.txt"

    record = [
        f"Title: {title}",
        f"URL: {url}",
        f"Host: {host}",
        f"Fetched At: {utc_now()}",
        "",
        text,
    ]

    file_path.write_text("\n".join(record), encoding="utf-8")

    return str(file_path.relative_to(PROJECT_ROOT))


def read_web_page(url: str, title: str = "") -> dict[str, Any]:
    clean_url = url.strip()

    if not clean_url:
        raise InternetSearchError("URL is required.")

    validate_public_url(clean_url)

    response = requests.get(
        clean_url,
        headers=REQUEST_HEADERS,
        timeout=25,
        allow_redirects=True,
    )
    response.raise_for_status()

    final_url = response.url
    validate_public_url(final_url)

    parsed = urlparse(final_url)
    host = parsed.hostname or ""

    content_type = response.headers.get("content-type", "")

    if "text/html" not in content_type and "text/plain" not in content_type:
        raise InternetSearchError(f"Unsupported content type: {content_type}")

    page_text = extract_page_text(response.text)

    if not page_text:
        raise InternetSearchError("No readable page text was extracted.")

    page_title = title.strip()

    if not page_title:
        soup = BeautifulSoup(response.text, "html.parser")
        page_title = clean_text(soup.title.get_text(" ", strip=True)) if soup.title else final_url

    vault_path = save_web_page_to_vault(
        url=final_url,
        title=page_title,
        host=host,
        text=page_text,
    )

    quality, score = classify_source_quality(host)

    return {
        "source": "internet",
        "category": "web_page",
        "data_type": "internet_full_page",
        "value": final_url,
        "unit": "url",
        "status": "complete",
        "title": page_title,
        "url": final_url,
        "host": host,
        "source_quality": quality,
        "source_score": score,
        "content_length": len(page_text),
        "content": page_text,
        "vault_path": vault_path,
        "created_at": utc_now(),
    }
