from __future__ import annotations

import os

from pathlib import Path
from engine.application.automatic_model_request_action import (
    process_automatic_model_request,
)
from engine.intelligence.generation_request import (
    IMAGE_GENERATION,
    resolve_generation_capability,
)
import json
import re
from datetime import datetime

import subprocess
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from engine.intelligence.memory_runtime import build_memory_context_for_provider, process_memory_command_from_definition

from engine.intelligence.search.public_source_search import PublicSourceSearch
from engine.intelligence.research.entity_research_service import EntityResearchService
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

    @staticmethod
    def _answer_from_page(page: dict) -> str:
        content = str(
            page.get("content", "")
        ).strip()

        title = str(
            page.get("title", "")
        ).strip()

        if not content:
            return title

        lines = content.splitlines()
        answer_lines: list[str] = []

        for index, line in enumerate(lines):
            stripped = line.strip()

            if (
                index == 0
                and stripped.startswith("#")
            ):
                continue

            if stripped.lower() == "related:":
                break

            if stripped:
                answer_lines.append(
                    stripped
                )

        answer = "\n".join(
            answer_lines
        ).strip()

        if answer:
            return answer

        return content

    def execute(self, request, instance) -> dict:
        tool_result = instance.execute_tool(
            "search_knowledge",
            {
                "query": request.question,
                "limit": 5,
            },
        )

        results = list(
            tool_result.get(
                "results",
                [],
            )
        )

        if not results:
            return {
                "capability": self.name,
                "source": "local_knowledge",
                "status": "not_found",
                "answer": (
                    "No matching local knowledge was found."
                ),
                "data": {
                    "action": (
                        "Searched approved local knowledge."
                    ),
                    "explanation": (
                        "The local knowledge search "
                        "completed without a match."
                    ),
                    "next_step": "",
                    "query": tool_result.get(
                        "query",
                        "",
                    ),
                    "result_count": 0,
                    "evidence": [],
                },
                "errors": [],
            }

        primary = results[0]

        evidence: list[dict] = []

        for page in results:
            content = str(
                page.get(
                    "content",
                    "",
                )
            )

            tags = page.get(
                "tags",
                [],
            )

            if not isinstance(tags, list):
                tags = []

            evidence.append(
                {
                    "source_id": str(
                        page.get(
                            "id",
                            "",
                        )
                    ),
                    "source_type": (
                        "knowledge_page"
                    ),
                    "title": str(
                        page.get(
                            "title",
                            "",
                        )
                    ),
                    "category": str(
                        page.get(
                            "category",
                            "knowledge",
                        )
                    ),
                    "tags": list(tags),
                    "source_excerpt": (
                        content[:500]
                    ),
                }
            )

        return {
            "capability": self.name,
            "source": "local_knowledge",
            "status": "success",
            "answer": self._answer_from_page(
                primary
            ),
            "data": {
                "action": (
                    "Retrieved approved local knowledge."
                ),
                "explanation": (
                    "The request was answered from "
                    "the existing local knowledge store."
                ),
                "next_step": "",
                "query": tool_result.get(
                    "query",
                    "",
                ),
                "result_count": len(
                    results
                ),
                "evidence": evidence,
            },
            "errors": [],
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
                "answer": parsed.clarification_question,
                "data": {
                    "action": "Request a research subject.",
                    "explanation": (
                        "The request did not contain a usable "
                        "research subject."
                    ),
                    "next_step": parsed.clarification_question,
                    "query": "",
                    "target_source": parsed.source,
                    "requested_output": (
                        parsed.requested_output
                    ),
                    "results": [],
                },
                "errors": [],
            }

        if not instance.definition.permissions.network_access:
            return {
                "capability": self.name,
                "source": "public_source_search",
                "status": "rejected",
                "answer": (
                    "Public source search is disabled by "
                    "the active configuration."
                ),
                "data": {
                    "action": (
                        "Rejected public source search."
                    ),
                    "explanation": (
                        "Network access must be enabled "
                        "before public search can run."
                    ),
                    "next_step": (
                        "Enable network access in the active "
                        "intelligence definition."
                    ),
                    "query": parsed.query,
                    "target_source": parsed.source,
                    "results": [],
                },
                "errors": ["network_access is false"],
            }

        if parsed.requested_output == "bio_summary":
            result = EntityResearchService().research(
                query=parsed.query,
                source=parsed.source,
                limit=5,
            )
            answer = result.get("answer", "")
            next_step = (
                "Review the retrieved source excerpts and "
                "open the associated source links."
            )

        else:
            result = PublicSourceSearch().search(
                query=parsed.query,
                source=parsed.source,
                requested_output=(
                    parsed.requested_output
                ),
                limit=8,
            )
            answer = build_search_answer_from_results(
                query=result.get(
                    "query",
                    parsed.query,
                ),
                target_source=result.get(
                    "target_source",
                    parsed.source,
                ),
                results=result.get(
                    "results",
                    [],
                ),
            )
            next_step = (
                "Open a source or request full "
                "entity research."
            )

        return {
            "capability": self.name,
            "source": "public_source_search",
            "status": result.get(
                "status",
                "error",
            ),
            "answer": answer,
            "data": {
                "action": (
                    f"Searched "
                    f"{result.get('target_source', parsed.source)}."
                ),
                "explanation": (
                    "The runtime used the subject and source "
                    "provided at request time."
                ),
                "next_step": next_step,
                "query": result.get(
                    "query",
                    parsed.query,
                ),
                "target_source": result.get(
                    "target_source",
                    parsed.source,
                ),
                "requested_output": (
                    parsed.requested_output
                ),
                "search_query": result.get(
                    "search_query",
                    "",
                ),
                "search_provider": result.get(
                    "search_provider",
                    "public_web_index",
                ),
                "search_method": result.get(
                    "search_method",
                    "",
                ),
                "attempted_queries": result.get(
                    "attempted_queries",
                    [],
                ),
                "research": result.get(
                    "research",
                    {},
                ),
                "results": [
                    {
                        "title": item.get(
                            "title",
                            "",
                        ),
                        "url": item.get(
                            "url",
                            "",
                        ),
                        "source": item.get(
                            "source",
                            "",
                        ),
                        "score": item.get(
                            "score",
                            0,
                        ),
                    }
                    for item in result.get(
                        "results",
                        [],
                    )
                ],
            },
            "errors": (
                [result["error"]]
                if result.get("error")
                else []
            ),
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

        if mode == "lookup":
            selected_memory = result.get("memory")
            value = result.get("value")
            predicate = result.get("predicate")

            if selected_memory and value is not None:
                answer = str(value)
                status = "success"
                errors = []
                action = "Retrieved matching memory."
                explanation = (
                    "The answer was retrieved directly from "
                    "the Data Engine memory store."
                )
                next_step = (
                    "Use the stored preference in the current request."
                )
            else:
                answer = (
                    "I do not have a saved preference for that yet."
                )
                status = "not_found"
                errors = []
                action = "No matching memory found."
                explanation = (
                    "The Data Engine did not contain an active "
                    "memory matching the requested preference."
                )
                next_step = (
                    "Save the preference and ask the question again."
                )

            return {
                "capability": self.name,
                "source": "data_engine_memory",
                "status": status,
                "answer": answer,
                "data": {
                    "action": action,
                    "explanation": explanation,
                    "next_step": next_step,
                    "predicate": predicate,
                    "memory": selected_memory,
                    "memory_count": len(memories),
                    "model_provider_used": False,
                },
                "errors": errors,
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
        provider_policy = (
            instance.definition.provider
        )

        if not provider_policy.enabled:
            return {
                "capability": self.name,
                "source": "provider",
                "status": "disabled",
                "answer": (
                    "Model reasoning is disabled "
                    "in the active Intelligence "
                    "Definition."
                ),
                "data": {
                    "action": (
                        "Provider use disabled."
                    ),
                    "explanation": (
                        "Automatic model reasoning "
                        "is disabled by policy."
                    ),
                    "next_step": (
                        "Enable model provider use "
                        "or use a deterministic "
                        "capability."
                    ),
                },
            }

        required_capability = (
            resolve_generation_capability(
                request.normalized_question
            )
        )

        memory_context = ""

        if (
            required_capability
            != IMAGE_GENERATION
        ):
            memory_context = (
                build_memory_context_for_provider(
                    root=Path.cwd(),
                    definition=(
                        instance.definition
                    ),
                    question=request.question,
                )
            )

        memory_block = ""

        if memory_context:
            memory_block = (
                "\n\nRelevant stored context "
                "from the Data Engine:\n"
                f"{memory_context}\n"
            )

        if (
            required_capability
            == IMAGE_GENERATION
        ):
            prompt = request.question
        else:
            prompt = (
                "Answer the user's request directly.\n"
                "Start with the information or result "
                "the user requested.\n"
                "Do not restate, repeat, summarize, "
                "or paraphrase the user's request "
                "before answering.\n"
                "Do not begin with conversational "
                "acknowledgements or introductory "
                "filler.\n"
                "Use natural, clear language.\n"
                "Do not expose backend routing, "
                "provider details, memory internals, "
                "or system internals.\n"
                "Keep the response concise unless "
                "the user asks for detail.\n"
                "Use relevant stored context only "
                "when it materially helps answer "
                "the request.\n"
                f"{memory_block}\n"
                f"User request: {request.question}"
            )

        try:
            provider_result = (
                process_automatic_model_request(
                    question=prompt,
                    required_capability=(
                        required_capability
                    ),
                    request_id=(
                        request.request_id
                    ),
                )
            )

            answer = str(
                provider_result.get(
                    "answer",
                    "",
                )
            ).strip()

            if not answer:
                raise RuntimeError(
                    "The selected model returned "
                    "no answer."
                )

            raw = provider_result.get(
                "raw",
                {},
            )

            if not isinstance(
                raw,
                dict,
            ):
                raw = {}

            provider_id = str(
                raw.get(
                    "provider_id",
                    "",
                )
            )

            model_id = str(
                raw.get(
                    "model_id",
                    "",
                )
            )

            provider_metadata = raw.get(
                "metadata",
                {},
            )

            if not isinstance(
                provider_metadata,
                dict,
            ):
                provider_metadata = {}

            selection = raw.get(
                "selection",
                {},
            )

            if not isinstance(
                selection,
                dict,
            ):
                selection = {}

            if (
                required_capability
                == IMAGE_GENERATION
            ):
                image_data_url = str(
                    provider_metadata.get(
                        "image_data_url",
                        "",
                    )
                )

                output_path = str(
                    provider_metadata.get(
                        "output_path",
                        "",
                    )
                )

                mime_type = str(
                    provider_metadata.get(
                        "mime_type",
                        "image/png",
                    )
                )

                if not image_data_url:
                    raise RuntimeError(
                        "The image model completed "
                        "without returning an image."
                    )

                return {
                    "capability": (
                        IMAGE_GENERATION
                    ),
                    "source": (
                        "model_provider"
                    ),
                    "status": "success",
                    "answer": (
                        "Image generated."
                    ),
                    "data": {
                        "action": (
                            "Generated image."
                        ),
                        "explanation": (
                            "Automatic routing "
                            "selected an available "
                            "image-generation model."
                        ),
                        "next_step": "",
                        "provider": provider_id,
                        "model": model_id,
                        "execution": (
                            "automatic_model_selection"
                        ),
                        "selection": selection,
                        "output": {
                            "type": "image",
                            "mime_type": (
                                mime_type
                            ),
                            "path": (
                                output_path
                            ),
                            "data_url": (
                                image_data_url
                            ),
                        },
                    },
                    "errors": [],
                }

            return {
                "capability": self.name,
                "source": "model_provider",
                "status": "success",
                "answer": answer,
                "data": {
                    "action": (
                        "Automatically selected "
                        "a compatible model."
                    ),
                    "explanation": (
                        "The Intelligence Layer "
                        "selected a model after "
                        "deterministic routing."
                    ),
                    "next_step": (
                        "Review the response or "
                        "refine the request."
                    ),
                    "provider": provider_id,
                    "model": model_id,
                    "provider_label": (
                        f"{provider_id}:"
                        f"{model_id}"
                    ),
                    "execution": (
                        "automatic_model_selection"
                    ),
                    "provider_metadata": (
                        provider_metadata
                    ),
                    "selection": selection,
                    "memory_context_used": (
                        bool(memory_context)
                    ),
                },
                "errors": [],
            }

        except Exception as error:
            return {
                "capability": self.name,
                "source": "model_provider",
                "status": "error",
                "answer": (
                    "No compatible model could "
                    "complete the request."
                ),
                "data": {
                    "action": (
                        "Automatic model "
                        "selection failed."
                    ),
                    "explanation": (
                        "No compatible model "
                        "completed the required "
                        "capability."
                    ),
                    "next_step": (
                        "Review provider health "
                        "and model capabilities."
                    ),
                    "execution": (
                        "automatic_model_selection"
                    ),
                    "error": str(error),
                },
                "errors": [
                    str(error)
                ],
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

        ollama_base_url = os.getenv(
            "OLLAMA_BASE_URL",
            "http://127.0.0.1:11434",
        ).rstrip("/")

        request = Request(
            f"{ollama_base_url}/api/generate",
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
