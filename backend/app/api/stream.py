"""HLS streaming API endpoints.

Serves the HLS master playlist and individual quality variant playlists /
segments.  The master playlist request triggers lazy transcoding if the
HLS cache does not yet exist for the requested media.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, Response

from app.api._streaming import playlist_response, segment_response
from app.core.dependencies import HLSServiceDep, LibraryServiceDep
from app.services.hls import QUALITY_PRESETS

router = APIRouter(tags=["streaming"])


@router.get(
    "/stream/{media_id}/master.m3u8",
    summary="HLS master playlist",
)
async def get_master_playlist(
    request: Request,
    media_id: str,
    library_service: LibraryServiceDep,
    hls_service: HLSServiceDep,
) -> Response:
    """Return the HLS master playlist for a media item.

    If the HLS cache does not exist, this triggers lazy transcoding
    (which may take significant time for the first request).
    """
    source_path = library_service.get_file_path_for_id(media_id)
    if source_path is None:
        raise HTTPException(status_code=404, detail="Media not found")

    master_path = await hls_service.get_master_playlist(media_id, source_path)
    if master_path is None or not master_path.is_file():
        raise HTTPException(
            status_code=503,
            detail="HLS generation failed — check server logs",
        )

    content = master_path.read_text(encoding="utf-8")
    return playlist_response(request, content, max_age=5)


@router.get(
    "/stream/{media_id}/{quality}/{segment}",
    summary="HLS segment or variant playlist",
)
async def get_segment(
    request: Request,
    media_id: str,
    quality: str,
    segment: str,
    library_service: LibraryServiceDep,
    hls_service: HLSServiceDep,
) -> FileResponse:
    """Serve an individual HLS segment (``.ts``) or variant playlist.

    Args:
        media_id: The media identifier.
        quality: Quality tier name (``1080p``, ``720p``, ``480p``, ``360p``).
        segment: Filename — either ``playlist.m3u8`` or ``segment_NNN.ts``.
    """
    if quality not in QUALITY_PRESETS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid quality '{quality}'. Valid: {', '.join(QUALITY_PRESETS)}",
        )

    source_path = library_service.get_file_path_for_id(media_id)
    if source_path is None:
        raise HTTPException(status_code=404, detail="Media not found")

    file_path = await hls_service.get_segment_path(media_id, quality, segment, source_path)
    if file_path is None:
        raise HTTPException(status_code=404, detail="Segment not found")

    if segment.endswith(".m3u8"):
        return playlist_response(request, file_path.read_text(encoding="utf-8"), max_age=5)
    if segment.endswith(".m4s"):
        media_type = "video/iso.segment"
    elif segment.endswith(".mp4"):
        media_type = "video/mp4"
    elif segment.endswith(".ts"):
        media_type = "video/mp2t"
    else:
        media_type = "application/octet-stream"
    return segment_response(file_path, media_type)
