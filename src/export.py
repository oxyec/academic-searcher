import csv
import os
from datetime import datetime
from .config import OUTPUT_CSV
from .utils import clean_text

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
