from __future__ import annotations

from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
from urllib.parse import parse_qs, quote_plus, unquote, urlparse
import urllib.error
import urllib.request


@dataclass(frozen=True)
class PublicSearchResult:
    title: str
    url: str
    source: str
    score: int


class AnchorSearchParser(HTMLParser):
    def __init__(self, engine_name: str) -> None:
        super().__init__()
        self.engine_name = engine_name
        self.results: list[PublicSearchResult] = []
        self._inside_anchor = False
        self._current_href = ""
        self._current_text: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag != "a":
            return

        attrs_dict = {
            key: value or ""
            for key, value in attrs
        }
        href = attrs_dict.get("href", "")

        if not href:
            return

        self._inside_anchor = True
        self._current_href = href
        self._current_text = []

    def handle_data(self, data: str) -> None:
        if self._inside_anchor:
            self._current_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or not self._inside_anchor:
            return

        title = " ".join(
            "".join(self._current_text).split()
        ).strip()
        url = self._clean_url(self._current_href)

        if title and self._is_usable_url(url):
            self.results.append(
                PublicSearchResult(
                    title=unescape(title),
                    url=url,
                    source=self.engine_name,
                    score=0,
                )
            )

        self._inside_anchor = False
        self._current_href = ""
        self._current_text = []

    def _clean_url(self, url: str) -> str:
        if not url:
            return ""

        if url.startswith("//"):
            url = f"https:{url}"

        parsed = urlparse(url)

        if (
            "duckduckgo.com" in parsed.netloc
            and parsed.path.startswith("/l/")
        ):
            query = parse_qs(parsed.query)
            redirected = query.get("uddg", [""])[0]

            if redirected:
                return unquote(redirected)

        return url

    def _is_usable_url(self, url: str) -> bool:
        if not url.startswith(("http://", "https://")):
            return False

        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        blocked_domains = (
            "duckduckgo.com",
            "bing.com",
            "microsoft.com",
            "go.microsoft.com",
            "r.bing.com",
            "www.bing.com",
        )

        return not any(
            blocked in domain
            for blocked in blocked_domains
        )


