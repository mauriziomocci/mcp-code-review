"""Abstract base for providers."""
from __future__ import annotations
from typing import Protocol
from mcp_code_review.models import ReviewData


class Provider(Protocol):
    async def fetch(self, **kwargs) -> ReviewData: ...
