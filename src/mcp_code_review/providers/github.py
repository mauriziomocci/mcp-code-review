"""GitHub PR provider."""
from __future__ import annotations

import os
import re

import httpx

from mcp_code_review.models import FileChange, ProjectConventions, ReviewData


def parse_github_url(url: str) -> tuple[str, str, int]:
    """Extract (owner, repo, pr_num) from a GitHub PR URL.

    Raises ValueError for invalid URLs.
    """
    pattern = r"https://github\.com/([^/]+)/([^/]+)/pull/(\d+)"
    match = re.fullmatch(pattern, url.rstrip("/"))
    if not match:
        raise ValueError(f"Invalid GitHub PR URL: {url!r}")
    owner, repo, pr_num = match.group(1), match.group(2), int(match.group(3))
    return owner, repo, pr_num


class GitHubProvider:
    """Provides ReviewData from a GitHub Pull Request."""

    BASE_URL = "https://api.github.com"

    def __init__(self, token: str | None = None) -> None:
        self.token = token or os.environ.get("GITHUB_TOKEN")

    async def _get(self, endpoint: str) -> dict | list:
        """Perform an authenticated GET request to the GitHub API."""
        headers = {"Accept": "application/vnd.github+json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}{endpoint}", headers=headers
            )
            response.raise_for_status()
            return response.json()

    async def fetch(self, url: str) -> ReviewData:
        """Fetch PR metadata and changed files from GitHub."""
        owner, repo, pr_num = parse_github_url(url)

        pr = await self._get(f"/repos/{owner}/{repo}/pulls/{pr_num}")
        files = await self._get(f"/repos/{owner}/{repo}/pulls/{pr_num}/files")

        files_changed: list[FileChange] = []
        for f in files:
            files_changed.append(
                FileChange(
                    path=f["filename"],
                    status=f["status"],
                    additions=f["additions"],
                    deletions=f["deletions"],
                    patch=f.get("patch", ""),
                )
            )

        total_additions = sum(fc.additions for fc in files_changed)
        total_deletions = sum(fc.deletions for fc in files_changed)

        return ReviewData(
            source="github_pr",
            title=pr["title"],
            author=pr["user"]["login"],
            branch=pr["head"]["ref"],
            base_branch=pr["base"]["ref"],
            url=pr["html_url"],
            files_changed=files_changed,
            total_additions=total_additions,
            total_deletions=total_deletions,
            conventions=ProjectConventions(language="python"),
        )
