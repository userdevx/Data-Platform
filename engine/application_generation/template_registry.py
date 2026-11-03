from __future__ import annotations

import json
from pathlib import Path, PurePosixPath


APPLICATION_TYPES = {
    "Web application": "web",
    "Desktop application": "desktop",
    "Data application": "data",
    "Automation tool": "automation",
}


class TemplateRegistryError(RuntimeError):
    pass


class ApplicationTemplateRegistry:
    """Load deterministic application templates from disk."""

    def __init__(self, template_root: Path | None = None):
        self.template_root = (
            Path(template_root)
            if template_root is not None
            else Path(__file__).parent / "templates"
        ).absolute()

    @staticmethod
    def _check_path(root: Path, relative: str) -> Path:
        if not isinstance(relative, str) or not relative:
            raise TemplateRegistryError("Invalid template path.")

        posix = PurePosixPath(relative)

        if (
            posix.is_absolute()
            or "\\" in relative
            or any(part in ("", ".", "..") for part in relative.split("/"))
            or ":" in relative
        ):
            raise TemplateRegistryError("Unsafe template path.")

        candidate = root.joinpath(*posix.parts)

        current = root
        if root.is_symlink():
            raise TemplateRegistryError("Symlinked template root.")

        for part in posix.parts:
            current = current / part
            if current.is_symlink():
                raise TemplateRegistryError(
                    "Template symlinks are not permitted."
                )

        if not candidate.resolve().is_relative_to(root.resolve()):
            raise TemplateRegistryError(
                "Template escapes its managed directory."
            )

        return candidate

    def load(self, application_type: str) -> dict[str, str]:
        folder = APPLICATION_TYPES.get(application_type)

        if folder is None:
            raise TemplateRegistryError(
                "Unsupported application type."
            )

        root = self._check_path(self.template_root, folder)

        if not root.is_dir():
            raise TemplateRegistryError(
                "Application template directory is missing."
            )

        manifest_path = self._check_path(root, "manifest.json")

        try:
            manifest = json.loads(
                manifest_path.read_text(encoding="utf-8")
            )
        except (OSError, ValueError) as exc:
            raise TemplateRegistryError(
                "Unable to load template manifest."
            ) from exc

        if not isinstance(manifest, dict):
            raise TemplateRegistryError(
                "Template manifest must be an object."
            )

        if manifest.get("version") != 1:
            raise TemplateRegistryError(
                "Unsupported template manifest version."
            )

        files = manifest.get("files")

        if not isinstance(files, dict) or not files:
            raise TemplateRegistryError(
                "Template manifest requires files."
            )

        result: dict[str, str] = {}

        for output_path, template_path in files.items():
            if not isinstance(template_path, str):
                raise TemplateRegistryError(
                    "Invalid template filename."
                )

            self._check_path(root, output_path)
            source = self._check_path(root, template_path)

            if not source.is_file():
                raise TemplateRegistryError(
                    "Template source file is missing."
                )

            if source.stat().st_size > 1024 * 1024:
                raise TemplateRegistryError(
                    "Template exceeds maximum size."
                )

            try:
                result[output_path] = source.read_text(
                    encoding="utf-8"
                )
            except (OSError, UnicodeError) as exc:
                raise TemplateRegistryError(
                    "Unable to read template source."
                ) from exc

        return result
