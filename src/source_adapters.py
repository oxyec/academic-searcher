"""Shared source adapters and diagnostics for every application interface."""

import asyncio
import html
import re
import xml.etree.ElementTree as ET
from time import perf_counter

import requests

from .app_utils import clean_text, normalize_doi, normalize_int, normalize_year
from .config import CSE_ID, GOOGLE_API_KEY, OPENALEX_API_KEY, S2_API_KEY, UNPAYWALL_EMAIL

DEFAULT_SOURCES = ("Semantic Scholar", "OpenAlex", "ArXiv", "Crossref")
SOURCE_ALIASES = {
    "semanticscholar": "Semantic Scholar", "s2": "Semantic Scholar",
    "openalex": "OpenAlex", "arxiv": "ArXiv", "crossref": "Crossref",
    "google": "Google Custom Search", "googlecustomsearch": "Google Custom Search",
}


class SourceError(RuntimeError):
    """Safe source failure without request URLs or credentials."""


class SourceRows(list):
    def __init__(self, rows=(), skipped_count=0):
        super().__init__(rows)
        self.skipped_count = skipped_count


def default_api_keys():
    return {"ss": S2_API_KEY, "openalex": OPENALEX_API_KEY, "google": GOOGLE_API_KEY, "cx": CSE_ID}


def normalize_sources(sources):
    output = []
    for source in sources:
        key = re.sub(r"[\s_-]+", "", str(source)).casefold()
        if key not in SOURCE_ALIASES:
            raise ValueError(f"Unsupported source: {source}")
        name = SOURCE_ALIASES[key]
        if name not in output:
            output.append(name)
    return output


async def make_request(url, params=None, headers=None, retries=3):
    request_headers = {"User-Agent": "AcademicResearchAssistant/1.0", **(headers or {})}
    for attempt in range(retries):
        try:
            response = await asyncio.to_thread(requests.get, url, params=params, headers=request_headers, timeout=10)
        except requests.RequestException as exc:
            if attempt == retries - 1:
                reason = "Request timed out" if isinstance(exc, requests.Timeout) else "Connection failed"
                raise SourceError(f"{reason} after {retries} attempts.") from None
            await asyncio.sleep(2 ** attempt)
            continue
        status = response.status_code
        if status == 200:
            return response
        if status not in (429, 500, 502, 503, 504) or attempt == retries - 1:
            reason = "Rate limit reached" if status == 429 else "Upstream request failed"
            raise SourceError(f"{reason} (HTTP {status}).")
        try:
            delay = float(response.headers.get("Retry-After", 2 ** (attempt + 1)))
        except (TypeError, ValueError):
            delay = 2 ** (attempt + 1)
        await asyncio.sleep(min(max(delay, 0), 30))
    raise SourceError("No response received.")


def _items(response, *path):
    if response is None:
        raise SourceError("No response received.")
    try:
        data = response.json()
        for key in path:
            data = data[key]
        if not isinstance(data, list):
            raise TypeError
        return data
    except (ValueError, KeyError, TypeError):
        raise SourceError("Source returned an invalid result payload.") from None


def _dict(value):
    return value if isinstance(value, dict) else {}


def _parse_rows(items, parser):
    rows, skipped = [], 0
    for item in items:
        try:
            if not isinstance(item, dict):
                raise TypeError
            rows.append(parser(item))
        except (TypeError, ValueError, AttributeError, IndexError, KeyError):
            skipped += 1
    return SourceRows(rows, skipped)


def _paper(source, title=None, authors=None, year=None, venue=None, url=None, pdf=None,
           doi=None, cites=0, abstract=None, oa=False, oa_status="unknown"):
    if not clean_text(title) and not clean_text(url) and not normalize_doi(doi):
        raise ValueError("Missing publication identity")
    return {
        "Source": source, "Title": clean_text(title) or "Untitled",
        "Authors": clean_text(authors) or "Unknown", "Year": normalize_year(year),
        "Venue": clean_text(venue), "URL": clean_text(url), "PDF": clean_text(pdf),
        "DOI": normalize_doi(doi), "Cites": max(0, normalize_int(cites)),
        "Abstract": clean_text(abstract), "OA": bool(oa), "OAStatus": oa_status or "unknown",
    }


