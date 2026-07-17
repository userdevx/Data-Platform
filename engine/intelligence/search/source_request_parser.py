from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class ParsedSourceSearchRequest:
    query: str
    source: str
    requested_output: str
    needs_clarification: bool
    clarification_question: str


class SourceSearchRequestParser:
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

    OUTPUT_KEYWORDS = {
        "profile_link": [
            "official profile",
            "profile link",
            "official link",
            "official account",
            "profile",
            "account",
            "handle",
            "link",
            "url",
            "official",
        ],
        "bio_summary": [
            "bio",
            "biography",
            "background",
            "about",
            "summary",
            "who is",
        ],
        "recent_activity": [
            "latest",
            "recent",
            "posts",
            "updates",
            "activity",
        ],
        "general_results": [
            "results",
            "matches",
            "general results",
        ],
    }

    EXTRA_REMOVABLE_WORDS = [
        "artist",
        "name",
        "person",
        "creator",
        "musician",
    ]

    def parse(self, text: str) -> ParsedSourceSearchRequest:
        source = self._extract_source(text)
        requested_output = self._extract_requested_output(text)
        query = self._extract_query(text, requested_output)

        needs_clarification = bool(source) and bool(query) and not requested_output

        return ParsedSourceSearchRequest(
            query=query,
            source=source or "web",
            requested_output=requested_output,
            needs_clarification=needs_clarification,
            clarification_question=(
                "What should be returned: official profile link, bio summary, "
                "recent activity, or general results?"
            ),
        )

    def _extract_source(self, text: str) -> str:
        normalized = text.lower()

        for alias, source in self.SOURCE_ALIASES.items():
            if re.search(rf"\b{re.escape(alias)}\b", normalized):
                return source

        return "web"

    def _extract_requested_output(self, text: str) -> str:
        normalized = text.lower()

        for output_type, keywords in self.OUTPUT_KEYWORDS.items():
            for keyword in keywords:
                if re.search(rf"\b{re.escape(keyword)}\b", normalized):
                    return output_type

        return ""

    def _extract_query(self, text: str, requested_output: str) -> str:
        cleaned = text.strip()

        source_pattern = "|".join(
            re.escape(item)
            for item in sorted(self.SOURCE_ALIASES.keys(), key=len, reverse=True)
        )

        cleaned = re.sub(
            rf"\b(on|from|in)\s+({source_pattern})\b",
            " ",
            cleaned,
            flags=re.IGNORECASE,
        )

        cleaned = re.sub(
            r"\b(search for|search|find|look up|lookup)\b",
            " ",
            cleaned,
            flags=re.IGNORECASE,
        )

        if requested_output:
            output_phrases = []
            for phrases in self.OUTPUT_KEYWORDS.values():
                output_phrases.extend(phrases)

            for phrase in sorted(output_phrases, key=len, reverse=True):
                cleaned = re.sub(
                    rf"\b{re.escape(phrase)}\b",
                    " ",
                    cleaned,
                    flags=re.IGNORECASE,
                )

        for word in self.EXTRA_REMOVABLE_WORDS:
            cleaned = re.sub(
                rf"\b{re.escape(word)}\b",
                " ",
                cleaned,
                flags=re.IGNORECASE,
            )

        cleaned = re.sub(
            r"\b(for|the|a|an|of)\b",
            " ",
            cleaned,
            flags=re.IGNORECASE,
        )

        cleaned = " ".join(cleaned.split()).strip(" ?.,:;")

        return cleaned
