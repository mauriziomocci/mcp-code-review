"""Bandit security analysis integration."""

from __future__ import annotations

import json
import shutil

from mcp_code_review.analyzers.ruff import run_command
from mcp_code_review.models import Finding

_SEVERITY_MAP = {
    "HIGH": "error",
    "MEDIUM": "warning",
    "LOW": "info",
}


class BanditAnalyzer:
    """Run bandit and parse results into Finding objects."""

    @staticmethod
    def is_available() -> bool:
        """Check if bandit is installed."""
        return shutil.which("bandit") is not None

    async def analyze(self, files: list[str], focus: str = "all") -> list[Finding]:
        """Run bandit on the given files and return findings."""
        if not self.is_available() or not files:
            return []

        cmd = ["bandit", "-f", "json", "-r", *files]
        _, stdout, _ = await run_command(cmd)

        if not stdout:
            return []

        return self._parse_output(stdout)

    def _parse_output(self, raw_json: str) -> list[Finding]:
        """Parse bandit JSON output into Finding objects."""
        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError:
            return []

        findings = []
        for item in data.get("results", []):
            severity = _SEVERITY_MAP.get(item.get("issue_severity", ""), "info")

            findings.append(Finding(
                tool="bandit",
                rule=item.get("test_id", ""),
                severity=severity,
                message=item.get("issue_text", ""),
                file=item.get("filename", ""),
                line=item.get("line_number", 0),
                code_snippet=item.get("code"),
            ))

        return findings
