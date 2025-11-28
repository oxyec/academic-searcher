import concurrent.futures
from .config import GOOGLE_API_KEY, CSE_ID
from .search import process_crossref, process_semanticscholar, process_google

def search_all_sources(query, limit):
    """
    Executes searches across all configured sources in parallel.
    Returns a combined list of result dictionaries.
    """
    all_results = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = []

        # 1. CrossRef
        futures.append(executor.submit(process_crossref, query, limit))

        # 2. Semantic Scholar
        futures.append(executor.submit(process_semanticscholar, query, limit))

        # 3. Google (only if configured)
        if GOOGLE_API_KEY and CSE_ID:
            futures.append(executor.submit(process_google, query, limit, GOOGLE_API_KEY, CSE_ID))

        # Gather results
        for future in concurrent.futures.as_completed(futures):
            try:
                data = future.result()
                if data:
                    all_results.extend(data)
            except Exception as exc:
                print(f"   [!] Search generated an exception: {exc}")

    return all_results
