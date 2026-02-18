import asyncio
import random
import xml.etree.ElementTree as ET
from time import perf_counter

import requests

from .app_utils import clean_text, normalize_int, normalize_year


async def make_request(url, params=None, headers=None, retries=3):
    for attempt in range(retries):
        try:
            await asyncio.sleep(random.uniform(0.2, 0.5))
            response = await asyncio.to_thread(
                requests.get,
                url,
                params=params,
                headers=headers,
                timeout=10,
            )

            if response.status_code in [429, 503]:
                await asyncio.sleep(2 ** (attempt + 1))
                continue

            response.raise_for_status()
            return response
        except Exception as exc:
            if attempt == retries - 1:
                print(f"Request failed for {url}: {exc}")
                return None
            await asyncio.sleep(1)
    return None


async def search_semantic_scholar(query, limit=10, api_key=None):
    url = "https://api.semanticscholar.org/graph/v1/paper/search"
    headers = {"x-api-key": api_key} if api_key else {}
    params = {
        "query": query,
        "limit": limit,
        "fields": "title,authors,year,url,openAccessPdf,venue,externalIds,citationCount,abstract,isOpenAccess",
    }

    response = await make_request(url, params, headers)
    if not response:
        return []

    results = []
    try:
        for item in response.json().get("data", []):
            authors = ", ".join([author.get("name", "") for author in item.get("authors", []) if author.get("name")])
            pdf = item.get("openAccessPdf", {}).get("url") if item.get("openAccessPdf") else None
            results.append(
                {
                    "Source": "Semantic Scholar",
                    "Title": item.get("title"),
                    "Authors": authors,
                    "Year": normalize_year(item.get("year")),
                    "Venue": item.get("venue"),
                    "URL": item.get("url"),
                    "PDF": pdf,
                    "DOI": item.get("externalIds", {}).get("DOI"),
                    "Cites": normalize_int(item.get("citationCount", 0)),
                    "Abstract": item.get("abstract"),
                    "OA": item.get("isOpenAccess", False) or bool(pdf),
                }
            )
    except Exception as exc:
        print(f"Error parsing Semantic Scholar: {exc}")
    return results


async def search_openalex(query, limit=10):
    url = "https://api.openalex.org/works"
    params = {"search": query, "per_page": limit}
    response = await make_request(url, params)
    if not response:
        return []

    results = []
    try:
        for item in response.json().get("results", []):
            authors = ", ".join(
                [
                    author.get("author", {}).get("display_name", "")
                    for author in item.get("authorships", [])
                    if author.get("author")
                ]
            )
            results.append(
                {
                    "Source": "OpenAlex",
                    "Title": item.get("title"),
                    "Authors": authors,
                    "Year": normalize_year(item.get("publication_year")),
                    "Venue": item.get("primary_location", {}).get("source", {}).get("display_name", "OpenAlex"),
                    "URL": item.get("doi") or item.get("id"),
                    "PDF": item.get("open_access", {}).get("oa_url"),
                    "DOI": str(item.get("doi", "")).replace("https://doi.org/", ""),
                    "Cites": normalize_int(item.get("cited_by_count", 0)),
                    "Abstract": "Abstract available via source link.",
                    "OA": bool(item.get("open_access", {}).get("is_oa", False)),
                }
            )
    except Exception as exc:
        print(f"Error parsing OpenAlex: {exc}")
    return results


async def search_arxiv(query, limit=10):
    url = "http://export.arxiv.org/api/query"
    params = {"search_query": f"all:{query}", "start": 0, "max_results": limit}
    response = await make_request(url, params)
    if not response:
        return []

    results = []
    try:
        root = ET.fromstring(response.content)
        namespace = {"atom": "http://www.w3.org/2005/Atom"}

        for entry in root.findall("atom:entry", namespace):
            title = clean_text(entry.findtext("atom:title", default="", namespaces=namespace))
            summary = clean_text(entry.findtext("atom:summary", default="", namespaces=namespace))
            published = clean_text(entry.findtext("atom:published", default="", namespaces=namespace))[:4]
            authors = ", ".join(
                [
                    clean_text(author.findtext("atom:name", default="", namespaces=namespace))
                    for author in entry.findall("atom:author", namespace)
                ]
            )
            link = clean_text(entry.findtext("atom:id", default="", namespaces=namespace))

            pdf_link = ""
            for item in entry.findall("atom:link", namespace):
                if item.attrib.get("title") == "pdf":
                    pdf_link = clean_text(item.attrib.get("href"))

            results.append(
                {
                    "Source": "ArXiv",
                    "Title": title,
                    "Authors": authors,
                    "Year": normalize_year(published),
                    "Venue": "ArXiv",
                    "URL": link,
                    "PDF": pdf_link,
                    "DOI": "",
                    "Cites": 0,
                    "Abstract": summary,
                    "OA": True,
                }
            )
    except Exception as exc:
        print(f"Error parsing ArXiv: {exc}")
    return results


