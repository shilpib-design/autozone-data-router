import json
import os
import time
from typing import Any, Dict

import httpx

from providers.base import ProviderResult

SCRAPE_DO_ENDPOINT = "https://api.scrape.do/"


class ScrapeDoProvider:
    """Scrape.do adapter for the frozen AutoZone test case."""

    name = "scrape.do"

    def __init__(self, token: str | None = None) -> None:
        self.token = token or os.getenv("SCRAPE_DO_API_KEY")
        if not self.token:
            raise RuntimeError("SCRAPE_DO_API_KEY is not set")

    def _request(self, request: Dict[str, Any], mode: str) -> ProviderResult:
        started = time.perf_counter()
        target_url = request["url"]
        session_id = request.get("session_id", "azmvp01")[:7]

        params: Dict[str, Any] = {
            "token": self.token,
            "url": target_url,
            "geoCode": "us",
            "sessionId": session_id,
        }

        if mode in {"render", "browser"}:
            params["render"] = "true"

        if mode == "browser":
            actions = [
                {"Action": "Wait", "Timeout": 3000},
                {
                    "Action": "Execute",
                    "Execute": """
                        (() => {
                            const clean = (s) => (s || '').replace(/\\s+/g, ' ').trim();
                            const inputs = [...document.querySelectorAll('input')].map((el, i) => ({
                                index: i, type: el.type || null, name: el.name || null,
                                id: el.id || null, placeholder: el.placeholder || null,
                                ariaLabel: el.getAttribute('aria-label'), value: el.value || null,
                                autocomplete: el.autocomplete || null
                            }));
                            const buttons = [...document.querySelectorAll('button, [role="button"]')].map((el, i) => ({
                                index: i, tag: el.tagName, id: el.id || null,
                                ariaLabel: el.getAttribute('aria-label'), text: clean(el.innerText).slice(0, 300)
                            }));
                            return JSON.stringify({
                                url: location.href,
                                title: document.title,
                                inputs, buttons,
                                bodyText: clean(document.body?.innerText).slice(0, 20000)
                            });
                        })()
                    """
                },
            ]
            params["returnJSON"] = "true"
            params["blockResources"] = "false"
            params["playWithBrowser"] = json.dumps(actions, separators=(",", ":"))

        try:
            with httpx.Client(timeout=55.0, follow_redirects=True) as client:
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
                provider=f"{self.name}:{mode}",
                request_success=response.is_success,
                raw_response={
                    "mode": mode,
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
                provider=f"{self.name}:{mode}",
                request_success=False,
                latency_ms=int((time.perf_counter() - started) * 1000),
                error=f"{type(exc).__name__}: {exc}",
            )

    def diagnose(self, request: Dict[str, Any]) -> list[ProviderResult]:
        """Run progressively more complex requests to isolate the failing layer."""
        return [self._request(request, mode) for mode in ("plain", "render", "browser")]


def run_discovery(test_case: Dict[str, Any]) -> ProviderResult:
    provider = ScrapeDoProvider()
    return provider._request({**test_case, "session_id": "azmvp01"}, "browser")
