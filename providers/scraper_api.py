import os
import time
from typing import Any, Dict

import httpx

SCRAPERAPI_ENDPOINT = "https://api.scraperapi.com/"


class ScraperAPIProvider:
    name = "scraper_api"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.getenv("SCRAPERAPI_API_KEY")
        if not self.api_key:
            raise RuntimeError("SCRAPERAPI_API_KEY is not set")

    def _request(self, target_url: str, label: str, extra_params: Dict[str, Any] | None = None) -> Dict[str, Any]:
        started = time.perf_counter()
        params: Dict[str, Any] = {"api_key": self.api_key, "url": target_url}
        if extra_params:
            params.update(extra_params)
        try:
            with httpx.Client(timeout=httpx.Timeout(90.0, connect=20.0), follow_redirects=True) as client:
                response = client.get(SCRAPERAPI_ENDPOINT, params=params)
            latency_ms = int((time.perf_counter() - started) * 1000)
            return {
                "provider": f"{self.name}:{label}",
                "label": label,
                "request_success": response.is_success,
                "status_code": response.status_code,
                "latency_ms": latency_ms,
                "provider_cost": None,
                "headers": {
                    "x-scraperapi-request-id": response.headers.get("x-scraperapi-request-id"),
                    "content-type": response.headers.get("content-type"),
                },
                "body": response.text,
                "error": None if response.is_success else f"HTTP {response.status_code}",
            }
        except Exception as exc:
            return {
                "provider": f"{self.name}:{label}",
                "label": label,
                "request_success": False,
                "status_code": None,
                "latency_ms": int((time.perf_counter() - started) * 1000),
                "provider_cost": None,
                "headers": {},
                "body": "",
                "error": f"{type(exc).__name__}: {exc}",
            }

    def controlled_diagnose(self, test_case: Dict[str, Any]) -> list[Dict[str, Any]]:
        url = test_case["url"]
        results: list[Dict[str, Any]] = []

        # Start with the cheapest standard route, then US geo + JS rendering.
        # We only escalate to premium proxies if both baseline routes fail.
        results.append(self._request(url, "autozone_plain"))
        results.append(self._request(url, "autozone_us_render", {
            "country_code": "us",
            "render": "true",
        }))

        if not any(r["request_success"] for r in results):
            results.append(self._request(url, "autozone_us_render_premium", {
                "country_code": "us",
                "render": "true",
                "premium": "true",
            }))

        return results
