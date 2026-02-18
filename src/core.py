import concurrent.futures
from .config import GOOGLE_API_KEY, CSE_ID
from .search import process_crossref, process_openalex, process_arxiv, process_google

def search_all_sources(query, limit, sources=None):
    """
    Orchestrates parallel searches across multiple academic and web sources.
    """
    if sources is None:
        sources = ["openalex", "arxiv", "crossref"]
        # Add Google if credentials are provided
        if GOOGLE_API_KEY and CSE_ID:
            sources.append("google")

    sources_lower = [s.lower() for s in sources]
    all_results = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = []

        if "openalex" in sources_lower:
            futures.append(executor.submit(process_openalex, query, limit))

        if "arxiv" in sources_lower:
            futures.append(executor.submit(process_arxiv, query, limit))

        if "crossref" in sources_lower:
            futures.append(executor.submit(process_crossref, query, limit))

        if "google" in sources_lower:
            futures.append(executor.submit(process_google, query, limit))

        for future in concurrent.futures.as_completed(futures):
            try:
                data = future.result()
                if data:
                    all_results.extend(data)
            except Exception as exc:
                print(f"   [!] Worker thread generated an exception: {exc}")

    return all_results