"""Ruff static analysis integration."""

from __future__ import annotations

import asyncio
import json
import shutil

from mcp_code_review.models import Finding

# Severity mapping: ruff codes → severity levels
_ERROR_PREFIXES = {"F", "E9"}  # fatal errors, syntax errors
_WARNING_PREFIXES = {"E", "W", "C", "N", "B", "S"}  # style, complexity, security


async def run_command(cmd: list[str]) -> tuple[int, str, str]:
    """Run a subprocess and return (returncode, stdout, stderr)."""
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    return proc.returncode, stdout.decode(), stderr.decode()


class RuffAnalyzer:
    """Run ruff and parse results into Finding objects."""

    @staticmethod
    def is_available() -> bool:
        """Check if ruff is installed."""
        return shutil.which("ruff") is not None

    async def analyze(self, files: list[str], focus: str = "all") -> list[Finding]:
        """Run ruff on the given files and return findings."""
        if not self.is_available() or not files:
            return []

        cmd = ["ruff", "check", "--output-format=json", *files]
        _, stdout, _ = await run_command(cmd)

        if not stdout or stdout.strip() == "[]":
            return []

        return self._parse_output(stdout, focus)

    def _parse_output(self, raw_json: str, focus: str) -> list[Finding]:
        """Parse ruff JSON output into Finding objects."""
        try:
            items = json.loads(raw_json)
        except json.JSONDecodeError:
            return []

        findings = []
        for item in items:
            code = item.get("code", "")
            severity = self._classify_severity(code)

            if focus == "security" and not code.startswith("S"):
                continue
            if focus == "performance" and code.startswith("S"):
                continue

            findings.append(Finding(
                tool="ruff",
                rule=code,
                severity=severity,
                message=item.get("message", ""),
                file=item.get("filename", ""),
                line=item.get("location", {}).get("row", 0),
            ))

        return findings

    @staticmethod
    def _classify_severity(code: str) -> str:
        """Map ruff rule code to severity level."""
        if any(code.startswith(p) for p in _ERROR_PREFIXES):
            return "error"
        if any(code.startswith(p) for p in _WARNING_PREFIXES):
            return "warning"
        return "info"
