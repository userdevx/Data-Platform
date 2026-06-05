from __future__ import annotations

import re


STOP_PHRASES = [
    "can you",
    "please",
    "tell me",
    "show me",
    "search for",
    "look up",
    "find me",
]


def rewrite_query(user_input: str, chat_history: list[str] | None = None) -> str:
    query = " ".join(user_input.strip().split())

    for phrase in STOP_PHRASES:
        query = re.sub(rf"\b{re.escape(phrase)}\b", "", query, flags=re.IGNORECASE)

    query = " ".join(query.split())

    if chat_history:
        last_context = " ".join(chat_history[-3:])
        if query.lower() in {"it", "that", "that error", "how do i fix it"}:
            query = f"{last_context} {query}"

    return query.strip()
