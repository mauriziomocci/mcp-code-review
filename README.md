# mcp-code-review

[![PyPI version](https://img.shields.io/pypi/v/mcp-code-review.svg)](https://pypi.org/project/mcp-code-review/)
[![Python versions](https://img.shields.io/pypi/pyversions/mcp-code-review.svg)](https://pypi.org/project/mcp-code-review/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An MCP server that brings structured code review into any MCP-compatible client. Review GitHub Pull Requests, GitLab Merge Requests, and local git diffs — with static analysis, project conventions, and multi-language report output.

---

## Features

- Review GitHub PRs and GitLab MRs by URL
- Review local git diffs against any base branch
- Review individual files with static analysis
- Scan entire projects for issues
- Post review comments back to GitHub PRs and GitLab MRs
- Static analysis via Ruff (linting) and Bandit (security)
- Project conventions loaded from `.codereview.yml` or auto-detected
- Multi-language report output: English, Italian, Spanish
- Configurable review focus: all, security, performance, quality
- Saves review reports as Markdown files
- **Professional engineering checklist** with 13 analysis categories (SOLID, architecture, security, performance, data layer, observability, concurrency, and more)

---

## Installation

Install the base package:

```bash
pip install mcp-code-review
```

Install with Python static analysis tools (Ruff + Bandit):

```bash
pip install "mcp-code-review[python]"
```

---

## Quick Start

Add `mcp-code-review` to your MCP client configuration.

**Claude Code** (`~/.claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "mcp-code-review": {
      "command": "mcp-code-review",
      "env": {
        "GITHUB_TOKEN": "ghp_your_token_here",
        "GITLAB_TOKEN": "glpat_your_token_here"
      }
    }
  }
}
```

**Cursor** (`.cursor/mcp.json` in project root or `~/.cursor/mcp.json` globally):

```json
{
  "mcpServers": {
    "mcp-code-review": {
      "command": "mcp-code-review",
      "env": {
        "GITHUB_TOKEN": "ghp_your_token_here"
      }
    }
  }
}
```

Once configured, tools are available in the assistant context. Example prompts:

- *"Review the PR at https://github.com/org/repo/pull/42"*
- *"Review the local diff against main, focus on security"*
- *"Review the file src/auth.py"*

---

## Tools

| Tool | Description |
|------|-------------|
| `review_github_pr` | Fetch and review a GitHub Pull Request by URL |
| `review_gitlab_mr` | Fetch and review a GitLab Merge Request by URL |
| `review_diff` | Review local git diff against a base branch |
| `review_file` | Review a single file with static analysis |
| `review_project` | Scan an entire project: structure, deps, security |
| `post_github_review` | Post review comments on a GitHub PR |
| `post_gitlab_review` | Post review comments on a GitLab MR |
| `save_review_report` | Save a review report as a Markdown file |
| `get_conventions` | Get project conventions from config or auto-detect |
| `list_analyzers` | List available static analysis tools |

All tools accept a `focus` parameter (`"all"`, `"security"`, `"performance"`, `"quality"`) and a `locale` parameter for report language.

---

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GITHUB_TOKEN` | GitHub personal access token | — |
| `GITLAB_TOKEN` | GitLab personal access token | — |
| `GITLAB_URL` | GitLab instance base URL | `https://gitlab.com` |
| `REVIEW_LOCALE` | Default report language (`en`, `it`, `es`) | `en` |
| `REVIEW_OUTPUT_DIR` | Directory for saved review reports | `.` |

### .codereview.yml

Place a `.codereview.yml` file at the root of a project to configure conventions:

```yaml
language: python
framework: fastapi     # optional: django, flask, fastapi
locale: en             # en | it | es

ignore:
  - "migrations/**"
  - "tests/**"

severity_overrides:
  E501: warning        # downgrade line-length errors to warnings

custom_rules:
  max_function_lines: 50
  require_docstrings: true
```

If no `.codereview.yml` is found, the server auto-detects the language and framework from project files (`pyproject.toml`, `requirements.txt`, import patterns).

---

## Multi-Language Support

Review reports can be generated in English, Italian, or Spanish. Set the language per-request via the `locale` parameter, or globally via the `REVIEW_LOCALE` environment variable or the `locale` key in `.codereview.yml`.

Supported locales:

| Code | Language |
|------|----------|
| `en` | English |
| `it` | Italian |
| `es` | Spanish |

---

## Claude Code Skill (Optional)

The repository includes a companion skill for Claude Code that provides a structured review process on top of the MCP tools — checklist, severity classification, report format, and multi-language support.

### Install the skill

```bash
# Symlink into Claude Code skills directory
ln -s /path/to/mcp-code-review/skills/code-review-mcp ~/.claude/skills/code-review-mcp
```

Or copy the file manually:

```bash
mkdir -p ~/.claude/skills/code-review-mcp
cp /path/to/mcp-code-review/skills/code-review-mcp/SKILL.md ~/.claude/skills/code-review-mcp/
```

The skill activates automatically when you ask for a code review in Claude Code. It orchestrates the MCP tools in the right order and produces a structured markdown report.

### What the skill adds

| Without skill | With skill |
|--------------|-----------|
| You call tools manually | Tools called automatically in the right order |
| No structured process | 13-category engineering checklist (see below) |
| Same depth for every change | Review depth scales to change size (trivial to large) |
| No change-type awareness | Different priorities for feature/bugfix/refactor/migration |
| Raw data returned | Full markdown report with severity classification |
| No verdict | Verdict: approved / changes requested / rejected |
| You decide the format | Consistent format across all reviews |

### Analysis Categories

The skill applies professional software engineering standards across 13 categories:

| # | Category | Key checks |
|---|----------|-----------|
| 1 | **PR/MR Description** | Purpose, scope, testing instructions, breaking changes |
| 2 | **Architecture & Design** | SOLID principles, coupling/cohesion, design patterns, separation of concerns |
| 3 | **Correctness** | Logic errors, edge cases, race conditions, contract violations |
| 4 | **Security** | OWASP top 10, injection, auth, crypto, secrets, CSRF, rate limiting |
| 5 | **Performance** | N+1 queries, algorithmic complexity, caching, connection pooling |
| 6 | **Error Handling** | Specific exceptions, resource cleanup, fail-fast, graceful degradation |
| 7 | **Code Quality** | Naming, DRY, nesting depth, magic numbers, abstraction level |
| 8 | **Testing** | Behavior tests, edge cases, minimal mocking, regression tests |
| 9 | **API Design** | Backward compatibility, REST conventions, versioning |
| 10 | **Data Layer** | Migration safety, rollback plan, schema design, Django-specific |
| 11 | **Dependencies** | License, maintenance, security, version pinning, necessity |
| 12 | **Observability** | Logging, metrics, health checks, tracing, PII protection |
| 13 | **Concurrency/Async** | Deadlocks, idempotency, retry safety, Celery, async/await |

---

## Development

Clone the repository and install dependencies with [uv](https://github.com/astral-sh/uv):

```bash
git clone https://github.com/mauriziomocci/mcp-code-review.git
cd mcp-code-review
uv sync --extra python
```

Run the test suite:

```bash
uv run pytest tests/ -v
```

Run linting:

```bash
uv run ruff check src/
```

---

## License

MIT License. See [LICENSE](LICENSE) for details.
