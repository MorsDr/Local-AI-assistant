import numpy as np
import aiohttp
import re
from datetime import datetime
import dateparser
from urllib.prase import urlprase
import random
import asyncio
import json
from utils import html_cleaner, browser_config, appeal_to_ollama, saving
from ddgs import DDGS
from playwright.async_api import async_playwright
from fake_useragent import UserAgent

ua_generator=UserAgent(browsers=['chrome', 'edge'])
def get_random_headers(config):
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
        results=ddgs.text(query, max_results=50)
        final_results=[]
        for r in results:
            url=r['href'].lower()
            if not any(domain in url for domain in excluded):
                final_results.append({"title":r.get("title",""), "link":r.get("href",""), "snippet":e.get("body",""),})
        return final_results

def get_yt_transcript(url):
    try:
        video_id=""
        if "v" in url:
            video_id=url.split("v=")[1].split("&")[0]
        elif "youtu.be" in url:
            video_id=url.split("youtu.be/")[1]
        transcript_list=YouTubeTranscriptApi.get_transcript(video_id, languages=['en', 'ru'])
        full_text=" ".join(item['text'] for item in transcript_list)
        return full_text
    except Exception as e:
        return ""

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
            context=await browser.new_context(user_agent=get_random_headers(config), viewport={'width':1920, 'height':1080})
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

def get_domain_category(url, config):
    domain=urlprase(url).netloc.lower().replace('www.', '')
    if domain in config.get("official_domains", []): return "official", 1.0
    reputation_db=config.get("domain_reputation", {})
    if domain in reputation_db:
        category=reputation_db[domain].get("category", "neutral")
    else: category="neutral"
    return category

def classify_url(url:str, config):
    for category, domains in config["sources"].items():
        for domain in domains:
            if domain in url:
                return category
    return "other"

def smart_trim(text, query, target_len):
    if len(text) <= target_len:
        return text
    sentences=re.split(r'(?<=[.!?])+', text)
    query_words=set(re.findall(r'\w{3,}',query.lower()))
    useful_sentences=[]
    for s in sentences:
        if any(word in s.lower() for word in query_words):
            useful_sentences.append(s)
    result=" ".join(useful_sentences)
    return result[:target_len] if result else text[:target_len]

def optimize_context(scored_data, config):
    max_total=config.get("max_text_len", 30000)
    total_len=sum(len(d['text']) for d in scored_data)
    if total_len<=max_total:
        return scored_data
    steps=[(0.30,len(scored_data)), (0.40, len(scored_data)), (0.50, 7), (0.55, 5), (0.65, 3)]
    from threshold, count in steps:
        optimized_data=[]
        start_idx=max(0, len(scored_data) - count)
        for i, site in enumerate(scored_data):
            if i>=start_idx:
               filtered=[s['text'] for s in site['text'] if s['score'] >= threshold]
               text=" ".join(filtered)
            else:
                text=" ".join([s['text'] for s in site['text']])
            optimized_data.append(text)
        current_result=" ".join(optimized_data)
        if len(current_result) <= max_total:
            return current_result 
    return current_result[:max_total]
    
def score_calc(items, query, config):
    weights=config.get("ranking_weights".{})
    score=0.0
    url=items.get("link","").lower()
    title=items.get("title","").lower()
    snippet=items.get("snippet","").lower()
    domain=urlprase(url).netloc
    category=get_domain_category(url, config)
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

async def get_site_rating(scored_sentences):
    if not scored_sentences: return 0.0
    all_grades=[s['score'] for s in scored_sentences]
    peak=sum(sorted(all_grades, reverse=True)[:5]/5)
    info_density=sum(all_grades)/len(all_grades)
    comb_quality=(peak*0.7)+(info_density*0.3)
    return comb_quality

async def vector_rating(text, query):
    sentences=re.split(r'(?<=[.!?])+', text)
    if not sentences: return 0.0, ""
    q_emb=np.array(ollama.embeddings(model="nomic-embed-text", prompt=query)['embedding'])
    scored_sentences=[]
    for s in sentences:
        if len(s)<15:continue
        res=ollama.embeddings(model="monic-embed-text", prompt=s)
        s_emb=np.array(res['embedding'])
        score=np.dot(q_emb, s_emb)/(np.linalg.norm(q_emb)*np.linalg.norm(s_emb))
        scored_sentences.append({"score":score, "text":s})
    avg_quality=get_site_rating(scored_sentences)
    return avg_quality,scored_sentences

def update_reputation(url, score, config, config_path):
    domain=urlprase(url).netloc.lower().replace('www.', '')
    if domain in config.get("official_domains", []):return
    db=config["domain_reputation"]
    if domain not in db:
        db[domain]={"category":"neutral", "history":[]}
    history=db[domain]["history"]
    history.append(score)
    if len(history)>5: history.pop()
    avg=sum(history)/len(history)
    if avg>0.75: new_cat="pristine"
    elif avg>0.60: new_cat="trusted"
    elif avg>0.45: new_cat="community"
    elif avg>0.30: new_cat="neutral"
    else: new_cat="shady"
    db[domain]["category"]=new_cat
    saving(config_path, "domain_reputation", key=None, db)
    
async def extract_relevant(text, query):
    prompt=f"""Extract useful information based on query. Delete duplicates in text. Do it without extra text from yourself.
        Query:\n{query}
        Text:\n{text}"""
    return await appeal_to_ollama(prompt, tokens=32000)

async def agent_worker(name, links, query, session, config):
    special_sites=config.get("special_treatment", [])
    domain=urlprase(url).netloc.lower().replace('www.', '')
    try:
        if any(site in domain for site in special_sites):
            if "youtube.com" in domain or "youtu.be" in domain:
                text=await get_yt_transcript(url)
                return {"url":url, "text":text}
            else:
                continue
        else:
            html=fetch_page(session, url)
            text=html_cleaner(html)
            if is_blocked(html, config.get("block_markers",[])) or len(text)<300:
                html=await fetch_page_adv(url, config)
                text=html_cleaner(html)
            if len(text)>300:
                return {"url":url, "text":text}
    except Exception as e:
        print(f"Error {name} in {url}: {e}")
        return None
    
async def run_agents(links, query, config):
    async with aiohttp.ClientSession(headers=get_random_headers(config)) as session:
        await session.get("https://duckduckgo.com")
        tasks=[]
        for i, url in enumerate(links):
            tasks.append(agent_worker(f"worker_{i+1}", url, query, session, config"))
        result=await asyncion.gather(*tasks)
        return [r for r in result if r]

async def browser_answer(query):
    config, config_path=browser_config()
    links=await search(query, config)
    ranked=rank_list(links, query, config)
    if not ranked:
        return "Search Error"
    pages_data=await run_agents(ranked, query, config)
    print(pages_data)
    if not pages_data:
        return "Cant get data from sites"
    for i, data in enumerate(pages_data):
        url=data['url']
        text=data['text']
        site_score, scored_text=await vector_rating(query, text)
        update_reputation(url, site_score, config, config_path)
        to_sum_context.append({"url":url, "text":scored_text})
    context=optimize_context(to_sum_context, config)
    final_context=extract_relevant(context, query)
    return final_context
