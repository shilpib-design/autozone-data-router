import json
import os
import time
from typing import Any, Dict

import httpx

from providers.base import ProviderResult

SCRAPEHERO_ENDPOINT = os.getenv("SCRAPEHERO_AUTOZONE_ENDPOINT", "https://get.scrapehero.com/autozone/product-details/")


class ScrapeHeroProvider:
    """ScrapeHero AutoZone API adapter for the frozen ZIP/store test."""

    name = "scrapehero"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.getenv("SCRAPEHERO_API_KEY")
        if not self.api_key:
            raise RuntimeError("SCRAPEHERO_API_KEY is not set")

    def diagnose(self, test_case: Dict[str, Any]) -> ProviderResult:
        started = time.perf_counter()
        url = test_case["url"]
        zip_code = test_case.get("location", {}).get("zip", "90001")
        params = {"x-api-key": self.api_key, "url": url, "zipcode": zip_code}

        try:
            with httpx.Client(timeout=httpx.Timeout(120.0, connect=20.0), follow_redirects=True) as client:
                response = client.get(SCRAPEHERO_ENDPOINT, params=params)
            latency_ms = int((time.perf_counter() - started) * 1000)
            try:
                body: Any = response.json()
            except ValueError:
                body = response.text
            return ProviderResult(
                provider=self.name,
                request_success=response.is_success,
                raw_response={
                    "endpoint": SCRAPEHERO_ENDPOINT,
                    "status_code": response.status_code,
                    "headers": {"content-type": response.headers.get("content-type")},
                    "body": body,
                },
                latency_ms=latency_ms,
                provider_cost=None,
                error=None if response.is_success else f"HTTP {response.status_code}",
            )
        except Exception as exc:
            return ProviderResult(
                provider=self.name,
                request_success=False,
                latency_ms=int((time.perf_counter() - started) * 1000),
                error=f"{type(exc).__name__}: {exc}",
            )

    def controlled_diagnose(self, test_case: Dict[str, Any]) -> list[ProviderResult]:
        return [self.diagnose(test_case)]


def run_discovery(test_case: Dict[str, Any]) -> ProviderResult:
    return ScrapeHeroProvider().diagnose(test_case)
