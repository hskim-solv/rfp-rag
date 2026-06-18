from __future__ import annotations

from pathlib import Path


class ArtifactPathError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def _contains_symlink(path: Path, root: Path) -> bool:
    candidates = [path, *path.parents]
    for candidate in candidates:
        if candidate == root.parent:
            break
        if candidate.exists() and candidate.is_symlink():
            return True
    return False


def safe_artifact_path(
    path: Path | str,
    *,
    root: Path | str = Path("."),
    allowed_prefixes: tuple[str, ...] = ("artifacts",),
    allowed_relatives: tuple[str, ...] = (),
    expected_name: str | None = None,
) -> Path:
    """Resolve a user-supplied local artifact path without allowing escapes."""

    root_path = Path(root).resolve()
    candidate = Path(path)
    resolved = (
        candidate.resolve()
        if candidate.is_absolute()
        else (root_path / candidate).resolve()
    )
    try:
        relative = resolved.relative_to(root_path)
    except ValueError as exc:
        raise ArtifactPathError(
            "artifact_path_not_allowed",
            f"path {path!s} must stay under repository root {root_path}",
        ) from exc

    relative_text = relative.as_posix()
    if allowed_relatives and relative_text not in allowed_relatives:
        raise ArtifactPathError(
            "artifact_path_not_allowed",
            f"path {relative_text} is not an approved artifact path",
        )
    if not allowed_relatives:
        first = relative.parts[0] if relative.parts else ""
        if first not in allowed_prefixes:
            raise ArtifactPathError(
                "artifact_path_not_allowed",
                f"path {relative_text} must be under one of {allowed_prefixes}",
            )
    if expected_name is not None and resolved.name != expected_name:
        raise ArtifactPathError(
            "artifact_path_not_allowed",
            f"path {relative_text} must end with {expected_name}",
        )
    if _contains_symlink(resolved, root_path):
        raise ArtifactPathError(
            "artifact_path_not_allowed",
            f"path {relative_text} must not traverse symlinks",
        )
    return resolved
