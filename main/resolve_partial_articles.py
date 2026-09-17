import asyncio
from playwright.async_api import async_playwright
import utils

async def resolve_partial_articles():

    
    cached_news_articles = utils.load_cached_news_articles()

    p = await async_playwright().start()

    ct = 0

    try:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        for url, text in cached_news_articles.items():
            if len(text) <= 128 and 'oops, something went wrong' in text:
                try:
                    await page.goto(url, wait_until="domcontentloaded")

                    data = await page.content()
                    article_text = utils.get_text_from_html(data)

                    if article_text:
                        cached_news_articles[url] = article_text
                        print(f"{url} successfully processed!")

                except Exception as e:
                    print(f"{url} still failed with exception: {e}")
                ct += 1

    finally:
        await browser.close()
        await p.stop()

    utils.overwrite_news_articles(cached_news_articles)


if __name__ == "__main__":
    asyncio.run(resolve_partial_articles())