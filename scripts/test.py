import asyncio
from browser_module import browser_answer
async def get():
    answ=await browser_answer("Погода в Москве")
    print(answ)
    return answ
get()
