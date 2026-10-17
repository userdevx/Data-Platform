from __future__ import annotations

import json
import os
from typing import Any

from engine.application.model_conversation_action import (
    ModelConversationError,
    process_model_conversation,
)
from engine.intelligence.registry import ToolRegistry


MAX_STEPS = int(
    os.environ.get(
        "DATA_PLATFORM_TOOL_MAX_STEPS",
        "8",
    )
)

MAX_OBSERVATION_CHARACTERS = 6000


class ToolLoopError(RuntimeError):
    """The tool loop could not complete."""


TOOL_SCHEMAS: list[
    dict[str, Any]
] = [
    {
        "type": "function",
        "function": {
            "name": "email_read",
            "description": (
                "Read email metadata from connected accounts. "
                "Supports unread messages and the latest received "
                "message. Returns sender, subject and date metadata. "
                "Message bodies are never returned."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": [
                            "unread",
                            "latest_received",
                        ],
                    },
                    "max_messages": {
                        "type": "integer"
                    },
                    "provider_id": {
                        "type": "string"
                    },
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": (
                "List files in a registered managed workspace."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "workspace_id": {
                        "type": "string"
                    },
                    "path": {
                        "type": "string"
                    },
                    "recursive": {
                        "type": "boolean"
                    },
                },
                "required": [
                    "workspace_id"
                ],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_files",
            "description": (
                "Read text files from a registered managed "
                "workspace."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "workspace_id": {
                        "type": "string"
                    },
                    "paths": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        },
                    },
                },
                "required": [
                    "workspace_id",
                    "paths",
                ],
                "additionalProperties": False,
            },
        },
    },
]


SYSTEM_PROMPT = (
    "You answer using the tools available to you.\n\n"
    "When a request concerns email, files, or anything you cannot "
    "know without looking, call the appropriate tool and answer "
    "from what it returns. Never describe what the user could do "
    "to find out for themselves, and never invent a command, a "
    "file listing, a count, or a message.\n\n"
    "If a tool reports success=false, say plainly what could not "
    "be done. Do not substitute a guess for a value you could not "
    "read.\n\n"
    "Once you have the information you need, give a direct answer "
    "in plain language."
)


