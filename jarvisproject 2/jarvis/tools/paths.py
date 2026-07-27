"""Shared path-allowlist boundary used by every filesystem-touching tool.

This is a code-level guardrail, not something the LLM is trusted to respect
on its own: every file tool must resolve its target path through
`resolve_within_allowed(...)` before touching disk. Paths outside the
configured allowed roots are refused, and symlink/`..`-traversal escapes are
rejected even if the raw string looks safe.
"""

from __future__ import annotations

from pathlib import Path


class PathNotAllowedError(ValueError):
    """Raised when a requested path falls outside the allowed directories."""


def resolve_within_allowed(raw_path: str, allowed_dirs: tuple[Path, ...]) -> Path:
    """Resolve `raw_path` and verify it lives under one of `allowed_dirs`.

    Raises PathNotAllowedError if the resolved path is not a descendant of
    any allowed root (this also catches `..` traversal and symlinks that
    resolve outside the allowlist).
    """
    candidate = Path(raw_path).expanduser()
    if not candidate.is_absolute():
        # Relative paths are resolved against the first allowed dir rather
        # than the process cwd, so a bare filename can't accidentally
        # escape via an unexpected working directory.
        candidate = allowed_dirs[0] / candidate

    resolved = candidate.resolve()

    for root in allowed_dirs:
        try:
            resolved.relative_to(root)
            return resolved
        except ValueError:
            continue

    allowed_list = ", ".join(str(d) for d in allowed_dirs)
    raise PathNotAllowedError(
        f"Refused: '{raw_path}' resolves to '{resolved}', which is outside "
        f"the allowed directories ({allowed_list})."
    )
