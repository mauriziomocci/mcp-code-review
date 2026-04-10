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
from mcp_code_review.models import FileChange, Finding, ProjectConventions, ReviewData
from mcp_code_review.providers.git_local import GitLocalProvider
from mcp_code_review.providers.github import GitHubProvider
from mcp_code_review.providers.gitlab import GitLabProvider
from mcp_code_review.report import build_report_template, slugify_title

mcp = FastMCP("MCP Code Review")


@mcp.tool()
async def review_github_pr(url: str, focus: str = "all", locale: str | None = None) -> dict:
    """Review a GitHub Pull Request. Fetches PR metadata, file diffs, and project conventions.

    Args:
        url: GitHub PR URL (e.g. https://github.com/org/repo/pull/42)
        focus: Review focus — "all", "security", "performance", "quality"
        locale: Report language — "en", "it", "es". Overrides project config.
    """
    provider = GitHubProvider()
    review = await provider.fetch(url=url)
    review.conventions = _resolve_conventions(locale=locale)
    return review.model_dump()


@mcp.tool()
async def review_gitlab_mr(url: str, focus: str = "all", locale: str | None = None) -> dict:
    """Review a GitLab Merge Request. Fetches MR metadata, file diffs, and project conventions.

    Args:
        url: GitLab MR URL (e.g. https://gitlab.com/org/repo/-/merge_requests/15)
        focus: Review focus — "all", "security", "performance", "quality"
        locale: Report language — "en", "it", "es".
    """
    provider = GitLabProvider()
    review = await provider.fetch(url=url)
    review.conventions = _resolve_conventions(locale=locale)
    return review.model_dump()


@mcp.tool()
async def review_diff(path: str = ".", base_branch: str = "main", focus: str = "all", locale: str | None = None) -> dict:
    """Review local git diff. Compares HEAD against base branch with static analysis.

    Args:
        path: Project root directory (default: current directory)
        base_branch: Branch to compare against (default: main)
        focus: Review focus — "all", "security", "performance", "quality"
        locale: Report language.
    """
    provider = GitLocalProvider()
    review = await provider.fetch(path=path, base_branch=base_branch)
    review.conventions = _resolve_conventions(project_path=Path(path), locale=locale)

    changed_files = [f.path for f in review.files_changed if f.status != "deleted"]
    if changed_files:
        review.static_analysis = await _run_analyzers(changed_files, focus)

    return review.model_dump()


@mcp.tool()
async def review_file(path: str, focus: str = "all", locale: str | None = None) -> dict:
    """Review a single file with static analysis.

    Args:
        path: Path to the file to review.
        focus: Review focus — "all", "security", "performance", "quality"
        locale: Report language.
    """
    file_path = Path(path)
    if not file_path.is_file():
        return {"error": f"File not found: {path}"}

    content = file_path.read_text(errors="ignore")
    lines = content.splitlines()

    file_change = FileChange(
        path=str(file_path), status="modified", additions=len(lines),
        deletions=0, patch="", content=content,
    )

    project_path = file_path.parent
    conventions = _resolve_conventions(project_path=project_path, locale=locale)
    findings = await _run_analyzers([str(file_path)], focus)

    review = ReviewData(
        source="file", title=file_path.name, files_changed=[file_change],
        total_additions=len(lines), total_deletions=0,
        static_analysis=findings, conventions=conventions,
    )
    return review.model_dump()


@mcp.tool()
async def review_project(path: str = ".", locale: str | None = None) -> dict:
    """Scan entire project: structure, dependencies, security.

    Args:
        path: Project root directory (default: current directory)
        locale: Report language.
    """
    project_path = Path(path)
    conventions = _resolve_conventions(project_path=project_path, locale=locale)

    py_files = [str(f) for f in project_path.rglob("*.py") if ".venv" not in str(f)]
    findings = await _run_analyzers(py_files, focus="all") if py_files else []

    return {
        "source": "project",
        "path": str(project_path.resolve()),
        "conventions": conventions.model_dump(),
        "total_python_files": len(py_files),
        "static_analysis": [f.model_dump() for f in findings],
        "analyzers": get_available_analyzers(),
    }


@mcp.tool()
async def post_github_review(pr_url: str, comments: list[dict], verdict: str = "changes_requested") -> dict:
    """Post review comments on a GitHub PR.

    Args:
        pr_url: GitHub PR URL.
        comments: List of comments. Each: {"path": str, "line": int, "body": str}
        verdict: "approved", "changes_requested", or "rejected".
    """
    from mcp_code_review.providers.github import parse_github_url
    import httpx

    owner, repo, pr_num = parse_github_url(pr_url)
    provider = GitHubProvider()

    event_map = {
        "approved": "APPROVE",
        "changes_requested": "REQUEST_CHANGES",
        "rejected": "REQUEST_CHANGES",
        "approved_with_reservations": "COMMENT",
    }

    body = {
        "event": event_map.get(verdict, "COMMENT"),
        "comments": [{"path": c["path"], "line": c["line"], "body": c["body"]} for c in comments],
    }

    headers = {"Accept": "application/vnd.github.v3+json"}
    if provider.token:
        headers["Authorization"] = f"Bearer {provider.token}"

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_num}/reviews",
            json=body, headers=headers,
        )
        resp.raise_for_status()
        return {"status": "posted", "review_id": resp.json().get("id")}


@mcp.tool()
async def post_gitlab_review(mr_url: str, comments: list[dict], verdict: str = "changes_requested") -> dict:
    """Post review comments on a GitLab MR.

    Args:
        mr_url: GitLab MR URL.
        comments: List of comments. Each: {"path": str, "line": int, "body": str}
        verdict: "approved", "changes_requested", or "rejected".
    """
    from mcp_code_review.providers.gitlab import parse_gitlab_url
    from urllib.parse import quote_plus
    import httpx

    base, project, mr_num = parse_gitlab_url(mr_url)
    encoded_project = quote_plus(project)
    provider = GitLabProvider()

    headers = {}
    if provider.token:
        headers["PRIVATE-TOKEN"] = provider.token

    results = []
    async with httpx.AsyncClient() as client:
        for comment in comments:
            body = {"body": f"**{comment.get('path', '')}:{comment.get('line', '')}** — {comment['body']}"}
            resp = await client.post(
                f"{base}/api/v4/projects/{encoded_project}/merge_requests/{mr_num}/notes",
                json=body, headers=headers,
            )
            resp.raise_for_status()
            results.append(resp.json().get("id"))

    return {"status": "posted", "note_ids": results}


@mcp.tool()
async def save_review_report(title: str, content: str, output_dir: str | None = None) -> dict:
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


@mcp.tool()
async def get_conventions(path: str = ".") -> dict:
    """Get project conventions from .codereview.yml or auto-detect.

    Args:
        path: Project root directory.
    """
    conventions = _resolve_conventions(project_path=Path(path))
    return conventions.model_dump()


@mcp.tool()
async def list_analyzers() -> list[dict]:
    """List available static analysis tools with install instructions."""
    return get_available_analyzers()


# ---------- Helpers ----------

def _resolve_conventions(project_path: Path | None = None, locale: str | None = None) -> ProjectConventions:
    conventions = load_conventions(project_path=project_path)
    if locale:
        conventions.locale = locale
    return conventions


async def _run_analyzers(files: list[str], focus: str) -> list[Finding]:
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
