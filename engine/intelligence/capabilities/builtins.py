from __future__ import annotations

from pathlib import Path
import json
import re
from datetime import datetime

import subprocess
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from engine.intelligence.memory_runtime import build_memory_context_for_provider, process_memory_command_from_definition

from engine.intelligence.search.public_source_search import PublicSourceSearch
from engine.intelligence.search.source_request_parser import SourceSearchRequestParser


class DateTimeCapability:
    name = "datetime"

    def execute(self, request, instance) -> dict:
        now = datetime.now().astimezone()
        normalized = request.normalized_question

        date_text = now.strftime("%A, %B %-d, %Y")
        time_text = now.strftime("%-I:%M %p %Z").strip()

        if "time" in normalized and "date" not in normalized:
            answer = f"It is {time_text}."
        elif "day" in normalized and "date" not in normalized:
            answer = f"Today is {now.strftime('%A')}."
        else:
            answer = f"Today is {date_text}."

        return {
            "capability": self.name,
            "source": "device_clock",
            "status": "success",
            "answer": answer,
            "data": {
                "action": "Read device clock.",
                "explanation": "Answered from the local device clock.",
                "next_step": "",
                "date": now.date().isoformat(),
                "time": now.strftime("%H:%M:%S"),
                "timezone": now.tzname(),
            },
            "errors": [],
        }


class IdentityCapability:
    name = "identity"

    def execute(self, request, instance) -> dict:
        return {
            "capability": self.name,
            "source": "intelligence_definition",
            "status": "success",
            "answer": (
                f"{instance.display_name} is configured as "
                f"{instance.role}. {instance.definition.identity.description}"
            ),
            "data": {
                "instance_id": instance.instance_id,
                "instance_name": instance.name,
                "instance_role": instance.role,
            },
        }


class SystemStatusCapability:
    name = "system_status"

    def execute(self, request, instance) -> dict:
        return {
            "capability": self.name,
            "source": "system_context",
            "status": "success",
            "answer": "System online.",
            "data": {
                "action": "Checked runtime, storage, Data Engine, and provider configuration.",
                "explanation": "The local system is available and ready to process requests.",
                "next_step": "Submit a request or run a search.",
                "instance_id": instance.instance_id,
                "runtime": "intelligence",
            },
        }


class RecordQueryCapability:
    name = "record_query"

    def execute(self, request, instance) -> dict:
        return {
            "capability": self.name,
            "source": "data_engine",
            "status": "not_implemented",
            "answer": (
                "The request matched record querying, but the Data Engine "
                "query adapter is not connected to the generic runtime yet."
            ),
            "data": {
                "action": "Matched record query route.",
                "explanation": "The runtime recognized a Data Engine query request.",
                "next_step": "Connect the Data Engine query adapter.",
                "allowed_operations": list(
                    instance.definition.data_engine.allowed_operations
                ),
            },
        }


class KnowledgeSearchCapability:
    name = "knowledge_search"

    def execute(self, request, instance) -> dict:
        return {
            "capability": self.name,
            "source": "knowledge",
            "status": "not_implemented",
            "answer": (
                "The request matched knowledge search, but the knowledge "
                "adapter is not connected to the generic runtime yet."
            ),
            "data": {
                "action": "Matched knowledge search route.",
                "explanation": "The runtime recognized a knowledge search request.",
                "next_step": "Connect the knowledge search adapter.",
            },
        }


class PublicSourceSearchCapability:
    name = "public_source_search"

    def execute(self, request, instance) -> dict:
        parser = SourceSearchRequestParser()
        parsed = parser.parse(request.question)

        if parsed.needs_clarification:
            return {
                "capability": self.name,
                "source": "public_source_search",
                "status": "clarification_needed",
                "answer": "More information is needed before running the source search.",
                "data": {
                    "action": "Request clarification.",
                    "explanation": (
                        "The request included a target and a source, but did not "
                        "specify what output should be returned."
                    ),
                    "next_step": parsed.clarification_question,
                    "query": parsed.query,
                    "target_source": parsed.source,
                    "requested_output": "",
                    "clarification_options": [
                        "official profile link",
                        "bio summary",
                        "recent activity",
                        "general results",
                    ],
                },
                "errors": [],
            }

        if not instance.definition.permissions.network_access:
            return {
                "capability": self.name,
                "source": "public_source_search",
                "status": "rejected",
                "answer": "Public source search is disabled by the active configuration.",
                "data": {
                    "action": "Rejected public source search.",
                    "explanation": "Network access must be enabled before public search can run.",
                    "next_step": "Enable network access in the active intelligence definition.",
                    "query": parsed.query,
                    "target_source": parsed.source,
                },
                "errors": ["network_access is false"],
            }

        searcher = PublicSourceSearch()
        result = searcher.search(
            query=parsed.query,
            source=parsed.source,
            requested_output=parsed.requested_output,
            limit=5,
        )

        return {
            "capability": self.name,
            "source": "public_source_search",
            "status": result.get("status", "error"),
            "answer": build_search_answer_from_results(
                query=result.get("query", parsed.query),
                target_source=result.get("target_source", parsed.source),
                results=result.get("results", []),
            ),
            "data": {
                "action": f"Searched {result.get('target_source', parsed.source)}.",
                "explanation": (
                    "The system used the user-provided target and source. "
                    "No names are hardcoded."
                ),
                "next_step": "Open a result or refine the request with more detail.",
                "query": result.get("query", parsed.query),
                "target_source": result.get("target_source", parsed.source),
                "requested_output": parsed.requested_output,
                "search_query": result.get("search_query", ""),
                "search_provider": result.get("search_provider", "public_web_index"),
                "search_method": result.get("search_method", "public_web_index_lookup"),
                "attempted_queries": result.get("attempted_queries", []),
                "results": [
                    {
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "source": item.get("source", ""),
                        "score": item.get("score", 0),
                    }
                    for item in result.get("results", [])
                ],
            },
            "errors": [result["error"]] if result.get("error") else [],
        }


