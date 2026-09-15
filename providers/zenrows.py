import os
import time
from typing import Any, Dict

import httpx

from providers.base import ProviderResult

ZENROWS_ENDPOINT = "https://api.zenrows.com/v1/"


class ZenRowsProvider:
    """ZenRows Fetch adapter for the frozen AutoZone ZIP/store test."""

    name = "zenrows"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.getenv("ZENROWS_API_KEY")
        if not self.api_key:
            raise RuntimeError("ZENROWS_API_KEY is not set")

    def _request(self, test_case: Dict[str, Any], label: str, extra_params: Dict[str, Any] | None = None) -> ProviderResult:
        started = time.perf_counter()
        target_url = test_case["url"]
        zip_code = test_case.get("location", {}).get("zip", "90001")
        params: Dict[str, Any] = {
            "apikey": self.api_key,
            "url": target_url,
            "mode": "auto",
            "proxy_country": "us",
        }
        if extra_params:
            params.update(extra_params)

        try:
            with httpx.Client(timeout=httpx.Timeout(120.0, connect=20.0), follow_redirects=True) as client:
                response = client.get(ZENROWS_ENDPOINT, params=params)

            latency_ms = int((time.perf_counter() - started) * 1000)
            try:
                body: Any = response.json()
            except ValueError:
                body = response.text

            text = response.text
            markers = {
                "product": any(x.lower() in text.lower() for x in ["MKD619", "Duralast", "97471"]),
                "zip": zip_code in text,
                "expected_store": any(x.lower() in text.lower() for x in ["5425", "1457 E Florence"]),
                "availability": any(x.lower() in text.lower() for x in ["in stock", "pickup", "delivery", "availability"]),
            }

            return ProviderResult(
                provider=f"{self.name}:{label}",
                request_success=response.is_success,
                raw_response={
                    "label": label,
                    "status_code": response.status_code,
                    "headers": {
                        "content-type": response.headers.get("content-type"),
                        "content-length": response.headers.get("content-length"),
                    },
                    "markers": markers,
                    "body": body,
                },
                latency_ms=latency_ms,
                provider_cost=None,
                error=None if response.is_success else f"HTTP {response.status_code}",
            )
        except Exception as exc:
            return ProviderResult(
                provider=f"{self.name}:{label}",
                request_success=False,
                latency_ms=int((time.perf_counter() - started) * 1000),
                error=f"{type(exc).__name__}: {exc}",
            )

    def diagnose(self, test_case: Dict[str, Any]) -> list[ProviderResult]:
        """Start with one controlled Fetch request; escalate only after inspecting it."""
        return [self._request(test_case, "auto_us")]


def run_discovery(test_case: Dict[str, Any]) -> ProviderResult:
    return ZenRowsProvider().diagnose(test_case)[0]
