"""Tests for the git local provider."""
from __future__ import annotations

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
    """Verify that a diff + numstat is parsed correctly into ReviewData."""
    provider = GitLocalProvider()

    with patch(
        "mcp_code_review.providers.git_local.run_git",
        new_callable=AsyncMock,
    ) as mock_run_git:
        # First call: diff; second call: numstat
        mock_run_git.side_effect = [SAMPLE_DIFF, SAMPLE_NUMSTAT]

        result = await provider.fetch(path="/fake/repo", base_branch="main")

    assert result.source == "local_diff"
    assert result.base_branch == "main"
    assert len(result.files_changed) == 1

    fc = result.files_changed[0]
    assert fc.path == "src/main.py"
    assert fc.status == "modified"
    assert fc.additions == 2
    assert fc.deletions == 1

    assert result.total_additions == 2
    assert result.total_deletions == 1


@pytest.mark.asyncio
async def test_git_local_fetch_no_changes():
    """Verify that an empty diff results in no files_changed."""
    provider = GitLocalProvider()

    with patch(
        "mcp_code_review.providers.git_local.run_git",
        new_callable=AsyncMock,
    ) as mock_run_git:
        mock_run_git.side_effect = ["", ""]

        result = await provider.fetch(path="/fake/repo", base_branch="main")

    assert result.source == "local_diff"
    assert result.files_changed == []
    assert result.total_additions == 0
    assert result.total_deletions == 0
