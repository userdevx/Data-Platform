from engine.memory.extraction import RuleBasedMemoryExtractor


def extract(text: str):
    extractor = RuleBasedMemoryExtractor()

    return extractor.extract(
        user_id="test_user",
        intelligence_id="default",
        conversation_id="test_conversation",
        message_id="test_message",
        text=text,
    )


def test_remember_implementation_examples_should_use_python() -> None:
    candidates = extract(
        "remember that implementation examples should use Python"
    )

    assert len(candidates) == 1

    candidate = candidates[0]

    assert candidate.namespace == "implementation_preferences"
    assert candidate.predicate == "preferred_implementation_language"
    assert candidate.value == "Python"
    assert candidate.explicit_request is True


def test_direct_python_preference() -> None:
    candidates = extract("I prefer Python.")

    assert len(candidates) == 1
    assert candidates[0].value == "Python"


def test_use_python_for_implementation_examples() -> None:
    candidates = extract("Use Python for implementation examples.")

    assert len(candidates) == 1
    assert candidates[0].value == "Python"


def test_code_examples_should_be_written_in_python() -> None:
    candidates = extract("Code examples should be written in Python.")

    assert len(candidates) == 1
    assert candidates[0].value == "Python"


def test_unrelated_sentence_does_not_create_memory() -> None:
    candidates = extract("Explain how a container works.")

    assert candidates == []
