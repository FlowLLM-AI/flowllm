import asyncio
from playwright.async_api import async_playwright
import time
import os
from datetime import datetime


async def crawl_with_playwright():
    """使用Playwright爬取股票页面"""
    
    async with async_playwright() as p:
        # 启动浏览器
        browser = await p.chromium.launch(
            headless=False,  # 显示浏览器窗口，方便调试
            args=[
                '--no-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--disable-web-security'
            ]
        )
        
        # 创建新页面
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        
        page = await context.new_page()
        
        try:
            print("开始访问页面...")
            
            # 访问页面
            await page.goto(
                "https://stockpage.10jqka.com.cn/000807/operate/",
                wait_until="domcontentloaded",  # 等待DOM加载完成
                timeout=15000  # 15秒超时
            )
            
            print("页面加载完成，等待内容...")
            
            # 等待页面稳定
            await page.wait_for_timeout(3000)
            
            # 滚动到页面底部，触发懒加载
            print("滚动页面加载更多内容...")
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            
            # 等待滚动后的内容加载
            await page.wait_for_timeout(2000)
            
            # 再次滚动确保所有内容加载
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(2000)
            
            # 尝试等待特定元素（如果知道的话）
            try:
                # 等待可能的加载指示器消失或内容出现
                await page.wait_for_function(
                    "document.readyState === 'complete'",
                    timeout=5000
                )
            except:
                print("等待页面完全加载超时，继续...")
            
            # 获取页面内容
            print("获取页面内容...")
            
            # 获取页面标题
            title = await page.title()
            print(f"页面标题: {title}")
            
            # 获取页面文本内容
            text_content = await page.evaluate("""
                () => {
                    // 移除脚本和样式标签
                    const scripts = document.querySelectorAll('script, style');
                    scripts.forEach(el => el.remove());
                    
                    // 获取body的文本内容
                    return document.body.innerText || document.body.textContent || '';
                }
            """)
            
            # 获取HTML内容（备用）
            html_content = await page.content()
            
            print(f"文本内容长度: {len(text_content)} 字符")
            print(f"HTML内容长度: {len(html_content)} 字符")
            
            # 保存内容到文件
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # 创建输出目录
            output_dir = "/Users/yuli/workspace/flowllm/test/crawl_output"
            os.makedirs(output_dir, exist_ok=True)
            
            # 保存文本内容
            text_filename = f"stock_content_{timestamp}.txt"
            text_filepath = os.path.join(output_dir, text_filename)
            
            with open(text_filepath, 'w', encoding='utf-8') as f:
                f.write(f"页面标题: {title}\n")
                f.write(f"爬取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"URL: https://stockpage.10jqka.com.cn/000807/operate/\n")
                f.write("=" * 50 + "\n\n")
                f.write(text_content)
            
            # 保存HTML内容
            html_filename = f"stock_html_{timestamp}.html"
            html_filepath = os.path.join(output_dir, html_filename)
            
            with open(html_filepath, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            print(f"\n✅ 内容已保存到文件:")
            print(f"📄 文本内容: {text_filepath}")
            print(f"🌐 HTML内容: {html_filepath}")
            
            if len(text_content) > 100:
                print("\n--- 页面文本内容预览 ---")
                print(text_content[:1000] + "..." if len(text_content) > 1000 else text_content)
            else:
                print("文本内容较少，显示HTML片段:")
                print(html_content[:1000] + "..." if len(html_content) > 1000 else html_content)
            
            return {
                'success': True,
                'title': title,
                'text': text_content,
                'html': html_content,
                'text_length': len(text_content),
                'html_length': len(html_content),
                'text_file': text_filepath,
                'html_file': html_filepath
            }
            
        except Exception as e:
            print(f"爬取过程中发生错误: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
        
        finally:
            # 关闭浏览器
            await browser.close()


async def main():
    """主函数"""
    print("使用Playwright爬取网页...")
    print("=" * 50)
    
    start_time = time.time()
    result = await crawl_with_playwright()
    end_time = time.time()
    
    print("\n" + "=" * 50)
    print(f"爬取完成，耗时: {end_time - start_time:.2f} 秒")
    
    if result['success']:
        print("✅ 爬取成功!")
        print(f"页面标题: {result['title']}")
        print(f"文本长度: {result['text_length']} 字符")
        print(f"HTML长度: {result['html_length']} 字符")
        print(f"📁 文件保存位置:")
        print(f"   文本文件: {result['text_file']}")
        print(f"   HTML文件: {result['html_file']}")
    else:
        print("❌ 爬取失败!")
        print(f"错误信息: {result['error']}")


if __name__ == "__main__":
    asyncio.run(main())