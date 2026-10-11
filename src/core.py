"""Shared search, normalization, deduplication and ranking workflow."""

import asyncio
import concurrent.futures

from .app_utils import clean_text, normalize_year, prepare_results
from .source_adapters import search_all_sources as search_sources


def to_api_rows(rows, query):
    output = []
    for row in rows:
        output.append({
            "query": query, "source": clean_text(row.get("Source")),
            "title": clean_text(row.get("Title")) or "Untitled",
            "authors": clean_text(row.get("Authors")) or "Unknown",
            "year": normalize_year(row.get("Year")), "venue": clean_text(row.get("Venue")),
            "doi": clean_text(row.get("DOI")), "url": clean_text(row.get("URL")),
            "oa_status": clean_text(row.get("OAStatus")) or ("open" if row.get("OA") else "unknown"),
            "pdf_link": clean_text(row.get("PDF")), "citations": int(row.get("Cites", 0)),
            "abstract": clean_text(row.get("Abstract")), "score": float(row.get("Score", 0)),
            "source_count": int(row.get("SourceCount", 1)), "record_id": clean_text(row.get("RecordId")),
            "text_match": float(row.get("TextMatch", 0)), "citation_signal": float(row.get("CitationSignal", 0)),
            "recency_signal": float(row.get("RecencySignal", 0)), "open_access_bonus": float(row.get("OpenAccessBonus", 0)),
        })
    return output


async def search_with_diagnostics_async(query, limit, sources=None):
    query = clean_text(query)
    raw_results, diagnostics = await search_sources(query, limit, sources=sources)
    _, df = prepare_results(raw_results, query)
    results = to_api_rows(df.to_dict(orient="records"), query) if not df.empty else []
    return results, diagnostics


async def search_all_sources_async(query, limit, sources=None):
    results, _ = await search_with_diagnostics_async(query, limit, sources)
    return results


def search_all_sources(query, limit, sources=None):
    """Sync compatibility wrapper, including callers with an existing event loop."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(search_all_sources_async(query, limit, sources=sources))
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(lambda: asyncio.run(search_all_sources_async(query, limit, sources=sources))).result()
