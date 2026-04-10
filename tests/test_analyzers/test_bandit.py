import json
from unittest.mock import AsyncMock, patch

import pytest

from mcp_code_review.analyzers.bandit import BanditAnalyzer


@pytest.fixture
def bandit_json_output():
    return json.dumps({
        "results": [
            {
                "test_id": "B101",
                "test_name": "assert_used",
                "issue_severity": "LOW",
                "issue_confidence": "HIGH",
                "issue_text": "Use of assert detected.",
                "filename": "src/main.py",
                "line_number": 15,
                "code": "    assert x > 0\n",
            },
            {
                "test_id": "B105",
                "test_name": "hardcoded_password_string",
                "issue_severity": "HIGH",
                "issue_confidence": "MEDIUM",
                "issue_text": "Possible hardcoded password.",
                "filename": "src/config.py",
                "line_number": 8,
                "code": '    password = "secret123"\n',
            },
        ],
    })


@pytest.mark.asyncio
async def test_bandit_analyze_parses_output(bandit_json_output):
    analyzer = BanditAnalyzer()
    with patch("mcp_code_review.analyzers.bandit.run_command", new_callable=AsyncMock) as mock_run, \
         patch.object(BanditAnalyzer, "is_available", return_value=True):
        mock_run.return_value = (0, bandit_json_output, "")
        findings = await analyzer.analyze(["src/main.py", "src/config.py"])

    assert len(findings) == 2
    assert findings[0].tool == "bandit"
    assert findings[0].rule == "B101"
    assert findings[0].severity == "info"  # LOW → info
    assert findings[1].rule == "B105"
    assert findings[1].severity == "error"  # HIGH → error


@pytest.mark.asyncio
async def test_bandit_analyze_empty():
    analyzer = BanditAnalyzer()
    with patch("mcp_code_review.analyzers.bandit.run_command", new_callable=AsyncMock) as mock_run, \
         patch.object(BanditAnalyzer, "is_available", return_value=True):
        mock_run.return_value = (0, json.dumps({"results": []}), "")
        findings = await analyzer.analyze(["src/main.py"])

    assert findings == []
