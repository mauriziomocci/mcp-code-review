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
