import os
import time
from typing import Any, Dict

import httpx

from providers.base import ProviderResult

SCRAPE_DO_ENDPOINT = "https://api.scrape.do/"


class ScrapeDoProvider:
    """Scrape.do adapter plus controlled AutoZone rendering diagnostics."""

    name = "scrape.do"

    def __init__(self, token: str | None = None) -> None:
        self.token = token or os.getenv("SCRAPE_DO_API_KEY")
        if not self.token:
            raise RuntimeError("SCRAPE_DO_API_KEY is not set")

    def _request(self, target_url: str, label: str, extra_params: Dict[str, Any] | None = None) -> ProviderResult:
        started = time.perf_counter()
        params: Dict[str, Any] = {"token": self.token, "url": target_url}
        if extra_params:
            params.update(extra_params)

        try:
            with httpx.Client(timeout=httpx.Timeout(120.0, connect=20.0), follow_redirects=True) as client:
                response = client.get(SCRAPE_DO_ENDPOINT, params=params)

            latency_ms = int((time.perf_counter() - started) * 1000)
            request_cost = response.headers.get("Scrape.do-Request-Cost")
            try:
                provider_cost = float(request_cost) if request_cost is not None else None
            except (TypeError, ValueError):
                provider_cost = None

            try:
                body: Any = response.json()
            except ValueError:
                body = response.text

            return ProviderResult(
                provider=f"{self.name}:{label}",
                request_success=response.is_success,
                raw_response={
                    "label": label,
                    "status_code": response.status_code,
                    "headers": {
                        "Scrape.do-Request-Cost": response.headers.get("Scrape.do-Request-Cost"),
                        "Scrape.do-Remaining-Credits": response.headers.get("Scrape.do-Remaining-Credits"),
                        "Scrape.do-Resolved-Url": response.headers.get("Scrape.do-Resolved-Url"),
                        "Scrape.do-Initial-Status-Code": response.headers.get("Scrape.do-Initial-Status-Code"),
                    },
                    "body": body,
                },
                latency_ms=latency_ms,
                provider_cost=provider_cost,
                error=None if response.is_success else f"HTTP {response.status_code}",
            )
        except Exception as exc:
            return ProviderResult(
                provider=f"{self.name}:{label}",
                request_success=False,
                latency_ms=int((time.perf_counter() - started) * 1000),
                error=f"{type(exc).__name__}: {exc}",
            )

    def controlled_diagnose(self, test_case: Dict[str, Any]) -> list[ProviderResult]:
        """Test the known-good ZIP route, then add rendering without browser actions."""
        autozone_url = test_case["url"]
        zip_code = test_case.get("location", {}).get("zip", "90001")
        zip_params = {"super": "true", "geoCode": "us", "postalcode": zip_code}
        return [
            self._request(autozone_url, "autozone_super_zip", zip_params),
            self._request(
                autozone_url,
                "autozone_super_zip_render",
                {**zip_params, "render": "true", "waitUntil": "networkidle2"},
            ),
        ]

    def diagnose(self, request: Dict[str, Any]) -> list[ProviderResult]:
        return self.controlled_diagnose(request)


def run_discovery(test_case: Dict[str, Any]) -> ProviderResult:
    provider = ScrapeDoProvider()
    return provider.controlled_diagnose(test_case)[-1]
