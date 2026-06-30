"""Library and search API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.core.dependencies import LibraryServiceDep
from app.models.responses import LibraryResponse, SearchResponse

router = APIRouter(tags=["library"])


@router.get(
    "/library",
    response_model=LibraryResponse,
    summary="Browse the full media library",
)
async def get_library(library_service: LibraryServiceDep) -> LibraryResponse:
    """Return the complete media library organised by category."""
    return LibraryResponse(
        library=library_service.library,
        summary=library_service.summary,
    )


@router.get(
    "/search",
    response_model=SearchResponse,
    summary="Search media by title",
)
async def search_media(
    library_service: LibraryServiceDep,
    q: str = Query(
        ...,
        min_length=1,
        max_length=200,
        description="Search query string",
    ),
) -> SearchResponse:
    """Search the library for media matching the given query term."""
    results = library_service.search(q)
    return SearchResponse(
        query=q,
        results=results,
        total=len(results),
    )
