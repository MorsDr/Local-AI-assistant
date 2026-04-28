import aiohttp
import random
import asyncio
import json
from utils import html_cleaner, browser_config, appeal_to_ollama
from ddgs import DDGS
from playwright.async_api import async_playwright

def get_random_headers(config):
    return {"User-agent": random.choice(config["user_agents"]),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Feth-Site": "none",
            "Sec-Feth-User": "?1",
           }

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
        final_links_list=[]
        for r in results:
            url=r['href'].lower()
            if not any(domain in url for domain in excluded):
                final_links_list.append(r['href'])
        return final_links_list

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

async def fetch_page_adv(url,config):
    print(f"В соответствии с ошибкой доступа к {url} запускаю продвинутый парсинг")
    try:
        async with async_playwright() as p:
            browser=await p.chromium.launch(headless=True)
            context=await browser.new_context(user_agent=random.choice(config["user_agents"]), viewport={'width':1920, 'height':1080})
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

def rank_list(links:list[str], config) -> list[str]:
    def score(url):
        category=classify_url(url,config)
        return config["trust_scores"].get(category,0)
    sorted_links=sorted(links, key=score, reverse=True)
    return sorted_links[:config["limits"]["max_links"]]

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
        text=html_cleaner(html)
        is_bad=is_blocked(html, block_markers) or len(text) < 500
        if is_bad:
            print(f"Advanced parser for {url}")
            html=await fetch_page_adv(url, config)
            text=html_cleaner(html)
        if text:
            summary=await extract_relevant(text, query)
            result.append(summary)
    return f"[{name}]\n" + "\n".join(result)

async def run_agents(links, query, config):
    agents_count=config["limits"]["agents"]
    split=split_links(links, agents_count)
    async with aiohttp.ClientSession(headers=get_random_headers(config)) as session:
        await session.get("https://duckduckgo.com")
        task=[agent_worker(f"agent_{i+1}", chunk, query, session, config) for i, chunk in enumerate(split)]
        return await asyncio.gather(*task)

async def browser_answer(query):
    config=browser_config()
    links=await search(query, config)
    ranked=rank_list(links,config)
    agent_result=await run_agents(ranked, query, config)
    context="\n\n".join(agent_result)
    print(context)
    return context
