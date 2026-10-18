#!/usr/bin/env python3
"""Create a skill scaffold using the create-skill metadata contract."""
from pathlib import Path
import argparse
import json
import re
import sys

KEYS = {
    "schema_version", "id", "name", "description", "version",
    "required_tools",
}
ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
TOOL = re.compile(r"[A-Za-z0-9_]+(?:[.:/-][A-Za-z0-9_]+)*")
VERSION = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)")
SECTIONS = (
    "Purpose", "When to use", "When not to use", "Inputs",
    "Preconditions", "Instructions", "Governance", "Models and runtimes",
    "Data and provenance", "Outputs", "Failure handling",
    "Verification", "Resources", "Completion report",
)


def checked(root, path):
    root = root.resolve()
    if not path.is_relative_to(root):
        raise ValueError(f"path outside skills root: {path}")
    current = root
    for part in path.relative_to(root).parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"symlink is not allowed: {current}")
    if not path.resolve().is_relative_to(root):
        raise ValueError(f"path resolves outside skills root: {path}")
    return path


def single_line(value, label):
    if any(character in value for character in "\r\n"):
        raise ValueError(f"{label} must be a single line")
    value = value.strip()
    if not value:
        raise ValueError(f"{label} must not be empty")
    return value


def read_metadata(path):
    # Deliberately supports one JSON-compatible value per front-matter line.
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "---":
        raise ValueError(f"{path}: missing front matter")
    try:
        end = lines.index("---", 1)
    except ValueError:
        raise ValueError(f"{path}: unclosed front matter") from None
    result = {}
    for line in lines[1:end]:
        key, separator, value = line.partition(":")
        key = key.strip()
        if not separator or not key or key in result:
            raise ValueError(f"{path}: invalid or repeated metadata key")
        result[key] = json.loads(value.strip())
    if set(result) != KEYS:
        raise ValueError(f"{path}: expected metadata keys {sorted(KEYS)}")
    if type(result["schema_version"]) is not int or result["schema_version"] != 1:
        raise ValueError(f"{path}: unsupported schema_version")
    for key in ("id", "name", "description", "version"):
        if not isinstance(result[key], str):
            raise ValueError(f"{path}: {key} must be a string")
        single_line(result[key], key)
    if not ID.fullmatch(result["id"]):
        raise ValueError(f"{path}: invalid id")
    if not VERSION.fullmatch(result["version"]):
        raise ValueError(f"{path}: invalid version")
    tools = result["required_tools"]
    if not isinstance(tools, list) or any(
        not isinstance(tool, str) or not TOOL.fullmatch(tool)
        for tool in tools
    ):
        raise ValueError(f"{path}: invalid required_tools")
    if len(tools) != len(set(tools)):
        raise ValueError(f"{path}: repeated tool identifiers")
    return result


def inventory(root):
    found = {}
    for folder in sorted(root.iterdir()):
        if folder.name.startswith("_"):
            continue
        if folder.is_symlink():
            raise ValueError(f"symlinked package is not allowed: {folder}")
        if not folder.is_dir():
            continue
        path = checked(root, folder / "SKILL.md")
        if not path.exists():
            continue
        metadata = read_metadata(path)
        identifier = metadata["id"]
        if identifier in found:
            raise ValueError(f"duplicate skill id: {identifier}")
        found[identifier] = path
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("id")
    parser.add_argument("--name", required=True)
    parser.add_argument("--description", required=True)
    parser.add_argument("--version", default="0.1.0")
    parser.add_argument("--tool", action="append", default=[])
    parser.add_argument("--skills-dir", default="skills")
    args = parser.parse_args()

    if not ID.fullmatch(args.id):
        raise ValueError("id must use lowercase letters, digits and single hyphens")
    name = single_line(args.name, "name")
    description = single_line(args.description, "description")
    if not VERSION.fullmatch(args.version):
        raise ValueError("version must use MAJOR.MINOR.PATCH")
    tools = list(dict.fromkeys(args.tool))
    if any(not TOOL.fullmatch(tool) for tool in tools):
        raise ValueError("invalid tool identifier")

    supplied = Path(args.skills_dir).absolute()
    for component in (supplied, *supplied.parents):
        if component.is_symlink():
            raise ValueError(f"symlinked skills path: {component}")
    if not supplied.is_dir():
        raise ValueError(f"skills directory does not exist: {supplied}")
    root = supplied.resolve()
    contract_path = checked(root, root / "create-skill" / "SKILL.md")
    contract = read_metadata(contract_path)
    if contract["id"] != "create-skill":
        raise ValueError("creation contract must have id create-skill")

    if args.id in inventory(root):
        raise ValueError(f"skill id already exists: {args.id}")
    package = checked(root, root / args.id)
    if package.exists():
        raise ValueError(f"refusing to overwrite: {package}")

    values = {
        "schema_version": contract["schema_version"],
        "id": args.id,
        "name": name,
        "description": description,
        "version": args.version,
        "required_tools": tools,
    }
    front = "".join(
        f"{key}: {json.dumps(value, ensure_ascii=False)}\n"
        for key, value in values.items()
    )
    body = f"# {name}\n" + "".join(
        f"\n## {section}\n" for section in SECTIONS
    )
    content = f"---\n{front}---\n\n{body}"
    target = package / "SKILL.md"
    package.mkdir()
    created = False
    try:
        with target.open("x", encoding="utf-8", newline="\n") as stream:
            created = True
            stream.write(content)
        if target.read_text(encoding="utf-8") != content:
            raise ValueError("written content differs")
        read_metadata(target)
    except BaseException:
        if created:
            target.unlink()
        package.rmdir()
        raise

    print(target)
    print("Package scaffold created; task-specific instructions remain to be authored.")
    if tools:
        print("Tool identifiers were syntax-checked; registry availability was not checked.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
