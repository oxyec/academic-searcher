import asyncio
import requests
import time
from .config import UNPAYWALL_EMAIL

def clean_text(text):
    """
    Standardizes text by removing newlines, tabs, and collapsing multiple spaces.
    Ensures CSV files remain properly formatted.
    """
    if not text:
        return ""
    if isinstance(text, list):
        text = " ".join([str(x) for x in text])
    
    text = str(text).replace('\n', ' ').replace('\r', '').replace('\t', ' ')
    return " ".join(text.split())

def _build_headers(headers=None):
    merged_headers = headers.copy() if headers else {}
    if 'User-Agent' not in merged_headers:
        merged_headers['User-Agent'] = f"AcademicSearchBot/1.0 (mailto:{UNPAYWALL_EMAIL})"
    return merged_headers

def safe_get(url, params=None, headers=None, timeout=20):
    """
    Performs a GET request with basic error handling and rate-limit backoff.
    """
    headers = _build_headers(headers)

    try:
        r = requests.get(url, params=params, headers=headers, timeout=timeout)

        if r.status_code == 429:
            print(f"   [!] Rate limit hit. Waiting 5s for: {url}")
            time.sleep(5)
            return None

        if r.status_code != 200:
            return None
        return r
    except Exception:
        return None

async def safe_get_async(url, params=None, headers=None, timeout=20):
    """
    Async-compatible wrapper for GET requests using a worker thread.
    """
    headers = _build_headers(headers)

    try:
        r = await asyncio.to_thread(
            requests.get,
            url,
            params=params,
            headers=headers,
            timeout=timeout
        )

        if r.status_code == 429:
            print(f"   [!] Rate limit hit. Waiting 5s for: {url}")
            await asyncio.sleep(5)
            return None

        if r.status_code != 200:
            return None
        return r
    except Exception:
        return None

def format_authors(authors_data):
    """
    Converts diverse author data structures into a consistent semi-colon separated string.
    """
    if not authors_data: return "N/A"
    formatted = []
    for a in authors_data:
        if isinstance(a, dict):
            name = a.get('name') or f"{a.get('given','')} {a.get('family','')}"
            formatted.append(name.strip())
        elif isinstance(a, str):
            formatted.append(a)
    
    return "; ".join(formatted[:3]) if formatted else "N/A"
