import random
from typing import List


def get_random_user_agent() -> str:
    if random.choice([True, False]):
        return _get_predefined_user_agent()
    else:
        return _generate_dynamic_user_agent()


def _get_predefined_user_agent() -> str:
    """Get a user agent from predefined list."""
    user_agents: List[str] = [
        # Chrome on Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
        # Chrome on macOS
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        # Chrome on Linux
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Ubuntu; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        # Firefox on Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
        # Firefox on macOS
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
        # Safari on macOS
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
        # Edge on Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    ]

    return random.choice(user_agents)


def _generate_dynamic_user_agent() -> str:
    """Generate a user agent with random component combinations."""

    # 操作系统组合
    os_combinations = [
        "Windows NT 10.0; Win64; x64",
        "Windows NT 11.0; Win64; x64",
        "Macintosh; Intel Mac OS X 10_15_7",
        "Macintosh; Intel Mac OS X 10_15_6",
        "Macintosh; Intel Mac OS X 11_7_10",
        "X11; Linux x86_64",
        "X11; Ubuntu; Linux x86_64",
        "X11; Linux i686",
    ]

    # Chrome版本
    chrome_versions = [
        "120.0.0.0",
        "119.0.0.0",
        "118.0.0.0",
        "117.0.0.0",
        "121.0.0.0",
        "116.0.0.0",
        "115.0.0.0",
    ]

    # WebKit版本
    webkit_versions = [
        "537.36",
        "537.35",
        "537.34",
    ]

    # Firefox版本
    firefox_versions = [
        "121.0",
        "120.0",
        "119.0",
        "118.0",
        "117.0",
    ]

    # Safari版本
    safari_versions = [
        ("605.1.15", "17.2"),
        ("605.1.15", "17.1"),
        ("605.1.15", "16.6"),
    ]

    # 随机选择浏览器类型
    browser_type = random.choice(["chrome", "firefox", "safari", "edge"])
    os_string = random.choice(os_combinations)

    if browser_type == "chrome":
        chrome_version = random.choice(chrome_versions)
        webkit_version = random.choice(webkit_versions)
        return f"Mozilla/5.0 ({os_string}) AppleWebKit/{webkit_version} (KHTML, like Gecko) Chrome/{chrome_version} Safari/{webkit_version}"

    elif browser_type == "firefox":
        if "Windows" in os_string:
            firefox_version = random.choice(firefox_versions)
            return f"Mozilla/5.0 ({os_string}; rv:{firefox_version}) Gecko/20100101 Firefox/{firefox_version}"
        else:
            # macOS/Linux Firefox
            firefox_version = random.choice(firefox_versions)
            return f"Mozilla/5.0 ({os_string}; rv:{firefox_version}) Gecko/20100101 Firefox/{firefox_version}"

    elif browser_type == "safari" and "Macintosh" in os_string:
        webkit_version, safari_version = random.choice(safari_versions)
        return f"Mozilla/5.0 ({os_string}) AppleWebKit/{webkit_version} (KHTML, like Gecko) Version/{safari_version} Safari/{webkit_version}"

    elif browser_type == "edge" and "Windows" in os_string:
        chrome_version = random.choice(chrome_versions)
        webkit_version = random.choice(webkit_versions)
        edge_version = chrome_version  # Edge版本通常与Chrome版本一致
        return f"Mozilla/5.0 ({os_string}) AppleWebKit/{webkit_version} (KHTML, like Gecko) Chrome/{chrome_version} Safari/{webkit_version} Edg/{edge_version}"

    # 如果组合不匹配，回退到Chrome
    chrome_version = random.choice(chrome_versions)
    webkit_version = random.choice(webkit_versions)
    return f"Mozilla/5.0 ({os_string}) AppleWebKit/{webkit_version} (KHTML, like Gecko) Chrome/{chrome_version} Safari/{webkit_version}"
