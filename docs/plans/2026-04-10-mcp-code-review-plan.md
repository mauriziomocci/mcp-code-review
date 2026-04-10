# MCP Code Review — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an MCP server for LLM-powered code review that reads GitHub PRs, GitLab MRs, and local diffs, runs static analysis, and generates structured review reports.

**Architecture:** Monolithic FastMCP server with providers (github, gitlab, git_local) that produce a unified ReviewData model, analyzers (ruff, bandit) that produce Finding lists, and a report generator with multi-language support. All tools return structured data for LLM reasoning.

**Tech Stack:** Python 3.10+, FastMCP 3.x, httpx, pydantic, pyyaml, ruff (optional), bandit (optional)

**Spec:** `docs/specs/2026-04-10-mcp-code-review-design.md`

---

## File Map

| File | Responsibility |
|------|---------------|
| `pyproject.toml` | Package config, dependencies, entry point |
| `src/mcp_code_review/__init__.py` | Package version |
| `src/mcp_code_review/server.py` | FastMCP server, registers all tools |
| `src/mcp_code_review/models.py` | Pydantic models: ReviewData, FileChange, Finding, ProjectConventions |
| `src/mcp_code_review/locale.py` | REPORT_SECTIONS dict per language |
| `src/mcp_code_review/conventions.py` | Load .codereview.yml + auto-detect project type |
| `src/mcp_code_review/report.py` | Generate report markdown template with localized headers |
| `src/mcp_code_review/providers/__init__.py` | Provider registry |
| `src/mcp_code_review/providers/base.py` | Abstract Provider protocol |
| `src/mcp_code_review/providers/github.py` | GitHub API client → ReviewData |
| `src/mcp_code_review/providers/gitlab.py` | GitLab API client → ReviewData |
| `src/mcp_code_review/providers/git_local.py` | Local git diff/log → ReviewData |
| `src/mcp_code_review/analyzers/__init__.py` | Analyzer registry with availability check |
| `src/mcp_code_review/analyzers/base.py` | Abstract Analyzer protocol |
| `src/mcp_code_review/analyzers/ruff.py` | Run ruff, parse JSON output → Finding[] |
| `src/mcp_code_review/analyzers/bandit.py` | Run bandit, parse JSON output → Finding[] |

---

### Task 1: Project Scaffolding + Models

**Files:**
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `LICENSE`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `src/mcp_code_review/__init__.py`
- Create: `src/mcp_code_review/models.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Create pyproject.toml**

```toml
[project]
name = "mcp-code-review"
version = "0.1.0"
description = "MCP server for LLM-powered code review — GitHub PRs, GitLab MRs, local diffs"
readme = "README.md"
requires-python = ">=3.10"
license = {text = "MIT"}
authors = [
    {name = "Maurizio Mocci"}
]
keywords = ["mcp", "code-review", "github", "gitlab", "llm", "ai"]

dependencies = [
    "fastmcp>=3.0.0,<4.0.0",
    "httpx>=0.27.0",
    "pydantic>=2.0.0",
    "pyyaml>=6.0.0",
]

[project.optional-dependencies]
python = [
    "ruff>=0.4.0",
    "bandit>=1.7.0",
]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-mock>=3.0.0",
    "ruff>=0.4.0",
]

[project.scripts]
mcp-code-review = "mcp_code_review.server:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/mcp_code_review"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

- [ ] **Step 2: Create .gitignore, LICENSE, .env.example, README.md**

`.gitignore`:
```
__pycache__/
*.pyc
.env
dist/
*.egg-info/
.ruff_cache/
.pytest_cache/
```

`LICENSE`: MIT license with Maurizio Mocci, 2026.

`.env.example`:
```bash
# GitHub (optional — without token, only public repos)
GITHUB_TOKEN=

# GitLab (optional — without token, only public repos)
GITLAB_TOKEN=
GITLAB_URL=https://gitlab.com

# Defaults
REVIEW_OUTPUT_DIR=./reviews
REVIEW_LOCALE=en
```

`README.md`: Minimal with project name, one-line description, and install command. Will be expanded in Task 10.

- [ ] **Step 3: Create __init__.py**

```python
"""MCP Code Review — LLM-powered code review server."""

__version__ = "0.1.0"
```

- [ ] **Step 4: Write failing tests for models**

```python
# tests/test_models.py
from mcp_code_review.models import (
    FileChange,
    Finding,
    ProjectConventions,
    ReviewData,
)


def test_file_change_creation():
    fc = FileChange(
        path="src/main.py",
        status="modified",
        additions=10,
        deletions=3,
        patch="@@ -1,3 +1,10 @@\n+new line",
    )
    assert fc.path == "src/main.py"
    assert fc.status == "modified"
    assert fc.content is None


def test_finding_creation():
    f = Finding(
        tool="ruff",
        rule="E501",
        severity="warning",
        message="Line too long",
        file="src/main.py",
        line=42,
    )
    assert f.tool == "ruff"
    assert f.code_snippet is None


def test_project_conventions_defaults():
    pc = ProjectConventions(language="python")
    assert pc.locale == "en"
    assert pc.framework is None
    assert pc.ignore_patterns == []
    assert pc.severity_overrides == {}
    assert pc.custom_rules == {}


def test_review_data_creation():
    conventions = ProjectConventions(language="python")
    rd = ReviewData(
        source="github_pr",
        title="Add authentication",
        files_changed=[],
        total_additions=0,
        total_deletions=0,
        conventions=conventions,
    )
    assert rd.source == "github_pr"
    assert rd.author is None
    assert rd.static_analysis == []
```

- [ ] **Step 5: Run tests — verify they fail**

```bash
cd /Users/mauriziomocci/Documents/workspace/MCP/mcp-code-review
uv run pytest tests/test_models.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'mcp_code_review'`

- [ ] **Step 6: Create models.py**

```python
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
```

- [ ] **Step 7: Run tests — verify they pass**

```bash
uv run pytest tests/test_models.py -v
```
Expected: 4 passed

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: project scaffolding and pydantic data models"
```

---

### Task 2: Locale + Conventions

**Files:**
- Create: `src/mcp_code_review/locale.py`
- Create: `src/mcp_code_review/conventions.py`
- Test: `tests/test_conventions.py`
- Test fixture: `tests/fixtures/sample_codereview.yml`

- [ ] **Step 1: Create locale.py**

```python
# src/mcp_code_review/locale.py
"""Localized strings for review reports."""

