from ollama import AsyncClient
import numpy as np
import aiohttp
import re
from datetime import datetime
import dateparser
from urllib.parse import urlparse
import random
import asyncio
import json
from youtube_transcript_api import YouTubeTranscriptApi
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
    if version_match:
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
                final_results.append({"title":r.get("title",""), "link":r.get("href",""), "snippet":r.get("body","")})
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
            full_headers=get_random_headers(config)
            ua_string=full_headers.get("User-Agent", "Mozilla/5.0(Windows NT 10,0; Win64; x64) AppleWebKit/537.36")
            context=await browser.new_context(user_agent=ua_string, extra_http_headers=full_headers, viewport={'width':1920, 'height':1080})
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
    domain=urlparse(url).netloc.lower().replace('www.', '')
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
#Arguments type: scored_data=[{"url":url address, "domain":domain, "text":full text w/o split, "sentences":[{"score": float num; rating this sentences, "text":one sentence}, repetition acording to a pattern], "data":data, format:year-month-day, "category":domain category}, {repetition according to a pattern up to len equal max_links variable(default value equal 10)}]
    max_total=config.get("max_text_len", 30000)
    total_len=sum(len(d['text']) for d in scored_data)
    def clean_out(data_list):
        cleaned=[]
        for item in data_list:
            new_item=item.copy()
            new_item.pop("sentences", None)
            cleaned.append(new_item)
        return cleaned
    
    if total_len<=max_total:
        return clean_out(scored_data)
    steps=[(0.30,len(scored_data)), (0.40, len(scored_data)), (0.50, 7), (0.55, 5), (0.65, 3)]
    for threshold, count in steps:
        optimized_data=[]
        start_idx=max(0, len(scored_data) - count)
        for i, item in enumerate(scored_data):
            current_item=item.copy()
            if i>=start_idx and "sentences" in current_item:
                filtered=[s['text'] for s in current_item['sentences'] if float(s.get("score", 0.0)) >= threshold]
                current_item["text"]=" ".join(filtered)
            else:
                current_item["text"]=" ".join([s['text'] for s in current_item['sentences']])
            current_item.pop("sentences", None)
            optimized_data.append(current_item)
        current_len=sum(len(d['text']) for d in optimized_data)
        if current_len <= max_total:
            return optimized_data 
    return optimized_data
    
def score_calc(items, query, config):
    def date_scoring(found_date, now, tag_score):
        print("Date found")
        score=0.0
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
        print(f"score after date func: {final_score}")
        for spec_link in espec_links:
            if spec_link in url:
                final_score*=weights.get("type_weights",{}).get("video", 0.6)
                print(f"score if date and youtube: {final_score}")
                break
        return final_score
        
    weights=config.get("ranking_weights", {})
    espec_links=config.get("special_treatment",[])    
    query_words=set(re.findall(r'\w{3,}', query.lower()))
    now=datetime.now()
    output_res=[]
    for item in items:
        final_score=0.0
        url=item.get("link","").lower()
        title=item.get("title","").lower()
        snippet=item.get("snippet","").lower()
        try:
            domain=urlparse(url).netloc
        except Exception:
            domain=""
        category=get_domain_category(url, config)
        impact=config.get("trust_scores",{}).get(category, 0.5)
        matches=sum(1 for word in query_words if word in (title+" "+snippet))
        tag_score=matches*weights.get("tag_match_weight", 1.0)
        found_date=dateparser.parse(title+" "+snippet, settings={'RELATIVE_BASE':now, 'PREFER_DATES_FROM':'past'})
        print(f"domain: {domain}")
        print(f"cat: {category} and it impact: {impact}\ntag matches: {matches} and final tag score: {tag_score}\ndate: {found_date}")
        if not found_date:
            try:
                print("Date not found")
                from dateparser.search import search_dates
                result=search_dates(title+" "+snippet, languages=['ru', 'en'])
                if result:
                    found_date=result[0][1]
                    final_score=date_scoring(found_date, now, tag_score)
                    print(f"score if date: {final_score}")
                else:
                    final_score+=(tag_score+1.5)*impact
                    print(f"score if not date: {final_score}")
                    for spec_link in espec_links:
                        if spec_link in url:
                            final_score*=weights.get("type_weights",{}).get("video", 0.6)
                            print(f"score if not date and youtube: {final_score}")
                            break
            except Exception as e:
                print(f"Error: {e}")
        else:
            final_score=date_scoring(found_date, now, tag_score)
            print(f"score if date: {final_score}")
        
        print(f"domain: {domain}\nscore before save: {final_score}")
        formatted_item={"url":url, "domain":domain, "category":category, "site_rate":final_score, "date":found_date.strftime("%Y-%m-%d") if found_date else None}
        output_res.append(formatted_item)
        print("------------------------------------------------------------------------------------------------")
    return output_res
        
