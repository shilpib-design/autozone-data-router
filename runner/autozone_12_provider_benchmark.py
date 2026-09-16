import json
import os
import re
import time
from pathlib import Path
from typing import Any
import httpx

CONFIG=json.loads(Path("config/autozone_benchmark.json").read_text())
TIMEOUT=httpx.Timeout(120.0,connect=20.0)

def textify(v:Any)->str:
    return v if isinstance(v,str) else json.dumps(v,ensure_ascii=False)

def clean(s:str)->str:
    s=re.sub(r"<script[\s\S]*?</script>"," ",s,flags=re.I); s=re.sub(r"<style[\s\S]*?</style>"," ",s,flags=re.I); s=re.sub(r"<[^>]+>"," ",s); return re.sub(r"\s+"," ",s).strip()

def evaluate(body:Any,case:dict)->dict:
    text=clean(textify(body)); low=text.lower(); part=case["part_number"].lower(); sku=case["sku"]
    price=bool(re.search(r"\$\s?\d+(?:\.\d{2})?|\bprice\b",text,re.I)); availability=any(x in low for x in ["in stock","out of stock","availability","pickup","shipping","delivery","available"]); product=any(x in low for x in ["duralast","brake pad","brake pads"])
    part_ok=part in low; sku_ok=sku in low; zip_ok=CONFIG["location"]["zip"] in text; store_ok=CONFIG["location"]["expected_store_id"] in text; address_ok=CONFIG["location"]["expected_address"].lower() in low
    return {"product_found":product,"part_number_correct":part_ok,"sku_found":sku_ok,"price_found":price,"availability_found":availability,"zip_correct":zip_ok,"store_correct":store_ok,"address_correct":address_ok,"validated_success":product and part_ok and price and availability and zip_ok and store_ok and address_ok,"response_chars":len(text)}

def make_result(provider,case,status,latency,body=None,cost=None,error=None,capability="tested"):
    return {"provider":provider,"test_id":case["id"],"url":case["url"],"http_status":status,"latency_ms":latency,"provider_cost":cost,"error":error,"capability":capability,"validation":evaluate(body,case) if body is not None else {"validated_success":False}}

def call(provider,case,method,endpoint,headers=None,params=None,json_body=None):
    started=time.perf_counter()
    try:
        with httpx.Client(timeout=TIMEOUT,follow_redirects=True) as client: r=client.request(method,endpoint,headers=headers,params=params,json=json_body)
        latency=int((time.perf_counter()-started)*1000)
        try: body=r.json()
        except Exception: body=r.text
        return make_result(provider,case,r.status_code,latency,body=body,error=None if r.is_success else f"HTTP {r.status_code}")
    except Exception as exc: return make_result(provider,case,None,int((time.perf_counter()-started)*1000),error=f"{type(exc).__name__}: {exc}")

