from __future__ import annotations

from dataclasses import dataclass


@dataclass
class QueryClassification:
    intent: str
    route: str
    reason: str


LOCAL_KEYWORDS = {
    "records",
    "record",
    "data",
    "database",
    "storage",
    "logs",
    "log",
    "pipeline",
    "source",
    "sources",
    "recent",
    "count",
    "status",
    "quality",
    "errors",
    "failed",
    "failures",
}

WEB_KEYWORDS = {
    "what is",
    "who is",
    "where is",
    "when is",
    "latest",
    "current",
    "news",
    "today",
}


def classify_query(question: str) -> QueryClassification:
    query = question.strip().lower()

    if not query:
        return QueryClassification(
            intent="empty",
            route="none",
            reason="No question was provided.",
        )

    if any(keyword in query for keyword in LOCAL_KEYWORDS):
        return QueryClassification(
            intent="data_platform_question",
            route="local_reasoning",
            reason="Question appears related to stored platform data.",
        )

    if any(keyword in query for keyword in WEB_KEYWORDS):
        return QueryClassification(
            intent="general_question",
            route="web_or_model_answer",
            reason="Question appears to need general knowledge or web-style answer.",
        )

    return QueryClassification(
        intent="general_question",
        route="web_or_model_answer",
        reason="Default route for general questions.",
    )