def build_search_answer_from_results(
    *,
    query: str,
    target_source: str | None,
    results: list[dict],
) -> str:
    clean_query = query.strip() or "the request"
    source_label = (target_source or "the web").strip()

    if not results:
        if target_source:
            return f"I could not find a clear result for {clean_query} on {source_label}."

        return f"I could not find a clear result for {clean_query}."

    top_result = results[0]

    title = str(top_result.get("title", "")).strip()
    url = str(top_result.get("url", "")).strip()

    if target_source:
        if title and url:
            return (
                f"I found a result for {clean_query} on {source_label}. "
                f"The top result is {title}. "
                "You can open the source below."
            )

        if title:
            return (
                f"I found a result for {clean_query} on {source_label}. "
                f"The top result is {title}."
            )

        if url:
            return (
                f"I found a result for {clean_query} on {source_label}. "
                "You can open the source below."
            )

        return f"I found a result for {clean_query} on {source_label}."

    if title and url:
        return (
            f"I found a result for {clean_query}. "
            f"The top result is {title}. "
            "You can open the source below."
        )

    if title:
        return f"I found a result for {clean_query}. The top result is {title}."

    return f"I found a result for {clean_query}."




class MemoryCommandCapability:
    name = "memory_command"

    def execute(self, request, instance) -> dict:
        result = process_memory_command_from_definition(
            root=Path.cwd(),
            definition=instance.definition,
            user_text=request.question,
            source=getattr(request, "source", "runtime"),
        )

        mode = result.get("mode")
        created = int(result.get("created", 0))
        deleted = int(result.get("deleted", 0))
        rejected = list(result.get("rejected", []))
        memories = list(result.get("memories", []))

        if mode == "list":
            if not memories:
                answer = "I do not have any saved memories yet."
            else:
                preview = [
                    str(memory.get("canonical_text") or memory.get("value"))
                    for memory in memories[:5]
                ]
                answer = "Here is what I remember:\n" + "\n".join(
                    f"- {item}" for item in preview
                )

            return {
                "capability": self.name,
                "source": "data_engine_memory",
                "status": "success",
                "answer": answer,
                "data": {
                    "action": "Listed active memories.",
                    "explanation": "Memories were retrieved through the Data Engine.",
                    "next_step": "Ask to forget a memory or add a new one.",
                    "memory_count": len(memories),
                    "memories": memories,
                },
                "errors": [],
            }

        if deleted > 0:
            answer = "Got it — I removed that memory."
        elif created > 0:
            answer = "Got it — I’ll remember that."
        elif rejected:
            answer = "I could not save that memory."
        else:
            answer = "I did not find a valid memory to save."

        return {
            "capability": self.name,
            "source": "data_engine_memory",
            "status": "success" if not rejected else "rejected",
            "answer": answer,
            "data": {
                "action": "Processed memory command.",
                "explanation": "The memory command was handled by the Memory Service and Data Engine.",
                "next_step": "Ask a related question to confirm the memory is used.",
                "created": created,
                "deleted": deleted,
                "rejected": rejected,
            },
            "errors": rejected,
        }


