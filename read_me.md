📚 Academic Research Assistant
A Python-based command-line tool that automates the process of searching for academic papers. It queries multiple databases simultaneously, checks for free (Open Access) PDFs, and exports the results into a clean, Excel-ready CSV file.
🚀 Features
Multi-Source Search: Queries CrossRef, Semantic Scholar, and Google Custom Search (optional).
PDF Discovery: Automatically checks Unpaywall and Semantic Scholar for direct links to free PDFs.
Excel-Ready Export: Saves data to a CSV file with proper encoding (UTF-8-SIG) and formatting.
Data Cleaning: Automatically cleans formatting issues in titles and author names.
Customizable: User defines how many results to fetch per source.
📋 Prerequisites
Python 3.8 or higher
Internet connection
🛠️ Installation
Clone or Download this repository.
Install dependencies using pip:
# pip install requirements.txt
⚙️ Configuration (API Keys)
This tool uses a .env file to manage API keys securely.
Create a file named .env in the same folder as your script.
Copy the following format into the file:
# .env file

# --- Required for Politeness ---
# Use your real email so APIs can contact you in case of issues
UNPAYWALL_EMAIL=your_email@example.com

# --- Optional: Semantic Scholar (Recommended) ---
# Get a free key here: https://www.semanticscholar.org/product/api
S2_API_KEY=your_semantic_scholar_key

# --- Optional: Google Search ---
# 1. Get API Key: https://developers.google.com/custom-search/v1/overview
# 2. Get CSE ID (Search Engine ID): https://programmablesearchengine.google.com/
GOOGLE_API_KEY=your_google_api_key
CSE_ID=your_cse_id
Note on API Keys:
CrossRef: No key required.
Semantic Scholar: Works without a key (lower rate limits) but works best with a key.
Google: Requires both a Key and an Engine ID. If left empty, the script will simply skip the Google search step.

💻 Usage
Run the script from your terminal:
code
Bash
python main.py
Interaction Flow:
The script will ask: "How many articles per source?" (Enter a number, e.g., 5).
It will ask for a "Research Topic/Keyword" (e.g., Machine Learning in Medicine).
The script searches all sources, processes the data, and saves it.
Type q to exit the program.
📂 Output Format
The results are saved to a file named research_results_YYYYMMDD_HHMMSS.csv.
You can open this directly in Microsoft Excel, Google Sheets, or LibreOffice.
Columns Included:
Search Query: The keyword used.
Source: Where the result came from (CrossRef, Semantic Scholar, etc.).
Title: Title of the paper.
Authors: First 3 authors.
Year: Publication year.
Venue/Journal: Journal name (if available).
DOI: Digital Object Identifier.
Open Access Status: gold, green, hybrid, or closed.
PDF Link: Direct link to the PDF if found.
Date Accessed: Timestamp of when the search was performed.
⚠️ Limitations & Rate Limits
CrossRef: Generally allows many requests, but the script pauses (1.5s) between searches to be polite.
Semantic Scholar: Without an API key, you may hit rate limits quickly. If this happens, wait a few minutes or get a free key.
Google: The free Custom Search JSON API provides 100 free search queries per day.
🤝 Contributing
Feel free to fork this project and submit pull requests if you want to add more sources (like arXiv or PubMed).
📄 License
This project is open-source. Feel free to modify and use it for your research needs.
This project is licensed under the MIT License 