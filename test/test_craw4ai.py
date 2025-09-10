import asyncio
from crawl4ai import *

# 4. 对浏览器的设置，尤其是反爬厉害的网站一定要设置
browser_config = BrowserConfig(
        headless=False,  # 可以设为True在后台运行
        java_script_enabled=True,  # 确保JavaScript加载评论
        # 可以添加代理、user-agent等配置来模拟真实用户，减少被屏蔽的风险
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        viewport={"width": 1280, "height": 800},
        verbose=True# 开启浏览器配置的详细日志
    )

# 5. 爬虫配置
crawler_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        page_timeout=900000,  # 增加页面加载超时时间，亚马逊页面可能较慢
        # 增加等待时间，确保动态加载的评论内容出现
        # 注意：crawl4ai目前没有直接的wait_for_selector或类似playwright的精细等待机制
        # 可以通过 page_timeout 间接控制等待时间，或者后续考虑用playwright直接操作
        verbose=True# 开启爬虫运行的详细日志
    )

# # 6. 开始爬取
# result = await crawler.arun(
#         url=self.url,
#         config=self.crawler_config,
#         js_code="window.scrollTo(0, document.body.scrollHeight);",
#         wait_for="document.querySelector('.loaded')"
#     )

async def main():
    # browser_config = BrowserConfig(browser_type="chromium", headless=False)
    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun(
            url="https://stockpage.10jqka.com.cn/000807/operate/",
            config=crawler_config,
            js_code="window.scrollTo(0, document.body.scrollHeight);",
            wait_for="document.querySelector('.loaded')"
        )
        print(result.markdown)

if __name__ == "__main__":
    asyncio.run(main())