def run_case(case):
    u=case["url"]; out=[]
    if os.getenv("SCRAPE_DO_API_KEY"):
        out.append(call("scrape.do",case,"GET","https://api.scrape.do/",params={"token":os.environ["SCRAPE_DO_API_KEY"],"url":u,"super":"true","geoCode":"us","postalcode":"90001","render":"true","waitUntil":"networkidle2"}))
    if os.getenv("SCRAPINGBEE_API_KEY"):
        out.append(call("scrapingbee",case,"GET","https://app.scrapingbee.com/api/v1/",headers={"Authorization":f"Bearer {os.environ['SCRAPINGBEE_API_KEY']}"},params={"url":u,"mode":"auto","render_js":"true","premium_proxy":"true","country_code":"us"}))
    if os.getenv("SCRAPERAPI_API_KEY"):
        out.append(call("scraperapi",case,"GET","https://api.scraperapi.com/",params={"api_key":os.environ["SCRAPERAPI_API_KEY"],"url":u,"country_code":"us","render":"true","premium":"true"}))
    if os.getenv("SCRAPEHERO_API_KEY"):
        out.append(call("scrapehero",case,"GET","https://get.scrapehero.com/autozone/product-details/",params={"x-api-key":os.environ["SCRAPEHERO_API_KEY"],"url":u,"zipcode":"90001"}))
    if os.getenv("ZENROWS_API_KEY"):
        out.append(call("zenrows",case,"GET","https://api.zenrows.com/v1/",params={"apikey":os.environ["ZENROWS_API_KEY"],"url":u,"js_render":"true","premium_proxy":"true","proxy_country":"us","wait":"3000"}))
    if os.getenv("FIRECRAWL_API_KEY"):
        out.append(call("firecrawl",case,"POST","https://api.firecrawl.dev/v2/scrape",headers={"Authorization":f"Bearer {os.environ['FIRECRAWL_API_KEY']}","Content-Type":"application/json"},json_body={"url":u,"formats":["markdown","html"],"waitFor":5000,"location":{"country":"US","languages":["en-US"]},"proxy":"auto","timeout":120000}))
    if os.getenv("MRSCRAPER_API_KEY"):
        prompt="Extract product_name, part_number, SKU, current price, availability, pickup, shipping, ZIP code, selected store ID and selected store address. Requested ZIP is 90001. Return JSON."
        out.append(call("mrscraper",case,"POST","https://api.mrscraper.com",headers={"x-api-token":os.environ["MRSCRAPER_API_KEY"],"Content-Type":"application/json"},params={"token":os.environ["MRSCRAPER_API_KEY"],"html":"true","super":"true"},json_body={"url":u,"prompt":prompt,"agent":"general"}))
    if os.getenv("PARSERA_API_KEY"):
        attrs=[{"name":"product_name","description":"AutoZone product name"},{"name":"part_number","description":"manufacturer part number"},{"name":"sku","description":"AutoZone SKU"},{"name":"price","description":"current displayed price in USD"},{"name":"availability","description":"current stock/pickup/shipping availability"},{"name":"zip_code","description":"ZIP code used for localized inventory"},{"name":"store_id","description":"selected AutoZone store ID"},{"name":"store_address","description":"selected AutoZone store address"}]
        out.append(call("parsera",case,"POST","https://api.parsera.org/v1/extractor/extract",headers={"X-API-KEY":os.environ["PARSERA_API_KEY"],"Content-Type":"application/json"},json_body={"url":u,"attributes":attrs,"proxy_country":"UnitedStates"}))
    if os.getenv("SCRAPINGANT_API_KEY"):
        out.append(call("scrapingant",case,"GET","https://api.scrapingant.com/v2/general",headers={"x-api-key":os.environ["SCRAPINGANT_API_KEY"]},params={"url":u,"browser":"true","return_page_source":"true"}))
    if os.getenv("SPIDERCLOUD_API_KEY"):
        out.append(call("spidercloud",case,"POST","https://api.spider.cloud/scrape",headers={"Authorization":f"Bearer {os.environ['SPIDERCLOUD_API_KEY']}","Content-Type":"application/json"},json_body={"url":u,"return_format":"markdown"}))
    if os.getenv("THUNDERBIT_API_KEY"):
        schema={"product_name":"product name","part_number":"manufacturer part number","sku":"AutoZone SKU","price":"current displayed price in USD","availability":"current stock, pickup, shipping or delivery availability","zip_code":"ZIP code used for inventory","store_id":"selected AutoZone store ID","store_address":"selected AutoZone store address"}
        out.append(call("thunderbit",case,"POST","https://openapi.thunderbit.com/openapi/v1/extract",headers={"Authorization":f"Bearer {os.environ['THUNDERBIT_API_KEY']}","Content-Type":"application/json"},json_body={"url":u,"schema":schema,"renderMode":"full","waitFor":3000,"timeout":120000}))
    if os.getenv("SOCIALCRAWL_API_KEY"):
        out.append(make_result("socialcrawl",case,None,0,capability="not_applicable",error="SocialCrawl is a social-media data API; AutoZone web scraping is outside its documented capability."))
    return out

def main():
    results=[]
    for case in CONFIG["tests"]: results.extend(run_case(case))
    Path("results").mkdir(exist_ok=True); Path("results/autozone_12_provider_results.json").write_text(json.dumps(results,indent=2,ensure_ascii=False),encoding="utf-8")
    providers=sorted({r["provider"] for r in results})
    print("\n========== AUTOZONE 12-PROVIDER BENCHMARK ==========")
    print(f"Tests: {len(CONFIG['tests'])} | Providers: {len(providers)} | Results: {len(results)}")
    print("Expected ZIP: 90001 | Store: #5425 | Address: 1457 E Florence, Los Angeles, CA 90001")
    print("\nProvider        Tests HTTP_OK Validated ZIP_OK Store_OK Avg_ms Status"); print("-"*78)
    for p in providers:
        rows=[r for r in results if r["provider"]==p]; tested=[r for r in rows if r["capability"]=="tested"]; http_ok=sum(1 for r in tested if r["http_status"] and 200<=r["http_status"]<300); valid=sum(1 for r in tested if r["validation"].get("validated_success")); zip_ok=sum(1 for r in tested if r["validation"].get("zip_correct")); store_ok=sum(1 for r in tested if r["validation"].get("store_correct") and r["validation"].get("address_correct")); avg=int(sum(r["latency_ms"] for r in tested)/len(tested)) if tested else 0; status="N/A" if not tested else ("PASS" if valid==len(tested) else ("PARTIAL" if valid else "FAIL")); print(f"{p:<15} {len(rows):>5} {http_ok:>7} {valid:>9} {zip_ok:>6} {store_ok:>8} {avg:>6}  {status}")
    print("======================================================\n")

if __name__=="__main__": main()
