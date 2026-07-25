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
        "profile_link": (
            "official profile",
            "profile link",
            "official link",
            "official account",
            "profile",
            "account",
            "handle",
            "url",
        ),
        "bio_summary": (
            "bio",
            "biography",
            "background",
            "tell me about",
            "who is",
            "research",
            "gather information",
            "find information",
        ),
        "recent_activity": (
            "latest",
            "recent",
            "posts",
            "updates",
            "activity",
        ),
        "general_results": (
            "results",
            "matches",
            "search",
            "find",
            "look up",
            "lookup",
        ),
    }

    REQUEST_PHRASES = (
        "can you tell me",
        "please tell me",
        "tell me",
        "can you",
        "please",
        "gather information",
        "find information",
        "search for",
        "look up",
        "lookup",
        "search",
        "find",
        "research",
    )

    EXTRA_REMOVABLE_WORDS = (
        "artist",
        "person",
        "creator",
        "musician",
        "individual",
        "subject",
        "named",
        "name",
    )

    CONNECTOR_WORDS = (
        "and",
        "or",
        "for",
        "the",
        "a",
        "an",
        "of",
        "about",
        "on",
        "from",
        "in",
    )

    def parse(self, text: str) -> ParsedSourceSearchRequest:
        source = self._extract_source(text)

        requested_output = (
            self._extract_requested_output(text)
            or "general_results"
        )

        query = self._extract_query(
            text=text,
            requested_output=requested_output,
        )

        needs_clarification = not bool(query)

        return ParsedSourceSearchRequest(
            query=query,
            source=source,
            requested_output=requested_output,
            needs_clarification=needs_clarification,
            clarification_question=(
                "Who or what should be researched?"
            ),
        )

    def _extract_source(self, text: str) -> str:
        normalized = text.lower()

        for alias, source in self.SOURCE_ALIASES.items():
            if re.search(
                rf"\b{re.escape(alias)}\b",
                normalized,
            ):
                return source

        return "web"

    def _extract_requested_output(self, text: str) -> str:
        normalized = text.lower()

        for output_type, keywords in self.OUTPUT_KEYWORDS.items():
            for keyword in keywords:
                if re.search(
                    rf"\b{re.escape(keyword)}\b",
                    normalized,
                ):
                    return output_type

        return ""

    def _extract_query(
        self,
        text: str,
        requested_output: str,
    ) -> str:
        cleaned = " ".join(text.strip().split())

        source_pattern = "|".join(
            re.escape(item)
            for item in sorted(
                self.SOURCE_ALIASES.keys(),
                key=len,
                reverse=True,
            )
        )

        # Remove phrases such as:
        # on internet
        # on the internet
        # from Facebook
        # in the web
        cleaned = re.sub(
            (
                rf"\b(?:on|from|in)\s+"
                rf"(?:the\s+)?"
                rf"(?:{source_pattern})\b"
            ),
            " ",
            cleaned,
            flags=re.IGNORECASE,
        )

        # Remove any remaining standalone source name.
        cleaned = re.sub(
            rf"\b(?:{source_pattern})\b",
            " ",
            cleaned,
            flags=re.IGNORECASE,
        )

        removable_phrases = list(self.REQUEST_PHRASES)

        for phrases in self.OUTPUT_KEYWORDS.values():
            removable_phrases.extend(phrases)

        for phrase in sorted(
            set(removable_phrases),
            key=len,
            reverse=True,
        ):
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

        connector_pattern = "|".join(
            re.escape(word)
            for word in self.CONNECTOR_WORDS
        )

        cleaned = re.sub(
            rf"\b(?:{connector_pattern})\b",
            " ",
            cleaned,
            flags=re.IGNORECASE,
        )

        cleaned = " ".join(cleaned.split())

        return cleaned.strip(" ?.,:;")
