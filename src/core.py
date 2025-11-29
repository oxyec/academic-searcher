import concurrent.futures
from .config import GOOGLE_API_KEY, CSE_ID
from .search import process_crossref, process_semanticscholar, process_google

def search_all_sources(query, limit, sources=None):
    """
    Executes selectable searches across configured sources in parallel.
    sources -> ['crossref','semantic','google'] can be passed as a list of strings.
    The strings are case-insensitive and can match partial names like "CrossRef", "Semantic Scholar".
    """
    if sources is None:
        sources = ["crossref", "semantic", "google"]

    # Normalize sources to lowercase for easier matching
    sources_lower = [s.lower() for s in sources]

    # Determine which sources to search
    use_crossref = any("crossref" in s for s in sources_lower)
    use_semantic = any("semantic" in s for s in sources_lower)
    use_google = any("google" in s for s in sources_lower)

    all_results = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = []

        # 1. CrossRef
        if use_crossref:
            futures.append(executor.submit(process_crossref, query, limit))

        # 2. Semantic Scholar
        if use_semantic:
            futures.append(executor.submit(process_semanticscholar, query, limit))

        # 3. Google (only if configured and selected)
        if use_google and GOOGLE_API_KEY and CSE_ID:
            futures.append(executor.submit(process_google, query, limit, GOOGLE_API_KEY, CSE_ID))

        for future in concurrent.futures.as_completed(futures):
            try:
                data = future.result()
                if data:
                    all_results.extend(data)
            except Exception as exc:
                print(f"   [!] Search generated an exception: {exc}")

    return all_results
