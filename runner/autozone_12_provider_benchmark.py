import json
import os
import re
import time
from pathlib import Path
from typing import Any

import httpx

from providers.scrape_do import ScrapeDoProvider
from providers.scrapingbee import ScrapingBeeProvider
from providers.scraper_api import ScraperAPIProvider
from providers.scrapehero import ScrapeHeroProvider
from providers.zenrows import ZenRowsProvider

CONFIG = json.loads(Path("config/autozone_benchmark.json").read_text())
TIMEOUT = httpx.Timeout(120.0, connect=20.0)


def textify(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def clean(text: str) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", " ", text, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def evaluate(body: Any, case: dict) -> dict:
    raw = textify(body)
    text = clean(raw)
    low = text.lower()
    part = case["part_number"].lower()
    sku = case["sku"]
    price = bool(re.search(r"(?:\$\s?\d+(?:\.\d{2})?|price[\"']?\s*[:=]\s*[\"']?\d+)", text, re.I))
    availability = any(x in low for x in ["in stock", "out of stock", "availability", "pickup", "shipping", "delivery", "available"])
    product = any(x in low for x in ["duralast", "brake pad", "brake pads"])
    part_ok = part in low
    sku_ok = sku in low
    zip_ok = CONFIG["location"]["zip"] in text
    store_ok = CONFIG["location"]["expected_store_id"] in text
    address_ok = CONFIG["location"]["expected_address"].lower() in low
    required_ok = product and part_ok and price and availability
    validated = required_ok and zip_ok and store_ok and address_ok
    return {
        "product_found": product,
        "part_number_correct": part_ok,
        "sku_found": sku_ok,
        "price_found": price,
        "availability_found": availability,
        "zip_correct": zip_ok,
        "store_correct": store_ok,
        "address_correct": address_ok,
        "validated_success": validated,
        "response_chars": len(raw),
    }


def result(provider, case, status, latency, cost=None, body=None, error=None, capability="tested"):
    return {
        "provider": provider,
        "test_id": case["id"],
        "url": case["url"],
        "http_status": status,
        "latency_ms": latency,
        "provider_cost": cost,
        "error": error,
        "capability": capability,
        "validation": evaluate(body, case) if body is not None else {"validated_success": False},
    }


def http_call(provider, case, method="POST", url="", **kwargs):
    started = time.perf_counter()
    try:
        with httpx.Client(timeout=TIMEOUT, follow_redirects=True) as client:
            r = client.request(method, url, **kwargs)
        latency = int((time.perf_counter() - started) * 1000)
        try:
            body = r.json()
        except Exception:
            body = r.text
        return result(provider, case, r.status_code, latency, body=body, error=None if r.is_success else f"HTTP {r.status_code}")
    except Exception as exc:
        return result(provider, case, None, int((time.perf_counter() - started) * 1000), error=f"{type(exc).__name__}: {exc}")


def direct_providers(case):
    url = case["url"]
    attrs = [
        {"name": "product_name", "description": "Product name"},
        {"name": "part_number", "description": "Manufacturer part number"},
        {"name": "sku", "description": "AutoZone SKU"},
        {"name": "price", "description": "Current product price in USD"},
        {"name": "availability", "description": "Product availability, pickup, shipping and delivery"},
        {"name": "zip_code", "description": "ZIP code used for localized inventory"},
        {"name": "store_id", "description": "AutoZone store ID selected for ZIP 90001"},
        {"name": "store_address", "description": "Selected AutoZone store address"},
    ]
    out = []

    # Firecrawl: v2 scrape, US location, auto proxy, JS wait.
    key = os.getenv("FIRECRAWL_API_KEY")
    if key:
        out.append(http_call("firecrawl", case, url="https://api.firecrawl.dev/v2/scrape", headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, json={"url": url, "formats":["markdown","html"], "waitFor":5000, "location":{"country":"US","languages":["en-US"]}, "proxy":"auto", "timeout":120000}))

    # MrScraper: one-shot general AI agent.
    key = os.getenv("MRSCRAPER_API_KEY")
    if key:
        prompt = "Extract product_name, part_number, AutoZone SKU, current price, availability, pickup, shipping, ZIP code, selected store ID and selected store address. The requested ZIP is 90001. Return JSON."
        out.append(http_call("mrscraper", case, url="https://api.mrscraper.com", headers={"x-api-token": key, "Content-Type":"application/json"}, params={"token":key,"html":"true","super":"true"}, json={"url":url,"prompt":prompt,"agent":"general"}))

    # Parsera: one-shot structured extractor with US proxy.
    key = os.getenv("PARSERA_API_KEY")
    if key:
        out.append(http_call("parsera", case, url="https://api.parsera.org/v1/extractor/extract", headers={"X-API-KEY":key,"Content-Type":"application/json"}, json={"url":url,"attributes":attrs,"proxy_country":"UnitedStates"}))

    # ScrapingAnt: browser extraction, US not explicitly required by API; URL itself is unchanged.
    key = os.getenv("SCRAPINGANT_API_KEY")
    if key:
        out.append(http_call("scrapingant", case, url="https://api.scrapingant.com/v2/general", headers={"x-api-key":key}, params={"url":url,"browser":"true","return_page_source":"true"}))

    # Spider Cloud.
    key = os.getenv("SPIDERCLOUD_API_KEY")
    if key:
        out.append(http_call("spidercloud", case, url="https://api.spider.cloud/scrape", headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"}, json={"url":url,"return_format":"markdown"}))

    # Thunderbit structured extraction, full browser render.
    key = os.getenv("THUNDERBIT_API_KEY")
    if key:
        schema = {"product_name":"product name","part_number":"manufacturer part number","sku":"AutoZone SKU","price":"current displayed price in USD","availability":"current stock/pickup/shipping availability","zip_code":"ZIP code used for inventory","store_id":"selected AutoZone store ID","store_address":"selected AutoZone store address"}
        out.append(http_call("thunderbit", case, url="https://openapi.thunderbit.com/openapi/v1/extract", headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"}, json={"url":url,"schema":schema,"renderMode":"full","waitFor":3000,"timeout":120000}))

    # SocialCrawl is a social-media data API, not a general web scraper. Do not burn credits on an invalid AutoZone call.
    if os.getenv("SOCIALCRAWL_API_KEY"):
        out.append(result("socialcrawl", case, None, 0, capability="not_applicable", error="Provider is a social-media data API; AutoZone web scraping is not an applicable capability."))

    return out


def existing_providers(case):
    out = []
    for name, fn in [
        ("scrape.do", lambda: ScrapeDoProvider()._request(case["url"], "benchmark", {"super":"true","geoCode":"us","postalcode":CONFIG["location"]["zip"],"render":"true","waitUntil":"networkidle2"})),
        ("scrapingbee", lambda: ScrapingBeeProvider()._request(case, "benchmark_auto", {"render_js":"true","premium_proxy":"true","country_code":"us"})),
        ("scraperapi", lambda: ScraperAPIProvider()._request(case["url"], "benchmark", {"render":"true","country_code":"us","premium":"true"})),
        ("scrapehero", lambda: ScrapeHeroProvider().diagnose(case)),
        ("zenrows", lambda: ZenRowsProvider()._request(case, "benchmark", {"js_render":"true","premium_proxy":"true","proxy_country":"us","wait":"5000"})),
    ]:
        if not any(os.getenv(k) for k in {
            "scrape.do":"SCRAPE_DO_API_KEY","scrapingbee":"SCRAPINGBEE_API_KEY","scraperapi":"SCRAPERAPI_API_KEY","scrapehero":"SCRAPEHERO_API_KEY","zenrows":"ZENROWS_API_KEY"}.items() if k == name):
            continue
        try:
            r = fn()
            if isinstance(r, list):
                r = r[0]
            raw = r.raw_response or {}
            body = raw.get("body")
            v = result(name, case, raw.get("status_code"), r.latency_ms, r.provider_cost, body, r.error)
            out.append(v)
        except Exception as exc:
            out.append(result(name, case, None, 0, error=f"{type(exc).__name__}: {exc}"))
    return out


def main():
    all_results = []
    for case in CONFIG["tests"]:
        all_results.extend(existing_providers(case))
        all_results.extend(direct_providers(case))

    Path("results").mkdir(exist_ok=True)
    Path("results/autozone_12_provider_results.json").write_text(json.dumps(all_results, indent=2, ensure_ascii=False), encoding="utf-8")

    providers = sorted({r["provider"] for r in all_results})
    print("\n========== AUTOZONE 12-PROVIDER BENCHMARK ==========")
    print(f"Tests: {len(CONFIG['tests'])} | Providers: {len(providers)} | Results: {len(all_results)}")
    print(f"Expected ZIP: {CONFIG['location']['zip']} | Store: #{CONFIG['location']['expected_store_id']} | Address: {CONFIG['location']['expected_address']}")
    print("\nProvider        Tests HTTP_OK Validated ZIP_OK Store_OK Avg_ms  Status")
    print("-" * 78)
    for p in providers:
        rows = [r for r in all_results if r["provider"] == p]
        tested = [r for r in rows if r["capability"] == "tested"]
        http_ok = sum(1 for r in tested if r["http_status"] and 200 <= r["http_status"] < 300)
        valid = sum(1 for r in tested if r["validation"].get("validated_success"))
        zip_ok = sum(1 for r in tested if r["validation"].get("zip_correct"))
        store_ok = sum(1 for r in tested if r["validation"].get("store_correct") and r["validation"].get("address_correct"))
        avg = int(sum(r["latency_ms"] for r in tested) / len(tested)) if tested else 0
        status = "N/A" if rows and rows[0]["capability"] == "not_applicable" else ("PASS" if valid == len(tested) and tested else ("PARTIAL" if valid else "FAIL"))
        print(f"{p:<15} {len(rows):>5} {http_ok:>7} {valid:>9} {zip_ok:>6} {store_ok:>8} {avg:>7}  {status}")
    print("======================================================\n")


if __name__ == "__main__":
    main()
