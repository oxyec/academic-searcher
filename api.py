from fastapi import FastAPI, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel
from src.core import search_all_sources_async

app = FastAPI(title="Academic Research API", version="1.0")
MAX_LIMIT = 50

class SearchResult(BaseModel):
    query: str
    source: str
    title: str
    authors: str
    year: Optional[str] = None
    venue: Optional[str] = None
    doi: Optional[str] = None
    url: Optional[str] = None
    oa_status: Optional[str] = None
    pdf_link: Optional[str] = None

@app.get("/")
async def read_root():
    return {"message": "Welcome to the Academic Research API. Use /search?query=... to find papers."}

@app.get("/search", response_model=List[SearchResult])
async def search_papers(
    query: str = Query(..., min_length=1, max_length=300),
    limit: int = Query(default=5, ge=1, le=MAX_LIMIT),
):
    """
    Search for academic papers across multiple sources.
    """
    safe_query = query.strip()
    if not safe_query:
        raise HTTPException(status_code=400, detail="Query parameter is required")

    print(f"API Request received (query_len={len(safe_query)}, limit={limit})")
    results = await search_all_sources_async(safe_query, limit)
    return results

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
