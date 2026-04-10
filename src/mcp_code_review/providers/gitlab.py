"""GitLab MR provider."""
from __future__ import annotations

import os
import re
from urllib.parse import quote_plus

import httpx

from mcp_code_review.models import FileChange, ProjectConventions, ReviewData


def parse_gitlab_url(url: str) -> tuple[str, str, int]:
    """Extract (base_url, project_path, mr_num) from a GitLab MR URL.

    Supports both gitlab.com and self-hosted instances.
    Raises ValueError for invalid URLs.
    """
    pattern = r"(https?://[^/]+)/(.+)/-/merge_requests/(\d+)"
    match = re.fullmatch(pattern, url.rstrip("/"))
    if not match:
        raise ValueError(f"Invalid GitLab MR URL: {url!r}")
    base_url = match.group(1)
    project_path = match.group(2)
    mr_num = int(match.group(3))
    return base_url, project_path, mr_num


def _count_diff_lines(diff: str) -> tuple[int, int]:
    """Count additions and deletions from a diff string.

    Excludes +++ and --- header lines from the count.
    """
    additions = 0
    deletions = 0
    for line in diff.split("\n"):
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            additions += 1
        elif line.startswith("-"):
            deletions += 1
    return additions, deletions


class GitLabProvider:
    """Provides ReviewData from a GitLab Merge Request."""

    def __init__(
        self,
        token: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.token = token or os.environ.get("GITLAB_TOKEN")
        self.base_url = base_url or os.environ.get("GITLAB_URL", "https://gitlab.com")

    async def _get(self, url: str) -> dict | list:
        """Perform an authenticated GET request to the GitLab API."""
        headers = {}
        if self.token:
            headers["PRIVATE-TOKEN"] = self.token

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()

    async def fetch(self, url: str) -> ReviewData:
        """Fetch MR metadata and changed files from GitLab."""
        base_url, project_path, mr_num = parse_gitlab_url(url)

        # Use the base_url from the parsed URL (supports self-hosted)
        encoded_project = quote_plus(project_path)
        api_base = f"{base_url}/api/v4/projects/{encoded_project}"

        mr = await self._get(f"{api_base}/merge_requests/{mr_num}")
        changes_data = await self._get(
            f"{api_base}/merge_requests/{mr_num}/changes"
        )

        files_changed: list[FileChange] = []
        for change in changes_data.get("changes", []):
            diff = change.get("diff", "")
            additions, deletions = _count_diff_lines(diff)

            if change.get("new_file"):
                status = "added"
            elif change.get("deleted_file"):
                status = "deleted"
            elif change.get("renamed_file"):
                status = "renamed"
            else:
                status = "modified"

            files_changed.append(
                FileChange(
                    path=change["new_path"],
                    status=status,
                    additions=additions,
                    deletions=deletions,
                    patch=diff,
                )
            )

        total_additions = sum(fc.additions for fc in files_changed)
        total_deletions = sum(fc.deletions for fc in files_changed)

        return ReviewData(
            source="gitlab_mr",
            title=mr["title"],
            author=mr["author"]["username"],
            branch=mr["source_branch"],
            base_branch=mr["target_branch"],
            url=mr["web_url"],
            files_changed=files_changed,
            total_additions=total_additions,
            total_deletions=total_deletions,
            conventions=ProjectConventions(language="python"),
        )
