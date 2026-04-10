"""Abstract base for analyzers."""

from __future__ import annotations

from typing import Protocol

from mcp_code_review.models import Finding


class Analyzer(Protocol):
    """Protocol for static analysis tools."""

    @staticmethod
    def is_available() -> bool:
        """Check if the analyzer binary is installed."""
        ...

    async def analyze(self, files: list[str], focus: str = "all") -> list[Finding]:
        """Run analysis on the given files."""
        ...
