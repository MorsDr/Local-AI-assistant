import logging
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
from project_logger import init_logging, logger

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
            logging.info(f"Router model received: {user_input}. Start creating json answer")
            system_prompt=self.config["prompts"]["router_system"]
            logging.info(f"Usig prompt: {system_prompt}. Promt take from 'configs/main_conf.json' key: [router_system]")
            response=await self.client.chat(model=self.router_model, messages=[{'role':'system', 'content':system_prompt}, {'role':'user', 'content':user_input}], format='json')
            return json.loads(response.message.content)
        except json.JSONDecodeError as e:
            print("Jsone error. For more information check log file.")
            preview=response.message.content
            logging.error(f"Router model returned unexpected or incorrect answer.\n Error: {e}.\nContent: {preview}.", exc_info=True)
            return {"task":[], "use_db":False, "intent":"fallback"}
        except Exception as e:
            print("Unexpected error. For more information check log file.")
            logging.error(f"Unexpected router model error: {e}", exc_info=True)
            return {"task":[], "use_db":False}

    async def execute_tasks(self, plan):
        context=""
        if plan.get('tasks'):
            for task in plan['tasks']:
                logging.info(f"Sending {task} in browser module to get information")
                result=await browser_answer(task)
                context += f"\nSearch result ({task}): {result}"
        #if plan.get('use_db'):

        logging.info(f"Retirning gatherd information: {context}")
        return context

    async def generate_final_answer(self, user_input, extra_context):
        logging.info(f"Main model received: {user_input}; {extra_context}")
        lang=self.config['lang']
        env=self.config['specs']['Environment']['os_family']+", "+self.config['specs']['Environment']['os_name']
        docker=self.config['specs']['Environment']['is_docker']
        docker_specs="CPU: "+self.config['specs']['Docker Specification']['CPU_limit']+", RAM: "+self.config['specs']['Docker Specification']['RAM_limit']
        host_specs="CPU: "+self.config['specs']['Host Specification']['CPU']+", GPU: "+self.config['specs']['Host Specification']['GPU']+", RAM: "+self.config['specs']['Host Specification']['RAM']
        system_prompt=self.config["prompts"]["main_model"]
        logging.info(f"Using prompt: {system_prompt}. Prompt take from 'configs/main_conf.json' key [main_model]")
        if extra_context:
            full_prompt=f"Context: {extra_context}\n\nUser question: {user_input}"
        else:
            full_prompt=user_input
        logging.info("Preparing data to sendind to AI")
        tmp_messages=self.history+[{'role':'user', 'content':full_prompt}]
        logging.info(f"Final view of data created based on 'self.history' and 'full_prompt': {tmp_messages}.\nSending data to main model to generate answer")
        response=await self.client.chat(model=self.main_model, messages=[{'role':'assistant', 'content':system_prompt}, *tmp_messages])
        logging.info("Updating history with response")
        self.history.append({'role':'user', 'content':user_input})
        self.history.append({'role':'assistant', 'content':response.message.content})
        return response.message.content

async def main_loop():
    logging.info("System itialization...")
    system=AI_System()
    logging.info("System initialized. Main model: codestral; Router model: qwen2.5:1.5b")
    print("To exit from dialog type: '/exit'. Dialog wil be saved local")
    sys_info=get_hardware_specs()
    savencheck_specs(sys_info)
    while True:
        try:
            user_input=input("You: ")
            if not user_input.strip():
                continue
            if user_input.strip() == "/exit":
                logging.info("Received command: 'exit'")
                #save to db
                break
            logging.info(f"Sending: {user_input} to router module")
            plan=await system.router_request(user_input)
            logging.info(f"Proccesing tasks from {plan}")
            extra_context=await system.execute_tasks(plan)
            logging.info("All data received, sending it to main model to generate final answer")
            answer=await system.generate_final_answer(user_input, extra_context)
            print(f"\nОтвет:\n{answer}\n")
        except KeyboardInterrupt:
            logging.info("Keyboard interrupt")
            print("\nSession interrupt. Saving data.....")
            #save to db
            break
        except Exception as e:
            logging.info(f"Unexpected error: {e}")
            print("Working error. For more information check log file")


if __name__ == "__main__":
    init_logging()
    asyncio.run(main_loop())
