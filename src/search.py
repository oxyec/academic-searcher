from urllib.parse import quote_plus
from .utils import safe_get, format_authors
from .config import S2_API_KEY, UNPAYWALL_EMAIL

def get_unpaywall_data(doi, email):
    if not doi: return "No DOI", ""
    url = f"https://api.unpaywall.org/v2/{quote_plus(doi)}"
    params = {"email": email}
    r = safe_get(url, params=params)
    if not r: return "Unknown", ""

    try:
        data = r.json()
        oa_status = data.get('oa_status', 'closed')
        pdf_link = ""
        best_loc = data.get('best_oa_location', {})
        if best_loc and isinstance(best_loc, dict):
            pdf_link = best_loc.get('url_for_pdf') or best_loc.get('url') or ""
        return oa_status, pdf_link
    except:
        return "Error", ""

def search_crossref(query, rows):
    url = "https://api.crossref.org/works"
    params = {"query.title": query, "rows": rows}
    r = safe_get(url, params=params)
    if not r: return []
    return r.json().get("message", {}).get("items", [])

def process_crossref(query, rows):
    print(f"   [Starting] CrossRef search for '{query}'...")
    items = search_crossref(query, rows)
    results = []
    for item in items:
        title = item.get('title',['No Title'])[0]
        doi = item.get('DOI')
        venue = item.get('container-title', [''])[0] if item.get('container-title') else ""

        oa_status, pdf_link = get_unpaywall_data(doi, UNPAYWALL_EMAIL)

        row = {
            'query': query, 'source': 'CrossRef',
            'title': title,
            'authors': format_authors(item.get('author')),
            'year': item.get('issued',{}).get('date-parts',[[None]])[0][0],
            'venue': venue,
            'doi': doi, 'url': item.get('URL'),
            'oa_status': oa_status, 'pdf_link': pdf_link
        }
        results.append(row)
    print(f"   [Finished] CrossRef found {len(results)} items.")
    return results

def search_semanticscholar(query, limit):
    url = "https://api.semanticscholar.org/graph/v1/paper/search"
    # Added 'venue' to fields
    params = {"query": query, "limit": limit, "fields": "title,authors,year,venue,doi,url,openAccessPdf"}

    headers = {}
    if S2_API_KEY:
        headers['x-api-key'] = S2_API_KEY

    r = safe_get(url, params=params, headers=headers)
    if not r: return []
    return r.json().get("data", [])

def process_semanticscholar(query, limit):
    print(f"   [Starting] Semantic Scholar search for '{query}'...")
    items = search_semanticscholar(query, limit)
    results = []
    for item in items:
        doi = item.get('doi')
        oa_status, pdf_link = get_unpaywall_data(doi, UNPAYWALL_EMAIL)

        if not pdf_link and item.get('openAccessPdf'):
            pdf_link = item.get('openAccessPdf', {}).get('url')
            oa_status = "gold (via S2)"

        row = {
            'query': query, 'source': 'SemanticScholar',
            'title': item.get('title'),
            'authors': format_authors(item.get('authors')),
            'year': item.get('year'),
            'venue': item.get('venue'),
            'doi': doi, 'url': item.get('url'),
            'oa_status': oa_status, 'pdf_link': pdf_link
        }
        results.append(row)
    print(f"   [Finished] Semantic Scholar found {len(results)} items.")
    return results

def search_google(query, key, cse, num):
    if not key or not cse: return []
    url = "https://www.googleapis.com/customsearch/v1"
    real_num = min(num, 10)
    params = {"q": query, "key": key, "cx": cse, "num": real_num}
    r = safe_get(url, params=params)
    if not r: return []
    return r.json().get("items", [])

def process_google(query, limit, key, cse):
    if not key or not cse:
        return []
    print(f"   [Starting] Google search for '{query}'...")
    items = search_google(query, key, cse, limit)
    results = []
    for item in items:
        row = {
            'query': query, 'source': 'Google',
            'title': item.get('title'), 'authors': 'Web Result',
            'year': '', 'venue': 'Web',
            'doi': '', 'url': item.get('link'),
            'oa_status': 'N/A', 'pdf_link': ''
        }
        results.append(row)
    print(f"   [Finished] Google found {len(results)} items.")
    return results
