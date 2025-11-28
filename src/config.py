import os
from datetime import datetime

# Load .env if available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# --- API KEYS ---
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
CSE_ID = os.getenv("CSE_ID")
S2_API_KEY = os.getenv("S2_API_KEY")

# --- EMAIL SETTINGS ---
DEFAULT_EMAIL = "academic-bot-user@example.com"
UNPAYWALL_EMAIL = os.getenv("UNPAYWALL_EMAIL") or DEFAULT_EMAIL

# --- APP SETTINGS ---
SLEEP_BETWEEN_REQUESTS = 1.5

# Using a standard timestamp for the filename
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
OUTPUT_CSV = f"research_results_{TIMESTAMP}.csv"
