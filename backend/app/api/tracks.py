"""Audio track and subtitle track API endpoints.

Exposes per-track HLS playlists for alternate audio tracks and
on-the-fly WebVTT subtitle extraction for embedded subtitle streams.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, Response

from app.api._streaming import playlist_response, segment_response
from app.core.dependencies import HLSServiceDep, LibraryServiceDep

router = APIRouter(tags=["tracks"])


@router.get(
    "/stream/{media_id}/audio_{track_index}/playlist.m3u8",
    summary="Audio track HLS playlist",
)
async def get_audio_track_playlist(
    request: Request,
    media_id: str,
    track_index: int,
    library_service: LibraryServiceDep,
    hls_service: HLSServiceDep,
) -> Response:
    """Return an HLS playlist for a specific embedded audio track.

    Triggers on-demand extraction of the audio track to a standalone HLS stream.
    The result is cached on disk for subsequent requests.
    """
    source_path = library_service.get_file_path_for_id(media_id)
    if source_path is None:
        raise HTTPException(status_code=404, detail="Media not found")

    playlist_path = await hls_service.get_audio_track_playlist(
        media_id, source_path, track_index
    )
    if playlist_path is None or not playlist_path.is_file():
        raise HTTPException(
            status_code=503,
            detail=f"Audio track {track_index} extraction failed",
        )

    content = playlist_path.read_text(encoding="utf-8")
    return playlist_response(request, content, max_age=5)


@router.get(
    "/stream/{media_id}/audio_{track_index}/{segment}",
    summary="Audio track HLS segment",
)
async def get_audio_segment(
    media_id: str,
    track_index: int,
    segment: str,
    library_service: LibraryServiceDep,
    hls_service: HLSServiceDep,
) -> FileResponse:
    """Serve an individual .ts segment for an audio track HLS stream."""
    source_path = library_service.get_file_path_for_id(media_id)
    file_path = await hls_service.get_audio_segment_path(media_id, track_index, segment, source_path)
    if file_path is None:
        raise HTTPException(status_code=404, detail="Audio segment not found")

    media_type = "video/iso.segment" if segment.endswith(".m4s") else "video/mp2t"
    return segment_response(file_path, media_type)


@router.get(
    "/stream/{media_id}/subtitle/{track_index}.vtt",
    summary="Subtitle track as WebVTT",
)
async def get_subtitle_vtt(
    media_id: str,
    track_index: int,
    library_service: LibraryServiceDep,
    hls_service: HLSServiceDep,
) -> Response:
    """Extract and serve a subtitle stream as a WebVTT file.

    Supports embedded SRT, ASS/SSA, and mov_text subtitle formats.
    The VTT file is cached on disk after first extraction.
    """
    source_path = library_service.get_file_path_for_id(media_id)
    if source_path is None:
        raise HTTPException(status_code=404, detail="Media not found")

    vtt_path = await hls_service.get_subtitle_vtt(media_id, source_path, track_index)
    if vtt_path is None or not vtt_path.is_file():
        raise HTTPException(
            status_code=503,
            detail=f"Subtitle track {track_index} extraction failed",
        )

    content = vtt_path.read_bytes()
    return Response(
        content=content,
        media_type="text/vtt",
        headers={
            "Cache-Control": "public, max-age=86400",
            "Access-Control-Allow-Origin": "*",
            "Content-Disposition": f'inline; filename="subtitle_{track_index}.vtt"',
        },
    )
