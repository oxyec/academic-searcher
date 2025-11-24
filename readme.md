# 📚 Academic Research Assistant

A Python-based command-line tool that automates the process of searching for academic papers. It queries multiple databases simultaneously, checks for free (Open Access) PDFs via Unpaywall, and exports the results into a clean, Excel-ready CSV file.

## 🚀 Features

*   **Multi-Source Search:** Queries **CrossRef**, **Semantic Scholar**, and **Google Custom Search** (optional).
*   **PDF Discovery:** Automatically checks **Unpaywall** and Semantic Scholar for direct links to free PDFs.
*   **Excel-Ready Export:** Saves data to a CSV file with proper encoding (`UTF-8-SIG`) so it opens correctly in Excel.
*   **Data Cleaning:** Automatically cleans formatting issues in titles and author names.
*   **Privacy Focused:** Uses environment variables to protect your API keys and contact info.

## 📋 Prerequisites

*   Python 3.8 or higher
*   Internet connection

## 🛠️ Installation

1.  **Clone this repository** (or download the files):
    ```bash
    git clone https://github.com/oxyec/academic-searcher.git
    cd academic-searcher
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## ⚙️ Configuration (API Keys)

This tool uses a `.env` file to manage API keys securely so they are not hardcoded in the script.

1.  Create a file named `.env` in the same folder as `main.py`.
2.  Copy and paste the following configuration into it:

```ini
# .env file configuration

# --- REQUIRED: Email for Politeness ---
# APIs like Unpaywall require an email to identify the bot.
# This stays local on your machine.
UNPAYWALL_EMAIL=your_email@example.com

# --- OPTIONAL: Semantic Scholar (Recommended) ---
# Works without a key, but works faster/better with one.
# Get free key: https://www.semanticscholar.org/product/api
S2_API_KEY=

# --- OPTIONAL: Google Search ---
# If left empty, the script simply skips the Google Search step.
# 1. API Key: https://developers.google.com/custom-search/v1/overview
# 2. CSE ID: https://programmablesearchengine.google.com/
GOOGLE_API_KEY=
CSE_ID=
```

### Interaction Flow:
1.  **Settings:** The script asks: *"How many articles per source?"* (Default is 5).
2.  **Search:** Enter a keyword or title (e.g., `Machine Learning in Healthcare`).
3.  **Processing:** The script queries all connected databases and checks for PDF links.
4.  **Save:** Results are appended to a CSV file.
5.  **Exit:** Type `q` to quit the program.

## 📂 Output Format

The results are saved to a file named `research_results_YYYYMMDD_HHMMSS.csv`.
This file opens directly in **Microsoft Excel**, **Google Sheets**, or **LibreOffice**.

**Columns Included:**
*   **Source:** (CrossRef, Semantic Scholar, Google)
*   **Title & Authors**
*   **Year & Venue**
*   **DOI:** Digital Object Identifier
*   **Open Access Status:** `gold`, `green`, `hybrid`, or `closed`
*   **PDF Link:** Direct clickable link to the PDF (if found)
*   **Date Accessed:** Timestamp of the search

## ⚠️ API Limits

*   **CrossRef:** Free. The script includes a politeness delay (`1.5s`) to prevent errors.
*   **Semantic Scholar:** Free. Rate limits are stricter without an API key.
*   **Google:** The free Custom Search API allows 100 queries per day.

## 🤝 Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

Copyright (c) 2025 **oxyec**