def rank_list(items, query, config):
    threshold=config.get("ranking_weights",{}).get("threshold", 1.2)
    ignored=config.get("ignored_domains", [])
    pre_filtered=[]
    for item in items:
        url=item.get("link", "").lower()
        try:
            domain=urlparse(url).netloc.lower()
        except Exception:
            domain=""
        if any(black_domain in domain for black_domain in ignored):
            continue
        pre_filtered.append(item)
    scored_items=score_calc(pre_filtered, query, config)
    print(scored_items)
    max_link=10
    filtered_items=[item for item in scored_items if item["site_rate"] >= threshold]
    filtered_items.sort(key=lambda x:x["site_rate"], reverse=True)
    return filtered_items[:max_link]

def get_site_rating(scored_sentences):
    if not scored_sentences: return 0.0
    print(scored_sentences)
    all_grades=np.array([s['score'] for s in scored_sentences], dtype=np.float64)
    print(all_grades)
    sorted_grades=np.sort(all_grades)[::-1]
    top_grades=sorted_grades[:5]
    peak=top_grades.mean() if top_grades.size > 0 else 0.0
    info_density=all_grades.mean() if all_grades.size > 0 else 0.0
    comb_quality=(peak*0.7)+(info_density*0.3)
    return comb_quality.item()

async def vector_rating(query, text):
    sentences=re.split(r'(?<=[.!?])+', text)
    if not sentences: return 0.0, ""
    q_resp=await AsyncClient().embed(model="nomic-embed-text", input=query)
    q_emb=np.array(q_resp['embeddings'][0])
    scored_sentences=[]
    for s in sentences:
        if len(s)<15:continue
        try:
            res=await AsyncClient().embed(model="nomic-embed-text", input=s)
            s_emb=np.array(res['embeddings'][0])
            score=np.dot(q_emb, s_emb)/(np.linalg.norm(q_emb)*np.linalg.norm(s_emb))
            print(f"score: {score}; sentence: {s}")
            scored_sentences.append({"score":score, "text":s})
        except Exception as e:
            print(f"sentence: {s} return error: {e}")
            continue
    avg_quality=get_site_rating(scored_sentences)
    return avg_quality,scored_sentences

def update_reputation(url, score, config, config_path):
    domain=urlparse(url).netloc.lower().replace('www.', '')
    if domain in config.get("official_domains", []):return
    db=config.get("domain_reputation", {})
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
    saving(config_path, db, "domain_reputation", None)
    
async def extract_relevant(datas_pool, query, config):
    input_data={item["url"]:item["text"] for item in datas_pool if len(item.get("text", "")) > 100}
    input_json_str=json.dumps(input_data, ensure_ascii=False)
    prompt=f"""{config.get("ai_prompt", "")}"""
    try:
        response=await AsyncClient().generate(model=worker, prompt=prompt, format=json, option={"temperature":0.1})
        cleaned_json=response.get('response', '').strip()
        final_data=json.load(cleaned_json)
        for item in datas_pool:
            url=item.get("url")
        if url in final_data:
            item["text"]=final_data[url]
    except Exception as e:
        print(f"Error: {e}")
    return datas_pool

async def agent_worker(name, item, query, session, config):
    special_sites=config.get("special_treatment", [])
    url=item.get("url", "")
    domain=item.get("domain", "")
    if not url:
        return None
    try:
        if any(site in domain for site in special_sites):
            if "youtube.com" in domain or "youtu.be" in domain:
                text=await get_yt_transcript(url)
                return {"text":text, "domain":domain, "data":item.get("data"), "category":item.get("category")}
        else:
            html=await fetch_page(session, url)
            text=html_cleaner(html)
            if is_blocked(html, config.get("block_markers",[])) or len(text)<300:
                html=await fetch_page_adv(url, config)
                text=html_cleaner(html)
            if len(text)>300:
                return {"url":url, "text":text, "domain":domain, "data":item.get("data"), "category":item.get("category")}
    except Exception as e:
        print(f"Error {name} in {url}: {e}")
        return None
    
async def run_agents(items, query, config):
    async with aiohttp.ClientSession(headers=get_random_headers(config)) as session:
        await session.get("https://duckduckgo.com")
        tasks=[]
        for i, item in enumerate(items):
            tasks.append(agent_worker(f"worker_{i+1}", item, query, session, config))
        result=await asyncio.gather(*tasks)
        return [r for r in result if r]

async def browser_answer(query):
    config, config_path=browser_config()
    raw_context=[]
    links=await search(query, config)
    ranked=rank_list(links, query, config)
    print(ranked)
    if not ranked:
        return "Search Error"
    pages_data=await run_agents(ranked, query, config)
    if not pages_data:
        return "Cant get data from sites"
    for item in pages_data:
        domain=item["domain"]
        text=item["text"]
        print(f"send data to scoring: {text}\n-------------------------------------------------------------------------------------------------")
        site_score, scored_text=await vector_rating(query, text)
        #Return type: site_score=1.2; scored_text=[{"score":float value, "text":sentence}, {"score":float value, "text":sentence}.....(until the sentences in the text run out)]
        update_reputation(domain, site_score, config, config_path)
        tmp_data={"url":item["url"], "domain":domain, "text":text, "sentences":scored_text, "site_score":site_score, "data":item["data"], "category":item["category"]}
        raw_context.append(tmp_data)
    context=optimize_context(raw_context, config)
    final_context=await extract_relevant(context, query, config)
    return final_context
