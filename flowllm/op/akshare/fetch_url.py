import requests
from bs4 import BeautifulSoup
import urllib3

# 禁用 SSL 警告（可选，用于处理不安全的 HTTPS）
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def fetch_webpage_text(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        # 发送请求
        response = requests.get(url, headers=headers, timeout=10, verify=False)
        response.raise_for_status()  # 检查请求是否成功
        response.encoding = response.apparent_encoding  # 自动识别编码

        # 使用 BeautifulSoup 解析 HTML
        soup = BeautifulSoup(response.text, 'html.parser')

        # 移除 script 和 style 标签内容，避免干扰
        for script_or_style in soup(['script', 'style', 'nav', 'footer', 'header']):
            script_or_style.decompose()

        # 提取文本
        text = soup.get_text()

        # 清理空白字符：去除多余空行和空格
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)

        return text

    except requests.exceptions.RequestException as e:
        return f"请求失败: {e}"
    except Exception as e:
        return f"解析失败: {e}"

# 示例使用
if __name__ == "__main__":
    url = "http://finance.eastmoney.com/a/202508133482756869.html"
    text = fetch_webpage_text(url)
    print(text)