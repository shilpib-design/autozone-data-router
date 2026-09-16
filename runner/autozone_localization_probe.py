import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import httpx

URL="https://www.autozone.com/p/duralast-disc-brake-pad-set-mkd619/97471"
ZIP="90001"
STORE="5425"
ADDRESS="1457 E Florence"
TIMEOUT=httpx.Timeout(90.0, connect=20.0)

JS="""
(async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const text = e => (e?.innerText || e?.textContent || '').replace(/\\s+/g,' ').trim();
  const clickText = (needle) => {
    const els=[...document.querySelectorAll('button,a,[role=button],div,span')];
    const el=els.find(e => text(e).toLowerCase().includes(needle));
    if(el){el.click();return true} return false;
  };
  const inputs=()=>[...document.querySelectorAll('input')].map(e=>({type:e.type,placeholder:e.placeholder,name:e.name,aria:e.getAttribute('aria-label'),value:e.value}));
  await sleep(4000);
  let opened=clickText('change store');
  await sleep(1500);
  let before=inputs();
  let inp=[...document.querySelectorAll('input')].find(e=>/zip|postal/i.test((e.placeholder||'')+' '+(e.name||'')+' '+(e.getAttribute('aria-label')||'')));
  if(!inp) inp=document.querySelector('input[type="text"]');
  if(inp){
    const setter=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
    setter.call(inp,'90001');
    inp.dispatchEvent(new Event('input',{bubbles:true}));
    inp.dispatchEvent(new Event('change',{bubbles:true}));
    await sleep(300);
    inp.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',code:'Enter',bubbles:true}));
  }
  await sleep(2500);
  let applied=clickText('apply');
  if(!applied) applied=clickText('update');
  if(!applied) applied=clickText('find stores');
  await sleep(5000);
  return {opened,applied,beforeInputs:before,afterInputs:inputs(),body:(document.body.innerText||'').slice(-12000)};
})()
"""

def clean(v):
    s=v if isinstance(v,str) else json.dumps(v,ensure_ascii=False)
    s=re.sub(r'<script[\\s\\S]*?</script>',' ',s,flags=re.I)
    s=re.sub(r'<style[\\s\\S]*?</style>',' ',s,flags=re.I)
    s=re.sub(r'<[^>]+>',' ',s)
    return re.sub(r'\\s+',' ',s).strip()

def validate(body):
    s=clean(body); low=s.lower()
    return {
      'product': 'duralast' in low or 'brake pad' in low,
      'part': 'mkd619' in low,
      'sku': '97471' in low,
      'zip': ZIP in s,
      'store': re.search(r'(?:store|#)\\s*5425\\b',s,re.I) is not None,
      'address': ADDRESS.lower() in low,
      'availability': any(x in low for x in ['in stock','out of stock','pickup','shipping','delivery','available'])
    }

def req(name, method, endpoint, headers=None, params=None, body=None):
    t=time.perf_counter()
    try:
      with httpx.Client(timeout=TIMEOUT,follow_redirects=True) as c:
        r=c.request(method,endpoint,headers=headers,params=params,json=body)
      ms=int((time.perf_counter()-t)*1000)
      try: data=r.json()
      except Exception: data=r.text
      return {'provider':name,'status':r.status_code,'latency_ms':ms,'validation':validate(data),'response':data}
    except Exception as e:
      return {'provider':name,'status':None,'latency_ms':int((time.perf_counter()-t)*1000),'error':f'{type(e).__name__}: {e}','validation':{}}

def run():
  jobs=[]
  if os.getenv('SCRAPE_DO_API_KEY'):
    jobs.append(('scrape.do','GET','https://api.scrape.do/',None,{'token':os.environ['SCRAPE_DO_API_KEY'],'url':URL,'super':'true','geoCode':'us','postalcode':ZIP,'render':'true','waitUntil':'networkidle2','customWait':'3000','returnJSON':'true','playWithBrowser':json.dumps([{'Action':'Wait','Timeout':3000},{'Action':'Execute','Execute':JS},{'Action':'Wait','Timeout':3000}],separators=(',',':'))},None))
  if os.getenv('FIRECRAWL_API_KEY'):
    jobs.append(('firecrawl','POST','https://api.firecrawl.dev/v2/scrape',{'Authorization':f"Bearer {os.environ['FIRECRAWL_API_KEY']}",'Content-Type':'application/json'},None,{'url':URL,'formats':['markdown','html'],'onlyMainContent':False,'waitFor':3000,'timeout':90000,'location':{'country':'US','languages':['en-US']},'proxy':'auto','actions':[{'type':'wait','milliseconds':3000},{'type':'executeJavascript','script':JS},{'type':'wait','milliseconds':3000}]}))
  if os.getenv('SCRAPINGBEE_API_KEY'):
    jobs.append(('scrapingbee','GET','https://app.scrapingbee.com/api/v1/',{'Authorization':f"Bearer {os.environ['SCRAPINGBEE_API_KEY']}"},{'url':URL,'render_js':'true','premium_proxy':'true','country_code':'us','wait':'3000','js_scenario':json.dumps({'strict':False,'instructions':[{'wait':3000},{'evaluate':JS},{'wait':3000}]},separators=(',',':'))},None))
  if os.getenv('MRSCRAPER_API_KEY'):
    prompt=('Open the AutoZone product page. Interact with the page, not just the raw HTML: open Change Store, set the ZIP/postal code to 90001, apply it, wait for the localized store/inventory to update, then extract product name, part number, SKU, price, availability, the displayed ZIP, selected store ID and selected store address. Return the exact observed values and explain if the ZIP/store interaction could not be completed.')
    jobs.append(('mrscraper','POST','https://api.mrscraper.com',{'x-api-token':os.environ['MRSCRAPER_API_KEY'],'Content-Type':'application/json'},{'token':os.environ['MRSCRAPER_API_KEY'],'html':'true','super':'true'}, {'url':URL,'prompt':prompt,'agent':'general'}))
  results=[]
  with ThreadPoolExecutor(max_workers=4) as pool:
    fs=[pool.submit(req,*j) for j in jobs]
    for f in as_completed(fs): results.append(f.result())
  results.sort(key=lambda x:x['provider'])
  print(json.dumps(results,indent=2,ensure_ascii=False))
  open('autozone_localization_probe_results.json','w',encoding='utf-8').write(json.dumps(results,indent=2,ensure_ascii=False))

if __name__=='__main__': run()
