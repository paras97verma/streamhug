"""Media detail and artwork API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.core.dependencies import LibraryServiceDep, SettingsDep
from app.models.responses import MediaDetailResponse
from app.utils import paths as path_utils

router = APIRouter(tags=["media"])


@router.get(
    "/movie/{media_id}",
    response_model=MediaDetailResponse,
    summary="Get media detail by ID",
)
async def get_media_detail(
    media_id: str, library_service: LibraryServiceDep
) -> MediaDetailResponse:
    """Return full details for a single media item or individual episode.

    Works for all media types despite the ``/movie/`` path prefix.
    """
    media = library_service.get_by_id(media_id)
    if media is not None:
        return MediaDetailResponse(media=media)

    # Check if it's an episode ID
    episode = library_service.get_episode_by_id(media_id)
    if episode is not None:
        return MediaDetailResponse(technical_info=episode.technical_info)

    raise HTTPException(status_code=404, detail="Media not found")


@router.get(
    "/poster/{media_id}",
    summary="Get poster image",
    response_class=FileResponse,
)
async def get_poster(media_id: str, settings: SettingsDep) -> FileResponse:
    """Serve the poster image for a media item."""
    poster = path_utils.poster_path(settings, media_id)
    if not poster.is_file():
        raise HTTPException(status_code=404, detail="Poster not found")
    return FileResponse(
        path=poster,
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.get(
    "/banner/{media_id}",
    summary="Get banner image",
    response_class=FileResponse,
)
async def get_banner(media_id: str, settings: SettingsDep) -> FileResponse:
    """Serve the banner image for a media item."""
    banner = path_utils.banner_path(settings, media_id)
    if not banner.is_file():
        raise HTTPException(status_code=404, detail="Banner not found")
    return FileResponse(
        path=banner,
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=86400"},
    )
