from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import scrapy
from scrapy.crawler import CrawlerProcess


PROJECT_ROOT = Path(__file__).resolve().parents[3]
CRAWLED_PAGES_FILE = PROJECT_ROOT / "data" / "pages" / "crawled_pages.jsonl"


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record) + "\n")


def clean_text(value: str) -> str:
    return " ".join(value.split()).strip()


def valid_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


class SourceCrawlerSpider(scrapy.Spider):
    name = "paige_spider"

    custom_settings = {
        "LOG_ENABLED": False,
        "ROBOTSTXT_OBEY": True,
        "DOWNLOAD_TIMEOUT": 15,
        "DEPTH_LIMIT": 1,
        "CONCURRENT_REQUESTS": 4,
        "USER_AGENT": "ApplicationCrawler/1.0",
    }

    def __init__(self, start_url: str, max_pages: int = 5, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.start_urls = [start_url]
        self.max_pages = int(max_pages)
        self.pages_seen = 0
        self.allowed_domain = urlparse(start_url).netloc

    def parse(self, response: scrapy.http.Response):
        if self.pages_seen >= self.max_pages:
            return

        self.pages_seen += 1

        title = clean_text(" ".join(response.css("title::text").getall()))
        headings = [
            clean_text(text)
            for text in response.css("h1::text, h2::text, h3::text").getall()
            if clean_text(text)
        ]

        paragraphs = [
            clean_text(text)
            for text in response.css("p::text, li::text").getall()
            if clean_text(text)
        ]

        text = clean_text(" ".join(paragraphs))[:8000]

        record = {
            "source": "internet",
            "category": "crawled_page",
            "data_type": "scrapy_page",
            "value": response.url,
            "unit": "url",
            "metadata": {
                "title": title or "Untitled",
                "url": response.url,
                "headings": headings[:20],
                "text": text,
            },
        }

        append_jsonl(CRAWLED_PAGES_FILE, record)

        for href in response.css("a::attr(href)").getall():
            if self.pages_seen >= self.max_pages:
                break

            next_url = response.urljoin(href)

            if not valid_url(next_url):
                continue

            if urlparse(next_url).netloc != self.allowed_domain:
                continue

            yield response.follow(next_url, callback=self.parse)


def crawl_site(start_url: str, max_pages: int = 5) -> dict[str, Any]:
    if not valid_url(start_url):
        return {
            "status": "error",
            "message": "Invalid URL.",
            "url": start_url,
        }

    before_count = 0
    if CRAWLED_PAGES_FILE.exists():
        before_count = sum(1 for line in CRAWLED_PAGES_FILE.open("r", encoding="utf-8") if line.strip())

    process = CrawlerProcess()
    process.crawl(SourceCrawlerSpider, start_url=start_url, max_pages=max_pages)
    process.start()

    after_count = 0
    if CRAWLED_PAGES_FILE.exists():
        after_count = sum(1 for line in CRAWLED_PAGES_FILE.open("r", encoding="utf-8") if line.strip())

    return {
        "status": "success",
        "message": "Crawl complete.",
        "url": start_url,
        "pages_added": max(after_count - before_count, 0),
        "output_file": str(CRAWLED_PAGES_FILE),
    }
