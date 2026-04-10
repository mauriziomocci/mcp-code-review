# CLAUDE.md

Guide for Claude Code - mcp-code-review: MCP server for LLM-powered code review.

## Quick Reference

```bash
# Development
uv sync --extra dev --extra python
uv run pytest tests/ -v

# Run server locally
uv run mcp-code-review

# Build package
uv build

# Lint
uv run ruff check src/ tests/
```

## Architecture

**Stack**: Python 3.10+ | FastMCP 3.x | httpx | Pydantic 2.x | PyYAML

**Package**: `mcp-code-review` on PyPI. Entry point: `mcp_code_review.server:main`

**Structure**: Monolithic FastMCP server with providers and analyzers.

```
src/mcp_code_review/
├── server.py          # FastMCP server, all 10 tools registered here
├── models.py          # Pydantic models: ReviewData, FileChange, Finding, ProjectConventions
├── locale.py          # REPORT_SECTIONS dict per language (en, it, es)
├── conventions.py     # Load .codereview.yml + auto-detect project type
├── report.py          # Generate markdown report template with localized headers
├── providers/
│   ├── base.py        # Provider protocol
│   ├── github.py      # GitHub API → ReviewData
│   ├── gitlab.py      # GitLab API → ReviewData
│   └── git_local.py   # git diff/log → ReviewData
└── analyzers/
    ├── base.py        # Analyzer protocol
    ├── ruff.py        # Run ruff, parse JSON → Finding[]
    └── bandit.py      # Run bandit, parse JSON → Finding[]
```

**Design principle**: providers produce a unified `ReviewData`, analyzers produce `list[Finding]`. The MCP server prepares structured data for the LLM — the reasoning happens in the LLM, not here.

**Data flow**: Provider fetches data → Conventions loader attaches project config → Analyzers run on local files only → Tool returns `ReviewData` as JSON → LLM analyzes and writes review.

## Tools

| Tool | What it does |
|------|-------------|
| `review_github_pr` | Fetch GitHub PR metadata + diffs + conventions |
| `review_gitlab_mr` | Fetch GitLab MR metadata + diffs + conventions |
| `review_diff` | Local git diff + static analysis + conventions |
| `review_file` | Single file content + static analysis |
| `review_project` | Full project scan (structure, deps, security) |
| `post_github_review` | Post review comments on a GitHub PR |
| `post_gitlab_review` | Post review comments on a GitLab MR |
| `save_review_report` | Save review as `review-<title>-<date>.md` |
| `get_conventions` | Load project conventions |
| `list_analyzers` | Show available/installed analyzers |

## Agent Rules

### CRITICAL: Understand Before Implementing

Before writing any code, invest time understanding the full context: how the existing system works, why it works that way, what already exists. Read and understand existing files before modifying code.

### CRITICAL: Verify Before Asserting

Never present assumptions as verified facts. Before stating how something works, verify it in the source code. If something has not been verified, say so explicitly.

### Core Behavior

- **Read CLAUDE.md first**: before starting any task, re-read these rules
- Read and understand existing files before modifying code
- Avoid over-engineering: only implement what is requested
- Prefer editing existing files over creating new ones
- Do NOT create documentation files unless explicitly requested
- Commit messages: **English**, no references to Claude/AI
- Code: PEP 8, double quotes, type hints on public interfaces
- Tests: **ZERO failing tests**

### Execution Discipline

1. **Plan before acting**: understand the codebase context before writing code
2. **Verify before asserting**: never state something as fact without evidence
3. **Handle errors, do not ignore them**: read the full error, diagnose root cause, fix and re-test
4. **Ask for clarification when needed**: if requirements are ambiguous, ask before proceeding
5. **Learn and update directives**: propose updates to CLAUDE.md if you discover recurring patterns

### Git Commits

```
type(scope): brief description

CHANGE: Technical explanation.
```

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`
Scope: module name (e.g. `models`, `providers`, `analyzers`, `server`, `report`)

**FORBIDDEN**: References to Claude/AI, emoji, Co-Authored-By, attribution lines. Commits must appear as entirely written by the human developer.

### Mandatory Code Review

After writing any code, BEFORE proposing a commit, perform a thorough code review verifying:

1. **Pythonic style**: clean, idiomatic Python
2. **DRY violations**: duplicated logic that can be extracted
3. **Exception handling**: specific exceptions, never bare `except Exception`
4. **Type consistency**: models, method signatures, and property names consistent across modules
5. **Test quality**: tests verify real behavior, not just mock behavior
6. **Security**: no sensitive data exposure, no hardcoded secrets

Fix issues BEFORE committing.

## Conventions

### Models

All data models are Pydantic v2 `BaseModel` in `models.py`. Every provider must return a `ReviewData` instance. Every analyzer must return `list[Finding]`.

### Providers

Each provider implements the `Provider` protocol from `providers/base.py`. The `fetch()` method is async and returns `ReviewData`. Providers do NOT run analyzers — that is done by the server.

### Analyzers

Each analyzer implements the `Analyzer` protocol from `analyzers/base.py`. The `is_available()` static method checks if the binary is installed. The `analyze()` method is async, runs the tool via subprocess, and parses JSON output into `list[Finding]`.

Static analysis runs **only on local files** (not remote PR/MR files). For remote PRs, the `static_analysis` field is empty.

### Locale

Multi-language support via `locale.py`. Section headers in `REPORT_SECTIONS` dict, keyed by locale code (`en`, `it`, `es`). Fallback to English if locale not found. New languages: add a dict entry, nothing else.

### Conventions Loader

Priority: explicit `.codereview.yml` > auto-detect from project files > defaults.
Auto-detection checks: `pyproject.toml` (Python), `INSTALLED_APPS` (Django), `FastAPI(` (FastAPI), `Flask(` (Flask).

### Environment Variables

```bash
GITHUB_TOKEN=          # GitHub API token (optional)
GITLAB_TOKEN=          # GitLab API token (optional)
GITLAB_URL=            # GitLab base URL (default: https://gitlab.com)
REVIEW_OUTPUT_DIR=     # Report output directory (default: .)
REVIEW_LOCALE=         # Default locale (default: en)
```

## Testing

```bash
uv run pytest tests/ -v                    # All tests
uv run pytest tests/test_models.py -v      # Single module
uv run pytest -k "github" -v              # By keyword
```

Tests use `unittest.mock` for external dependencies (HTTP calls, subprocess, git commands). No real API calls in tests. Fixtures in `tests/fixtures/`.

## Workflows

### Adding a new provider

1. Create `src/mcp_code_review/providers/<name>.py`
2. Implement `Provider` protocol: `async def fetch(**kwargs) -> ReviewData`
3. Add tests in `tests/test_providers/test_<name>.py`
4. Register tool in `server.py`

### Adding a new analyzer

1. Create `src/mcp_code_review/analyzers/<name>.py`
2. Implement `Analyzer` protocol: `is_available()` + `async def analyze(files, focus) -> list[Finding]`
3. Add to `analyzers/__init__.py` → `get_available_analyzers()`
4. Add tests in `tests/test_analyzers/test_<name>.py`
5. Add to `pyproject.toml` optional dependencies if needed

### Adding a new locale

1. Add dict entry in `locale.py` → `REPORT_SECTIONS["xx"]`
2. No other changes needed — `get_sections()` handles fallback

## Known Limitations

- Static analysis on remote PR/MR files not supported (unreliable without full project context) — planned for v1.1
- Only Python analyzers (ruff, bandit) — other languages planned for v1.1
- No review history/persistence — planned for v1.1
