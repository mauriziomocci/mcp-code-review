"""Static analysis tools."""

from mcp_code_review.analyzers.ruff import RuffAnalyzer


def get_available_analyzers() -> list[dict[str, str]]:
    analyzers = [
        {"name": "ruff", "available": RuffAnalyzer.is_available(), "install": "pip install mcp-code-review[python]"},
    ]
    try:
        from mcp_code_review.analyzers.bandit import BanditAnalyzer
        analyzers.append({"name": "bandit", "available": BanditAnalyzer.is_available(), "install": "pip install mcp-code-review[python]"})
    except ImportError:
        pass
    return analyzers