def execute_tool(
    name: str,
    arguments: dict[str, Any],
    *,
    registry: ToolRegistry | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    tool_registry = (
        registry
        or ToolRegistry()
    )

    if not tool_registry.has(name):
        return {
            "success": False,
            "error": "tool_not_registered",
            "name": name,
            "available": list(
                tool_registry.names()
            ),
        }

    tool = tool_registry.get(name)

    execute = getattr(
        tool,
        "execute",
        None,
    )

    if not callable(execute):
        return {
            "success": False,
            "error": "tool_not_executable",
            "name": name,
        }

    try:
        result = execute(
            arguments or {},
            context or {},
        )
    except Exception as error:
        return {
            "success": False,
            "error": "tool_failed",
            "name": name,
            "error_type": (
                type(error).__name__
            ),
        }

    if isinstance(result, dict):
        return {
            "success": True,
            **result,
        }

    return {
        "success": True,
        "result": result,
    }


def _first_call(
    message: dict[str, Any],
) -> tuple[
    str | None,
    dict[str, Any],
]:
    calls = (
        message.get("tool_calls")
        or []
    )

    if not calls:
        return None, {}

    function = calls[0].get(
        "function",
        {},
    )

    arguments = function.get(
        "arguments",
        {},
    )

    if isinstance(arguments, str):
        try:
            arguments = json.loads(
                arguments
            )
        except json.JSONDecodeError:
            arguments = {}

    if not isinstance(
        arguments,
        dict,
    ):
        arguments = {}

    return (
        function.get("name"),
        arguments,
    )



def _email_operation_for_question(
    question: str,
) -> str | None:
    normalized = " ".join(
        str(
            question or ""
        ).casefold().split()
    )

    email_context = any(
        term in normalized
        for term in (
            "email",
            "e-mail",
            "inbox",
            "mailbox",
        )
    )

    if not email_context:
        return None

    if "unread" in normalized:
        return "unread"

    latest_markers = (
        "last email",
        "latest email",
        "newest email",
        "most recent email",
        "last received email",
        "latest received email",
        "most recent received email",
        "last email received",
        "latest email received",
        "most recent email received",
    )

    if any(
        marker in normalized
        for marker in latest_markers
    ):
        return "latest_received"

    return None


def _grounded_email_answer(
    *,
    operation: str,
    observation: dict[str, Any],
) -> str:
    if not observation.get(
        "success"
    ):
        return (
            "I couldn't retrieve email from "
            "the connected account."
        )

    messages = observation.get(
        "messages",
        [],
    )

    if not isinstance(
        messages,
        list,
    ):
        messages = []

    if operation == "latest_received":
        if not messages:
            return (
                "No received email metadata "
                "was returned."
            )

        message = messages[0]

        return "\n".join(
            (
                "Latest received email",
                "From: "
                + str(
                    message.get(
                        "from",
                        "",
                    )
                ),
                "Subject: "
                + str(
                    message.get(
                        "subject",
                        "",
                    )
                ),
                "Date: "
                + str(
                    message.get(
                        "date",
                        "",
                    )
                ),
            )
        )

    unread_count = observation.get(
        "unread_count"
    )

    lines = [
        (
            "Unread email count: "
            + str(
                unread_count
            )
        )
    ]

    if messages:
        message = messages[0]

        lines.extend(
            (
                "Most recent unread email",
                "From: "
                + str(
                    message.get(
                        "from",
                        "",
                    )
                ),
                "Subject: "
                + str(
                    message.get(
                        "subject",
                        "",
                    )
                ),
                "Date: "
                + str(
                    message.get(
                        "date",
                        "",
                    )
                ),
            )
        )

    return "\n".join(
        lines
    )


def route_grounded_request(
    question: str,
    *,
    registry: ToolRegistry | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    operation = (
        _email_operation_for_question(
            question
        )
    )

    if operation is None:
        return None

    arguments: dict[str, Any] = {
        "operation": operation,
        "max_messages": (
            1
            if operation
            == "latest_received"
            else 5
        ),
    }

    observation = execute_tool(
        "email_read",
        arguments,
        registry=registry,
        context=context,
    )

    success = bool(
        observation.get(
            "success"
        )
    )

    trajectory = [
        {
            "step": 1,
            "tool": "email_read",
            "arguments": arguments,
            "success": success,
            "error": observation.get(
                "error"
            ),
        }
    ]

    return {
        "status": (
            "success"
            if success
            else "error"
        ),
        "answer": _grounded_email_answer(
            operation=operation,
            observation=observation,
        ),
        "steps": 1,
        "tool_calls": 1,
        "trajectory": trajectory,
        "model": "",
        "provider": "email_service",
        "processing_location": "local",
        "observation": observation,
    }


def run_with_tools(
    question: str,
    *,
    conversation_context: str = "",
    max_steps: int = MAX_STEPS,
    registry: ToolRegistry | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    content = question

    if conversation_context:
        content = (
            "Recent conversation:\n"
            + conversation_context
            + "\n\nRequest: "
            + question
        )

    messages: list[
        dict[str, Any]
    ] = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": content,
        },
    ]

    tool_registry = (
        registry
        or ToolRegistry()
    )

    grounded_result = route_grounded_request(
        question,
        registry=tool_registry,
        context=context,
    )

    if grounded_result is not None:
        return grounded_result

    trajectory: list[
        dict[str, Any]
    ] = []

    model_id = ""
    provider_id = ""
    processing_location = ""

    for step in range(
        1,
        max_steps + 1,
    ):
        try:
            turn = (
                process_model_conversation(
                    messages=messages,
                    tools=TOOL_SCHEMAS,
                )
            )
        except ModelConversationError as error:
            raise ToolLoopError(
                str(error)
            ) from error

        message = turn["message"]

        model_id = turn[
            "model_id"
        ]

        provider_id = turn[
            "provider_id"
        ]

        processing_location = turn[
            "processing_location"
        ]

        name, arguments = _first_call(
            message
        )

        if name is None:
            return {
                "status": "success",
                "answer": str(
                    message.get(
                        "content",
                        "",
                    )
                ).strip(),
                "steps": step,
                "tool_calls": len(
                    trajectory
                ),
                "trajectory": trajectory,
                "model": model_id,
                "provider": provider_id,
                "processing_location": (
                    processing_location
                ),
            }

        observation = execute_tool(
            name,
            arguments,
            registry=tool_registry,
            context=context,
        )

        trajectory.append(
            {
                "step": step,
                "tool": name,
                "arguments": arguments,
                "success": bool(
                    observation.get(
                        "success"
                    )
                ),
                "error": observation.get(
                    "error"
                ),
            }
        )

        messages.append(
            message
        )

        messages.append(
            {
                "role": "tool",
                "name": name,
                "content": json.dumps(
                    observation
                )[
                    :MAX_OBSERVATION_CHARACTERS
                ],
            }
        )

    return {
        "status": "error",
        "answer": "",
        "error": "step_limit_reached",
        "steps": max_steps,
        "tool_calls": len(
            trajectory
        ),
        "trajectory": trajectory,
        "model": model_id,
        "provider": provider_id,
        "processing_location": (
            processing_location
        ),
    }
