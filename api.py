from fastapi import FastAPI, HTTPException, Query, Response
from typing import List, Optional
from pydantic import BaseModel
from src.core import search_with_diagnostics_async

app = FastAPI(title="Academic Research API", version="1.1")
MAX_LIMIT = 50

class SearchResult(BaseModel):
    query: str
    source: str
    title: str
    authors: str
    year: Optional[int] = None
    venue: Optional[str] = None
    doi: Optional[str] = None
    url: Optional[str] = None
    oa_status: Optional[str] = None
    pdf_link: Optional[str] = None
    citations: int = 0
    abstract: str = ""
    score: float = 0.0
    source_count: int = 1
    record_id: str = ""
    text_match: float = 0.0
    citation_signal: float = 0.0
    recency_signal: float = 0.0
    open_access_bonus: float = 0.0


class SourceDiagnostic(BaseModel):
    source: str
    result_count: int
    duration_sec: float
    status: str
    error: str = ""
    skipped_count: int = 0


class SearchReport(BaseModel):
    results: List[SearchResult]
    diagnostics: List[SourceDiagnostic]


async def run_search(query, limit, sources):
    safe_query = query.strip()
    if not safe_query:
        raise HTTPException(status_code=400, detail="Query parameter is required")
    if sources == []:
        raise HTTPException(status_code=400, detail="Select at least one source")
    try:
        results, diagnostics = await search_with_diagnostics_async(safe_query, limit, sources)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    if diagnostics and all(stat["status"] == "Error" for stat in diagnostics):
        raise HTTPException(status_code=503, detail={"message": "All selected sources failed", "diagnostics": diagnostics})
    return results, diagnostics

@app.get("/")
async def read_root():
    return {"message": "Welcome to the Academic Research API. Use /search?query=... to find papers."}

@app.get("/search", response_model=List[SearchResult])
async def search_papers(
    response: Response,
    query: str = Query(..., min_length=1, max_length=300),
    limit: int = Query(default=5, ge=1, le=MAX_LIMIT),
    sources: Optional[List[str]] = Query(default=None, max_length=10),
):
    """
    Search for academic papers across multiple sources.
    """
    results, diagnostics = await run_search(query, limit, sources)
    response.headers["X-Search-Degraded"] = str(any(stat["status"] != "OK" for stat in diagnostics)).lower()
    response.headers["X-Search-Failed-Sources"] = str(sum(stat["status"] == "Error" for stat in diagnostics))
    return results


@app.get("/search/report", response_model=SearchReport)
async def search_report(
    query: str = Query(..., min_length=1, max_length=300),
    limit: int = Query(default=5, ge=1, le=MAX_LIMIT),
    sources: Optional[List[str]] = Query(default=None, max_length=10),
):
    results, diagnostics = await run_search(query, limit, sources)
    return {"results": results, "diagnostics": diagnostics}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
