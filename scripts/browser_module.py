import random
import asyncio
import json
from utils import html_cleaner, browser_config, appeal_to_ollama
from ddgs import DDGS
import aiohttp

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

async def search(query):
    await asyncio.sleep(random.uniform(1,4))
    with DDGS() as ddgs:
        results=ddgs.text(query, max_results=20)
        return [r['href'] for r in results]

async def fetch_page(session, url):
    try:
        async with session.get(url, timeout=10) as response:
            if response.status == 200:
                return await response.text()
            else:
                print(f"Ошибка доступа к {url}: статус {response.status}")
                return ""
    except Exception as e:
        print(f"Не удалось загрузить {url}:{e}")
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

async def extract_revelant(text, query):
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
        if is_blocked(html, block_markers):
            continue
        text=html_cleaner(html)
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
    links=await search(query)
    ranked=rank_list(links,config)
    agent_result=await run_agents(ranked, query, config)
    context="/n/n".join(agent_result)
    final_prompt=f"""Answer the question using the context below.
                     {context}
                     Question:
                     {query}"""
    return await appeal_to_ollama(final_prompt)
