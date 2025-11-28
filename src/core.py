import concurrent.futures
from .config import GOOGLE_API_KEY, CSE_ID
from .search import process_crossref, process_semanticscholar, process_google

def search_all_sources(query, limit, sources=None):
    """
    Executes selectable searches across configured sources in parallel.
    sources -> ['crossref','semantic','google'] şeklinde list alabilir.
    """
    if sources is None:
        sources = ["crossref", "semantic", "google"]  # default hepsi

    all_results = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = []

        if "crossref" in sources:
            futures.append(executor.submit(process_crossref, query, limit))

        if "semantic" in sources:
            futures.append(executor.submit(process_semanticscholar, query, limit))

        if "google" in sources and GOOGLE_API_KEY and CSE_ID:
            futures.append(executor.submit(process_google, query, limit, GOOGLE_API_KEY, CSE_ID))

        for future in concurrent.futures.as_completed(futures):
            try:
                data = future.result()
                if data:
                    all_results.extend(data)
            except Exception as exc:
                print(f"[!] Search generated an exception: {exc}")

    return all_results
