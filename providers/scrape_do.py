import json
import os
import time
import urllib.parse
from typing import Any, Dict

import httpx

from providers.base import ProviderResult


SCRAPE_DO_ENDPOINT = "https://api.scrape.do/"


class ScrapeDoProvider:
    """Scrape.do discovery adapter for the frozen AutoZone test case.

    This first version deliberately does not guess AutoZone selectors or cookie names.
    It opens the product page in a rendered browser session and captures:
    - rendered/network response data
    - browser action results
    - DOM inputs/buttons/links/text signals
    - Scrape.do request cost and cookie headers

    The next step is to use the observed DOM/network evidence to implement the
    ZIP/store-selection flow rather than hard-coding assumptions.
    """

    name = "scrape.do"

    def __init__(self, token: str | None = None) -> None:
        self.token = token or os.getenv("SCRAPE_DO_API_KEY")
        if not self.token:
            raise RuntimeError("SCRAPE_DO_API_KEY is not set")

    def scrape(self, request: Dict[str, Any]) -> ProviderResult:
        started = time.perf_counter()
        target_url = request["url"]
        session_id = request.get("session_id", "autozone-mvp-discovery")

        browser_actions = [
            {"Action": "Wait", "Timeout": 5000},
            {
                "Action": "Execute",
                "Execute": """
                    (() => {
                        const clean = (s) => (s || '').replace(/\\s+/g, ' ').trim();
                        const inputs = [...document.querySelectorAll('input')].map((el, i) => ({
                            index: i,
                            type: el.type || null,
                            name: el.name || null,
                            id: el.id || null,
                            placeholder: el.placeholder || null,
                            ariaLabel: el.getAttribute('aria-label'),
                            value: el.value || null,
                            autocomplete: el.autocomplete || null
                        }));
                        const buttons = [...document.querySelectorAll('button, [role="button"]')].map((el, i) => ({
                            index: i,
                            tag: el.tagName,
                            id: el.id || null,
                            ariaLabel: el.getAttribute('aria-label'),
                            text: clean(el.innerText).slice(0, 300)
                        }));
                        const links = [...document.querySelectorAll('a')].map((el, i) => ({
                            index: i,
                            text: clean(el.innerText).slice(0, 200),
                            href: el.href || null
                        })).filter(x => x.text || x.href).slice(0, 150);
                        return JSON.stringify({
                            url: location.href,
                            title: document.title,
                            cookies: document.cookie,
                            inputs,
                            buttons,
                            links,
                            bodyText: clean(document.body?.innerText).slice(0, 20000)
                        });
                    })()
                """,
            },
        ]

        params = {
            "token": self.token,
            "url": target_url,
            "render": "true",
            "returnJSON": "true",
            "geoCode": "us",
            "sessionId": session_id,
            "blockResources": "false",
            "playWithBrowser": json.dumps(browser_actions, separators=(",", ":")),
        }

        try:
            with httpx.Client(timeout=90.0, follow_redirects=True) as client:
                response = client.get(SCRAPE_DO_ENDPOINT, params=params)

            latency_ms = int((time.perf_counter() - started) * 1000)
            request_cost = response.headers.get("Scrape.do-Request-Cost")
            try:
                provider_cost = float(request_cost) if request_cost is not None else None
            except ValueError:
                provider_cost = None

            try:
                body: Any = response.json()
            except ValueError:
                body = response.text

            return ProviderResult(
                provider=self.name,
                request_success=response.is_success,
                raw_response={
                    "status_code": response.status_code,
                    "headers": {
                        "Scrape.do-Request-Cost": response.headers.get("Scrape.do-Request-Cost"),
                        "Scrape.do-Remaining-Credits": response.headers.get("Scrape.do-Remaining-Credits"),
                        "Scrape.do-Cookies": response.headers.get("Scrape.do-Cookies"),
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
                provider=self.name,
                request_success=False,
                latency_ms=int((time.perf_counter() - started) * 1000),
                error=f"{type(exc).__name__}: {exc}",
            )


def run_discovery(test_case: Dict[str, Any]) -> ProviderResult:
    provider = ScrapeDoProvider()
    return provider.scrape(
        {
            **test_case,
            "session_id": "autozone-mvp-discovery",
        }
    )