class PublicSourceSearch:
    SOURCE_SITE_MAP = {
        "instagram": "instagram.com",
        "youtube": "youtube.com",
        "spotify": "open.spotify.com",
        "facebook": "facebook.com",
        "tiktok": "tiktok.com",
        "twitter": "twitter.com",
        "x": "x.com",
        "web": "",
    }

    SOURCE_ALIASES = {
        "ig": "instagram",
        "instagram": "instagram",
        "youtube": "youtube",
        "yt": "youtube",
        "spotify": "spotify",
        "facebook": "facebook",
        "tiktok": "tiktok",
        "twitter": "twitter",
        "x": "x",
        "web": "web",
        "internet": "web",
    }

    SEARCH_ENDPOINTS = (
        {
            "name": "duckduckgo",
            "url": (
                "https://html.duckduckgo.com/"
                "html/?q={query}"
            ),
        },
        {
            "name": "duckduckgo_lite",
            "url": (
                "https://lite.duckduckgo.com/"
                "lite/?q={query}"
            ),
        },
        {
            "name": "bing",
            "url": (
                "https://www.bing.com/"
                "search?q={query}"
            ),
        },
    )

    def search(
        self,
        query: str,
        source: str = "web",
        requested_output: str = "",
        limit: int = 5,
        timeout: int = 20,
    ) -> dict:
        clean_query = " ".join(query.split()).strip()
        clean_source = self.normalize_source(source)
        safe_limit = max(1, min(limit, 20))

        if not clean_query:
            return {
                "status": "error",
                "answer": "No search query was provided.",
                "query": "",
                "target_source": clean_source,
                "requested_output": requested_output,
                "search_query": "",
                "attempted_queries": [],
                "results": [],
                "search_provider": "public_web_index",
                "search_method": "multi_query_lookup",
                "error": "empty query",
            }

        attempted_queries = self.build_search_queries(
            query=clean_query,
            source=clean_source,
            requested_output=requested_output,
        )

        all_results: list[PublicSearchResult] = []
        errors: list[str] = []

        for search_query in attempted_queries:
            for endpoint in self.SEARCH_ENDPOINTS:
                endpoint_results, error = self._run_search(
                    engine_name=endpoint["name"],
                    endpoint_template=endpoint["url"],
                    search_query=search_query,
                    source=clean_source,
                    timeout=timeout,
                )

                if error:
                    errors.append(error)

                all_results.extend(endpoint_results)

        ranked_results = self._rank_and_filter_results(
            results=all_results,
            query=clean_query,
            source=clean_source,
            requested_output=requested_output,
            limit=safe_limit,
        )

        if ranked_results:
            return {
                "status": "success",
                "answer": (
                    f"Found {len(ranked_results)} public "
                    f"source result(s) for {clean_query}."
                ),
                "query": clean_query,
                "target_source": clean_source,
                "requested_output": requested_output,
                "search_query": (
                    attempted_queries[0]
                    if attempted_queries
                    else ""
                ),
                "attempted_queries": attempted_queries,
                "results": ranked_results,
                "search_provider": "public_web_index",
                "search_method": "multi_query_lookup",
                "error": "",
            }

        return {
            "status": "not_found",
            "answer": (
                f"No public results were found for "
                f"{clean_query}."
            ),
            "query": clean_query,
            "target_source": clean_source,
            "requested_output": requested_output,
            "search_query": (
                attempted_queries[0]
                if attempted_queries
                else ""
            ),
            "attempted_queries": attempted_queries,
            "results": [],
            "search_provider": "public_web_index",
            "search_method": "multi_query_lookup",
            "error": "; ".join(errors[-3:]),
        }

    def normalize_source(self, source: str) -> str:
        clean_source = source.lower().strip()
        return self.SOURCE_ALIASES.get(
            clean_source,
            clean_source or "web",
        )

    def build_search_queries(
        self,
        query: str,
        source: str,
        requested_output: str,
    ) -> list[str]:
        site = self.SOURCE_SITE_MAP.get(source, "")
        handle_candidate = "".join(
            character.lower()
            for character in query
            if character.isalnum()
        )

        queries = [
            f'"{query}"',
            query,
        ]

        if requested_output == "bio_summary":
            research_terms = (
                "biography",
                "background",
                "interview",
                "official website",
                "news",
                "profile",
            )

            for term in research_terms:
                queries.append(f'"{query}" {term}')

        elif requested_output == "profile_link":
            profile_terms = (
                "official profile",
                "official account",
                "profile link",
                "account",
                "handle",
            )

            for term in profile_terms:
                queries.append(f'"{query}" {term}')

        elif requested_output == "recent_activity":
            activity_terms = (
                "latest",
                "recent activity",
                "updates",
                "news",
            )

            for term in activity_terms:
                queries.append(f'"{query}" {term}')

        if site:
            queries.extend(
                [
                    f'"{query}" {source}',
                    f"{query} {source}",
                    f"{query} {source} official",
                    f"site:{site} \"{query}\"",
                    f"site:{site} {query}",
                    f"site:{site} {handle_candidate}",
                ]
            )

        return self._dedupe_strings(queries)

    def _run_search(
        self,
        engine_name: str,
        endpoint_template: str,
        search_query: str,
        source: str,
        timeout: int,
    ) -> tuple[list[PublicSearchResult], str]:
        url = endpoint_template.format(
            query=quote_plus(search_query)
        )

        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 DataPlatformSearch/1.0 "
                    "(public source lookup)"
                ),
                "Accept": (
                    "text/html,"
                    "application/xhtml+xml"
                ),
            },
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=timeout,
            ) as response:
                html = response.read().decode(
                    "utf-8",
                    errors="replace",
                )

        except urllib.error.URLError as error:
            return [], f"{engine_name}: {error}"

        parser = AnchorSearchParser(
            engine_name=engine_name
        )
        parser.feed(html)

        results = [
            item
            for item in parser.results
            if self._result_matches_source(
                item.url,
                source,
            )
        ]

        return results, ""

    def _result_matches_source(
        self,
        url: str,
        source: str,
    ) -> bool:
        if source == "web":
            return True

        site = self.SOURCE_SITE_MAP.get(source, "")

        if not site:
            return True

        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        if site not in domain:
            return False

        if source == "instagram":
            return self._is_likely_instagram_profile(url)

        return True

    def _is_likely_instagram_profile(
        self,
        url: str,
    ) -> bool:
        parsed = urlparse(url)
        path_parts = [
            part
            for part in parsed.path.split("/")
            if part.strip()
        ]

        if not path_parts:
            return False

        blocked_first_parts = {
            "p",
            "reel",
            "reels",
            "stories",
            "explore",
            "accounts",
            "about",
            "developer",
            "privacy",
        }

        return (
            path_parts[0].lower()
            not in blocked_first_parts
        )

    def _rank_and_filter_results(
        self,
        results: list[PublicSearchResult],
        query: str,
        source: str,
        requested_output: str,
        limit: int,
    ) -> list[dict]:
        seen_urls: set[str] = set()
        unique_results: list[PublicSearchResult] = []

        for item in results:
            clean_url = item.url.rstrip("/")

            if clean_url in seen_urls:
                continue

            seen_urls.add(clean_url)
            unique_results.append(item)

        tokens = [
            token.lower()
            for token in query.split()
            if len(token) > 1
        ]

        ranked: list[PublicSearchResult] = []

        for item in unique_results:
            combined = (
                f"{item.title} {item.url}"
            ).lower()
            score = 0

            for token in tokens:
                if token in combined:
                    score += 2

            if source != "web":
                site = self.SOURCE_SITE_MAP.get(
                    source,
                    "",
                )

                if site and site in item.url.lower():
                    score += 8

            if requested_output == "profile_link":
                score += 4

            if requested_output == "bio_summary":
                score += 3

            if (
                source == "instagram"
                and self._is_likely_instagram_profile(
                    item.url
                )
            ):
                score += 6

            ranked.append(
                PublicSearchResult(
                    title=item.title,
                    url=item.url,
                    source=item.source,
                    score=score,
                )
            )

        ranked.sort(
            key=lambda item: item.score,
            reverse=True,
        )

        return [
            {
                "title": item.title,
                "url": item.url,
                "source": item.source,
                "score": item.score,
            }
            for item in ranked[:limit]
            if item.score > 0
        ]

    def _dedupe_strings(
        self,
        values: list[str],
    ) -> list[str]:
        seen: set[str] = set()
        output: list[str] = []

        for value in values:
            clean_value = " ".join(
                value.split()
            ).strip()

            if clean_value and clean_value not in seen:
                seen.add(clean_value)
                output.append(clean_value)

        return output
