"""Compatibility imports; source adapters are shared by web, CLI and API."""

from .source_adapters import (
    DEFAULT_SOURCES,
    SourceError,
    make_request,
    search_all_sources,
    search_arxiv,
    search_crossref,
    search_google,
    search_openalex,
    search_semantic_scholar,
)

__all__ = [
    "DEFAULT_SOURCES", "SourceError", "make_request", "search_all_sources",
    "search_arxiv", "search_crossref", "search_google", "search_openalex",
    "search_semantic_scholar",
]