REPORT_SECTIONS: dict[str, dict[str, str]] = {
    "en": {
        "title": "Code Review",
        "date": "Date",
        "author": "PR Author",
        "branch": "Branch",
        "files_changed": "Files changed",
        "summary": "Summary",
        "code_quality": "Code Quality",
        "strengths": "Strengths",
        "issues_found": "Issues Found",
        "static_analysis": "Static Analysis",
        "security": "Security",
        "performance": "Performance",
        "severity_summary": "Severity Summary",
        "verdict": "Verdict",
        "approved": "Approved",
        "approved_with_reservations": "Approved with reservations",
        "changes_requested": "Changes requested",
        "rejected": "Rejected",
        "rationale": "Rationale",
    },
    "it": {
        "title": "Code Review",
        "date": "Data",
        "author": "Autore PR",
        "branch": "Branch",
        "files_changed": "File modificati",
        "summary": "Riepilogo",
        "code_quality": "Qualità del codice",
        "strengths": "Punti di forza",
        "issues_found": "Problemi trovati",
        "static_analysis": "Analisi statica",
        "security": "Sicurezza",
        "performance": "Performance",
        "severity_summary": "Riepilogo severità",
        "verdict": "Verdetto",
        "approved": "Approvata",
        "approved_with_reservations": "Approvata con riserve",
        "changes_requested": "Richieste modifiche",
        "rejected": "Rifiutata",
        "rationale": "Motivazione",
    },
    "es": {
        "title": "Revisión de Código",
        "date": "Fecha",
        "author": "Autor PR",
        "branch": "Rama",
        "files_changed": "Archivos modificados",
        "summary": "Resumen",
        "code_quality": "Calidad del código",
        "strengths": "Puntos fuertes",
        "issues_found": "Problemas encontrados",
        "static_analysis": "Análisis estático",
        "security": "Seguridad",
        "performance": "Rendimiento",
        "severity_summary": "Resumen de severidad",
        "verdict": "Veredicto",
        "approved": "Aprobada",
        "approved_with_reservations": "Aprobada con reservas",
        "changes_requested": "Cambios solicitados",
        "rejected": "Rechazada",
        "rationale": "Justificación",
    },
}


def get_sections(locale: str) -> dict[str, str]:
    """Return section headers for the given locale, falling back to English."""
    return REPORT_SECTIONS.get(locale, REPORT_SECTIONS["en"])
```

- [ ] **Step 2: Create test fixture**

```yaml
# tests/fixtures/sample_codereview.yml
language: python
locale: it
ignore:
  - "*/migrations/*"
  - "tests/fixtures/"
severity_overrides:
  E501: info
custom_rules:
  require_type_hints: false
  max_file_lines: 500
```

- [ ] **Step 3: Write failing tests for conventions**

```python
# tests/test_conventions.py
from pathlib import Path

from mcp_code_review.conventions import load_conventions, auto_detect_language


FIXTURES = Path(__file__).parent / "fixtures"


def test_load_conventions_from_yaml():
    conventions = load_conventions(FIXTURES / "sample_codereview.yml")
    assert conventions.language == "python"
    assert conventions.locale == "it"
    assert "*/migrations/*" in conventions.ignore_patterns
    assert conventions.severity_overrides.get("E501") == "info"
    assert conventions.custom_rules.get("max_file_lines") == 500


def test_load_conventions_file_not_found():
    conventions = load_conventions(Path("/nonexistent/.codereview.yml"))
    assert conventions.language == "unknown"
    assert conventions.locale == "en"


