import asyncio
import xml.etree.ElementTree as ET
from urllib.parse import quote_plus
from .utils import safe_get_async, format_authors
from .config import UNPAYWALL_EMAIL, GOOGLE_API_KEY, CSE_ID

def reconstruct_abstract(inverted_index):
    """
    Rebuilds the abstract text from OpenAlex's inverted index format.
    """
    if not inverted_index:
        return "Abstract not available."
    
    word_index = []
    for word, positions in inverted_index.items():
        for pos in positions:
            word_index.append((pos, word))
    
    word_index.sort()
    return " ".join([word for _, word in word_index])

async def get_unpaywall_data(doi, email):
    """
    Retrieves Open Access status and PDF links using the Unpaywall API.
    """
    if not doi: return "No DOI", ""
    url = f"https://api.unpaywall.org/v2/{quote_plus(doi)}"
    params = {"email": email}
    r = await safe_get_async(url, params=params)
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

async def process_openalex(query, limit):
    """
    Queries the OpenAlex API and processes results into a standard format.
    """
    print(f"   [Starting] OpenAlex search for '{query}'...")
    url = "https://api.openalex.org/works"
    params = {"search": query, "per_page": limit, "mailto": UNPAYWALL_EMAIL}
    
    r = await safe_get_async(url, params=params)
    if not r: return []
    
    results = []
    try:
        items = r.json().get("results", [])
        for item in items:
            doi_url = item.get('doi') or ""
            doi = doi_url.replace("https://doi.org/", "")
            
            authorships = item.get('authorships', [])
            authors_list = [a.get('author', {}).get('display_name') for a in authorships if a.get('author')]
            
            results.append({
                'query': query, 'source': 'OpenAlex',
                'title': item.get('display_name'),
                'authors': ", ".join(authors_list[:3]),
                'year': item.get('publication_year'),
                'venue': item.get('primary_location', {}).get('source', {}).get('display_name', 'Unknown'),
                'doi': doi, 'url': doi_url,
                'oa_status': item.get('open_access', {}).get('oa_status', 'closed'),
                'pdf_link': item.get('open_access', {}).get('oa_url', ''),
                'citations': item.get('cited_by_count', 0),
                'abstract': reconstruct_abstract(item.get('abstract_inverted_index'))
            })
    except Exception as e:
        print(f"   [!] OpenAlex processing error: {e}")
        
    return results

async def process_arxiv(query, limit):
    """
    Queries the ArXiv API and parses the XML response.
    """
    print(f"   [Starting] ArXiv search for '{query}'...")
    url = "https://export.arxiv.org/api/query"
    params = {"search_query": f"all:{query}", "start": 0, "max_results": limit}
    
    r = await safe_get_async(url, params=params)
    if not r or not r.content: return []
    
    results = []
    try:
        root = ET.fromstring(r.content)
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        
        for entry in root.findall('atom:entry', ns):
            title = entry.find('atom:title', ns).text.strip().replace('\n', ' ')
            published = entry.find('atom:published', ns).text[:4]
            
            links = entry.findall('atom:link', ns)
            pdf_link = next((l.get('href') for l in links if l.get('title') == 'pdf'), "")
            url = next((l.get('href') for l in links if l.get('rel') == 'alternate'), "")
            
            authors = [a.find('atom:name', ns).text for a in entry.findall('atom:author', ns)]
            
            results.append({
                'query': query, 'source': 'ArXiv',
                'title': title,
                'authors': ", ".join(authors[:3]),
                'year': int(published) if published.isdigit() else 0,
                'venue': 'ArXiv Preprint',
                'doi': '', 'url': url,
                'oa_status': 'gold',
                'pdf_link': pdf_link,
                'citations': 0,
                'abstract': entry.find('atom:summary', ns).text.strip().replace('\n', ' ')
            })
    except Exception as e:
        print(f"   [!] ArXiv parsing error: {e}")
        
    return results

async def process_crossref(query, limit):
    """
    Queries the CrossRef API and enriches results with Unpaywall data.
    """
    print(f"   [Starting] CrossRef search for '{query}'...")
    url = "https://api.crossref.org/works"
    params = {"query.title": query, "rows": limit}
    
    r = await safe_get_async(url, params=params)
    if not r: return []
    
    results = []
    try:
        items = r.json().get("message", {}).get("items", [])
        oa_data = await asyncio.gather(
            *(get_unpaywall_data(item.get('DOI'), UNPAYWALL_EMAIL) for item in items),
            return_exceptions=True
        )

        for item, oa_result in zip(items, oa_data):
            doi = item.get('DOI')
            if isinstance(oa_result, Exception):
                oa_status, pdf_link = "Error", ""
            else:
                oa_status, pdf_link = oa_result

            results.append({
                'query': query, 'source': 'CrossRef',
                'title': item.get('title', ['No Title'])[0],
                'authors': format_authors(item.get('author')),
                'year': item.get('issued', {}).get('date-parts', [[None]])[0][0],
                'venue': item.get('container-title', [''])[0],
                'doi': doi, 'url': item.get('URL'),
                'oa_status': oa_status, 'pdf_link': pdf_link,
                'citations': item.get('is-referenced-by-count', 0),
                'abstract': "Abstract not available via CrossRef."
            })
    except Exception as e:
        print(f"   [!] CrossRef processing error: {e}")
        
    return results

async def process_google(query, limit):
    """
    Queries Google Custom Search API to find relevant academic pages or PDFs.
    """
    if not GOOGLE_API_KEY or not CSE_ID:
        return []

    print(f"   [Starting] Google search for '{query}'...")
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": GOOGLE_API_KEY,
        "cx": CSE_ID,
        "q": query,
        "num": min(limit, 10) # API limit is 10
    }
    
    r = await safe_get_async(url, params=params)
    if not r: return []
    
    results = []
    try:
        items = r.json().get("items", [])
        for item in items:
            results.append({
                'query': query, 'source': 'Google',
                'title': item.get('title'),
                'authors': "N/A",
                'year': "N/A",
                'venue': "Web Search",
                'doi': "", 'url': item.get('link'),
                'oa_status': "unknown",
                'pdf_link': item.get('link') if item.get('link', '').endswith('.pdf') else "",
                'citations': 0,
                'abstract': item.get('snippet', '')
            })
    except Exception as e:
        print(f"   [!] Google Search processing error: {e}")
        
    return results

async def process_semanticscholar(query, limit):
    # Placeholder for future implementation
    return []
