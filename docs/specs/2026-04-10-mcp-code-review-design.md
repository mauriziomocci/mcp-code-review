# MCP Code Review — Design Spec

**Date:** 2026-04-10
**Status:** Approved
**Author:** Maurizio Mocci + Claude

---

## Overview

MCP server for structured code review. Reads PRs from GitHub, MRs from GitLab, and local git diffs. Returns structured data for LLM-powered review. Runs static analysis (ruff, bandit) on local code. Generates markdown review reports. Posts review comments back to PR/MR.

Published on PyPI as `mcp-code-review` with optional extras for Python static analysis.

## Goals

- Unified interface for GitHub PR, GitLab MR, and local git diff review
- Structured output optimized for LLM reasoning
- Static analysis (ruff, bandit) on local diffs only (not remote PRs)
- Markdown review report generation with multi-language support
- Post review comments back to GitHub/GitLab
- Zero mandatory configuration — works out of the box
- Optional `.codereview.yml` for project-specific conventions
- PyPI-ready with optional extras

## Non-Goals (v1)

- Structural analysis (cyclomatic complexity, function length metrics) — v1.1
- Static analysis on remote PR files (unreliable without full project context) — v1.1
- Languages other than Python for static analysis — v1.1
- CI/CD integration — v1.1
- Review history/persistence — v1.1

---

## Tools

### Review tools

| Tool | Parameters | Returns |
|------|-----------|---------|
| `review_github_pr` | `url: str`, `focus?: str`, `locale?: str` | PR metadata + diffs + conventions |
| `review_gitlab_mr` | `url: str`, `focus?: str`, `locale?: str` | MR metadata + diffs + conventions |
| `review_diff` | `path?: str`, `base_branch?: str`, `focus?: str`, `locale?: str` | Local diff + static analysis + conventions |
| `review_file` | `path: str`, `focus?: str`, `locale?: str` | File content + static analysis |
| `review_project` | `path?: str`, `locale?: str` | Project structure, dependencies, security scan |

### Action tools

| Tool | Parameters | Returns |
|------|-----------|---------|
| `post_github_review` | `pr_url: str`, `comments: list`, `verdict: str` | Posts review on PR |
| `post_gitlab_review` | `mr_url: str`, `comments: list`, `verdict: str` | Posts review on MR |
| `save_review_report` | `title: str`, `content: str`, `output_dir?: str` | Saves `review-<title>-<date>.md` |

### Utility tools

| Tool | Parameters | Returns |
|------|-----------|---------|
| `get_conventions` | `path?: str` | Project conventions (from file or auto-detect) |
| `list_analyzers` | — | Available/installed analyzers |

### Parameter details

- `focus`: `"all"` (default), `"security"`, `"performance"`, `"quality"` — tells the LLM what to focus on, and filters static analysis rules accordingly
- `locale`: `"en"` (default), `"it"`, `"es"`, `"de"`, `"fr"` — language for report headers and labels. Overrides `.codereview.yml` setting.

---

## Data Model

```python
@dataclass
class ReviewData:
    source: str                    # "github_pr", "gitlab_mr", "local_diff", "file"
    title: str
    author: str | None
    branch: str | None
    base_branch: str | None
    url: str | None
    files_changed: list[FileChange]
    total_additions: int
    total_deletions: int
    static_analysis: list[Finding]
    conventions: ProjectConventions

@dataclass
class FileChange:
    path: str
    status: str                    # "added", "modified", "deleted", "renamed"
    additions: int
    deletions: int
    patch: str                     # the diff
    content: str | None            # full content (only for review_file)

@dataclass
class Finding:
    tool: str                      # "ruff", "bandit"
    rule: str                      # "E501", "B101", etc.
    severity: str                  # "error", "warning", "info"
    message: str
    file: str
    line: int
    code_snippet: str | None

@dataclass
class ProjectConventions:
    language: str                  # auto-detected or from .codereview.yml
    framework: str | None          # auto-detected
    locale: str                    # "en" default
    ignore_patterns: list[str]
    severity_overrides: dict
    custom_rules: dict
```

---

## Project Conventions

### `.codereview.yml` (optional)

```yaml
language: python
locale: en
ignore:
  - "*/migrations/*"
  - "tests/fixtures/"
severity_overrides:
  E501: info        # line too long → info instead of warning
custom_rules:
  require_type_hints: false
  max_file_lines: 500
```

### Auto-detection (when no `.codereview.yml`)

1. Check `pyproject.toml` → Python
2. Check `requirements.txt` / `setup.py` → Python
3. Check `INSTALLED_APPS` in settings → Django
4. Check `FastAPI` / `Flask` imports → framework detection
5. Default locale: `en` (override via env var `REVIEW_LOCALE`)

---

## Authentication

Via environment variables only. No global config file.

