import json
from unittest.mock import AsyncMock, patch

import pytest

from mcp_code_review.analyzers.ruff import RuffAnalyzer


@pytest.fixture
def ruff_json_output():
    return json.dumps([
        {
            "code": "E501",
            "message": "Line too long (120 > 88)",
            "filename": "src/main.py",
            "location": {"row": 42, "column": 1},
            "fix": None,
        },
        {
            "code": "F401",
            "message": "os imported but unused",
            "filename": "src/main.py",
            "location": {"row": 1, "column": 1},
            "fix": None,
        },
    ])


@pytest.mark.asyncio
async def test_ruff_analyze_parses_output(ruff_json_output):
    analyzer = RuffAnalyzer()
    with patch("mcp_code_review.analyzers.ruff.run_command", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = (0, ruff_json_output, "")
        findings = await analyzer.analyze(["src/main.py"])

    assert len(findings) == 2
    assert findings[0].tool == "ruff"
    assert findings[0].rule == "E501"
    assert findings[0].severity == "warning"
    assert findings[0].line == 42
    assert findings[1].rule == "F401"


@pytest.mark.asyncio
async def test_ruff_analyze_empty_when_no_issues():
    analyzer = RuffAnalyzer()
    with patch("mcp_code_review.analyzers.ruff.run_command", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = (0, "[]", "")
        findings = await analyzer.analyze(["src/main.py"])

    assert findings == []


def test_ruff_is_available():
    # Just verify the method exists and returns a bool
    result = RuffAnalyzer.is_available()
    assert isinstance(result, bool)
