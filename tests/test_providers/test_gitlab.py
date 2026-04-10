"""Tests for the GitLab MR provider."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from mcp_code_review.providers.gitlab import GitLabProvider, parse_gitlab_url

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def _load_fixture() -> dict:
    return json.loads((FIXTURES_DIR / "sample_mr_response.json").read_text())


def test_parse_gitlab_url():
    base_url, project, mr_num = parse_gitlab_url(
        "https://gitlab.com/org/repo/-/merge_requests/15"
    )
    assert base_url == "https://gitlab.com"
    assert project == "org/repo"
    assert mr_num == 15


def test_parse_gitlab_url_self_hosted():
    base_url, project, mr_num = parse_gitlab_url(
        "https://git.mycompany.com/team/subgroup/myproject/-/merge_requests/7"
    )
    assert base_url == "https://git.mycompany.com"
    assert project == "team/subgroup/myproject"
    assert mr_num == 7


@pytest.mark.asyncio
async def test_gitlab_fetch():
    """Mock _get with fixture data and verify ReviewData is built correctly."""
    fixture = _load_fixture()
    mr_data = fixture["mr"]
    changes_data = fixture["changes"]

    provider = GitLabProvider(token="fake-token")

    with patch.object(
        provider, "_get", new_callable=AsyncMock
    ) as mock_get:
        mock_get.side_effect = [mr_data, changes_data]

        result = await provider.fetch(
            "https://gitlab.com/org/repo/-/merge_requests/15"
        )

    assert result.source == "gitlab_mr"
    assert result.title == "Fix database migration"
    assert result.author == "janedoe"
    assert result.branch == "fix/migration"
    assert result.base_branch == "main"
    assert result.url == "https://gitlab.com/org/repo/-/merge_requests/15"
    assert len(result.files_changed) == 1

    fc = result.files_changed[0]
    assert fc.path == "migrations/0042.py"
    assert fc.status == "added"
    # diff has 2 added lines (+class Migration: and +    pass)
    assert fc.additions == 2
    assert fc.deletions == 0

    assert result.total_additions == 2
    assert result.total_deletions == 0
