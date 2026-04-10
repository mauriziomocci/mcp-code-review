"""Generate markdown review report templates."""

from __future__ import annotations

import re
from datetime import date

from mcp_code_review.locale import get_sections
from mcp_code_review.models import ReviewData


def build_report_template(review_data: ReviewData) -> str:
    """Build a markdown report template with localized headers."""
    s = get_sections(review_data.conventions.locale)
    lines = [
        f"# {s['title']} — {review_data.title}",
        "",
        f"**{s['date']}:** {date.today().isoformat()}",
    ]

    if review_data.author:
        lines.append(f"**{s['author']}:** {review_data.author}")
    if review_data.branch:
        branch_str = review_data.branch
        if review_data.base_branch:
            branch_str = f"{review_data.branch} → {review_data.base_branch}"
        lines.append(f"**{s['branch']}:** {branch_str}")
    if review_data.url:
        lines.append(f"**URL:** {review_data.url}")

    lines.append(
        f"**{s['files_changed']}:** {len(review_data.files_changed)} "
        f"(+{review_data.total_additions} -{review_data.total_deletions})"
    )

    sections = [
        "summary", "code_quality", "static_analysis",
        "security", "performance", "severity_summary", "verdict",
    ]

    for section in sections:
        lines.extend(["", "---", "", f"## {s[section]}", ""])
        if section == "code_quality":
            lines.extend([f"### {s['strengths']}", "", f"### {s['issues_found']}", ""])
        elif section == "verdict":
            lines.extend([
                f"- [ ] {s['approved']}",
                f"- [ ] {s['approved_with_reservations']}",
                f"- [ ] {s['changes_requested']}",
                f"- [ ] {s['rejected']}",
                "",
                f"**{s['rationale']}:**",
                "",
            ])

    return "\n".join(lines)


def slugify_title(title: str) -> str:
    """Convert a title to a URL/filename-safe slug."""
    slug = title.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")
