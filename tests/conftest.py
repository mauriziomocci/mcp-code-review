"""Shared test fixtures."""
import pytest
from mcp_code_review.models import FileChange, Finding, ProjectConventions, ReviewData

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
            FileChange(path="src/auth.py", status="added", additions=50, deletions=0, patch="@@ -0,0 +1,50 @@\n+import jwt"),
        ],
        total_additions=50,
        total_deletions=0,
        static_analysis=[
            Finding(tool="ruff", rule="F401", severity="warning", message="jwt imported but unused", file="src/auth.py", line=1),
        ],
        conventions=sample_conventions,
    )