```bash
# GitHub (optional — without token, only public repos)
GITHUB_TOKEN=ghp_xxx

# GitLab (optional — without token, only public repos)
GITLAB_TOKEN=glpat_xxx
GITLAB_URL=https://gitlab.com    # default; override for self-hosted

# Defaults (optional)
REVIEW_OUTPUT_DIR=./reviews      # where to save reports
REVIEW_LOCALE=en                 # default locale
```

---

## Static Analysis Strategy

**Local diffs only.** Ruff and bandit run on the full project where all context (imports, config, dependencies) is available. For remote PRs/MRs, only structured data is returned — the LLM reasons on the diff directly.

**Graceful degradation.** If ruff/bandit are not installed, the review works anyway. The `static_analysis` field is empty, and `list_analyzers` shows what is missing with install instructions.

### Ruff

```bash
ruff check --output-format=json --select=ALL <files>
```

Output parsed into `Finding[]`. Respects project's `ruff.toml` / `pyproject.toml [tool.ruff]` if present.

### Bandit

```bash
bandit -f json -r <files>
```

Output parsed into `Finding[]`. Focuses on security findings.

---

## Report Template

The `save_review_report` tool saves markdown generated by the LLM. The MCP provides a locale-aware header template that the LLM fills in.

### Localized section headers

```python
REPORT_SECTIONS = {
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
}
```

---

## Project Structure

```
mcp-code-review/
├── pyproject.toml
├── README.md
├── LICENSE                        # MIT
├── .gitignore
├── .env.example
├── src/
│   └── mcp_code_review/
│       ├── __init__.py
│       ├── server.py              # FastMCP server, registers all tools
│       ├── models.py              # ReviewData, FileChange, Finding, ProjectConventions
│       ├── locale.py              # REPORT_SECTIONS dict per language
│       ├── conventions.py         # load .codereview.yml + auto-detect
│       ├── report.py              # generate report markdown template
│       ├── providers/
│       │   ├── __init__.py
│       │   ├── base.py            # abstract Provider class
│       │   ├── github.py          # GitHub API → ReviewData
│       │   ├── gitlab.py          # GitLab API → ReviewData
│       │   └── git_local.py       # git diff/log → ReviewData
│       └── analyzers/
│           ├── __init__.py
│           ├── base.py            # abstract Analyzer class
│           ├── ruff.py            # run ruff, parse → Finding[]
│           └── bandit.py          # run bandit, parse → Finding[]
└── tests/
    ├── conftest.py
    ├── test_providers/
    │   ├── test_github.py
    │   ├── test_gitlab.py
    │   └── test_git_local.py
    ├── test_analyzers/
    │   ├── test_ruff.py
    │   └── test_bandit.py
    ├── test_conventions.py
    ├── test_report.py
    └── fixtures/
        ├── sample_diff.patch
        ├── sample_pr_response.json
        ├── sample_mr_response.json
        └── sample_codereview.yml
```

---

## PyPI Configuration

```toml
[project]
name = "mcp-code-review"
version = "0.1.0"
description = "MCP server for LLM-powered code review — GitHub PRs, GitLab MRs, local diffs"
readme = "README.md"
requires-python = ">=3.10"
license = {text = "MIT"}
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
```

---

## Flow: Review a GitHub PR

```
1. LLM calls: review_github_pr(url="github.com/org/repo/pull/42")

2. GitHub provider:
   - GET /repos/{owner}/{repo}/pulls/42        → title, author, branch, description
   - GET /repos/{owner}/{repo}/pulls/42/files  → list of FileChange with patches

3. Conventions loader:
   - GET repo contents .codereview.yml via API
   - If not found: auto-detect from pyproject.toml etc.

4. Static analysis: SKIPPED (remote PR, no local files)

5. Returns ReviewData to LLM (structured JSON)

6. LLM analyzes diffs, writes review

7. LLM calls: save_review_report(title="PR #42 - Add auth", content="...")
   → Saves review-pr-42-add-auth-2026-04-10.md

8. (Optional) LLM calls: post_github_review(pr_url, comments, verdict="changes_requested")
   → Posts review comments on the PR via GitHub API
```

## Flow: Review a local diff

```
1. LLM calls: review_diff(base_branch="main")

2. Git local provider:
   - git diff main...HEAD                      → list of FileChange with patches
   - git log main..HEAD --oneline              → commit history

3. Conventions loader:
   - Read .codereview.yml from project root
   - If not found: auto-detect

4. Static analysis (if installed):
   - ruff check --output-format=json on changed files
   - bandit -f json on changed files
   - Results attached as Finding[]

5. Returns ReviewData to LLM

6. LLM analyzes, writes review, optionally saves report
```

---

## v1.1 Roadmap (not in scope)

- Structural analyzer (cyclomatic complexity, function length, file size metrics)
- Static analysis on remote PR files (clone to temp dir)
- JavaScript/TypeScript support (eslint)
- Review history persistence (SQLite)
- CI/CD integration (GitHub Actions, GitLab CI)
- Configurable review templates
