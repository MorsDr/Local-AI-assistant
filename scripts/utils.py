import aiohttp
import hashlib
from pathlib import Path
from bs4 import BeautifulSoup
import json

def html_cleaner(raw_text):
    if not raw_text:
        return ""
    soup=BeautifulSoup(raw_text, 'lxml')
    for anchor in soup.find_all("a", class_="headelink"):
        anchor.decompose()
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    clean_text=soup.get_text(separator=' ')
    lines=[line.strip() for line in clean_text.splitlines() if line.strip()]
    return " ".join(lines)

def browser_config():
    config_path=Path(__file__).resolve().parents[1]/"configs/browser_config.json"
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"Ошибка структуры файла конфинурации: {config_path.name} в строке: {e.lineno}")
    except Exception as e:
        print(f"Ошибка загрузки конфиг-файла {config_path.name} : {e}")

def handler_config():
    config_path=Path(__file__).resolve().parents[1]/"configs/main_conf.json"
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"Ошибка структуры файла конфигурации: {config_path.name} в строке: {e.lineno}")
    except Exception as e:
        print(f"Ошибка загрузки конфиг-файла {config_path.name} : {e}")

async def appeal_to_ollama(full_prompt):
    async with aiohttp.ClientSession() as session:
        async with session.post("http://localhost:11434/api/chat", json={"model":"worker", "prompt":full_prompt, "stream":False}) as r:
            data=await r.json()
            return data.get("response","")

def savencheck_specs(current_data):
    path=Path("configs/main_conf.json")
    comb_data={}
    data={}
    try:
        with open(path, "r", encoding='utf-8') as f:
            data=json.load(f)
        for tupl in current_data:
            comb_data |= tupl
    except Exception as e:
        print(e)
    spec_string=json.dumps(comb_data, sort_keys=True).encode('utf-8')
    spec_hash=hashlib.md5(spec_string).hexdigest()
    if spec_hash != data.get("hash"): 
        print("Specification data uncorrect or missing\n Rewriting...")
        structured_data={"hash":spec_hash,
            "Environment":current_data[0],
            "Host Specification":current_data[1],
            "Docker Specification":current_data[2]}
        data["specs"]=structured_data
        with open(path, "w", encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    else:
        print("Specification data up-to-date")