def reconstruct_abstract(inverted_index):
    if not isinstance(inverted_index, dict):
        return ""
    words = []
    for word, positions in inverted_index.items():
        if isinstance(positions, list):
            words.extend((position, word) for position in positions if isinstance(position, int))
    return " ".join(str(word) for _, word in sorted(words))


async def search_semantic_scholar(query, limit=10, api_key=None):
    params = {"query": query, "limit": limit,
              "fields": "title,authors,year,url,openAccessPdf,venue,externalIds,citationCount,abstract,isOpenAccess"}
    response = await make_request("https://api.semanticscholar.org/graph/v1/paper/search", params,
                                  {"x-api-key": api_key} if api_key else {})

    def parse(item):
        authors = ", ".join(clean_text(_dict(author).get("name")) for author in (item.get("authors") or []) if _dict(author).get("name"))
        pdf = _dict(item.get("openAccessPdf")).get("url")
        oa = item.get("isOpenAccess", False) or bool(pdf)
        return _paper("Semantic Scholar", item.get("title"), authors, item.get("year"), item.get("venue"),
                      item.get("url"), pdf, _dict(item.get("externalIds")).get("DOI"),
                      item.get("citationCount"), item.get("abstract"), oa,
                      "open" if oa else ("closed" if item.get("isOpenAccess") is False else "unknown"))
    return _parse_rows(_items(response, "data"), parse)


async def search_openalex(query, limit=10, api_key=None):
    params = {"search": query, "per_page": limit}
    if api_key:
        params["api_key"] = api_key
    response = await make_request("https://api.openalex.org/works", params)

    def parse(item):
        authors = ", ".join(clean_text(_dict(_dict(author).get("author")).get("display_name"))
                            for author in (item.get("authorships") or []) if _dict(_dict(author).get("author")).get("display_name"))
        primary = _dict(item.get("primary_location"))
        oa = _dict(item.get("open_access"))
        best = _dict(item.get("best_oa_location"))
        return _paper("OpenAlex", item.get("title") or item.get("display_name"), authors, item.get("publication_year"),
                      _dict(primary.get("source")).get("display_name"), item.get("doi") or primary.get("landing_page_url") or item.get("id"),
                      best.get("pdf_url") or primary.get("pdf_url"), item.get("doi"), item.get("cited_by_count"),
                      reconstruct_abstract(item.get("abstract_inverted_index")), oa.get("is_oa", False), oa.get("oa_status", "unknown"))
    return _parse_rows(_items(response, "results"), parse)


async def search_arxiv(query, limit=10):
    response = await make_request("https://export.arxiv.org/api/query", {"search_query": f"all:{query}", "start": 0, "max_results": limit})
    if response is None:
        raise SourceError("No response received.")
    try:
        root = ET.fromstring(response.content)
    except ET.ParseError:
        raise SourceError("Source returned invalid XML.") from None
    if root.tag != "{http://www.w3.org/2005/Atom}feed":
        raise SourceError("Source returned an invalid Atom feed.")
    namespace = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
    rows, skipped = [], 0
    for entry in root.findall("atom:entry", namespace):
        link = clean_text(entry.findtext("atom:id", default="", namespaces=namespace))
        if "/api/errors" in link:
            raise SourceError("ArXiv rejected the search query.")
        try:
            authors = ", ".join(clean_text(author.findtext("atom:name", default="", namespaces=namespace))
                                for author in entry.findall("atom:author", namespace))
            pdf = next((item.get("href") for item in entry.findall("atom:link", namespace) if item.get("title") == "pdf"), "")
            rows.append(_paper("ArXiv", entry.findtext("atom:title", namespaces=namespace), authors,
                               clean_text(entry.findtext("atom:published", namespaces=namespace))[:4], "ArXiv Preprint", link, pdf,
                               entry.findtext("arxiv:doi", namespaces=namespace), abstract=entry.findtext("atom:summary", namespaces=namespace),
                               oa=True, oa_status="open"))
        except (ValueError, TypeError):
            skipped += 1
    return SourceRows(rows, skipped)


