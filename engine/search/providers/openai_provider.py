from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()

SearchResult = dict[str, Any]


def get_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is missing from .env")

    return OpenAI(api_key=api_key)


def search_openai(query: str, limit: int = 5) -> list[SearchResult]:
    clean_query = query.strip()

    if not clean_query:
        return []

    client = get_client()
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

    prompt = f"""
You are the configured intelligence runtime. Use the active intelligence definition for identity, capabilities, and behavior.

Answer the user's question clearly.
Do not return unrelated local records.

User question:
{clean_query}
"""

    response = client.responses.create(
        model=model,
        input=prompt,
    )

    answer = response.output_text.strip()

    return [
        {
            "title": "Intelligence Answer",
            "url": "",
            "source_excerpt": answer or "The intelligence runtime could not generate an answer.",
            "provider": "openai_answer",
            "query": clean_query,
            "score": 999,
            "answer_type": "direct_answer",
            "rank": 1,
        }
    ][:limit]
