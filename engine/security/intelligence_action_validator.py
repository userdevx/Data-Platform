import fnmatch
import re
from pathlib import Path
from typing import Any

from engine.security.intelligence_action_request import IntelligenceActionRequest
from engine.security.intelligence_execution_manifest import INTELLIGENCE_EXECUTION_MANIFEST


class IntelligenceSecurityError(Exception):
    pass


class IntelligenceValidationError(Exception):
    pass


SAFE_PATH_PATTERN = re.compile(r"^[a-zA-Z0-9/_\-. ]+$")
API_ENDPOINT_PATTERN = re.compile(r"^/[a-zA-Z0-9/_\-.]*$")


def validate_intelligence_action_request(action_request: IntelligenceActionRequest) -> None:
    validate_tool_exists(action_request.tool_name)
    validate_tool_enabled(action_request.tool_name)
    validate_tool_risk(action_request.tool_name)
    validate_params(action_request.tool_name, action_request.params)
    validate_file_boundaries(action_request.tool_name, action_request.params)
    validate_network_boundaries(action_request.tool_name, action_request.params)


def validate_tool_exists(tool_name: str) -> None:
    if not isinstance(tool_name, str):
        raise IntelligenceValidationError("Tool name must be a string.")

    if not tool_name.strip():
        raise IntelligenceValidationError("Tool name cannot be empty.")

    if tool_name not in INTELLIGENCE_EXECUTION_MANIFEST:
        raise IntelligenceSecurityError(f"Tool is not registered: {tool_name}")


def validate_tool_enabled(tool_name: str) -> None:
    rule = INTELLIGENCE_EXECUTION_MANIFEST[tool_name]

    if rule.get("enabled") is not True:
        raise IntelligenceSecurityError(f"Tool is disabled: {tool_name}")


def validate_tool_risk(tool_name: str) -> None:
    rule = INTELLIGENCE_EXECUTION_MANIFEST[tool_name]

    if rule.get("risk") == "critical":
        raise IntelligenceSecurityError(f"Critical-risk tool is blocked: {tool_name}")


def validate_params(tool_name: str, params: dict[str, Any]) -> None:
    if not isinstance(params, dict):
        raise IntelligenceValidationError("Params must be a dictionary.")

    rule = INTELLIGENCE_EXECUTION_MANIFEST[tool_name]
    schema = rule.get("allowed_params", {})

    incoming_keys = set(params.keys())
    allowed_keys = set(schema.keys())
    unknown_keys = incoming_keys - allowed_keys

    if unknown_keys:
        joined = ", ".join(sorted(unknown_keys))
        raise IntelligenceValidationError(f"Unsupported params: {joined}")

    for param_name, param_rule in schema.items():
        required = param_rule.get("required", False)

        if required and param_name not in params:
            raise IntelligenceValidationError(f"Missing required param: {param_name}")

        if param_name not in params:
            continue

        value = params[param_name]
        expected_type = param_rule.get("type")

        if expected_type == "string":
            validate_string_param(param_name, value, param_rule)
        elif expected_type == "integer":
            validate_integer_param(param_name, value, param_rule)
        else:
            raise IntelligenceValidationError(
                f"Unsupported schema type for param {param_name}: {expected_type}"
            )


def validate_string_param(
    param_name: str,
    value: Any,
    param_rule: dict[str, Any],
) -> None:
    if not isinstance(value, str):
        raise IntelligenceValidationError(f"Param must be a string: {param_name}")

    max_length = param_rule.get("max_length")

    if max_length is not None and len(value) > max_length:
        raise IntelligenceValidationError(f"Param is too long: {param_name}")

    enum_values = param_rule.get("enum")

    if enum_values is not None and value not in enum_values:
        raise IntelligenceValidationError(f"Param has unsupported value: {param_name}")

    pattern = param_rule.get("pattern")

    if pattern == "safe_path" and not SAFE_PATH_PATTERN.match(value):
        raise IntelligenceValidationError(f"Path contains unsafe characters: {param_name}")

    if pattern == "api_endpoint" and not API_ENDPOINT_PATTERN.match(value):
        raise IntelligenceValidationError(f"Endpoint contains unsafe characters: {param_name}")


def validate_integer_param(
    param_name: str,
    value: Any,
    param_rule: dict[str, Any],
) -> None:
    if not isinstance(value, int):
        raise IntelligenceValidationError(f"Param must be an integer: {param_name}")

    minimum = param_rule.get("minimum")
    maximum = param_rule.get("maximum")

    if minimum is not None and value < minimum:
        raise IntelligenceValidationError(f"Param is below minimum: {param_name}")

    if maximum is not None and value > maximum:
        raise IntelligenceValidationError(f"Param is above maximum: {param_name}")


def validate_file_boundaries(tool_name: str, params: dict[str, Any]) -> None:
    if tool_name != "files.read_approved":
        return

    rule = INTELLIGENCE_EXECUTION_MANIFEST[tool_name]
    path_value = params.get("path")

    if not isinstance(path_value, str):
        raise IntelligenceValidationError("File path must be a string.")

    normalized_path = normalize_path(path_value)

    allowed_paths = rule.get("allowed_paths", [])
    forbidden_paths = rule.get("forbidden_paths", [])

    is_allowed = any(
        fnmatch.fnmatch(normalized_path, pattern)
        for pattern in allowed_paths
    )

    if not is_allowed:
        raise IntelligenceSecurityError(f"Path is not in approved folders: {path_value}")

    for pattern in forbidden_paths:
        if fnmatch.fnmatch(normalized_path, pattern):
            raise IntelligenceSecurityError(f"Path is forbidden: {path_value}")


def validate_network_boundaries(tool_name: str, params: dict[str, Any]) -> None:
    if tool_name != "network.call_approved_api":
        return

    rule = INTELLIGENCE_EXECUTION_MANIFEST[tool_name]
    domain = params.get("domain")

    if not isinstance(domain, str):
        raise IntelligenceValidationError("Domain must be a string.")

    normalized_domain = domain.lower().strip()

    allowed_domains = set(rule.get("allowed_domains", []))
    forbidden_domains = set(rule.get("forbidden_domains", []))

    if normalized_domain in forbidden_domains:
        raise IntelligenceSecurityError(f"Domain is forbidden: {normalized_domain}")

    if normalized_domain not in allowed_domains:
        raise IntelligenceSecurityError(f"Domain is not allowlisted: {normalized_domain}")


def normalize_path(path_value: str) -> str:
    normalized = str(Path(path_value)).replace("\\", "/")

    if Path(normalized).is_absolute():
        raise IntelligenceSecurityError("Absolute paths are blocked.")

    if ".." in Path(normalized).parts:
        raise IntelligenceSecurityError("Path traversal is blocked.")

    return normalized
