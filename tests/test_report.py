from mcp_code_review.report import build_report_template, slugify_title
from mcp_code_review.models import ReviewData, ProjectConventions


def test_build_report_template_english():
    conventions = ProjectConventions(language="python", locale="en")
    rd = ReviewData(
        source="github_pr",
        title="Add authentication",
        author="johndoe",
        branch="feature/auth",
        base_branch="main",
        url="https://github.com/org/repo/pull/42",
        files_changed=[],
        total_additions=100,
        total_deletions=20,
        conventions=conventions,
    )
    template = build_report_template(rd)
    assert "# Code Review" in template
    assert "Add authentication" in template
    assert "johndoe" in template
    assert "## Summary" in template
    assert "## Verdict" in template


def test_build_report_template_italian():
    conventions = ProjectConventions(language="python", locale="it")
    rd = ReviewData(
        source="gitlab_mr",
        title="Fix login bug",
        files_changed=[],
        total_additions=5,
        total_deletions=2,
        conventions=conventions,
    )
    template = build_report_template(rd)
    assert "## Riepilogo" in template
    assert "## Verdetto" in template


def test_slugify_title():
    assert slugify_title("Add user authentication") == "add-user-authentication"
    assert slugify_title("PR #42 — Fix bug!") == "pr-42-fix-bug"
    assert slugify_title("  spaces  ") == "spaces"