async def search_crossref(query, email, limit=10):
    url = "https://api.crossref.org/works"
    params = {"query": query, "rows": limit, "mailto": email}
    response = await make_request(url, params)
    if not response:
        return []

    results = []
    try:
        for item in response.json().get("message", {}).get("items", []):
            authors = ", ".join(
                [
                    clean_text(f"{author.get('given', '')} {author.get('family', '')}")
                    for author in item.get("author", [])
                ]
            )
            date_parts = item.get("issued", {}).get("date-parts")
            year = date_parts[0][0] if date_parts else None

            results.append(
                {
                    "Source": "Crossref",
                    "Title": (item.get("title") or ["No title"])[0],
                    "Authors": authors,
                    "Year": normalize_year(year),
                    "Venue": (item.get("container-title") or ["Crossref"])[0],
                    "URL": item.get("URL"),
                    "PDF": "",
                    "DOI": item.get("DOI"),
                    "Cites": normalize_int(item.get("is-referenced-by-count", 0)),
                    "Abstract": "",
                    "OA": False,
                }
            )
    except Exception as exc:
        print(f"Error parsing Crossref: {exc}")
    return results


async def search_google(query, api_key, cx_id, limit=10):
    if not api_key or not cx_id:
        return []

    url = "https://www.googleapis.com/customsearch/v1"
    params = {"q": query, "key": api_key, "cx": cx_id, "num": min(limit, 10)}
    response = await make_request(url, params)
    if not response:
        return []

    results = []
    try:
        for item in response.json().get("items", []):
            link = item.get("link", "")
            results.append(
                {
                    "Source": "Google",
                    "Title": item.get("title"),
                    "Authors": "See link",
                    "Year": None,
                    "Venue": item.get("displayLink"),
                    "URL": link,
                    "PDF": link if link.endswith(".pdf") else "",
                    "DOI": "",
                    "Cites": 0,
                    "Abstract": item.get("snippet", ""),
                    "OA": False,
                }
            )
    except Exception as exc:
        print(f"Error parsing Google: {exc}")
    return results


async def search_all_sources(query, limit, sources, api_keys, email, progress_callback=None):
    all_results = []
    source_stats = []

    async def run_source(source):
        started = perf_counter()
        if source == "Semantic Scholar":
            rows = await search_semantic_scholar(query, limit, api_keys.get("ss"))
        elif source == "OpenAlex":
            rows = await search_openalex(query, limit)
        elif source == "ArXiv":
            rows = await search_arxiv(query, limit)
        elif source == "Crossref":
            rows = await search_crossref(query, email, limit)
        elif source == "Google Custom Search":
            rows = await search_google(query, api_keys.get("google"), api_keys.get("cx"), limit)
        else:
            rows = []
        return source, rows, "", perf_counter() - started

    tasks = [asyncio.create_task(run_source(source)) for source in sources]
    total = len(tasks)
    if total == 0:
        return [], []

    completed = 0
    for task in asyncio.as_completed(tasks):
        try:
            source_name, source_results, error_text, duration = await task
            if source_results:
                all_results.extend(source_results)
        except Exception as exc:
            source_name = "Unknown"
            source_results = []
            error_text = str(exc)
            duration = 0.0
            print(f"Source task failed: {exc}")

        source_stats.append(
            {
                "source": source_name,
                "result_count": len(source_results),
                "duration_sec": duration,
                "error": error_text,
                "status": "Error" if error_text else "OK",
            }
        )
        completed += 1
        if progress_callback:
            progress_callback(completed / total)

    source_stats.sort(key=lambda item: item["source"])
    return all_results, source_stats
