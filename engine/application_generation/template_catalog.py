from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


class TemplateCatalogError(RuntimeError):
    pass


IDENTIFIER = re.compile(r"[a-z][a-z0-9-]{0,63}\Z")

ALLOWED_RENDER_MODES = frozenset({
    "literal",
    "html",
    "python-string",
})


@dataclass(frozen=True)
class TemplateFile:
    source: str
    destination: str
    render_mode: str


@dataclass(frozen=True)
class TemplateDefinition:
    template_id: str
    display_name: str
    category: str
    language: str
    framework: str | None
    platforms: tuple[str, ...]
    capabilities: tuple[str, ...]
    files: tuple[TemplateFile, ...]
    directory: Path


def _identifier(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise TemplateCatalogError(f"Invalid {field}.")

    if IDENTIFIER.fullmatch(value) is None:
        raise TemplateCatalogError(f"Invalid {field}.")

    return value


def _relative_path(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise TemplateCatalogError("Invalid file path.")

    if (
        "\x00" in value
        or "\\" in value
        or ":" in value
        or any(
            part in ("", ".", "..")
            for part in value.split("/")
        )
    ):
        raise TemplateCatalogError("Unsafe file path.")

    path = PurePosixPath(value)

    if path.is_absolute():
        raise TemplateCatalogError("Absolute path rejected.")

    return value


def _string_array(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise TemplateCatalogError(f"Invalid {field}.")

    if not value:
        raise TemplateCatalogError(f"Empty {field}.")

    result = tuple(_identifier(item, field) for item in value)

    if len(result) != len(set(result)):
        raise TemplateCatalogError(f"Duplicate {field}.")

    return result


class ApplicationTemplateCatalog:
    """Discover template definitions without fixed application types."""

    def __init__(self, template_root: Path | None = None):
        self.root = (
            Path(template_root)
            if template_root is not None
            else Path(__file__).parent / "templates"
        ).absolute()

    def _check_root(self) -> None:
        if self.root.is_symlink():
            raise TemplateCatalogError(
                "Symlinked template root rejected."
            )

        if not self.root.is_dir():
            raise TemplateCatalogError(
                "Template root does not exist."
            )

    @staticmethod
    def _safe_file(directory: Path, relative: str) -> Path:
        _relative_path(relative)

        current = directory

        for part in relative.split("/"):
            current = current / part

            if current.is_symlink():
                raise TemplateCatalogError(
                    "Symlinked template file rejected."
                )

        candidate = current

        if not candidate.resolve().is_relative_to(
            directory.resolve()
        ):
            raise TemplateCatalogError(
                "Template path escapes directory."
            )

        if not candidate.is_file():
            raise TemplateCatalogError(
                f"Template file missing: {relative}"
            )

        if candidate.stat().st_size > 1024 * 1024:
            raise TemplateCatalogError(
                "Template file exceeds 1 MiB."
            )

        return candidate

    def _load_definition(
        self,
        directory: Path,
    ) -> TemplateDefinition:
        manifest_path = self._safe_file(
            directory,
            "manifest.json",
        )

        try:
            document = json.loads(
                manifest_path.read_text(encoding="utf-8")
            )
        except (ValueError, OSError, UnicodeError) as exc:
            raise TemplateCatalogError(
                "Invalid template manifest."
            ) from exc

        if not isinstance(document, dict):
            raise TemplateCatalogError(
                "Manifest must be a JSON object."
            )

        if document.get("schema_version") != 1:
            raise TemplateCatalogError(
                "Unsupported manifest schema."
            )

        template_id = _identifier(
            document.get("template_id"),
            "template_id",
        )

        display_name = document.get("display_name")

        if (
            not isinstance(display_name, str)
            or not display_name.strip()
        ):
            raise TemplateCatalogError(
                "Invalid display name."
            )

        category = _identifier(
            document.get("category"),
            "category",
        )
        language = _identifier(
            document.get("language"),
            "language",
        )

        framework = document.get("framework")

        if framework is not None:
            framework = _identifier(
                framework,
                "framework",
            )

        platforms = _string_array(
            document.get("platforms"),
            "platforms",
        )
        capabilities = _string_array(
            document.get("capabilities"),
            "capabilities",
        )

        file_entries = document.get("files")

        if not isinstance(file_entries, list) or not file_entries:
            raise TemplateCatalogError(
                "Manifest must declare files."
            )

        files = []
        destinations = set()

        for entry in file_entries:
            if not isinstance(entry, dict):
                raise TemplateCatalogError(
                    "Invalid file declaration."
                )

            source = _relative_path(entry.get("source"))
            destination = _relative_path(
                entry.get("destination")
            )
            render_mode = entry.get("render_mode")

            if render_mode not in ALLOWED_RENDER_MODES:
                raise TemplateCatalogError(
                    "Unsupported rendering mode."
                )

            if destination in destinations:
                raise TemplateCatalogError(
                    "Duplicate output destination."
                )

            destinations.add(destination)

            self._safe_file(directory, source)

            files.append(
                TemplateFile(
                    source=source,
                    destination=destination,
                    render_mode=render_mode,
                )
            )

        return TemplateDefinition(
            template_id=template_id,
            display_name=display_name,
            category=category,
            language=language,
            framework=framework,
            platforms=platforms,
            capabilities=capabilities,
            files=tuple(files),
            directory=directory,
        )

    def discover(self) -> dict[str, TemplateDefinition]:
        self._check_root()

        definitions = {}

        for directory in sorted(self.root.iterdir()):
            if directory.name.startswith("_"):
                continue

            if directory.is_symlink():
                raise TemplateCatalogError(
                    "Symlinked template directory rejected."
                )

            if not directory.is_dir():
                continue

            manifest = directory / "manifest.json"

            if not manifest.exists() and not manifest.is_symlink():
                continue

            definition = self._load_definition(directory)

            if definition.template_id in definitions:
                raise TemplateCatalogError(
                    "Duplicate template identifier."
                )

            definitions[definition.template_id] = definition

        return definitions

    def get(self, template_id: str) -> TemplateDefinition:
        _identifier(template_id, "template_id")

        definitions = self.discover()

        if template_id not in definitions:
            raise TemplateCatalogError(
                "Template is not registered."
            )

        return definitions[template_id]

    def read_files(
        self,
        template_id: str,
    ) -> dict[str, str]:
        definition = self.get(template_id)
        result = {}

        for entry in definition.files:
            source = self._safe_file(
                definition.directory,
                entry.source,
            )
            try:
                result[entry.destination] = source.read_text(
                    encoding="utf-8"
                )
            except (OSError, UnicodeError) as exc:
                raise TemplateCatalogError(
                    "Cannot read template content."
                ) from exc

        return result
