# src/mcp_code_review/conventions.py
"""Load project conventions from .codereview.yml or auto-detect."""

from __future__ import annotations

import os
from pathlib import Path

import yaml

from mcp_code_review.models import ProjectConventions


def load_conventions(
    config_path: Path | None = None,
    project_path: Path | None = None,
) -> ProjectConventions:
    """Load conventions from .codereview.yml or auto-detect.

    Args:
        config_path: Explicit path to a .codereview.yml file.
        project_path: Project root for auto-detection.

    Returns:
        ProjectConventions with loaded or detected settings.
    """
    # Try explicit config path
    if config_path and config_path.is_file():
        return _load_from_yaml(config_path)

    # Try project root
    if project_path:
        candidate = project_path / ".codereview.yml"
        if candidate.is_file():
            return _load_from_yaml(candidate)

        # Auto-detect
        lang, framework = auto_detect_language(project_path)
        return ProjectConventions(
            language=lang,
            framework=framework,
            locale=os.environ.get("REVIEW_LOCALE", "en"),
        )

    return ProjectConventions(
        language="unknown",
        locale=os.environ.get("REVIEW_LOCALE", "en"),
    )


def _load_from_yaml(path: Path) -> ProjectConventions:
    """Parse a .codereview.yml file into ProjectConventions."""
    with open(path) as f:
        data = yaml.safe_load(f) or {}

    return ProjectConventions(
        language=data.get("language", "unknown"),
        framework=data.get("framework"),
        locale=data.get("locale", os.environ.get("REVIEW_LOCALE", "en")),
        ignore_patterns=data.get("ignore", []),
        severity_overrides=data.get("severity_overrides", {}),
        custom_rules=data.get("custom_rules", {}),
    )


def auto_detect_language(project_path: Path) -> tuple[str, str | None]:
    """Auto-detect language and framework from project files.

    Returns:
        Tuple of (language, framework). framework may be None.
    """
    # Python detection — check marker files or presence of .py files
    python_markers = ["pyproject.toml", "requirements.txt", "setup.py", "setup.cfg"]
    is_python = any((project_path / m).exists() for m in python_markers)

    if not is_python:
        # Fall back: any .py file in the tree also counts as Python
        is_python = any(project_path.rglob("*.py"))

    if not is_python:
        return ("unknown", None)

    # Framework detection
    framework = _detect_python_framework(project_path)
    return ("python", framework)


def _detect_python_framework(project_path: Path) -> str | None:
    """Detect Python framework by scanning common patterns.

    Limits search to top-level files and one level of subdirectories
    (including src/) to avoid slow rglob on large repositories.
    """
    search_dirs = [project_path]
    src_dir = project_path / "src"
    if src_dir.is_dir():
        search_dirs.extend(p for p in src_dir.iterdir() if p.is_dir())
    search_dirs.extend(
        p for p in project_path.iterdir()
        if p.is_dir() and p.name not in {".venv", "venv", "node_modules", ".git", "__pycache__"}
    )

    for search_dir in search_dirs:
        for py_file in search_dir.glob("*.py"):
            try:
                content = py_file.read_text(errors="ignore")
            except (OSError, PermissionError):
                continue

            if "INSTALLED_APPS" in content:
                return "django"
            if "FastAPI(" in content:
                return "fastapi"
            if "Flask(" in content:
                return "flask"

    return None
