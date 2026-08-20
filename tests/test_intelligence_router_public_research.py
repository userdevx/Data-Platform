from uuid import uuid4

from engine.intelligence.router import IntelligenceRouter


def dynamic_subject() -> str:
    return f"subject-{uuid4().hex}"


def test_who_is_question_requires_public_research():
    router = IntelligenceRouter()
    question = f"who is {dynamic_subject()}?"

    assert router._public_source_search(question) is True


def test_who_was_question_requires_public_research():
    router = IntelligenceRouter()
    question = f"who was {dynamic_subject()}?"

    assert router._public_source_search(question) is True


def test_tell_me_about_question_requires_public_research():
    router = IntelligenceRouter()
    question = f"tell me about {dynamic_subject()}"

    assert router._public_source_search(question) is True


def test_biography_question_requires_public_research():
    router = IntelligenceRouter()
    question = f"give me a biography of {dynamic_subject()}"

    assert router._public_source_search(question) is True


def test_current_role_question_requires_public_research():
    router = IntelligenceRouter()
    question = f"who is the current {dynamic_subject()}?"

    assert router._public_source_search(question) is True


def test_explicit_web_search_requires_public_research():
    router = IntelligenceRouter()
    question = f"search the web for {dynamic_subject()}"

    assert router._public_source_search(question) is True


def test_general_creation_request_does_not_require_public_research():
    router = IntelligenceRouter()
    question = f"create a plan for {dynamic_subject()}"

    assert router._public_source_search(question) is False


def test_internal_record_request_does_not_require_public_research():
    router = IntelligenceRouter()
    question = "show stored records"

    assert router._public_source_search(question) is False


def test_empty_question_does_not_require_public_research():
    router = IntelligenceRouter()

    assert router._public_source_search("") is False
