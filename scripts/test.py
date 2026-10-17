from browser_module import browser_answer
import asyncio

async def b_answ(query):
    answer=await browser_answer(query)
    return answer

while True:
    print("Query:\n")
    query=input()
    params, tokens=asyncio.run(b_answ(query))
    print(f"Browser return: {params} and\n{tokens}")
