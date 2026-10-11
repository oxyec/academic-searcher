"""Legacy lowercase-record entry points backed by the shared source adapters."""

from urllib.parse import quote

from .config import CSE_ID, GOOGLE_API_KEY, OPENALEX_API_KEY, S2_API_KEY, UNPAYWALL_EMAIL
from .core import to_api_rows
from .source_adapters import (
    SourceError, make_request, reconstruct_abstract, search_arxiv,
    search_crossref, search_google, search_openalex, search_semantic_scholar,
)


async def process_openalex(query, limit):
    return to_api_rows(await search_openalex(query, limit, OPENALEX_API_KEY), query)


async def process_arxiv(query, limit):
    return to_api_rows(await search_arxiv(query, limit), query)


async def process_crossref(query, limit):
    return to_api_rows(await search_crossref(query, UNPAYWALL_EMAIL, limit), query)


async def process_google(query, limit):
    return to_api_rows(await search_google(query, GOOGLE_API_KEY, CSE_ID, limit), query)


async def process_semanticscholar(query, limit):
    return to_api_rows(await search_semantic_scholar(query, limit, S2_API_KEY), query)


async def get_unpaywall_data(doi, email):
    """Optional standalone enrichment helper retained for existing callers."""
    if not doi:
        return "No DOI", ""
    try:
        response = await make_request(f"https://api.unpaywall.org/v2/{quote(doi, safe='')}", {"email": email})
        data = response.json()
        best = data.get("best_oa_location") or {}
        return data.get("oa_status", "unknown"), best.get("url_for_pdf") or ""
    except (SourceError, ValueError, TypeError, AttributeError):
        return "Unknown", ""
