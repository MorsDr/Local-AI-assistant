import asyncio
from playwright.async_api import async_playwright
from playwright_stealth import Stealth


async def fetch_web_data(url, proxy=None, retries=2):

    for attempt in range(retries):

        try:
            async with async_playwright() as p:

                browser_args = {}

                if proxy:
                    browser_args["proxy"] = {"server": proxy}

                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        "--disable-blink-features=AutomationControlled"
                    ],
                    **browser_args
                )

                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                    locale="en-US",
                    timezone_id="Europe/Warsaw",
                    viewport={"width": 1920, "height": 1080}
                )

                page = await context.new_page()

                stealth = Stealth()
                await stealth.apply_stealth_async(page)

                page.set_default_timeout(30000)

                await page.goto(url, wait_until="domcontentloaded")

                # немного подождать рендер
                await page.wait_for_timeout(2000)

                # получить текст
                content = await page.evaluate(
                    """() => {
                        return document.body.innerText
                    }"""
                )

                await browser.close()

                # ограничение для LLM
                return content[:8000]

        except Exception as e:

            if attempt == retries - 1:
                return f"Ошибка браузинга: {e}"

            await asyncio.sleep(2)


async def main():

    url = "https://example.com"

    data = await fetch_web_data(url)

    print(data)


if __name__ == "__main__":
    asyncio.run(main())
