from __future__ import annotations

import re
from dataclasses import dataclass


# Questions whose answers are general knowledge. Nothing about the
# user's world is established by asking them.
_GENERAL_KNOWLEDGE = re.compile(
    r"^(hi|hello|hey|thanks|thank you|ok|okay|yes|no|sure)\b"
    r"|^(what is|what are|who is|who are|when was|where is|"
    r"define|explain)\s"
    # Instruction and how-to shapes. A first-person pronoun inside a
    # request ("how do i ...") is grammar, not a durable assertion.
    r"|^(how do i|how do we|how can i|how to|can you|could you|"
    r"please|show me|list|tell me)\b"
)

# Text-in shapes that establish something durable. Any one is enough.
_DURABLE_SIGNALS = (
    # Personal fact, preference, or situation.
    re.compile(r"\b(i|i'm|i am|my|mine|we|we're|we are|our)\b"),
    # Declared state of the project or system, with no first person.
    # "Data Engine is the system of record" must qualify.
    re.compile(
        r"\b(is|are|will be|must|should|shall|becomes?)\s+"
        r"(the\s+)?(system of record|canonical|authoritative|required|"
        r"deprecated|removed|renamed|standard|default|invariant)\b"
    ),
    # Decisions and rules.
    re.compile(
        r"\b(decided|decision|we chose|use|prefer|always|never|"
        r"do not|don't|rule|policy|convention|invariant)\b"
    ),
    # Naming and identity assertions.
    re.compile(r"\b(called|named|refers? to|means)\b"),
)


@dataclass(frozen=True)
class ExtractionDecision:
    extract: bool
    reason: str
    matched_signal: int | None = None

    def as_record_value(self, *, conversation_id: str) -> dict:
        return {
            "conversation_id": conversation_id,
            "extracted": self.extract,
            "reason": self.reason,
            "matched_signal": self.matched_signal,
        }


def decide(
    *,
    normalized_question: str,
    answer: str = "",
) -> ExtractionDecision:
    """
    Deterministic gate run before any extraction model call.

    The decision rests on the text-in. A user can state something
    durable and receive a one-line acknowledgement, so answer length
    is not evidence either way. The answer is accepted as a parameter
    only so a later revision can use it without changing callers.
    """

    question = (normalized_question or "").strip().lower()

    if not question:
        return ExtractionDecision(False, "empty_question")

    if _GENERAL_KNOWLEDGE.match(question):
        return ExtractionDecision(False, "general_knowledge_question")

    for index, signal in enumerate(_DURABLE_SIGNALS):
        if signal.search(question):
            return ExtractionDecision(True, "durable_signal", index)

    return ExtractionDecision(False, "no_durable_signal")
