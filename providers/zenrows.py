import os
import time
from typing import Any, Dict

import httpx

from providers.base import ProviderResult

ZENROWS_ENDPOINT = "https://api.zenrows.com/v1/"


class ZenRowsProvider:
    """Controlled ZenRows adapter for the frozen AutoZone ZIP/store test."""

    name = "zenrows"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.getenv("ZENROWS_API_KEY")
        if not self.api_key:
            raise RuntimeError("ZENROWS_API_KEY is not set")

    def _request(self, test_case: Dict[str, Any], label: str, extra_params: Dict[str, Any] | None = None) -> ProviderResult:
        started = time.perf_counter()
        params: Dict[str, Any] = {"apikey": self.api_key, "url": test_case["url"]}
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
            text = response.text.lower()
            zip_code = str(test_case.get("location", {}).get("zip", "90001"))
            markers = {
                "product": any(x.lower() in text for x in ["mkd619", "duralast", "97471"]),
                "zip": zip_code.lower() in text,
                "expected_store": any(x.lower() in text for x in ["5425", "1457 e florence"]),
                "availability": any(x in text for x in ["in stock", "pickup", "delivery", "availability"]),
            }
            cost = response.headers.get("X-Request-Cost")
            try:
                cost_value = float(cost) if cost else None
            except ValueError:
                cost_value = None
            return ProviderResult(
                provider=f"{self.name}:{label}",
                request_success=response.is_success,
                raw_response={
                    "label": label,
                    "status_code": response.status_code,
                    "headers": {
                        "X-Request-Cost": response.headers.get("X-Request-Cost"),
                        "X-Request-Id": response.headers.get("X-Request-Id"),
                        "Concurrency-Limit": response.headers.get("Concurrency-Limit"),
                        "Concurrency-Remaining": response.headers.get("Concurrency-Remaining"),
                        "Zr-Final-Url": response.headers.get("Zr-Final-Url"),
                    },
                    "markers": markers,
                    "body": body,
                },
                latency_ms=latency_ms,
                provider_cost=cost_value,
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
        results: list[ProviderResult] = []
        baseline = self._request(test_case, "autozone_plain")
        results.append(baseline)
        if self._is_complete(baseline):
            return results

        protected = self._request(
            test_case,
            "autozone_js_premium_us",
            {"js_render": "true", "premium_proxy": "true", "proxy_country": "us", "wait": "3000"},
        )
        results.append(protected)
        if self._is_complete(protected):
            return results

        extracted = self._request(
            test_case,
            "autozone_js_premium_us_autoparse",
            {"js_render": "true", "premium_proxy": "true", "proxy_country": "us", "wait": "3000", "autoparse": "true"},
        )
        results.append(extracted)
        return results

    @staticmethod
    def _is_complete(result: ProviderResult) -> bool:
        if not result.request_success:
            return False
        markers = (result.raw_response or {}).get("markers", {})
        return all(markers.get(k) for k in ["product", "zip", "expected_store", "availability"])

    def diagnose(self, test_case: Dict[str, Any]) -> list[ProviderResult]:
        return self.controlled_diagnose(test_case)


def run_discovery(test_case: Dict[str, Any]) -> ProviderResult:
    return ZenRowsProvider().diagnose(test_case)[-1]
