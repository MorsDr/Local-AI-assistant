import requests
import psycopg2
import os
import sys
from datetime import datetime, timedelta
import asyncio
from browser_module import browser_answer
import re
from rag_access import docs_search

# Конфигурация
DB_CONFIG = {
    "dbname": "ai_system",
    "user": "ai_manager",
    "password": "556645gghhfg", # Замени на свой
    "host": "localhost"
}
OLLAMA_URL = "http://localhost:11434/api/generate"

def get_file_content(path):
    """Одноразовое чтение файла для передачи в контекст"""
    try:
        if os.path.isfile(path):
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
    except Exception as e:
        return f"[Ошибка доступа к файлу: {e}]"
    return None

def log_to_db(prompt, thought, response, file_path=None):
    try:
        with psycopg2.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:
                query = """
                INSERT INTO chat_history (ts, prompt, thought, response, access_count, file_path) 
                VALUES (%s, %s, %s, %s, %s, %s)
                """
                cur.execute(query, (datetime.now(), prompt, thought, response, 1, file_path))
    except Exception as e:
        print(f"Ошибка БД: {e}")

def ask_deepseek(user_input, target_file=None):
    context_content = ""
    if target_file:
        content = get_file_content(target_file)
        if content:
            context_content = f"\n\n--- СОДЕРЖИМОЕ ФАЙЛА {target_file} ---\n{content}\n--- КОНЕЦ ФАЙЛА ---\n"
    
    # Формируем промпт. Контент файла идет как одноразовая добавка.
    full_prompt = f"{user_input}{context_content}"
    
    payload = {
        "model": "Archangel",
        "prompt": ful_prompt,
        "stream": False
    }
    
    try:
        r = requests.post(OLLAMA_URL, json=payload, timeout=120)
        r.raise_for_status()
        data = r.json()
        
        full_response = data.get("response", "")
        
        # Парсим рассуждения (thought)
        if "<think>" in full_response and "</think>" in full_response:
            parts = full_response.split("</think>", 1)
            thought = parts[0].replace("<think>", "").strip()
            answer = parts[1].strip()
        else:
            thought = "No chain of thought provided."
            answer = full_response.strip()

        log_to_db(user_input, thought, answer, target_file)
        return thought, answer
    except Exception as e:
        return None, f"Ошибка при обращении к Ollama: {e}"

async def main_loop():

    print("--- Система готова. Жду запрос (DeepSeek-R1) ---")

    while True:

        user_input = input("\nВы: ")

        if user_input.lower() in ["exit", "quit"]:
            break

        file_to_read = None

        # обработка команды file:
        if user_input.startswith("file:"):

            parts = user_input.split(" ", 1)
            file_to_read = parts[0].replace("file:", "")
            user_input = parts[1] if len(parts) > 1 else "Проанализируй этот файл."

        # первый запрос модели
        thought, answer = ask_deepseek(user_input, file_to_read)

        print(f"\n[ХОД МЫСЛЕЙ]\n{thought}")

        # проверяем нужен ли интернет
        if "[SEARCH:" in answer:

            try:

                query = answer.split("[SEARCH:")[1].split("]")[0].strip()

                print(f"\n[*] Модель запросила поиск: {query}")
                print(f"\nОтвет:\n{browser_answer(query)}")

            except Exception as e:

                print(f"[Ошибка браузера]: {e}")

        else:
            print(f"\n[ОТВЕТ]\n{answer}")

        if "[DOCS:" in answer:
            try:
                match=re.search(r"\[DOCS:<(.*?)>\]", answer)
                if match:
                    query_text=match.group(1)
                    print(f"Запрос к БД с темой: {query_text}")
                    DB_answer=docs_search(query_text)
                    print("Данные получены формирую финальный ответ")

                    final_prompt = f"""Контент по запросу: {query_text}, найденый в БД документаций {DB_answer}.
                    На основе этих данных сформируй финальный ответ на вопрос пользователя {user_input}"""

                    thought, final_answer=ask_deepseek(final_prompt)
                    print(f"\n[ОТВЕТ]\n{final_answer}")

            except Exception as e:
                print(f"Ошибка БД: {e}")
        else:
            print(f"\n[ОТВЕТ]\n{answer}")


if __name__ == "__main__":
    asyncio.run(main_loop())
