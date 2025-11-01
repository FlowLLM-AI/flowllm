import asyncio

from crawl4ai import *


async def main():
    browser_config = BrowserConfig(
        headless=True,
        java_script_enabled=True,
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        viewport={"width": 1280, "height": 800},
        verbose=True)

    crawler_config = CrawlerRunConfig(cache_mode=CacheMode.BYPASS,
                                      page_timeout=9000,
                                      verbose=True)

    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun(
            # url="https://stockpage.10jqka.com.cn/000807/operate/",
            # url="https://basic.10jqka.com.cn/601899/operate.html#stockpage",
            # url="https://basic.10jqka.com.cn/601899/worth.html#stockpage",
            url="https://basic.10jqka.com.cn/601899/finance.html#stockpage",
            config=crawler_config,
            js_code="window.scrollTo(0, document.body.scrollHeight);",
            wait_for="document.querySelector('.loaded')"
        )
        print(result.markdown)

        with open("output.md", "w", encoding="utf-8") as f:
            f.write(result.markdown)

if __name__ == "__main__":
    asyncio.run(main())