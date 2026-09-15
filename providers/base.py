"""Common provider interface for the AutoZone benchmark."""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class ProviderResult:
    provider: str
    request_success: bool = False
    raw_response: Any = None
    normalized_data: Dict[str, Any] = field(default_factory=dict)
    zip_applied: Optional[bool] = None
    store_detected: Optional[str] = None
    store_match: Optional[bool] = None
    latency_ms: Optional[int] = None
    provider_cost: Optional[float] = None
    error: Optional[str] = None


class Provider:
    name = "base"

    def scrape(self, request: Dict[str, Any]) -> ProviderResult:
        raise NotImplementedError
