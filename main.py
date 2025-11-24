import requests
import time
import csv
import os
from datetime import datetime
from urllib.parse import quote_plus

# Load .env if available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# --- SETTINGS ---

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
CSE_ID = os.getenv("CSE_ID")
S2_API_KEY = os.getenv("S2_API_KEY") 

DEFAULT_EMAIL = "academic-bot-user@example.com" 
UNPAYWALL_EMAIL = os.getenv("UNPAYWALL_EMAIL") or DEFAULT_EMAIL

SLEEP_BETWEEN_REQUESTS = 1.5 

# Using a standard timestamp for the filename
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
OUTPUT_CSV = f"research_results_{TIMESTAMP}.csv"

# --- HELPER: DATA CLEANING ---
def clean_text(text):
    """
    Removes newlines, tabs, and extra spaces to ensure CSV stays clean.
    """
    if not text:
        return ""
    if isinstance(text, list):
        text = " ".join([str(x) for x in text])
    # Replace newlines with spaces, remove tabs
    text = str(text).replace('\n', ' ').replace('\r', '').replace('\t', ' ')
    # Remove double spaces
    return " ".join(text.split())

def safe_get(url, params=None, headers=None, timeout=20):
    if headers is None: headers = {}
    if 'User-Agent' not in headers:
        headers['User-Agent'] = f"AcademicSearchBot/1.0 (mailto:{UNPAYWALL_EMAIL})"

    try:
        r = requests.get(url, params=params, headers=headers, timeout=timeout)
        
        if r.status_code == 403 and "semanticscholar" in url:
            print("   [!] Semantic Scholar Error: API Key required or Invalid.")
            return None
        elif r.status_code == 429:
            print(f"   [!] Too many requests. Cooling down... {url}")
            time.sleep(5)
            return None

        if r.status_code != 200:
            return None
        return r
    except Exception:
        return None

# --- SEARCH FUNCTIONS ---

def search_crossref(query, rows):
    url = "https://api.crossref.org/works"
    params = {"query.title": query, "rows": rows}
    r = safe_get(url, params=params)
    if not r: return []
    return r.json().get("message", {}).get("items", [])

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

def search_google(query, key, cse, num):
    if not key or not cse: return []
    url = "https://www.googleapis.com/customsearch/v1"
    real_num = min(num, 10) 
    params = {"q": query, "key": key, "cx": cse, "num": real_num}
    r = safe_get(url, params=params)
    if not r: return []
    return r.json().get("items", [])

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

def format_authors(authors_data):
    if not authors_data: return ""
    formatted = []
    for a in authors_data:
        if isinstance(a, dict):
            name = a.get('name') 
            if not name:
                name = f"{a.get('given','')} {a.get('family','')}"
            formatted.append(name.strip())
        elif isinstance(a, str):
            formatted.append(a)
    return "; ".join(formatted[:3])

# --- CSV IMPROVED SAVING ---

def save_to_csv(data_row):
    file_exists = os.path.isfile(OUTPUT_CSV)
    
    # 1. More descriptive Column Headers
    fieldnames = [
        'Search Query', 
        'Source', 
        'Title', 
        'Authors', 
        'Year', 
        'Venue/Journal',  # New Column
        'DOI', 
        'Open Access Status', 
        'PDF Link', 
        'URL', 
        'Date Accessed'   # New Column
    ]
    
    # Map the internal keys to the nice CSV headers
    row_mapping = {
        'Search Query': clean_text(data_row.get('query')),
        'Source': data_row.get('source'),
        'Title': clean_text(data_row.get('title')),
        'Authors': clean_text(data_row.get('authors')),
        'Year': data_row.get('year'),
        'Venue/Journal': clean_text(data_row.get('venue')),
        'DOI': data_row.get('doi'),
        'Open Access Status': data_row.get('oa_status'),
        'PDF Link': data_row.get('pdf_link'),
        'URL': data_row.get('url'),
        'Date Accessed': datetime.now().strftime("%Y-%m-%d %H:%M")
    }

    # 2. Open with 'utf-8-sig' for Excel support and QUOTE_ALL for safety
    with open(OUTPUT_CSV, "a", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        if not file_exists: 
            writer.writeheader()
        writer.writerow(row_mapping)

# --- MAIN ---

def main():
    print("\n" + "="*60)
    print("   ACADEMIC RESEARCH ASSISTANT - Article Finder")
    print("   contact: oxyec in github.com ")
    print("="*60 + "\n")

    while True:
        try:
            user_input = input("How many articles per source? (Default 5): ").strip()
            if not user_input:
                results_limit = 5
            else:
                results_limit = int(user_input)
                if results_limit < 1: results_limit = 1
            break
        except ValueError:
            print("Please enter a valid number.")

    print(f"\n   -> Saving to: {OUTPUT_CSV}\n")
    print("Type 'q' to exit.\n")

    while True:
        query = input("Research Topic/Keyword: ").strip()
        if query.lower() in ['q', 'exit', 'quit']:
            print("Goodbye!")
            break
        if not query: continue

        print(f"\n🔎 Searching for '{query}'...")

        # --- 1. CrossRef ---
        print(f"   [1/3] CrossRef...")
        cr_results = search_crossref(query, results_limit)
        for item in cr_results:
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
            save_to_csv(row)
        
        time.sleep(SLEEP_BETWEEN_REQUESTS)

        # --- 2. Semantic Scholar ---
        print(f"   [2/3] Semantic Scholar...")
        ss_results = search_semanticscholar(query, results_limit)
        for item in ss_results:
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
            save_to_csv(row)

        # --- 3. Google ---
        if GOOGLE_API_KEY and CSE_ID:
            time.sleep(SLEEP_BETWEEN_REQUESTS)
            print(f"   [3/3] Google...")
            gs_results = search_google(query, GOOGLE_API_KEY, CSE_ID, results_limit)
            for item in gs_results:
                row = {
                    'query': query, 'source': 'Google',
                    'title': item.get('title'), 'authors': 'Web Result',
                    'year': '', 'venue': 'Web',
                    'doi': '', 'url': item.get('link'),
                    'oa_status': 'N/A', 'pdf_link': ''
                }
                save_to_csv(row)
        
        print(f"\n✅ Data appended to: {OUTPUT_CSV}\n")

if __name__ == "__main__":
    main()