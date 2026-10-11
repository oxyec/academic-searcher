# Academic Research Assistant

# Demo link = https://academic-searcher.streamlit.app

Academic Research Assistant is a multi-interface paper discovery project:
- Streamlit web app (`app.py`)
- CLI workflow (`main.py`)
- FastAPI service (`api.py`)

The project helps researchers discover papers and build an initial reading list. All three interfaces use the same source adapters, metadata normalization, deduplication, and ranking workflow. Search snapshots summarize retrieved metadata; they do not synthesize findings or provide exhaustive literature reviews.

## Highlights

- Async multi-source search across Semantic Scholar, OpenAlex, ArXiv, Crossref, and optional Google Custom Search.
- Smart deduplication and relevance scoring with adjustable weights.
- Research workflow tools: saved setups, reading list, and exports (CSV, JSON, BibTeX, markdown search snapshot).
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
|   |-- source_adapters.py  # shared async adapters and source diagnostics
|   |-- search_sources.py   # compatibility imports
|   |-- core.py             # ranked search and API/CLI serialization
|   |-- search.py           # legacy compatibility entry points
|   |-- export.py           # CSV export helpers
|   |-- config.py           # env-based config
|   `-- utils.py            # request and text utilities
|-- requirements.txt
`-- .streamlit/config.toml  # Streamlit theme/config
```

## Requirements

- Python 3.11+ (the pinned NumPy version requires 3.11 or newer)
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
OPENALEX_API_KEY=
GOOGLE_API_KEY=
CSE_ID=
```

Configuration reference:

| Variable | Used by | Required | Purpose |
|---|---|---|---|
| `UNPAYWALL_EMAIL` | All interfaces | Recommended | Contact email for Crossref; also used by the standalone Unpaywall helper |
| `S2_API_KEY` | All interfaces | Optional | Semantic Scholar API key |
| `OPENALEX_API_KEY` | All interfaces | Optional | OpenAlex API key for a higher usage budget |
| `GOOGLE_API_KEY` | CLI/API + app (manual input allowed) | Optional | Google Custom Search API key |
| `CSE_ID` | CLI/API + app (manual input allowed) | Optional | Google Custom Search Engine ID |
| `ACADEMIC_SEARCH_PERSIST_STATE` | Streamlit app | Optional (default `false`) | Enable disk persistence for saved setups/bookmarks (`true` enables `.academic_search_state.json`) |

Notes:
- In Streamlit, API keys can also be entered in the sidebar and do not need `.env`.
- Crossref email is configurable directly in the UI.
- Default sources are Semantic Scholar, OpenAlex, ArXiv, and Crossref. Google is opt-in.
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

`limit` is the number requested per source (1–50 for API, 1–100 for CLI, 5–100 in the UI), not the final total. Results are deduplicated and sorted by the default relevance score. `year` is an integer or `null`; responses include abstracts, citations, source counts, record IDs, and score components.

Choose sources with repeated parameters, e.g. `sources=openalex&sources=arxiv`. `/search` keeps its list response and adds `X-Search-Degraded` and `X-Search-Failed-Sources` headers. `/search/report` returns `{results, diagnostics}`. An empty successful search returns an empty list; complete upstream failure returns HTTP 503 with diagnostics. Partial failures keep available results.

## Outputs

- Streamlit app provides in-app downloads for:
  - results CSV
  - results JSON
  - BibTeX references
  - markdown search snapshot
  - reading list exports
- CLI writes timestamped CSV files:
  - `research_results_YYYYMMDD_HHMMSS.csv`
  - includes abstracts, citations, relevance score, and source counts
- App state stays in the current session by default. Optional local disk persistence uses `.academic_search_state.json`. Browser reloads reset session-only reading lists; download them before leaving.

## Known Limits

- Google Custom Search returns max 10 results per request.
- External API rate limits and occasional upstream downtime can affect response time and coverage.
- Result quality depends on source metadata consistency.
- Filters apply to the retrieved sample; there is no pagination or exhaustive coverage guarantee yet.
- Ranking uses whole-word matching, citations, recency, and an open-access bonus. It is a heuristic, not a scientific quality rating or semantic search.
- Source counts measure indexing in this search sample, not independent scientific agreement.
- Title-based merges require compatible authors and years. Conflicting DOIs remain separate; uncertain preprint/article relationships may remain separate.
- Crossref open-access status remains unknown without another source's evidence. Automatic Unpaywall enrichment is no longer part of the shared search; its helper remains available for explicit use.
- [Google Custom Search JSON API](https://developers.google.com/custom-search/v1/overview) is closed to new customers and ends January 1, 2027. It remains a legacy opt-in adapter; a replacement has not been selected.
- [OpenAlex authentication](https://help.openalex.org/api/authentication/) supports basic keyless use; configure a key for a larger usage budget.

## Validation

```bash
python -m unittest discover -s tests -v
```

The regression suite uses fake source responses and Streamlit's app testing API. It does not call upstream services. It covers nullable metadata, retries, partial/complete failures, shared ranking and serialization, deduplication conflicts, BibTeX, and the saved-setup/single-source UI flows.

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

MIT
