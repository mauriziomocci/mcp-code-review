"""Git local diff provider."""
from __future__ import annotations

import asyncio
import re

from mcp_code_review.models import FileChange, ProjectConventions, ReviewData


async def run_git(args: list[str], cwd: str = ".") -> str:
    """Run a git command and return stdout as a string."""
    proc = await asyncio.create_subprocess_exec(
        "git",
        *args,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {stderr.decode()}")
    return stdout.decode()


def _parse_diff(diff: str, numstat: str) -> list[FileChange]:
    """Parse git diff and numstat output into FileChange objects."""
    # Build additions/deletions map from numstat
    additions_map: dict[str, int] = {}
    deletions_map: dict[str, int] = {}
    for line in numstat.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) >= 3:
            adds_str, dels_str, path = parts[0], parts[1], parts[2]
            # Binary files show "-" instead of numbers
            additions_map[path] = int(adds_str) if adds_str != "-" else 0
            deletions_map[path] = int(dels_str) if dels_str != "-" else 0

    if not diff.strip():
        return []

    # Split diff by "diff --git" header; skip first empty element
    chunks = re.split(r"(?=^diff --git )", diff, flags=re.MULTILINE)
    files: list[FileChange] = []

    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue

        # Extract paths from "diff --git a/... b/..."
        header_match = re.match(r"diff --git a/(.+?) b/(.+?)$", chunk, re.MULTILINE)
        if not header_match:
            continue

        path_a = header_match.group(1)
        path_b = header_match.group(2)

        # Detect status
        if re.search(r"^new file mode", chunk, re.MULTILINE):
            status = "added"
            path = path_b
        elif re.search(r"^deleted file mode", chunk, re.MULTILINE):
            status = "deleted"
            path = path_a
        elif path_a != path_b:
            status = "renamed"
            path = path_b
        else:
            status = "modified"
            path = path_b

        additions = additions_map.get(path, 0)
        deletions = deletions_map.get(path, 0)

        files.append(
            FileChange(
                path=path,
                status=status,
                additions=additions,
                deletions=deletions,
                patch=chunk,
            )
        )

    return files


class GitLocalProvider:
    """Provides ReviewData from a local git repository diff."""

    async def fetch(self, path: str = ".", base_branch: str = "main") -> ReviewData:
        """Fetch diff between base_branch and HEAD and parse into ReviewData."""
        diff = await run_git(["diff", f"{base_branch}...HEAD"], cwd=path)
        numstat = await run_git(
            ["diff", f"{base_branch}...HEAD", "--numstat"], cwd=path
        )

        files_changed = _parse_diff(diff, numstat)
        total_additions = sum(f.additions for f in files_changed)
        total_deletions = sum(f.deletions for f in files_changed)

        return ReviewData(
            source="local_diff",
            title=f"Local diff vs {base_branch}",
            branch=None,
            base_branch=base_branch,
            url=None,
            files_changed=files_changed,
            total_additions=total_additions,
            total_deletions=total_deletions,
            conventions=ProjectConventions(language="python"),
        )
