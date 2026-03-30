from bs4 import BeautifulSoup
import json

def html_cleaner(raw_text):
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
        print(f"Ошибка загрузки конфиг-файла: {e}")

async def appeal_to_ollama(full_prompt):
    async with aiohttp.ClientSession() as session:
        async with session.post("http://;ocalhost:11434/api/generate", json={"model":"archangel", "prompt":full_prompt, "stream":False}) as r:
            data=await r.json()
            return data.get("response","")