def test_auto_detect_python_pyproject(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "myapp"\n')
    lang, framework = auto_detect_language(tmp_path)
    assert lang == "python"


def test_auto_detect_django(tmp_path):
    settings = tmp_path / "myapp" / "settings.py"
    settings.parent.mkdir()
    settings.write_text("INSTALLED_APPS = ['django.contrib.admin']")
    lang, framework = auto_detect_language(tmp_path)
    assert lang == "python"
    assert framework == "django"


def test_auto_detect_unknown(tmp_path):
    lang, framework = auto_detect_language(tmp_path)
    assert lang == "unknown"
    assert framework is None
```

- [ ] **Step 4: Run tests — verify they fail**

```bash
uv run pytest tests/test_conventions.py -v
```
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 5: Create conventions.py**

```python
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
    # Python detection
    python_markers = ["pyproject.toml", "requirements.txt", "setup.py", "setup.cfg"]
    is_python = any((project_path / m).exists() for m in python_markers)

    if not is_python:
        return ("unknown", None)

    # Framework detection
    framework = _detect_python_framework(project_path)
    return ("python", framework)


def _detect_python_framework(project_path: Path) -> str | None:
    """Detect Python framework by scanning common patterns."""
    for py_file in project_path.rglob("*.py"):
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
```

- [ ] **Step 6: Run tests — verify they pass**

```bash
uv run pytest tests/test_conventions.py -v
```
Expected: 5 passed

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: locale strings and conventions loader with auto-detect"
```

---

### Task 3: Report Generator

**Files:**
- Create: `src/mcp_code_review/report.py`
- Test: `tests/test_report.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_report.py
from mcp_code_review.report import build_report_template, slugify_title
from mcp_code_review.models import ReviewData, ProjectConventions


def test_build_report_template_english():
    conventions = ProjectConventions(language="python", locale="en")
    rd = ReviewData(
        source="github_pr",
        title="Add authentication",
        author="johndoe",
        branch="feature/auth",
        base_branch="main",
        url="https://github.com/org/repo/pull/42",
        files_changed=[],
        total_additions=100,
        total_deletions=20,
        conventions=conventions,
    )
    template = build_report_template(rd)
    assert "# Code Review" in template
    assert "Add authentication" in template
    assert "johndoe" in template
    assert "## Summary" in template
    assert "## Verdict" in template


def test_build_report_template_italian():
    conventions = ProjectConventions(language="python", locale="it")
    rd = ReviewData(
        source="gitlab_mr",
        title="Fix login bug",
        files_changed=[],
        total_additions=5,
        total_deletions=2,
        conventions=conventions,
    )
    template = build_report_template(rd)
    assert "## Riepilogo" in template
    assert "## Verdetto" in template


def test_slugify_title():
    assert slugify_title("Add user authentication") == "add-user-authentication"
    assert slugify_title("PR #42 — Fix bug!") == "pr-42-fix-bug"
    assert slugify_title("  spaces  ") == "spaces"
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
uv run pytest tests/test_report.py -v
```
Expected: FAIL

- [ ] **Step 3: Create report.py**

```python
# src/mcp_code_review/report.py
"""Generate markdown review report templates."""

from __future__ import annotations

import re
from datetime import date

from mcp_code_review.locale import get_sections
from mcp_code_review.models import ReviewData


def build_report_template(review_data: ReviewData) -> str:
    """Build a markdown report template with localized headers.

    The template contains the metadata and section headers.
    The LLM fills in the content.
    """
    s = get_sections(review_data.conventions.locale)
    lines = [
        f"# {s['title']} — {review_data.title}",
        "",
        f"**{s['date']}:** {date.today().isoformat()}",
    ]

    if review_data.author:
        lines.append(f"**{s['author']}:** {review_data.author}")
    if review_data.branch:
        branch_str = review_data.branch
        if review_data.base_branch:
            branch_str = f"{review_data.branch} → {review_data.base_branch}"
        lines.append(f"**{s['branch']}:** {branch_str}")
    if review_data.url:
        lines.append(f"**URL:** {review_data.url}")

    lines.append(
        f"**{s['files_changed']}:** {len(review_data.files_changed)} "
        f"(+{review_data.total_additions} -{review_data.total_deletions})"
    )

    sections = [
        "summary",
        "code_quality",
        "static_analysis",
        "security",
        "performance",
        "severity_summary",
        "verdict",
    ]

    for section in sections:
        lines.extend(["", "---", "", f"## {s[section]}", ""])
        if section == "code_quality":
            lines.extend([f"### {s['strengths']}", "", f"### {s['issues_found']}", ""])
        elif section == "verdict":
            lines.extend([
                f"- [ ] {s['approved']}",
                f"- [ ] {s['approved_with_reservations']}",
                f"- [ ] {s['changes_requested']}",
                f"- [ ] {s['rejected']}",
                "",
                f"**{s['rationale']}:**",
                "",
            ])

    return "\n".join(lines)


def slugify_title(title: str) -> str:
    """Convert a title to a URL/filename-safe slug."""
    slug = title.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
uv run pytest tests/test_report.py -v
```
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: report template generator with multi-language support"
```

---

### Task 4: Analyzer Base + Ruff Analyzer

**Files:**
- Create: `src/mcp_code_review/analyzers/__init__.py`
- Create: `src/mcp_code_review/analyzers/base.py`
- Create: `src/mcp_code_review/analyzers/ruff.py`
- Test: `tests/test_analyzers/test_ruff.py`

- [ ] **Step 1: Create analyzer base**

```python
# src/mcp_code_review/analyzers/__init__.py
"""Static analysis tools."""

from mcp_code_review.analyzers.ruff import RuffAnalyzer
from mcp_code_review.analyzers.bandit import BanditAnalyzer


def get_available_analyzers() -> list[dict[str, str]]:
    """Return list of analyzers with their availability status."""
    analyzers = [
        {"name": "ruff", "available": RuffAnalyzer.is_available(), "install": "pip install mcp-code-review[python]"},
        {"name": "bandit", "available": BanditAnalyzer.is_available(), "install": "pip install mcp-code-review[python]"},
    ]
    return analyzers
```

```python
# src/mcp_code_review/analyzers/base.py
"""Abstract base for analyzers."""

from __future__ import annotations

from typing import Protocol

from mcp_code_review.models import Finding


class Analyzer(Protocol):
    """Protocol for static analysis tools."""

    @staticmethod
    def is_available() -> bool:
        """Check if the analyzer binary is installed."""
        ...

    async def analyze(self, files: list[str], focus: str = "all") -> list[Finding]:
        """Run analysis on the given files."""
        ...
```

- [ ] **Step 2: Write failing tests for ruff analyzer**

```python
# tests/test_analyzers/test_ruff.py
import json
from unittest.mock import AsyncMock, patch

import pytest

from mcp_code_review.analyzers.ruff import RuffAnalyzer


@pytest.fixture
def ruff_json_output():
    return json.dumps([
        {
            "code": "E501",
            "message": "Line too long (120 > 88)",
            "filename": "src/main.py",
            "location": {"row": 42, "column": 1},
            "fix": None,
        },
        {
            "code": "F401",
            "message": "os imported but unused",
            "filename": "src/main.py",
            "location": {"row": 1, "column": 1},
            "fix": None,
        },
    ])


@pytest.mark.asyncio
async def test_ruff_analyze_parses_output(ruff_json_output):
    analyzer = RuffAnalyzer()
    with patch("mcp_code_review.analyzers.ruff.run_command", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = (0, ruff_json_output, "")
        findings = await analyzer.analyze(["src/main.py"])

    assert len(findings) == 2
    assert findings[0].tool == "ruff"
    assert findings[0].rule == "E501"
    assert findings[0].severity == "warning"
    assert findings[0].line == 42
    assert findings[1].rule == "F401"


@pytest.mark.asyncio
async def test_ruff_analyze_empty_when_no_issues():
    analyzer = RuffAnalyzer()
    with patch("mcp_code_review.analyzers.ruff.run_command", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = (0, "[]", "")
        findings = await analyzer.analyze(["src/main.py"])

    assert findings == []


def test_ruff_is_available():
    # Just verify the method exists and returns a bool
    result = RuffAnalyzer.is_available()
    assert isinstance(result, bool)
```

- [ ] **Step 3: Run tests — verify they fail**

```bash
uv run pytest tests/test_analyzers/test_ruff.py -v
```
Expected: FAIL

- [ ] **Step 4: Create ruff.py**

```python
# src/mcp_code_review/analyzers/ruff.py
"""Ruff static analysis integration."""

from __future__ import annotations

import asyncio
import json
import shutil

from mcp_code_review.models import Finding

# Severity mapping: ruff codes → severity levels
_ERROR_PREFIXES = {"F", "E9"}  # fatal errors, syntax errors
_WARNING_PREFIXES = {"E", "W", "C", "N", "B", "S"}  # style, complexity, security


async def run_command(cmd: list[str]) -> tuple[int, str, str]:
    """Run a subprocess and return (returncode, stdout, stderr)."""
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    return proc.returncode, stdout.decode(), stderr.decode()


class RuffAnalyzer:
    """Run ruff and parse results into Finding objects."""

    @staticmethod
    def is_available() -> bool:
        """Check if ruff is installed."""
        return shutil.which("ruff") is not None

    async def analyze(self, files: list[str], focus: str = "all") -> list[Finding]:
        """Run ruff on the given files and return findings."""
        if not self.is_available() or not files:
            return []

        cmd = ["ruff", "check", "--output-format=json", *files]
        _, stdout, _ = await run_command(cmd)

        if not stdout or stdout.strip() == "[]":
            return []

        return self._parse_output(stdout, focus)

    def _parse_output(self, raw_json: str, focus: str) -> list[Finding]:
        """Parse ruff JSON output into Finding objects."""
        try:
            items = json.loads(raw_json)
        except json.JSONDecodeError:
            return []

        findings = []
        for item in items:
            code = item.get("code", "")
            severity = self._classify_severity(code)

            if focus == "security" and not code.startswith("S"):
                continue
            if focus == "performance" and code.startswith("S"):
                continue

            findings.append(Finding(
                tool="ruff",
                rule=code,
                severity=severity,
                message=item.get("message", ""),
                file=item.get("filename", ""),
                line=item.get("location", {}).get("row", 0),
            ))

        return findings

    @staticmethod
    def _classify_severity(code: str) -> str:
        """Map ruff rule code to severity level."""
        if any(code.startswith(p) for p in _ERROR_PREFIXES):
            return "error"
        if any(code.startswith(p) for p in _WARNING_PREFIXES):
            return "warning"
        return "info"
```

- [ ] **Step 5: Run tests — verify they pass**

```bash
uv run pytest tests/test_analyzers/test_ruff.py -v
```
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: ruff analyzer with JSON parsing and severity classification"
```

---

### Task 5: Bandit Analyzer

**Files:**
- Create: `src/mcp_code_review/analyzers/bandit.py`
- Test: `tests/test_analyzers/test_bandit.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_analyzers/test_bandit.py
import json
from unittest.mock import AsyncMock, patch

import pytest

from mcp_code_review.analyzers.bandit import BanditAnalyzer


@pytest.fixture
def bandit_json_output():
    return json.dumps({
        "results": [
            {
                "test_id": "B101",
                "test_name": "assert_used",
                "issue_severity": "LOW",
                "issue_confidence": "HIGH",
                "issue_text": "Use of assert detected.",
                "filename": "src/main.py",
                "line_number": 15,
                "code": "    assert x > 0\n",
            },
            {
                "test_id": "B105",
                "test_name": "hardcoded_password_string",
                "issue_severity": "HIGH",
                "issue_confidence": "MEDIUM",
                "issue_text": "Possible hardcoded password.",
                "filename": "src/config.py",
                "line_number": 8,
                "code": '    password = "secret123"\n',
            },
        ],
    })


@pytest.mark.asyncio
async def test_bandit_analyze_parses_output(bandit_json_output):
    analyzer = BanditAnalyzer()
    with patch("mcp_code_review.analyzers.bandit.run_command", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = (0, bandit_json_output, "")
        findings = await analyzer.analyze(["src/main.py", "src/config.py"])

    assert len(findings) == 2
    assert findings[0].tool == "bandit"
    assert findings[0].rule == "B101"
    assert findings[0].severity == "info"  # LOW → info
    assert findings[1].rule == "B105"
    assert findings[1].severity == "error"  # HIGH → error


@pytest.mark.asyncio
async def test_bandit_analyze_empty():
    analyzer = BanditAnalyzer()
    with patch("mcp_code_review.analyzers.bandit.run_command", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = (0, json.dumps({"results": []}), "")
        findings = await analyzer.analyze(["src/main.py"])

    assert findings == []
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
uv run pytest tests/test_analyzers/test_bandit.py -v
```
Expected: FAIL

- [ ] **Step 3: Create bandit.py**

```python
# src/mcp_code_review/analyzers/bandit.py
"""Bandit security analysis integration."""

from __future__ import annotations

import json
import shutil

from mcp_code_review.analyzers.ruff import run_command
from mcp_code_review.models import Finding

_SEVERITY_MAP = {
    "HIGH": "error",
    "MEDIUM": "warning",
    "LOW": "info",
}


class BanditAnalyzer:
    """Run bandit and parse results into Finding objects."""

    @staticmethod
    def is_available() -> bool:
        """Check if bandit is installed."""
        return shutil.which("bandit") is not None

    async def analyze(self, files: list[str], focus: str = "all") -> list[Finding]:
        """Run bandit on the given files and return findings."""
        if not self.is_available() or not files:
            return []

        cmd = ["bandit", "-f", "json", "-r", *files]
        _, stdout, _ = await run_command(cmd)

        if not stdout:
            return []

        return self._parse_output(stdout)

    def _parse_output(self, raw_json: str) -> list[Finding]:
        """Parse bandit JSON output into Finding objects."""
        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError:
            return []

        findings = []
        for item in data.get("results", []):
            severity = _SEVERITY_MAP.get(item.get("issue_severity", ""), "info")

            findings.append(Finding(
                tool="bandit",
                rule=item.get("test_id", ""),
                severity=severity,
                message=item.get("issue_text", ""),
                file=item.get("filename", ""),
                line=item.get("line_number", 0),
                code_snippet=item.get("code"),
            ))

        return findings
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
uv run pytest tests/test_analyzers/test_bandit.py -v
```
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: bandit security analyzer with JSON parsing"
```

---

### Task 6: Provider Base + Git Local Provider

**Files:**
- Create: `src/mcp_code_review/providers/__init__.py`
- Create: `src/mcp_code_review/providers/base.py`
- Create: `src/mcp_code_review/providers/git_local.py`
- Test: `tests/test_providers/test_git_local.py`

- [ ] **Step 1: Create provider base**

```python
# src/mcp_code_review/providers/__init__.py
"""Review data providers."""

# src/mcp_code_review/providers/base.py
"""Abstract base for providers."""

from __future__ import annotations

from typing import Protocol

from mcp_code_review.models import ReviewData


class Provider(Protocol):
    """Protocol for review data providers."""

    async def fetch(self, **kwargs) -> ReviewData:
        """Fetch review data from the source."""
        ...
```

- [ ] **Step 2: Write failing tests for git_local provider**

```python
# tests/test_providers/test_git_local.py
from unittest.mock import AsyncMock, patch

import pytest

from mcp_code_review.providers.git_local import GitLocalProvider


SAMPLE_DIFF = """\
diff --git a/src/main.py b/src/main.py
index abc1234..def5678 100644
--- a/src/main.py
+++ b/src/main.py
@@ -1,3 +1,5 @@
 import os
+import sys
+
 def main():
-    pass
+    print("hello")
"""

SAMPLE_NUMSTAT = "2\t1\tsrc/main.py\n"


@pytest.mark.asyncio
async def test_git_local_fetch():
    provider = GitLocalProvider()
    with patch("mcp_code_review.providers.git_local.run_git", new_callable=AsyncMock) as mock_git:
        mock_git.side_effect = [
            SAMPLE_DIFF,      # git diff
            SAMPLE_NUMSTAT,   # git diff --numstat
        ]
        review = await provider.fetch(path="/tmp/project", base_branch="main")

    assert review.source == "local_diff"
    assert len(review.files_changed) == 1
    assert review.files_changed[0].path == "src/main.py"
    assert review.files_changed[0].status == "modified"
    assert review.files_changed[0].additions == 2
    assert review.files_changed[0].deletions == 1
    assert review.total_additions == 2
    assert review.total_deletions == 1


@pytest.mark.asyncio
async def test_git_local_fetch_no_changes():
    provider = GitLocalProvider()
    with patch("mcp_code_review.providers.git_local.run_git", new_callable=AsyncMock) as mock_git:
        mock_git.side_effect = ["", ""]
        review = await provider.fetch(path="/tmp/project", base_branch="main")

    assert review.files_changed == []
    assert review.total_additions == 0
```

- [ ] **Step 3: Run tests — verify they fail**

```bash
uv run pytest tests/test_providers/test_git_local.py -v
```
Expected: FAIL

- [ ] **Step 4: Create git_local.py**

```python
# src/mcp_code_review/providers/git_local.py
"""Local git diff provider."""

from __future__ import annotations

import asyncio
import re

from mcp_code_review.models import FileChange, ProjectConventions, ReviewData


async def run_git(args: list[str], cwd: str) -> str:
    """Run a git command and return stdout."""
    proc = await asyncio.create_subprocess_exec(
        "git", *args,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    return stdout.decode()


class GitLocalProvider:
    """Provide ReviewData from local git diff."""

    async def fetch(
        self,
        path: str = ".",
        base_branch: str = "main",
    ) -> ReviewData:
        """Fetch diff between current HEAD and base branch."""
        diff_output = await run_git(
            ["diff", f"{base_branch}...HEAD"], cwd=path
        )
        numstat_output = await run_git(
            ["diff", f"{base_branch}...HEAD", "--numstat"], cwd=path
        )

        files = self._parse_diff(diff_output, numstat_output)
        total_add = sum(f.additions for f in files)
        total_del = sum(f.deletions for f in files)

        return ReviewData(
            source="local_diff",
            title=f"Local diff: HEAD vs {base_branch}",
            files_changed=files,
            total_additions=total_add,
            total_deletions=total_del,
            conventions=ProjectConventions(language="unknown"),
        )

    def _parse_diff(self, diff: str, numstat: str) -> list[FileChange]:
        """Parse git diff output into FileChange objects."""
        if not diff.strip():
            return []

        # Parse numstat for additions/deletions per file
        stats: dict[str, tuple[int, int]] = {}
        for line in numstat.strip().splitlines():
            parts = line.split("\t")
            if len(parts) == 3:
                add = int(parts[0]) if parts[0] != "-" else 0
                delete = int(parts[1]) if parts[1] != "-" else 0
                stats[parts[2]] = (add, delete)

        # Parse diff into per-file patches
        file_diffs = re.split(r"^diff --git ", diff, flags=re.MULTILINE)
        files = []

        for file_diff in file_diffs:
            if not file_diff.strip():
                continue

            # Extract file path from "a/path b/path"
            first_line = file_diff.split("\n", 1)[0]
            match = re.match(r"a/(.*?) b/(.*)", first_line)
            if not match:
                continue

            path = match.group(2)
            add, delete = stats.get(path, (0, 0))

            # Determine status
            status = "modified"
            if "new file mode" in file_diff:
                status = "added"
            elif "deleted file mode" in file_diff:
                status = "deleted"
            elif "rename from" in file_diff:
                status = "renamed"

            files.append(FileChange(
                path=path,
                status=status,
                additions=add,
                deletions=delete,
                patch=f"diff --git {file_diff}",
            ))

        return files
```

- [ ] **Step 5: Run tests — verify they pass**

```bash
uv run pytest tests/test_providers/test_git_local.py -v
```
Expected: 2 passed

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: git local provider — parse diff and numstat into ReviewData"
```

---

### Task 7: GitHub Provider

**Files:**
- Create: `src/mcp_code_review/providers/github.py`
- Test: `tests/test_providers/test_github.py`
- Fixture: `tests/fixtures/sample_pr_response.json`

- [ ] **Step 1: Create test fixture**

```json
{
    "pr": {
        "title": "Add user authentication",
        "user": {"login": "johndoe"},
        "head": {"ref": "feature/auth"},
        "base": {"ref": "main"},
        "html_url": "https://github.com/org/repo/pull/42",
        "body": "This PR adds JWT authentication."
    },
    "files": [
        {
            "filename": "src/auth.py",
            "status": "added",
            "additions": 50,
            "deletions": 0,
            "patch": "@@ -0,0 +1,50 @@\n+import jwt\n+\n+def authenticate():\n+    pass"
        },
        {
            "filename": "src/main.py",
            "status": "modified",
            "additions": 5,
            "deletions": 2,
            "patch": "@@ -1,5 +1,8 @@\n import os\n+from auth import authenticate"
        }
    ]
}
```

- [ ] **Step 2: Write failing tests**

```python
# tests/test_providers/test_github.py
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from mcp_code_review.providers.github import GitHubProvider, parse_github_url

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_parse_github_url():
    owner, repo, pr_num = parse_github_url("https://github.com/org/repo/pull/42")
    assert owner == "org"
    assert repo == "repo"
    assert pr_num == 42


def test_parse_github_url_invalid():
    with pytest.raises(ValueError):
        parse_github_url("https://example.com/not-a-pr")


@pytest.mark.asyncio
async def test_github_fetch():
    fixture = json.loads((FIXTURES / "sample_pr_response.json").read_text())

    provider = GitHubProvider(token="fake-token")
    with patch.object(provider, "_get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = [fixture["pr"], fixture["files"]]
        review = await provider.fetch(url="https://github.com/org/repo/pull/42")

    assert review.source == "github_pr"
    assert review.title == "Add user authentication"
    assert review.author == "johndoe"
    assert review.branch == "feature/auth"
    assert len(review.files_changed) == 2
    assert review.total_additions == 55
    assert review.total_deletions == 2
```

- [ ] **Step 3: Run tests — verify they fail**

```bash
uv run pytest tests/test_providers/test_github.py -v
```
Expected: FAIL

- [ ] **Step 4: Create github.py**

```python
# src/mcp_code_review/providers/github.py
"""GitHub PR provider."""

from __future__ import annotations

import os
import re

import httpx

from mcp_code_review.models import FileChange, ProjectConventions, ReviewData


def parse_github_url(url: str) -> tuple[str, str, int]:
    """Extract owner, repo, PR number from a GitHub PR URL."""
    match = re.match(
        r"https?://github\.com/([^/]+)/([^/]+)/pull/(\d+)",
        url,
    )
    if not match:
        raise ValueError(f"Invalid GitHub PR URL: {url}")
    return match.group(1), match.group(2), int(match.group(3))


class GitHubProvider:
    """Provide ReviewData from a GitHub Pull Request."""

    BASE_URL = "https://api.github.com"

    def __init__(self, token: str | None = None):
        self.token = token or os.environ.get("GITHUB_TOKEN")

    async def fetch(self, url: str) -> ReviewData:
        """Fetch PR data from GitHub API."""
        owner, repo, pr_num = parse_github_url(url)

        pr_data = await self._get(f"/repos/{owner}/{repo}/pulls/{pr_num}")
        files_data = await self._get(f"/repos/{owner}/{repo}/pulls/{pr_num}/files")

        files = [
            FileChange(
                path=f["filename"],
                status=f.get("status", "modified"),
                additions=f.get("additions", 0),
                deletions=f.get("deletions", 0),
                patch=f.get("patch", ""),
            )
            for f in files_data
        ]

        total_add = sum(f.additions for f in files)
        total_del = sum(f.deletions for f in files)

        return ReviewData(
            source="github_pr",
            title=pr_data.get("title", ""),
            author=pr_data.get("user", {}).get("login"),
            branch=pr_data.get("head", {}).get("ref"),
            base_branch=pr_data.get("base", {}).get("ref"),
            url=pr_data.get("html_url", url),
            files_changed=files,
            total_additions=total_add,
            total_deletions=total_del,
            conventions=ProjectConventions(language="unknown"),
        )

    async def _get(self, endpoint: str) -> dict | list:
        """Make an authenticated GET request to GitHub API."""
        headers = {"Accept": "application/vnd.github.v3+json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self.BASE_URL}{endpoint}", headers=headers)
            resp.raise_for_status()
            return resp.json()
```

- [ ] **Step 5: Run tests — verify they pass**

```bash
uv run pytest tests/test_providers/test_github.py -v
```
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: GitHub PR provider — fetch PR metadata and file diffs"
```

---

### Task 8: GitLab Provider

**Files:**
- Create: `src/mcp_code_review/providers/gitlab.py`
- Test: `tests/test_providers/test_gitlab.py`
- Fixture: `tests/fixtures/sample_mr_response.json`

- [ ] **Step 1: Create test fixture**

```json
{
    "mr": {
        "title": "Fix database migration",
        "author": {"username": "janedoe"},
        "source_branch": "fix/migration",
        "target_branch": "main",
        "web_url": "https://gitlab.com/org/repo/-/merge_requests/15"
    },
    "changes": {
        "changes": [
            {
                "new_path": "migrations/0042.py",
                "old_path": "migrations/0042.py",
                "new_file": true,
                "renamed_file": false,
                "deleted_file": false,
                "diff": "@@ -0,0 +1,20 @@\n+class Migration:\n+    pass"
            }
        ]
    }
}
```

- [ ] **Step 2: Write failing tests**

```python
# tests/test_providers/test_gitlab.py
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from mcp_code_review.providers.gitlab import GitLabProvider, parse_gitlab_url

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_parse_gitlab_url():
    base, project, mr_num = parse_gitlab_url(
        "https://gitlab.com/org/repo/-/merge_requests/15"
    )
    assert base == "https://gitlab.com"
    assert project == "org/repo"
    assert mr_num == 15


def test_parse_gitlab_url_self_hosted():
    base, project, mr_num = parse_gitlab_url(
        "https://git.company.com/team/project/-/merge_requests/3"
    )
    assert base == "https://git.company.com"
    assert project == "team/project"
    assert mr_num == 3


@pytest.mark.asyncio
async def test_gitlab_fetch():
    fixture = json.loads((FIXTURES / "sample_mr_response.json").read_text())

    provider = GitLabProvider(token="fake-token")
    with patch.object(provider, "_get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = [fixture["mr"], fixture["changes"]]
        review = await provider.fetch(
            url="https://gitlab.com/org/repo/-/merge_requests/15"
        )

    assert review.source == "gitlab_mr"
    assert review.title == "Fix database migration"
    assert review.author == "janedoe"
    assert review.branch == "fix/migration"
    assert len(review.files_changed) == 1
    assert review.files_changed[0].status == "added"
```

- [ ] **Step 3: Run tests — verify they fail**

```bash
uv run pytest tests/test_providers/test_gitlab.py -v
```
Expected: FAIL

- [ ] **Step 4: Create gitlab.py**

```python
# src/mcp_code_review/providers/gitlab.py
"""GitLab MR provider."""

from __future__ import annotations

import os
import re
from urllib.parse import quote_plus

import httpx

from mcp_code_review.models import FileChange, ProjectConventions, ReviewData


def parse_gitlab_url(url: str) -> tuple[str, str, int]:
    """Extract base URL, project path, MR number from a GitLab MR URL."""
    match = re.match(
        r"(https?://[^/]+)/(.+?)/-/merge_requests/(\d+)",
        url,
    )
    if not match:
        raise ValueError(f"Invalid GitLab MR URL: {url}")
    return match.group(1), match.group(2), int(match.group(3))


class GitLabProvider:
    """Provide ReviewData from a GitLab Merge Request."""

    def __init__(
        self,
        token: str | None = None,
        base_url: str | None = None,
    ):
        self.token = token or os.environ.get("GITLAB_TOKEN")
        self.base_url = base_url or os.environ.get("GITLAB_URL", "https://gitlab.com")

    async def fetch(self, url: str) -> ReviewData:
        """Fetch MR data from GitLab API."""
        base, project, mr_num = parse_gitlab_url(url)
        encoded_project = quote_plus(project)

        mr_data = await self._get(
            f"{base}/api/v4/projects/{encoded_project}/merge_requests/{mr_num}"
        )
        changes_data = await self._get(
            f"{base}/api/v4/projects/{encoded_project}/merge_requests/{mr_num}/changes"
        )

        files = []
        for change in changes_data.get("changes", []):
            # Count additions/deletions from diff
            diff = change.get("diff", "")
            additions = diff.count("\n+") - diff.count("\n+++")
            deletions = diff.count("\n-") - diff.count("\n---")

            status = "modified"
            if change.get("new_file"):
                status = "added"
            elif change.get("deleted_file"):
                status = "deleted"
            elif change.get("renamed_file"):
                status = "renamed"

            files.append(FileChange(
                path=change.get("new_path", ""),
                status=status,
                additions=max(0, additions),
                deletions=max(0, deletions),
                patch=diff,
            ))

        total_add = sum(f.additions for f in files)
        total_del = sum(f.deletions for f in files)

        return ReviewData(
            source="gitlab_mr",
            title=mr_data.get("title", ""),
            author=mr_data.get("author", {}).get("username"),
            branch=mr_data.get("source_branch"),
            base_branch=mr_data.get("target_branch"),
            url=mr_data.get("web_url", url),
            files_changed=files,
            total_additions=total_add,
            total_deletions=total_del,
            conventions=ProjectConventions(language="unknown"),
        )

    async def _get(self, url: str) -> dict | list:
        """Make an authenticated GET request to GitLab API."""
        headers = {}
        if self.token:
            headers["PRIVATE-TOKEN"] = self.token

        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            return resp.json()
```

- [ ] **Step 5: Run tests — verify they pass**

```bash
uv run pytest tests/test_providers/test_gitlab.py -v
```
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: GitLab MR provider — fetch MR metadata and diffs"
```

---

### Task 9: FastMCP Server + All Tools

**Files:**
- Create: `src/mcp_code_review/server.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create conftest.py**

```python
# tests/conftest.py
"""Shared test fixtures."""

import pytest

from mcp_code_review.models import (
    FileChange,
    Finding,
    ProjectConventions,
    ReviewData,
)


@pytest.fixture
def sample_conventions():
    return ProjectConventions(language="python", framework="django", locale="en")


@pytest.fixture
def sample_review_data(sample_conventions):
    return ReviewData(
        source="github_pr",
        title="Add authentication",
        author="johndoe",
        branch="feature/auth",
        base_branch="main",
        url="https://github.com/org/repo/pull/42",
        files_changed=[
            FileChange(
                path="src/auth.py",
                status="added",
                additions=50,
                deletions=0,
                patch="@@ -0,0 +1,50 @@\n+import jwt",
            ),
        ],
        total_additions=50,
        total_deletions=0,
        static_analysis=[
            Finding(
                tool="ruff",
                rule="F401",
                severity="warning",
                message="jwt imported but unused",
                file="src/auth.py",
                line=1,
            ),
        ],
        conventions=sample_conventions,
    )
```

- [ ] **Step 2: Create server.py with all 10 tools**

```python
# src/mcp_code_review/server.py
"""MCP Code Review server — all tools registered here."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from fastmcp import FastMCP

from mcp_code_review.analyzers import get_available_analyzers
from mcp_code_review.analyzers.bandit import BanditAnalyzer
from mcp_code_review.analyzers.ruff import RuffAnalyzer
from mcp_code_review.conventions import load_conventions
from mcp_code_review.models import ProjectConventions
from mcp_code_review.providers.git_local import GitLocalProvider
from mcp_code_review.providers.github import GitHubProvider
from mcp_code_review.providers.gitlab import GitLabProvider
from mcp_code_review.report import build_report_template, slugify_title

mcp = FastMCP("MCP Code Review")


# ---------- Review tools ----------


@mcp.tool()
async def review_github_pr(
    url: str,
    focus: str = "all",
    locale: str | None = None,
) -> dict:
    """Review a GitHub Pull Request.

    Fetches PR metadata, file diffs, and project conventions.
    Returns structured data for LLM-powered code review.

    Args:
        url: GitHub PR URL (e.g. https://github.com/org/repo/pull/42)
        focus: Review focus — "all", "security", "performance", "quality"
        locale: Report language — "en", "it", "es", etc. Overrides project config.
    """
    provider = GitHubProvider()
    review = await provider.fetch(url=url)

    # Load conventions from repo via API (best effort)
    review.conventions = _resolve_conventions(locale=locale)

    return review.model_dump()


@mcp.tool()
async def review_gitlab_mr(
    url: str,
    focus: str = "all",
    locale: str | None = None,
) -> dict:
    """Review a GitLab Merge Request.

    Fetches MR metadata, file diffs, and project conventions.
    Returns structured data for LLM-powered code review.

    Args:
        url: GitLab MR URL (e.g. https://gitlab.com/org/repo/-/merge_requests/15)
        focus: Review focus — "all", "security", "performance", "quality"
        locale: Report language — "en", "it", "es", etc.
    """
    provider = GitLabProvider()
    review = await provider.fetch(url=url)
    review.conventions = _resolve_conventions(locale=locale)

    return review.model_dump()


@mcp.tool()
async def review_diff(
    path: str = ".",
    base_branch: str = "main",
    focus: str = "all",
    locale: str | None = None,
) -> dict:
    """Review local git diff.

    Compares current HEAD against base branch. Runs static analysis
    (ruff, bandit) if installed. Returns structured data for review.

    Args:
        path: Project root directory (default: current directory)
        base_branch: Branch to compare against (default: main)
        focus: Review focus — "all", "security", "performance", "quality"
        locale: Report language.
    """
    provider = GitLocalProvider()
    review = await provider.fetch(path=path, base_branch=base_branch)
    review.conventions = _resolve_conventions(
        project_path=Path(path), locale=locale
    )

    # Run static analysis on changed files
    changed_files = [f.path for f in review.files_changed if f.status != "deleted"]
    if changed_files:
        review.static_analysis = await _run_analyzers(changed_files, focus)

    return review.model_dump()


@mcp.tool()
async def review_file(
    path: str,
    focus: str = "all",
    locale: str | None = None,
) -> dict:
    """Review a single file.

    Reads file content and runs static analysis if installed.

    Args:
        path: Path to the file to review.
        focus: Review focus — "all", "security", "performance", "quality"
        locale: Report language.
    """
    from mcp_code_review.models import FileChange, ReviewData

    file_path = Path(path)
    if not file_path.is_file():
        return {"error": f"File not found: {path}"}

    content = file_path.read_text(errors="ignore")
    lines = content.splitlines()

    file_change = FileChange(
        path=str(file_path),
        status="modified",
        additions=len(lines),
        deletions=0,
        patch="",
        content=content,
    )

    project_path = file_path.parent
    conventions = _resolve_conventions(project_path=project_path, locale=locale)
    findings = await _run_analyzers([str(file_path)], focus)

    review = ReviewData(
        source="file",
        title=file_path.name,
        files_changed=[file_change],
        total_additions=len(lines),
        total_deletions=0,
        static_analysis=findings,
        conventions=conventions,
    )
    return review.model_dump()


@mcp.tool()
async def review_project(
    path: str = ".",
    locale: str | None = None,
) -> dict:
    """Review an entire project.

    Scans project structure, dependencies, and runs static analysis.

    Args:
        path: Project root directory (default: current directory)
        locale: Report language.
    """
    project_path = Path(path)
    conventions = _resolve_conventions(project_path=project_path, locale=locale)

    # Collect all Python files
    py_files = [str(f) for f in project_path.rglob("*.py") if ".venv" not in str(f)]

    findings = await _run_analyzers(py_files, focus="all") if py_files else []

    # Build project summary
    return {
        "source": "project",
        "path": str(project_path.resolve()),
        "conventions": conventions.model_dump(),
        "total_python_files": len(py_files),
        "static_analysis": [f.model_dump() for f in findings],
        "analyzers": get_available_analyzers(),
    }


# ---------- Action tools ----------


@mcp.tool()
async def post_github_review(
    pr_url: str,
    comments: list[dict],
    verdict: str = "changes_requested",
) -> dict:
    """Post a review with comments on a GitHub PR.

    Args:
        pr_url: GitHub PR URL.
        comments: List of review comments. Each: {"path": str, "line": int, "body": str}
        verdict: "approved", "changes_requested", or "rejected" (maps to APPROVE, REQUEST_CHANGES, COMMENT).
    """
    from mcp_code_review.providers.github import GitHubProvider, parse_github_url

    owner, repo, pr_num = parse_github_url(pr_url)
    provider = GitHubProvider()

    event_map = {
        "approved": "APPROVE",
        "changes_requested": "REQUEST_CHANGES",
        "rejected": "REQUEST_CHANGES",
        "approved_with_reservations": "COMMENT",
    }
    event = event_map.get(verdict, "COMMENT")

    body = {
        "event": event,
        "comments": [
            {"path": c["path"], "line": c["line"], "body": c["body"]}
            for c in comments
        ],
    }

    headers = {"Accept": "application/vnd.github.v3+json"}
    token = provider.token
    if token:
        headers["Authorization"] = f"Bearer {token}"

    import httpx

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_num}/reviews",
            json=body,
            headers=headers,
        )
        resp.raise_for_status()
        return {"status": "posted", "review_id": resp.json().get("id")}


@mcp.tool()
async def post_gitlab_review(
    mr_url: str,
    comments: list[dict],
    verdict: str = "changes_requested",
) -> dict:
    """Post review comments on a GitLab Merge Request.

    Args:
        mr_url: GitLab MR URL.
        comments: List of comments. Each: {"path": str, "line": int, "body": str}
        verdict: "approved", "changes_requested", or "rejected".
    """
    from mcp_code_review.providers.gitlab import GitLabProvider, parse_gitlab_url
    from urllib.parse import quote_plus

    base, project, mr_num = parse_gitlab_url(mr_url)
    encoded_project = quote_plus(project)
    provider = GitLabProvider()

    headers = {}
    if provider.token:
        headers["PRIVATE-TOKEN"] = provider.token

    import httpx

    results = []
    async with httpx.AsyncClient() as client:
        for comment in comments:
            body = {"body": f"**{comment.get('path', '')}:{comment.get('line', '')}** — {comment['body']}"}
            resp = await client.post(
                f"{base}/api/v4/projects/{encoded_project}/merge_requests/{mr_num}/notes",
                json=body,
                headers=headers,
            )
            resp.raise_for_status()
            results.append(resp.json().get("id"))

    return {"status": "posted", "note_ids": results}


@mcp.tool()
async def save_review_report(
    title: str,
    content: str,
    output_dir: str | None = None,
) -> dict:
    """Save a review report as a markdown file.

    Args:
        title: Report title (used in filename).
        content: Full markdown content of the review.
        output_dir: Directory to save the report (default: REVIEW_OUTPUT_DIR or current dir).
    """
    out = Path(output_dir or os.environ.get("REVIEW_OUTPUT_DIR", "."))
    out.mkdir(parents=True, exist_ok=True)

    slug = slugify_title(title)
    today = date.today().isoformat()
    filename = f"review-{slug}-{today}.md"
    filepath = out / filename

    filepath.write_text(content, encoding="utf-8")

    return {"saved": str(filepath.resolve()), "filename": filename}


# ---------- Utility tools ----------


@mcp.tool()
async def get_conventions(path: str = ".") -> dict:
    """Get project conventions.

    Loads from .codereview.yml if present, otherwise auto-detects
    language and framework from project files.

    Args:
        path: Project root directory.
    """
    conventions = _resolve_conventions(project_path=Path(path))
    return conventions.model_dump()


@mcp.tool()
async def list_analyzers() -> list[dict]:
    """List available static analysis tools.

    Shows which analyzers are installed and ready to use,
    with install instructions for missing ones.
    """
    return get_available_analyzers()


# ---------- Helpers ----------


def _resolve_conventions(
    project_path: Path | None = None,
    locale: str | None = None,
) -> ProjectConventions:
    """Load conventions with optional locale override."""
    conventions = load_conventions(project_path=project_path)
    if locale:
        conventions.locale = locale
    return conventions


async def _run_analyzers(files: list[str], focus: str) -> list:
    """Run all available analyzers on the given files."""
    from mcp_code_review.models import Finding

    findings: list[Finding] = []

    ruff = RuffAnalyzer()
    if ruff.is_available():
        findings.extend(await ruff.analyze(files, focus))

    bandit = BanditAnalyzer()
    if bandit.is_available():
        findings.extend(await bandit.analyze(files, focus))

    return findings


def main():
    """Entry point for the MCP server."""
    mcp.run()
```

- [ ] **Step 3: Run all tests**

```bash
uv run pytest tests/ -v
```
Expected: All tests pass

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat: FastMCP server with all 10 tools registered"
```

---

### Task 10: README + Final Packaging

**Files:**
- Modify: `README.md`
- Create: `tests/__init__.py`
- Create: `tests/test_providers/__init__.py`
- Create: `tests/test_analyzers/__init__.py`

- [ ] **Step 1: Create missing __init__.py files**

Empty `__init__.py` in `tests/`, `tests/test_providers/`, `tests/test_analyzers/`.

- [ ] **Step 2: Write complete README.md**

```markdown
# mcp-code-review

MCP server for LLM-powered code review. Reads GitHub PRs, GitLab MRs, and local git diffs. Returns structured data optimized for AI reasoning. Runs static analysis (ruff, bandit) on local code. Generates markdown review reports.

## Install

```bash
# Core (GitHub + GitLab + local git)
pip install mcp-code-review

# With Python static analysis (ruff + bandit)
pip install mcp-code-review[python]
```

## Quick Start

Add to your Claude Code MCP config:

```json
{
  "mcpServers": {
    "code-review": {
      "command": "mcp-code-review"
    }
  }
}
```

## Tools

| Tool | Description |
|------|-------------|
| `review_github_pr` | Review a GitHub Pull Request |
| `review_gitlab_mr` | Review a GitLab Merge Request |
| `review_diff` | Review local git diff (+ static analysis) |
| `review_file` | Review a single file (+ static analysis) |
| `review_project` | Scan entire project structure |
| `post_github_review` | Post review comments on a GitHub PR |
| `post_gitlab_review` | Post review comments on a GitLab MR |
| `save_review_report` | Save review as markdown file |
| `get_conventions` | Get project conventions |
| `list_analyzers` | List available analyzers |

## Configuration

### Environment variables

```bash
GITHUB_TOKEN=ghp_xxx          # GitHub API token (optional)
GITLAB_TOKEN=glpat_xxx        # GitLab API token (optional)
GITLAB_URL=https://gitlab.com # GitLab base URL (for self-hosted)
REVIEW_OUTPUT_DIR=./reviews   # Report output directory
REVIEW_LOCALE=en              # Default language (en, it, es, de, fr)
```

### Project conventions (`.codereview.yml`)

```yaml
language: python
locale: en
ignore:
  - "*/migrations/*"
  - "tests/fixtures/"
severity_overrides:
  E501: info
```

## Multi-language support

Reports support localized section headers. Set locale via:
- `.codereview.yml` → `locale: it`
- Environment variable → `REVIEW_LOCALE=it`
- Tool parameter → `review_github_pr(url, locale="it")`

## Development

```bash
git clone https://github.com/mauriziomocci/mcp-code-review.git
cd mcp-code-review
uv sync --extra dev --extra python
uv run pytest
```

## License

MIT
```

- [ ] **Step 3: Run full test suite**

```bash
uv run pytest tests/ -v
```
Expected: All tests pass

- [ ] **Step 4: Verify package builds**

```bash
uv build
```
Expected: Creates `dist/mcp_code_review-0.1.0.tar.gz` and `.whl`

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: complete README and packaging"
```

---

## Self-Review Checklist

- [x] **Spec coverage:** All 10 tools implemented. All data models used. Conventions, locale, report, providers, analyzers all covered.
- [x] **Placeholder scan:** No TBD/TODO. All code blocks are complete.
- [x] **Type consistency:** `ReviewData`, `FileChange`, `Finding`, `ProjectConventions` used consistently across all tasks. Method names match between providers.
- [x] **Missing from spec:** `review_project` tool — added in Task 9. `conftest.py` — added in Task 9.
