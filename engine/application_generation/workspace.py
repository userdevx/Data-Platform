from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


APPLICATION_ID_PATTERN = re.compile(
    r"[a-z][a-z0-9-]{0,63}\Z"
)


class ApplicationWorkspaceError(RuntimeError):
    pass


@dataclass(frozen=True)
class ApplicationWorkspace:
    application_id: str
    path: Path


class ApplicationWorkspaceManager:
    """Own isolated application-generation workspaces."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = Path(project_root).resolve(
            strict=True
        )

        self.workspace_root = (
            self.project_root
            / "var"
            / "application-generation"
        )

    @staticmethod
    def validate_application_id(
        application_id: str,
    ) -> str:
        if (
            not isinstance(application_id, str)
            or APPLICATION_ID_PATTERN.fullmatch(
                application_id
            ) is None
        ):
            raise ApplicationWorkspaceError(
                "Invalid application identifier."
            )

        if application_id in {".", ".."}:
            raise ApplicationWorkspaceError(
                "Invalid application identifier."
            )

        return application_id

    def _verify_managed_root(self) -> None:
        current = self.project_root

        for component in ("var", "application-generation"):
            current = current / component

            if current.is_symlink():
                raise ApplicationWorkspaceError(
                    "Managed workspace path contains a symlink."
                )

            if current.exists() and not current.is_dir():
                raise ApplicationWorkspaceError(
                    "Managed workspace path is not a directory."
                )

        resolved = self.workspace_root.resolve()

        if not resolved.is_relative_to(self.project_root):
            raise ApplicationWorkspaceError(
                "Workspace root escapes project root."
            )

    def create(
        self,
        application_id: str,
    ) -> ApplicationWorkspace:
        identifier = self.validate_application_id(
            application_id
        )

        self._verify_managed_root()

        self.workspace_root.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._verify_managed_root()

        project_path = self.workspace_root / identifier

        try:
            project_path.mkdir(
                mode=0o755,
                exist_ok=False,
            )
        except FileExistsError as exc:
            raise ApplicationWorkspaceError(
                "Application workspace already exists."
            ) from exc

        return ApplicationWorkspace(
            application_id=identifier,
            path=project_path,
        )

    def get_existing(
        self,
        application_id: str,
    ) -> ApplicationWorkspace:
        identifier = self.validate_application_id(
            application_id
        )

        self._verify_managed_root()

        path = self.workspace_root / identifier

        if path.is_symlink() or not path.is_dir():
            raise ApplicationWorkspaceError(
                "Application workspace does not exist "
                "or is not a regular directory."
            )

        resolved = path.resolve(strict=True)

        if not resolved.is_relative_to(
            self.workspace_root.resolve(strict=True)
        ):
            raise ApplicationWorkspaceError(
                "Application workspace escapes managed root."
            )

        return ApplicationWorkspace(
            application_id=identifier,
            path=resolved,
        )
