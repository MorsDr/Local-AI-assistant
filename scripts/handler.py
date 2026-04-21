import psycopg2
import sys
from get_system_info import get_hardware_specs
from datetime import datetime, timedelta
import asyncio
from browser_module import browser_answer
import re
from rag_access import docs_search
from utils import handler_config, savencheck_specs
from ollama import AsyncClient
import json

# Конфигурация
DB_CONFIG = {
    "dbname": "dialog_log",
    "user": "logging",
    "password": "12345", # Замени на свой
    "host": "localhost"
}

def log_to_db(prompt, thought, response):
    try:
        with psycopg2.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:
                query = """
                INSERT INTO dialogs (ts, prompt, thought, response, access_count) 
                VALUES (%s, %s, %s, %s, %s)
                """
                cur.execute(query, (datetime.now(), prompt, thought, response, 1))
    except Exception as e:
        print(f"Ошибка БД: {e}")

class AI_System:
    def __init__(self):
        self.client=AsyncClient(host='http://localhost:11434')
        self.router_model="router"
        self.main_model="worker"
        self.history=[]
        self.config=handler_config()

    async def router_request(self, user_input):
        try:
            system_prompt=self.config["prompts"]["router_system"]
            response=await self.client.chat(model=self.router_model, messages=[{'role':'system', 'content':system_prompt}, {'role':'user', 'content':user_input}], format='json')
            return json.loads(response.message.content)
        except json.JSONDecodeError:
            print("Ошибка струтуры json")
            return {"task":[], "use_db":False, "intent":"fallback"}
        except Exception as e:
            print(f"Ошибка: {e}")
            return {"task":[], "use_db":False}

    async def execute_tasks(self, plan):
        context=""
        if plan.get('tasks'):
            for task in plan['tasks']:
                result=await browser_answer(task)
                context += f"\nSearch result ({task}): {result}"
        #if plan.get('use_db'):
            
        return context

    async def generate_final_answer(self, user_input, extra_context):
        if extra_context:
            full_prompt=f"Контекст для ответа: {extra_context}\n\nЗапрос пользователя: {user_input}"
        else:
            full_prompt=user_input
        tmp_messages=self.history+[{'role':'user', 'content':full_prompt}]
        response=await self.client.chat(model=self.main_model, messages=tmp_messages)
        print(type(response))
        self.history.append({'role':'user', 'content':user_input})
        self.history.append({'role':'assistant', 'content':response.message.content})
        return response.message.content

async def main_loop():
    print("Инициализация Системы.....")
    system=AI_System()
    print(f"Инициализация завершена.\nМодель-роутер: qwen2.5:1.5b\nОсновная модель: codestral")
    print("Для выхода из диалога введите '/exit'. История будет сохранена локально")
    sys_info=get_hardware_specs()
    savencheck_specs(sys_info)
    while True:
        try:
            user_input=input("Вы: ")
            if not user_input.strip():
                continue
            if user_input.strip() == "/exit":
                #save to db
                break
            plan=await system.router_request(user_input)
            extra_context=await system.execute_tasks(plan)
            print(plan, extra_context)
            answer=await system.generate_final_answer(user_input, extra_context)
            print(f"\nОтвет:\n{answer}\n")
        except KeyboardInterrupt:
            print("\nПрерывание сессии. Сохраняю данные.....")
            #save to db
            break
        except Exception as e:
            print(f"Ошибка работы: {e}")


if __name__ == "__main__":
    asyncio.run(main_loop())
