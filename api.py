from fastapi import FastAPI, HTTPException
from typing import List, Optional
from pydantic import BaseModel
from src.core import search_all_sources

app = FastAPI(title="Academic Research API", version="1.0")

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
def read_root():
    return {"message": "Welcome to the Academic Research API. Use /search?query=... to find papers."}

@app.get("/search", response_model=List[SearchResult])
def search_papers(query: str, limit: int = 5):
    """
    Search for academic papers across multiple sources.
    """
    if not query:
        raise HTTPException(status_code=400, detail="Query parameter is required")

    print(f"API Request: Search '{query}' with limit {limit}")
    results = search_all_sources(query, limit)
    return results

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
