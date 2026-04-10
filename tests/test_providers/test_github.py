"""Tests for the GitHub PR provider."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from mcp_code_review.providers.github import GitHubProvider, parse_github_url

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def _load_fixture() -> dict:
    return json.loads((FIXTURES_DIR / "sample_pr_response.json").read_text())


def test_parse_github_url():
    owner, repo, pr_num = parse_github_url("https://github.com/org/repo/pull/42")
    assert owner == "org"
    assert repo == "repo"
    assert pr_num == 42


def test_parse_github_url_invalid():
    with pytest.raises(ValueError, match="Invalid GitHub PR URL"):
        parse_github_url("https://github.com/org/repo/issues/42")


@pytest.mark.asyncio
async def test_github_fetch():
    """Mock _get with fixture data and verify ReviewData is built correctly."""
    fixture = _load_fixture()
    pr_data = fixture["pr"]
    files_data = fixture["files"]

    provider = GitHubProvider(token="fake-token")

    with patch.object(
        provider, "_get", new_callable=AsyncMock
    ) as mock_get:
        mock_get.side_effect = [pr_data, files_data]

        result = await provider.fetch("https://github.com/org/repo/pull/42")

    assert result.source == "github_pr"
    assert result.title == "Add user authentication"
    assert result.author == "johndoe"
    assert result.branch == "feature/auth"
    assert result.base_branch == "main"
    assert result.url == "https://github.com/org/repo/pull/42"
    assert len(result.files_changed) == 2

    auth_file = result.files_changed[0]
    assert auth_file.path == "src/auth.py"
    assert auth_file.status == "added"
    assert auth_file.additions == 50
    assert auth_file.deletions == 0

    main_file = result.files_changed[1]
    assert main_file.path == "src/main.py"
    assert main_file.status == "modified"
    assert main_file.additions == 5
    assert main_file.deletions == 2

    assert result.total_additions == 55
    assert result.total_deletions == 2
