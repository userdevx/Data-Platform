from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import scrapy
from scrapy.crawler import CrawlerProcess


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[3]
)

CRAWLED_PAGES_FILE = (
    PROJECT_ROOT
    / "data"
    / "pages"
    / "crawled_pages.jsonl"
)

CRAWLER_SPIDER_NAME = (
    Path(__file__)
    .stem
)


CrawlerRecord = dict[
    str,
    Any,
]

RecordSink = Callable[
    [
        CrawlerRecord,
    ],
    None,
]


def append_jsonl(
    path: Path,
    record: CrawlerRecord,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "a",
        encoding="utf-8",
    ) as file:
        file.write(
            json.dumps(
                record,
                ensure_ascii=False,
            )
            + "\n"
        )


def clean_text(
    value: str,
) -> str:
    if not isinstance(
        value,
        str,
    ):
        raise TypeError(
            "value must be a string."
        )

    return " ".join(
        value.split()
    ).strip()


def valid_url(
    url: str,
) -> bool:
    if not isinstance(
        url,
        str,
    ):
        return False

    parsed = urlparse(
        url
    )

    return (
        parsed.scheme
        in {
            "http",
            "https",
        }
        and bool(
            parsed.netloc
        )
    )


def build_page_record(
    *,
    url: str,
    title: str,
    headings: list[str],
    paragraphs: list[str],
) -> CrawlerRecord:
    if not valid_url(
        url
    ):
        raise ValueError(
            "url must be a valid "
            "HTTP or HTTPS URL."
        )

    normalized_title = (
        clean_text(
            title
        )
    )

    normalized_headings = [
        clean_text(
            heading
        )
        for heading in headings
        if clean_text(
            heading
        )
    ]

    normalized_paragraphs = [
        clean_text(
            paragraph
        )
        for paragraph in paragraphs
        if clean_text(
            paragraph
        )
    ]

    retrieved_text = (
        clean_text(
            " ".join(
                normalized_paragraphs
            )
        )[:8000]
    )

    return {
        "source": "internet",
        "category": "crawled_page",
        "data_type": "web_page",
        "value": url,
        "unit": "url",

        "source_url": url,

        "retrieved_text": (
            retrieved_text
        ),

        "metadata": {
            "collector": "scrapy",
            "title": (
                normalized_title
                or "Untitled"
            ),
            "url": url,
            "headings": (
                normalized_headings[
                    :20
                ]
            ),
        },
    }


class SourceCrawlerSpider(
    scrapy.Spider
):
    name = CRAWLER_SPIDER_NAME

    custom_settings = {
        "LOG_ENABLED": False,
        "ROBOTSTXT_OBEY": True,
        "DOWNLOAD_TIMEOUT": 15,
        "DEPTH_LIMIT": 1,
        "CONCURRENT_REQUESTS": 4,
    }

    def __init__(
        self,
        start_url: str,
        max_pages: int = 5,
        record_sink: (
            RecordSink
            | None
        ) = None,
        persist_jsonl: bool = True,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            *args,
            **kwargs,
        )

        if not valid_url(
            start_url
        ):
            raise ValueError(
                "start_url must be a valid "
                "HTTP or HTTPS URL."
            )

        normalized_max_pages = int(
            max_pages
        )

        if normalized_max_pages < 1:
            raise ValueError(
                "max_pages must be greater "
                "than zero."
            )

        self.start_urls = [
            start_url
        ]

        self.max_pages = (
            normalized_max_pages
        )

        self.pages_seen = 0

        self.allowed_domain = (
            urlparse(
                start_url
            )
            .netloc
        )

        self.record_sink = (
            record_sink
        )

        self.persist_jsonl = bool(
            persist_jsonl
        )

    def parse(
        self,
        response: scrapy.http.Response,
    ):
        if (
            self.pages_seen
            >= self.max_pages
        ):
            return

        self.pages_seen += 1

        title = clean_text(
            " ".join(
                response.css(
                    "title::text"
                )
                .getall()
            )
        )

        headings = [
            clean_text(
                text
            )
            for text in response.css(
                (
                    "h1::text, "
                    "h2::text, "
                    "h3::text"
                )
            )
            .getall()
            if clean_text(
                text
            )
        ]

        paragraphs = [
            clean_text(
                text
            )
            for text in response.css(
                "p::text, li::text"
            )
            .getall()
            if clean_text(
                text
            )
        ]

        record = (
            build_page_record(
                url=response.url,
                title=title,
                headings=headings,
                paragraphs=paragraphs,
            )
        )

        if (
            self.record_sink
            is not None
        ):
            self.record_sink(
                record
            )

        if self.persist_jsonl:
            append_jsonl(
                CRAWLED_PAGES_FILE,
                record,
            )

        for href in (
            response.css(
                "a::attr(href)"
            )
            .getall()
        ):
            if (
                self.pages_seen
                >= self.max_pages
            ):
                break

            next_url = (
                response.urljoin(
                    href
                )
            )

            if not valid_url(
                next_url
            ):
                continue

            if (
                urlparse(
                    next_url
                )
                .netloc
                != self.allowed_domain
            ):
                continue

            yield response.follow(
                next_url,
                callback=self.parse,
            )


