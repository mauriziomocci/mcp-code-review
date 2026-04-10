# src/mcp_code_review/models.py
"""Data models for code review."""

from __future__ import annotations

from pydantic import BaseModel, Field


class FileChange(BaseModel):
    """A single file changed in a PR/MR/diff."""

    path: str
    status: str  # "added", "modified", "deleted", "renamed"
    additions: int
    deletions: int
    patch: str
    content: str | None = None


class Finding(BaseModel):
    """A single finding from a static analysis tool."""

    tool: str  # "ruff", "bandit"
    rule: str  # "E501", "B101"
    severity: str  # "error", "warning", "info"
    message: str
    file: str
    line: int
    code_snippet: str | None = None


class ProjectConventions(BaseModel):
    """Project conventions loaded from .codereview.yml or auto-detected."""

    language: str
    framework: str | None = None
    locale: str = "en"
    ignore_patterns: list[str] = Field(default_factory=list)
    severity_overrides: dict[str, str] = Field(default_factory=dict)
    custom_rules: dict[str, object] = Field(default_factory=dict)


class ReviewData(BaseModel):
    """Unified review data returned by all providers."""

    source: str  # "github_pr", "gitlab_mr", "local_diff", "file"
    title: str
    author: str | None = None
    branch: str | None = None
    base_branch: str | None = None
    url: str | None = None
    files_changed: list[FileChange]
    total_additions: int
    total_deletions: int
    static_analysis: list[Finding] = Field(default_factory=list)
    conventions: ProjectConventions
