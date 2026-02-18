import asyncio
import concurrent.futures
from .config import GOOGLE_API_KEY, CSE_ID
from .search import process_crossref, process_openalex, process_arxiv, process_google

async def search_all_sources_async(query, limit, sources=None):
    """
    Orchestrates async searches across multiple academic and web sources.
    """
    if sources is None:
        sources = ["openalex", "arxiv", "crossref"]
        # Add Google if credentials are provided
        if GOOGLE_API_KEY and CSE_ID:
            sources.append("google")

    sources_lower = [s.lower() for s in sources]
    all_results = []
    tasks = []

    if "openalex" in sources_lower:
        tasks.append(process_openalex(query, limit))

    if "arxiv" in sources_lower:
        tasks.append(process_arxiv(query, limit))

    if "crossref" in sources_lower:
        tasks.append(process_crossref(query, limit))

    if "google" in sources_lower:
        tasks.append(process_google(query, limit))

    results = await asyncio.gather(*tasks, return_exceptions=True)
    for result in results:
        if isinstance(result, Exception):
            print(f"   [!] Async task generated an exception: {result}")
            continue
        if result:
            all_results.extend(result)

    return all_results

def search_all_sources(query, limit, sources=None):
    """
    Sync compatibility wrapper for CLI and non-async callers.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(search_all_sources_async(query, limit, sources=sources))

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(
            lambda: asyncio.run(search_all_sources_async(query, limit, sources=sources))
        ).result()
