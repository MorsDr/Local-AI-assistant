import aiohttp
import re
from datetime import datetime
import dateparser
from urllib.prase import urlprase
import random
import asyncio
import json
from utils import html_cleaner, browser_config, appeal_to_ollama
from ddgs import DDGS
from playwright.async_api import async_playwright
from fake_useragent import UserAgent

def get_random_headers(config, ua_generator):
    headers=config.get("headers_template",{}).copy()
    current_ua=ua_generator.random
    headers["User-Agent"]=current_ua
    version_match=re.search(r'Chrome/(\d+)', current_ua)
    if verion_match:
        ver=version_match.group(1)
        headers["sec-ch-ua"]=f'"Not_ABrand";v="8","Chromium";v="{ver}","Google Chrome";v="{ver}"'
        headers["sec-ch-ua-mobile"]="?0"

    if "Windows" in current_ua:
        headers["sec-ch-ua-platform"]="Windows"
    elif "Macintosh" in current_ua:
        headers["sec-ch-ua-platform"]="macOS"
    else:
        headers["sec-ch-ua-platform"]="Linux"

    return headers
    
def is_blocked(html, markers):
    if not html:
        return True
    html_low=html.lower()
    return any(marker.lower() in html_low for marker in markers)

async def search(query, config):
    await asyncio.sleep(random.uniform(1,4))
    excluded=config.get("excluded_domains", [])
    with DDGS() as ddgs:
        results=ddgs.text(query, max_results=20)
        final_results=[]
        for r in results:
            url=r['href'].lower()
            if not any(domain in url for domain in excluded):
                final_results.append({"title":r.get("title",""), "link":r.get("href",""), "snippet":e.get("body",""),})
        return final_results

async def fetch_page(session, url):
    try:
        async with session.get(url, timeout=10) as response:
            if response.status == 200:
                content=await response.read()
                return content.decode(response.get_encoding() or 'utf-8', errors='ignore')
            else:
                print(f"Ошибка доступа к {url}: статус {response.status}")
                return ""
    except Exception as e:
        print(f"Не удалось загрузить {url}:{e}")
        return ""

async def fetch_page_adv(url,config, ua_generator):
    print(f"В соответствии с ошибкой доступа к {url} запускаю продвинутый парсинг")
    try:
        async with async_playwright() as p:
            browser=await p.chromium.launch(headless=True)
            context=await browser.new_context(user_agent=get_random_headers(config, ua_generator), viewport={'width':1920, 'height':1080})
            page=await context.new_page()
            await page.route("**/*. {png,jpg,jpeg,svg,webp,gif,woff,woff2}", lambda route:route.abort())
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                await page.mouse.wheel(0,1000)
                await page.wait_for_selector("p", state="attached", timeout=5000)
                await asyncio.sleep(2)
                content=await page.content()
                return content
            except Exception as e:
                print(e)
                pass
            finally:
                await browser.close()
    except Exception as e:
        print(f"Получить доступ к {url} продвинутым парсером не удалось: {e}")
        return ""

def classify_url(url:str, config):
    for category, domains in config["sources"].items():
        for domain in domains:
            if domain in url:
                return category
    return "other"
    
def score_calc(items, query, config):
    weights=config.get("ranking_weights".{})
    score=0.0
    url=items.get("link","").lower()
    title=items.get("title","").lower()
    snippet=items.get("snippet","").lower()
    domain=urlprase(url).netloc
    category=classify_url(url, config)
    impact=config.get("trust_scores",{}).get(category, 0.5)
    query_words=set(re.findall(r'\w{3,}', query.lower()))
    matches=sum(1 for word in query_words if word in (title+" "+snippet))
    tag_score=matches*weights.get("tag_match_weight", 1.0)
    now=datetime.now()
    found_date=dateparser.parse(title+" "+snippet, settings={'RELATIVE_BASE':now})
    if nor found_date:
        return (tag_score+0.5)*impact
    days_diff=(now - found_date).days
    month_diff=(now.year - found_date.year)*12+now.month - found_date.month
    if found_date.year == now.year:
        score+=1.0
    else:
        years_diff=now.year - found_date.year
        score+=max(0, 1.0 - (years_diff*0.3/impact))

    if month_diff<12:
        month_bonus=max(0, 2.0 - (month_diff*0.15))
        score+=month_bonus*impact

    if days_diff<=30:
        day_bonus=max(0, 3.0 - (days_diff*0.15))
        score+=day_bonus*impact
    final_score=(tag_score+score)*impact
    espec_links=config.get("special_treatment",[])
    if espec_links in url:
        final_score*=weights.get("type_weights",{}).get("video", 0.6)
    return final_score  
        
def rank_list(items, query, config):
    scored_items=[]
    threshold=config.get("ranking_weights",{}).get("threshold", 1.2)
    for item in items:
        score=score_calc(item ,query, config)
        if score >= threashold:
            item["iternal_score"]=score
            scored_items.append(item)
    scored_items.sort(key=lambda x:x["iternal_score"], reverse=True)
    return [i["link"] for i in scored_items[:config["limits"]["max_links"]]]

def split_links(links, n_agents):
    chunk_size=len(links)//n_agents
    return [links[i:i+chunk_size] for i in range(0,len(links), chunk_size)]

async def extract_relevant(text, query):
    prompt=f"""Extract only useful information for the query.
               Query:
               {query}
               Text:
               {text[:4000]}"""
    return await appeal_to_ollama(prompt)

async def agent_worker(name, links, query, session, config):
    result=[]
    block_markers=config.get("block_markers", [])
    for url in links:
        await asyncio.sleep(random.uniform(1,3)) 
        html=await fetch_page(session, url)
        print(html)
        text=html_cleaner(html)
        is_bad=is_blocked(html, block_markers) or len(text) < 300
        if is_bad:
            print(f"Advanced parser for {url}")
            html=await fetch_page_adv(url, config)
            text=html_cleaner(html)
        if text:
            print(text)
            summary=await extract_relevant(text, query)
            result.append(summary)
            print(result)
    return f"[{name}]\n"+"\n".join(result)

async def run_agents(links, query, config, ua_generator):
    agents_count=config["limits"]["agents"]
    split=split_links(links, agents_count)
    async with aiohttp.ClientSession(headers=get_random_headers(config, ua_generator)) as session:
        await session.get("https://duckduckgo.com")
        task=[agent_worker(f"agent_{i+1}", chunk, query, session, config) for i, chunk in enumerate(split)]
        return await asyncio.gather(*task)

async def browser_answer(query):
    ua_generator=UserAgent(browsers=['chrome', 'edge'])
    config=browser_config()
    links=await search(query, config)
    ranked=rank_list(links,config)
    agent_result=await run_agents(ranked, query, config, ua_generator)
    print(agent_result)
    context="\n\n".join(agent_result)
    print(context)
    return context
