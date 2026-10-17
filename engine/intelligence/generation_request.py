from __future__ import annotations

import re


TEXT_INPUT = "text_input"
CODE_GENERATION = "code_generation"

IMAGE_GENERATION = (
    "image_generation"
)

APPLICATION_GENERATION = (
    "application_generation"
)


def _tokenize(
    text: str,
) -> frozenset[str]:
    return frozenset(
        re.findall(
            r"[a-z0-9]+",
            str(text).lower(),
        )
    )


def is_simple_code_request(
    text: str,
) -> bool:
    """
    Return True for a bounded request whose output is source code,
    rather than a request to create or modify an application.

    This classification is language/provider independent.
    """

    normalized = " ".join(
        str(text).lower().split()
    ).strip()

    if not normalized:
        return False
    else:
        tokens = _tokenize(
            normalized
        )

    code_subjects = frozenset(
        {
            "code",
            "function",
            "method",
            "class",
            "script",
            "algorithm",
            "program",
            "python",
            "javascript",
            "typescript",
            "java",
            "rust",
            "sql",
        }
    )

    code_actions = frozenset(
        {
            "write",
            "create",
            "generate",
            "fix",
            "correct",
            "refactor",
            "debug",
            "complete",
            "explain",
            "rewrite",
        }
    )

    application_scope = frozenset(
        {
            "application",
            "app",
            "software",
            "project",
            "repository",
            "repo",
            "codebase",
            "workspace",
            "package",
            "desktop",
            "mobile",
            "server",
            "client",
            "deploy",
            "deployment",
            "release",
        }
    )

    has_code_subject = bool(
        tokens
        & code_subjects
    )

    has_code_action = bool(
        tokens
        & code_actions
    )

    has_application_scope = bool(
        tokens
        & application_scope
    )

    if has_application_scope:
        return False
    elif (
        has_code_subject
        and has_code_action
    ):
        return True
    else:
        return False


def resolve_generation_capability(
    text: str,
) -> str:
    tokens = _tokenize(
        text
    )

    if not tokens:
        return TEXT_INPUT

    if is_simple_code_request(text):
        return CODE_GENERATION
    else:
        pass

    image_terms = frozenset(
        {
            "image",
            "images",
            "picture",
            "pictures",
            "photo",
            "photos",
            "illustration",
            "illustrations",
            "drawing",
            "drawings",
            "artwork",
            "graphic",
            "graphics",
            "render",
            "renders",
        }
    )

    image_actions = frozenset(
        {
            "create",
            "generate",
            "make",
            "draw",
            "render",
            "produce",
        }
    )

    if (
        bool(
            tokens
            & image_terms
        )
        and bool(
            tokens
            & image_actions
        )
    ):
        return IMAGE_GENERATION

    software_terms = frozenset(
        {
            "application",
            "applications",
            "app",
            "apps",
            "software",
            "program",
            "programs",
            "code",
            "script",
            "scripts",
            "website",
            "webapp",
            "api",
            "service",
            "cli",
            "game",
            "repository",
            "repo",
            "codebase",
            "project",
            "source",
            "file",
            "files",
            "folder",
            "folders",
            "directory",
            "directories",
            "module",
            "modules",
        }
    )

    software_actions = frozenset(
        {
            "create",
            "generate",
            "make",
            "build",
            "develop",
            "implement",
            "write",
            "produce",
            "provide",
            "show",
            "give",
            "add",
            "modify",
            "change",
            "update",
            "fix",
            "refactor",
            "extend",
            "inspect",
            "scan",
            "list",
            "read",
            "analyze",
        }
    )

    if (
        bool(
            tokens
            & software_terms
        )
        and bool(
            tokens
            & software_actions
        )
    ):
        return APPLICATION_GENERATION

    return TEXT_INPUT