def crawl_site(
    start_url: str,
    max_pages: int = 5,
    *,
    persist_jsonl: bool = True,
    user_agent: str = (
        "Data-Platform/"
        "Public-Web-Collector"
    ),
) -> dict[str, Any]:
    if not valid_url(
        start_url
    ):
        return {
            "status": "error",
            "message": "Invalid URL.",
            "url": start_url,
            "records": (),
        }

    if (
        not isinstance(
            max_pages,
            int,
        )
        or isinstance(
            max_pages,
            bool,
        )
    ):
        raise TypeError(
            "max_pages must be "
            "an integer."
        )

    if max_pages < 1:
        raise ValueError(
            "max_pages must be "
            "greater than zero."
        )

    normalized_user_agent = (
        clean_text(
            user_agent
        )
    )

    if not normalized_user_agent:
        raise ValueError(
            "user_agent cannot "
            "be empty."
        )

    collected_records: list[
        CrawlerRecord
    ] = []

    def collect_record(
        record: CrawlerRecord,
    ) -> None:
        collected_records.append(
            record
        )

    process = CrawlerProcess(
        settings={
            "USER_AGENT": (
                normalized_user_agent
            ),
        }
    )

    process.crawl(
        SourceCrawlerSpider,
        start_url=start_url,
        max_pages=max_pages,
        record_sink=collect_record,
        persist_jsonl=(
            persist_jsonl
        ),
    )

    process.start()

    return {
        "status": "success",
        "message": (
            "Crawl complete."
        ),
        "url": start_url,
        "pages_added": len(
            collected_records
        ),
        "records": tuple(
            collected_records
        ),
        "output_file": (
            str(
                CRAWLED_PAGES_FILE
            )
            if persist_jsonl
            else None
        ),
    }


def crawl_site_records(
    start_url: str,
    max_pages: int = 5,
    *,
    user_agent: str = (
        "Data-Platform/"
        "Public-Web-Collector"
    ),
) -> tuple[
    CrawlerRecord,
    ...,
]:
    """
    Retrieve public website information directly
    into memory.

    This path does not write the crawler JSONL file.

    It is intended for Data Platform ingestion.
    """

    result = crawl_site(
        start_url,
        max_pages,
        persist_jsonl=False,
        user_agent=user_agent,
    )

    if (
        result.get(
            "status"
        )
        != "success"
    ):
        raise RuntimeError(
            str(
                result.get(
                    "message",
                    "Crawl failed.",
                )
            )
        )

    records = result.get(
        "records",
        (),
    )

    if not isinstance(
        records,
        tuple,
    ):
        raise RuntimeError(
            "Crawler returned an invalid "
            "record collection."
        )

    return records