def clean_provider_output(text: str) -> str:
    ansi_escape_pattern = re.compile(
        r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])"
    )

    cleaned = ansi_escape_pattern.sub("", text)

    cleaned = cleaned.replace("\b", "")

    control_chars = {
        "\r": "\n",
        "\x00": "",
        "\x01": "",
        "\x02": "",
        "\x03": "",
        "\x04": "",
        "\x05": "",
        "\x06": "",
        "\x07": "",
        "\x0b": "",
        "\x0c": "",
        "\x0e": "",
        "\x0f": "",
    }

    for old, new in control_chars.items():
        cleaned = cleaned.replace(old, new)

    lines = [
        " ".join(line.split())
        for line in cleaned.splitlines()
        if line.strip()
    ]

    return "\n".join(lines).strip()


class ModelReasoningCapability:
    name = "model_reasoning"

    def execute(self, request, instance) -> dict:
        provider = instance.definition.provider

        if not provider.enabled:
            return {
                "capability": self.name,
                "source": "provider",
                "status": "disabled",
                "answer": (
                    "Model reasoning matched the request, but provider use "
                    "is disabled in the active Intelligence Definition."
                ),
                "data": {
                    "action": "Provider disabled.",
                    "explanation": "The active configuration does not allow model reasoning.",
                    "next_step": "Enable a provider or route the request to a deterministic capability.",
                    "provider": provider.name,
                    "model": provider.model,
                },
            }

        if provider.name != "ollama":
            return {
                "capability": self.name,
                "source": "provider",
                "status": "error",
                "answer": "The configured provider is not supported by this runtime path yet.",
                "data": {
                    "provider": provider.name,
                    "model": provider.model,
                },
                "errors": [f"Unsupported provider: {provider.name}"],
            }

        model = provider.model or "llama3.2:3b"

        memory_context = build_memory_context_for_provider(
            root=Path.cwd(),
            definition=instance.definition,
            question=request.question,
        )

        memory_block = ""
        if memory_context:
            memory_block = (
                "\n\nRelevant stored context from the Data Engine:\n"
                f"{memory_context}\n"
            )

        prompt = (
            "Respond naturally to the user.\n"
            "Use plain conversational language.\n"
            "Do not use labels like Answer, Action, Explanation, or Next Step.\n"
            "Do not expose backend routing, provider details, memory internals, or system internals.\n"
            "Keep the response concise unless the user asks for detail.\n"
            "For greetings, respond like a normal conversation.\n"
            "Use relevant stored context only when it helps answer the request.\n"
            f"{memory_block}\n"
            f"User request: {request.question}"
        )

        try:
            answer = self._ollama_api_generate(
                model=model,
                prompt=prompt,
                timeout=90,
            )

            return {
                "capability": self.name,
                "source": "model_provider",
                "status": "success",
                "answer": answer,
                "data": {
                    "action": "Routed request to model reasoning.",
                    "explanation": "The request required provider reasoning after deterministic routing.",
                    "next_step": "Review the response or refine the request.",
                    "provider": provider.name,
                    "model": model,
                    "provider_label": f"ollama:{model}",
                    "execution": "ollama_api",
                    "memory_context_used": bool(memory_context),
                },
                "errors": [],
            }

        except Exception as error:
            return {
                "capability": self.name,
                "source": "model_provider",
                "status": "error",
                "answer": "The selected model provider could not complete the request.",
                "data": {
                    "action": "Model provider request failed.",
                    "explanation": "The provider did not return a successful response.",
                    "next_step": "Try a shorter request or use a deterministic route.",
                    "provider": provider.name,
                    "model": model,
                    "execution": "ollama_api",
                    "error": str(error),
                },
                "errors": [str(error)],
            }

    def _ollama_api_generate(
        self,
        model: str,
        prompt: str,
        timeout: int,
    ) -> str:
        payload = json.dumps(
            {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.2,
                },
            }
        ).encode("utf-8")

        request = Request(
            "http://127.0.0.1:11434/api/generate",
            data=payload,
            headers={
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=timeout) as response:
                response_payload = json.loads(
                    response.read().decode("utf-8")
                )

        except HTTPError as error:
            raise RuntimeError(
                f"Ollama API failed with status {error.code}: {error.reason}"
            ) from error

        except URLError as error:
            raise RuntimeError(
                f"Ollama API is not available: {error.reason}"
            ) from error

        answer = str(response_payload.get("response", "")).strip()

        if not answer:
            raise RuntimeError("Ollama API returned no response text.")

        return clean_provider_output(answer)



CAPABILITIES = {
    "datetime": DateTimeCapability(),
    "memory_command": MemoryCommandCapability(),
    "identity": IdentityCapability(),
    "system_status": SystemStatusCapability(),
    "record_query": RecordQueryCapability(),
    "knowledge_search": KnowledgeSearchCapability(),
    "public_source_search": PublicSourceSearchCapability(),
    "model_reasoning": ModelReasoningCapability(),
}


def get_capability(name: str):
    return CAPABILITIES[name]
