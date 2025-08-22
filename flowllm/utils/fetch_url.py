import random
import time

import requests
import urllib3
from bs4 import BeautifulSoup

# Disable SSL warnings (optional, for handling insecure HTTPS)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def get_random_headers():
    """Generate random headers to avoid detection"""
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.82 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:89.0) Gecko/20100101 Firefox/89.0',
        'Mozilla/5.0 (X11; Linux x86_64; rv:89.0) Gecko/20100101 Firefox/89.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/91.0.864.59'
    ]

    accept_languages = [
        'en-US,en;q=0.9',
        'zh-CN,zh;q=0.9,en;q=0.8',
        'en-GB,en;q=0.9',
        'fr-FR,fr;q=0.9,en;q=0.8',
        'de-DE,de;q=0.9,en;q=0.8'
    ]

    accept_encodings = [
        'gzip, deflate, br',
        'gzip, deflate',
        'br, gzip, deflate'
    ]

    headers = {
        'User-Agent': random.choice(user_agents),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': random.choice(accept_languages),
        'Accept-Encoding': random.choice(accept_encodings),
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }

    # Randomly add some optional headers
    if random.random() > 0.5:
        headers['DNT'] = '1'
    if random.random() > 0.7:
        headers['Cache-Control'] = 'max-age=0'
    if random.random() > 0.6:
        headers['Sec-Fetch-Dest'] = 'document'
        headers['Sec-Fetch-Mode'] = 'navigate'
        headers['Sec-Fetch-Site'] = 'none'

    return headers


def fetch_webpage_text(url, min_delay=1, max_delay=3):
    """
    Fetch and extract text content from a webpage with randomization
    
    Args:
        url (str): The URL to fetch
        min_delay (int): Minimum delay before request (seconds)
        max_delay (int): Maximum delay before request (seconds)
    
    Returns:
        str: Extracted text content or error message
    """
    # Add random delay to avoid being detected as bot
    delay = random.uniform(min_delay, max_delay)
    time.sleep(delay)

    headers = get_random_headers()

    # Random timeout between 8-15 seconds
    timeout = random.randint(8, 15)

    try:
        # Send request with random headers and timeout
        response = requests.get(url, headers=headers, timeout=timeout, verify=False)
        response.raise_for_status()  # Check if request was successful
        response.encoding = response.apparent_encoding  # Auto-detect encoding

        # Parse HTML using BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')

        # Remove script, style and navigation elements to avoid interference
        for script_or_style in soup(['script', 'style', 'nav', 'footer', 'header']):
            script_or_style.decompose()

        # Extract text content
        text = soup.get_text()

        # Clean whitespace: remove extra blank lines and spaces
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)

        return text

    except requests.exceptions.RequestException as e:
        return f"Request failed: {e}"
    except Exception as e:
        return f"Parsing failed: {e}"


# Example usage
if __name__ == "__main__":
    url = "http://finance.eastmoney.com/a/202508133482756869.html"
    text = fetch_webpage_text(url)
    print(text)
