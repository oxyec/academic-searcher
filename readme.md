# 📚 Academic Research Assistant

A Python-based tool that automates the process of searching for academic papers. It queries multiple databases simultaneously, checks for free (Open Access) PDFs via Unpaywall, and exports the results.

Now featuring a **CLI**, a **Web App**, and a **REST API**!

## 🚀 Features

*   **Multi-Source Search:** Queries **CrossRef**, **Semantic Scholar**, and **Google Custom Search** (optional).
*   **PDF Discovery:** Automatically checks **Unpaywall** and Semantic Scholar for direct links to free PDFs.
*   **Excel-Ready Export:** Saves data to a CSV file with proper encoding (`UTF-8-SIG`).
*   **Three Interfaces:**
    *   **CLI:** Interactive command-line tool.
    *   **Web App:** Modern browser-based interface powered by Streamlit.
    *   **API:** REST API powered by FastAPI.

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

Create a `.env` file in the project root:

```ini
# .env configuration
UNPAYWALL_EMAIL=your_email@example.com
# Optional
S2_API_KEY=
GOOGLE_API_KEY=
CSE_ID=
```

## 🏃‍♂️ How to Run

### 1. Web App (Recommended)
The easiest way to use the tool. Opens in your browser.
```bash
# Option A (Standard Streamlit way)
streamlit run app.py

# Option B (Direct Python execution)
# Use this if 'streamlit' command is not found
python app.py
```

### 2. Command Line Interface (CLI)
Classic interactive terminal mode.
```bash
python main.py
```

### 3. REST API
Start the API server (available at `http://localhost:8000`).
```bash
python api.py
```
*   **Swagger Docs:** Visit `http://localhost:8000/docs` to test endpoints.
*   **Example Query:** `http://localhost:8000/search?query=machine+learning&limit=5`

## ❓ Troubleshooting

**Error: `'streamlit' is not recognized as the name of a cmdlet...`**
*   This means the `streamlit` executable is not in your system's PATH.
*   **Solution 1:** Use `python app.py` instead. This version of the app includes a helper to launch itself correctly.
*   **Solution 2:** Use `python -m streamlit run app.py`.
*   **Solution 3:** Ensure you have installed dependencies (`pip install -r requirements.txt`).

## 📂 Output Format

Results from the CLI and Web App are saved as `research_results_YYYYMMDD_HHMMSS.csv`.

**Columns Included:**
*   **Source:** (CrossRef, Semantic Scholar, Google)
*   **Title & Authors**
*   **Year & Venue**
*   **DOI:** Digital Object Identifier
*   **Open Access Status:** `gold`, `green`, `hybrid`, or `closed`
*   **PDF Link:** Direct clickable link to the PDF
*   **Date Accessed:** Timestamp

## ⚠️ API Limits

*   **CrossRef:** Free (politeness delay included).
*   **Semantic Scholar:** Free (stricter limits without key).
*   **Google:** Free Custom Search API allows 100 queries/day.

## 🤝 Contributing

Pull requests are welcome.

## 📄 License

MIT License. Copyright (c) 2025 **oxyec**.