async def search_crossref(query, email, limit=10):
    params = {"query": query, "rows": limit}
    if email:
        params["mailto"] = email
    response = await make_request("https://api.crossref.org/works", params)

    def parse(item):
        authors = ", ".join(clean_text(f"{_dict(author).get('given') or ''} {_dict(author).get('family') or ''}")
                            for author in (item.get("author") or []))
        parts = _dict(item.get("issued")).get("date-parts") or []
        year = parts[0][0] if parts and parts[0] else None
        pdf = next((_dict(link).get("URL") for link in (item.get("link") or []) if _dict(link).get("content-type") == "application/pdf"), "")
        abstract = html.unescape(re.sub(r"<[^>]+>", " ", item.get("abstract") or ""))
        return _paper("Crossref", (item.get("title") or [""])[0], authors, year,
                      (item.get("container-title") or [""])[0], item.get("URL"), pdf, item.get("DOI"),
                      item.get("is-referenced-by-count"), abstract)
    return _parse_rows(_items(response, "message", "items"), parse)


async def search_google(query, api_key, cx_id, limit=10):
    if not api_key or not cx_id:
        raise SourceError("Google API key and search engine ID are required.")
    response = await make_request("https://www.googleapis.com/customsearch/v1", {"q": query, "key": api_key, "cx": cx_id, "num": min(limit, 10)})
    # Google omits items for successful searches without any matches.
    try:
        data = response.json() if response is not None else None
        if not isinstance(data, dict) or not isinstance(data.get("items", []), list):
            raise ValueError
    except (ValueError, TypeError):
        raise SourceError("Source returned an invalid result payload.") from None

    def parse(item):
        link = clean_text(item.get("link"))
        return _paper("Google", item.get("title"), venue=item.get("displayLink"), url=link,
                      pdf=link if link.split("?")[0].casefold().endswith(".pdf") else "", abstract=item.get("snippet"))
    return _parse_rows(data.get("items", []), parse)


async def search_all_sources(query, limit, sources=None, api_keys=None, email=None, progress_callback=None):
    query = clean_text(query)
    if not query or len(query) > 300:
        raise ValueError("Query must contain between 1 and 300 characters.")
    if not isinstance(limit, int) or not 1 <= limit <= 100:
        raise ValueError("Results per source must be between 1 and 100.")
    sources = normalize_sources(DEFAULT_SOURCES if sources is None else sources)
    api_keys = default_api_keys() if api_keys is None else api_keys
    email = UNPAYWALL_EMAIL if email is None else email

    async def run_source(source):
        started = perf_counter()
        rows, error, status = [], "", "OK"
        try:
            if source == "Semantic Scholar":
                rows = await search_semantic_scholar(query, limit, api_keys.get("ss"))
            elif source == "OpenAlex":
                rows = await search_openalex(query, limit, api_keys.get("openalex"))
            elif source == "ArXiv":
                rows = await search_arxiv(query, limit)
            elif source == "Crossref":
                rows = await search_crossref(query, email, limit)
            elif source == "Google Custom Search":
                rows = await search_google(query, api_keys.get("google"), api_keys.get("cx"), limit)
            skipped = getattr(rows, "skipped_count", 0)
            if skipped:
                error = f"Skipped {skipped} malformed records."
                status = "Partial" if rows else "Error"
        except SourceError as exc:
            error, status = str(exc), "Error"
        except Exception as exc:
            error, status = f"Unexpected source failure ({type(exc).__name__}).", "Error"
        return source, rows, {"source": source, "result_count": len(rows), "duration_sec": perf_counter() - started,
                              "error": error, "status": status, "skipped_count": getattr(rows, "skipped_count", 0)}

    tasks = [asyncio.create_task(run_source(source)) for source in sources]
    collected = {}
    for completed, task in enumerate(asyncio.as_completed(tasks), 1):
        source, rows, stat = await task
        collected[source] = (rows, stat)
        if progress_callback:
            progress_callback(completed / len(tasks))
    # Preserve source priority regardless of which network request finishes first.
    all_results = [row for source in sources for row in collected[source][0]]
    source_stats = [collected[source][1] for source in sources]
    return all_results, source_stats
