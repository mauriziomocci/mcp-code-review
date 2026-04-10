"""Static analysis tools."""

from mcp_code_review.analyzers.ruff import RuffAnalyzer
from mcp_code_review.analyzers.bandit import BanditAnalyzer


def get_available_analyzers() -> list[dict[str, str]]:
    """Return list of analyzers with their availability status."""
    analyzers = [
        {"name": "ruff", "available": RuffAnalyzer.is_available(), "install": "pip install mcp-code-review[python]"},
        {"name": "bandit", "available": BanditAnalyzer.is_available(), "install": "pip install mcp-code-review[python]"},
    ]
    return analyzers
