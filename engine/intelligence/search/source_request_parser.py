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
        "interent": "web",
        "intenet": "web",
        "intternet": "web",
    }

    BIO_KEYWORDS = (
        "who is",
        "who",
        "bio",
        "biography",
        "background",
        "tell me about",
        "tell me who",
        "research",
        "gather information",
        "find information",
    )

    PROFILE_KEYWORDS = (
        "official profile",
        "profile link",
        "official link",
        "official account",
        "profile",
        "account",
        "handle",
        "url",
    )

    ACTIVITY_KEYWORDS = (
        "latest",
        "recent",
        "posts",
        "updates",
        "activity",
    )

    GENERAL_KEYWORDS = (
        "results",
        "matches",
        "search",
        "find",
        "look up",
        "lookup",
    )

    REQUEST_PHRASES = (
        "can you tell me",
        "please tell me",
        "tell me",
        "can you",
        "please",
        "perform an internet search",
        "perform a internet search",
        "perform internet search",
        "perfrom an interent search",
        "perfrom a interent search",
        "perfrom interent search",
        "perform a search",
        "perfrom a search",
        "search the internet",
        "search internet",
        "search the web",
        "gather information",
        "find information",
        "provide feedback",
        "provide me feedback",
        "give me feedback",
        "search for",
        "look up",
        "lookup",
        "research",
        "search",
        "find",
        "perform",
        "perfrom",
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
        normalized_text = self._normalize_input(text)
        source = self._extract_source(normalized_text)
        requested_output = self._extract_requested_output(
            normalized_text
        )
        query = self._extract_query(
            normalized_text,
            requested_output,
        )

        return ParsedSourceSearchRequest(
            query=query,
            source=source,
            requested_output=requested_output,
            needs_clarification=not bool(query),
            clarification_question=(
                "Who or what should be researched?"
            ),
        )

    def _normalize_input(self, text: str) -> str:
        normalized = " ".join(text.strip().split())

        replacements = {
            r"\bperfrom\b": "perform",
            r"\binterent\b": "internet",
            r"\bintenet\b": "internet",
            r"\bintternet\b": "internet",
        }

        for pattern, replacement in replacements.items():
            normalized = re.sub(
                pattern,
                replacement,
                normalized,
                flags=re.IGNORECASE,
            )

        return normalized

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

        if self._contains_any(
            normalized,
            self.BIO_KEYWORDS,
        ):
            return "bio_summary"

        if self._contains_any(
            normalized,
            self.PROFILE_KEYWORDS,
        ):
            return "profile_link"

        if self._contains_any(
            normalized,
            self.ACTIVITY_KEYWORDS,
        ):
            return "recent_activity"

        return "general_results"

    def _contains_any(
        self,
        text: str,
        phrases: tuple[str, ...],
    ) -> bool:
        return any(
            re.search(
                rf"\b{re.escape(phrase)}\b",
                text,
            )
            for phrase in phrases
        )

    def _extract_query(
        self,
        text: str,
        requested_output: str,
    ) -> str:
        entity_query = self._extract_who_entity(text)

        if entity_query:
            return entity_query

        return self._clean_general_query(
            text,
            requested_output,
        )

    def _extract_who_entity(self, text: str) -> str:
        instruction_words = (
            "perform",
            "search",
            "research",
            "look",
            "find",
            "gather",
            "provide",
            "check",
            "review",
            "open",
        )

        instruction_pattern = "|".join(
            re.escape(word)
            for word in instruction_words
        )

        boundary = (
            rf"(?="
            rf"\s+(?:(?:and|or|then|please)\s+)?"
            rf"(?:{instruction_pattern})\b"
            rf"|[?.!,]"
            rf"|$"
            rf")"
        )

        patterns = (
            rf"\bwho\s+is\s+(.+?){boundary}",
            rf"\bwho\s+(.+?)\s+is{boundary}",
            rf"\btell\s+me\s+about\s+(.+?){boundary}",
            rf"\binformation\s+about\s+(.+?){boundary}",
        )

        for pattern in patterns:
            match = re.search(
                pattern,
                text,
                flags=re.IGNORECASE,
            )

            if not match:
                continue

            entity = self._clean_entity(
                match.group(1)
            )

            if entity:
                return entity

        return ""

    def _clean_general_query(
        self,
        text: str,
        requested_output: str,
    ) -> str:
        cleaned = text

        source_pattern = "|".join(
            re.escape(alias)
            for alias in sorted(
                self.SOURCE_ALIASES,
                key=len,
                reverse=True,
            )
        )

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

        cleaned = re.sub(
            rf"\b(?:{source_pattern})\b",
            " ",
            cleaned,
            flags=re.IGNORECASE,
        )

        removable_phrases = list(
            self.REQUEST_PHRASES
        )

        removable_phrases.extend(
            self.BIO_KEYWORDS
        )
        removable_phrases.extend(
            self.PROFILE_KEYWORDS
        )
        removable_phrases.extend(
            self.ACTIVITY_KEYWORDS
        )
        removable_phrases.extend(
            self.GENERAL_KEYWORDS
        )

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

        return self._clean_entity(cleaned)

    def _clean_entity(self, value: str) -> str:
        cleaned = " ".join(value.split())
        return cleaned.strip(" ?.,:;!-")
