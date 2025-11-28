import requests
import time
from .config import UNPAYWALL_EMAIL

def clean_text(text):
    """
    Removes newlines, tabs, and extra spaces to ensure CSV stays clean.
    """
    if not text:
        return ""
    if isinstance(text, list):
        text = " ".join([str(x) for x in text])
    # Replace newlines with spaces, remove tabs
    text = str(text).replace('\n', ' ').replace('\r', '').replace('\t', ' ')
    # Remove double spaces
    return " ".join(text.split())

def safe_get(url, params=None, headers=None, timeout=20, retries=1):
    if headers is None: headers = {}
    if 'User-Agent' not in headers:
        headers['User-Agent'] = f"AcademicSearchBot/1.0 (mailto:{UNPAYWALL_EMAIL})"

    for attempt in range(retries + 1):
        try:
            r = requests.get(url, params=params, headers=headers, timeout=timeout)

            if r.status_code == 403 and "semanticscholar" in url:
                print("   [!] Semantic Scholar Error: API Key required or Invalid.")
                return None

            elif r.status_code == 429:
                if attempt < retries:
                    print(f"   [!] Too many requests. Cooling down... {url} (Attempt {attempt+1})")
                    time.sleep(5)
                    continue # Retry
                else:
                    print(f"   [!] Too many requests. Giving up on {url}")
                    return None

            if r.status_code != 200:
                return None
            return r
        except Exception:
            return None
    return None

def format_authors(authors_data):
    if not authors_data: return ""
    formatted = []
    for a in authors_data:
        if isinstance(a, dict):
            name = a.get('name')
            if not name:
                name = f"{a.get('given','')} {a.get('family','')}"
            formatted.append(name.strip())
        elif isinstance(a, str):
            formatted.append(a)
    return "; ".join(formatted[:3])
