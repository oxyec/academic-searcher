# Academic Research Assistant

# Demo link = https://academic-searcher.streamlit.app

Academic Research Assistant is a multi-interface paper discovery project:
- Streamlit web app (`app.py`)
- CLI workflow (`main.py`)
- FastAPI service (`api.py`)

The web app is optimized for interactive research with filtering, ranking, deduplication, diagnostics, and export workflows.

## Highlights

- Async multi-source search across Semantic Scholar, OpenAlex, ArXiv, Crossref, and optional Google Custom Search.
- Smart deduplication and relevance scoring with adjustable weights.
- Research workflow tools: saved setups, reading list, and exports (CSV, JSON, BibTeX, markdown brief).
- API and CLI options for automation or scripting.

## Tech Stack

- Python
- Streamlit
- FastAPI + Uvicorn
- Pandas + Altair
- Requests + asyncio

## Project Structure

```text
.
|-- app.py                  # Streamlit UI (main app)
|-- api.py                  # FastAPI service
|-- main.py                 # CLI entry point
|-- src/
|   |-- app_utils.py        # scoring, dedupe, dataframe prep, persistence helpers
|   |-- search_sources.py   # async source adapters for the Streamlit app
|   |-- core.py             # async orchestration used by CLI/API path
|   |-- search.py           # source processors used by CLI/API path
|   |-- export.py           # CSV export helpers
|   |-- config.py           # env-based config
|   `-- utils.py            # request and text utilities
|-- requirements.txt
`-- .streamlit/config.toml  # Streamlit theme/config
```

## Requirements

- Python 3.9+
- internet access for upstream APIs

## Quick Start

```bash
git clone <your-repo-url>
cd acedamic-searcher
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python -m streamlit run app.py
```

## Configuration

You can use the Streamlit app without API keys, but optional keys improve quality and limits.

Create a `.env` file in the project root if you want defaults for CLI/API:

```ini
UNPAYWALL_EMAIL=your_email@example.com
S2_API_KEY=
GOOGLE_API_KEY=
CSE_ID=
```

Configuration reference:

| Variable | Used by | Required | Purpose |
|---|---|---|---|
| `UNPAYWALL_EMAIL` | CLI/API path | Recommended | Contact email for Unpaywall/Crossref politeness |
| `S2_API_KEY` | CLI/API config | Optional | Semantic Scholar API key |
| `GOOGLE_API_KEY` | CLI/API + app (manual input allowed) | Optional | Google Custom Search API key |
| `CSE_ID` | CLI/API + app (manual input allowed) | Optional | Google Custom Search Engine ID |
| `ACADEMIC_SEARCH_PERSIST_STATE` | Streamlit app | Optional (default `false`) | Enable disk persistence for saved setups/bookmarks (`true` enables `.academic_search_state.json`) |

Notes:
- In Streamlit, API keys can also be entered in the sidebar and do not need `.env`.
- Crossref email is configurable directly in the UI.
- Streamlit deployments should keep `ACADEMIC_SEARCH_PERSIST_STATE=false` to avoid shared cross-user state.

## Run Modes

### Streamlit app (recommended)

```bash
python -m streamlit run app.py
```

### CLI

```bash
python main.py
```

### API

```bash
python api.py
```

Alternative API startup:

```bash
uvicorn api:app --host 0.0.0.0 --port 8000 --reload
```

Swagger docs: `http://localhost:8000/docs`

## API Usage Example

```bash
curl "http://localhost:8000/search?query=graph+neural+networks&limit=5"
```

## Outputs

- Streamlit app provides in-app downloads for:
  - results CSV
  - results JSON
  - BibTeX references
  - markdown research brief
  - reading list exports
- CLI writes timestamped CSV files:
  - `research_results_YYYYMMDD_HHMMSS.csv`
- App state is persisted to:
  - `.academic_search_state.json`

## Known Limits

- Google Custom Search returns max 10 results per request.
- External API rate limits and occasional upstream downtime can affect response time and coverage.
- Result quality depends on source metadata consistency.

## Troubleshooting

- If `streamlit` is not in PATH:
  - run `python -m streamlit run app.py`
- If imports fail:
  - activate your virtual environment
  - run `pip install -r requirements.txt`
- If searches are empty:
  - verify internet access
  - test with fewer sources first
  - provide optional API keys for stricter-rate-limit providers


## License

This project is licensed under the **GNU Affero General Public License v3.0 (AGPL-3.0)**. 
See the [LICENSE](LICENSE) file for the full text.

Copyright (c) 2026 oxyec
