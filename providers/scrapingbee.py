import os
import time
from typing import Any, Dict

import httpx

SCRAPINGBEE_ENDPOINT = "https://app.scrapingbee.com/api/v1/"


class ScrapingBeeProvider:
    name = "scrapingbee"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.getenv("SCRAPINGBEE_API_KEY")
        if not self.api_key:
            raise RuntimeError("SCRAPINGBEE_API_KEY is not set")

    def _request(
        self,
        target_url: str,
        label: str,
        extra_params: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        started = time.perf_counter()
        params: Dict[str, Any] = {"url": target_url}
        if extra_params:
            params.update(extra_params)

        try:
            with httpx.Client(
                timeout=httpx.Timeout(90.0, connect=20.0),
                follow_redirects=True,
            ) as client:
                response = client.get(
                    SCRAPINGBEE_ENDPOINT,
                    params=params,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )

            latency_ms = int((time.perf_counter() - started) * 1000)
            try:
                body: Any = response.json()
            except ValueError:
                body = response.text

            def header(name: str) -> str | None:
                return response.headers.get(name)

            try:
                cost = float(header("Spb-cost")) if header("Spb-cost") is not None else None
            except (TypeError, ValueError):
                cost = None

            return {
                "provider": f"{self.name}:{label}",
                "label": label,
                "request_success": response.is_success,
                "status_code": response.status_code,
                "latency_ms": latency_ms,
                "provider_cost": cost,
                "headers": {
                    "Spb-cost": header("Spb-cost"),
                    "Spb-auto-cost": header("Spb-auto-cost"),
                    "Spb-initial-status-code": header("Spb-initial-status-code"),
                    "Spb-resolved-url": header("Spb-resolved-url"),
                    "Spb-request-id": header("Spb-request-id"),
                },
                "body": body,
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
        zip_code = test_case.get("location", {}).get("zip", "90001")

        # First establish whether ScrapingBee can retrieve the AutoZone page at all.
        # Then test JS rendering, Auto-Mode, and a browser DOM inspection scenario.
        # We intentionally do not invent a ZIP parameter for the HTML API; ZIP/store
        # behavior must be demonstrated by the returned AutoZone state.
        scenario = {
            "instructions": [
                {"wait": 3000},
                {
                    "evaluate": """
                    (() => {
                      const text = document.body ? document.body.innerText : '';
                      const els = Array.from(document.querySelectorAll('*')).filter(e => {
                        const t = (e.innerText || '').trim();
                        const a = (e.getAttribute('aria-label') || '').trim();
                        return /change store|select store|store/i.test(a + ' ' + t) && t.length < 500;
                      }).slice(0, 30);
                      return JSON.stringify({zip: %s, locationText: text.slice(0, 12000), storeCandidates: els.map(e => ({tag:e.tagName, aria:e.getAttribute('aria-label'), text:(e.innerText||'').trim()}))});
                    })()
                    """ % repr(zip_code)
                },
            ]
        }

        return [
            self._request(url, "autozone_plain"),
            self._request(url, "autozone_render", {"render_js": "true", "block_resources": "false"}),
            self._request(url, "autozone_auto", {"mode": "auto"}),
            self._request(
                url,
                "autozone_browser_discovery",
                {"render_js": "true", "block_resources": "false", "js_scenario": __import__("json").dumps(scenario)},
            ),
        ]
