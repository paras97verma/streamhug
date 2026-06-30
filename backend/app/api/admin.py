"""Admin endpoints for media management.

Provides privileged operations such as deleting media files and their
associated caches. These endpoints are intentionally obscured via
non-obvious paths to prevent accidental use.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from app.core.dependencies import (
    CurrentAdminDep,
    EventServiceDep,
    HLSServiceDep,
    LibraryServiceDep,
    ScannerServiceDep,
    SettingsDep,
)

router = APIRouter(tags=["admin"])


@router.delete(
    "/d3l3t3/{media_id}",
    summary="Delete a media file and all its caches",
)
async def delete_media(
    media_id: str,
    current_admin: CurrentAdminDep,
    library_service: LibraryServiceDep,
    hls_service: HLSServiceDep,
    scanner_service: ScannerServiceDep,
    event_service: EventServiceDep,
    settings: SettingsDep,
) -> JSONResponse:
    """Permanently delete a media file and all associated cache entries.

    Performs these steps in order:
    1. Resolve the original file path from the library.
    2. Delete the original video file from ``media/originals``.
    3. Delete the HLS cache directory, ffprobe cache, metadata, poster, and banner.
    4. Trigger a library rescan.
    5. Broadcast a ``library_updated`` SSE event to all connected clients.

    Args:
        media_id: The unique identifier of the media item to delete.
    """
    _ = current_admin
    source_path = library_service.get_file_path_for_id(media_id)
    if source_path is None:
        raise HTTPException(status_code=404, detail="Media not found in library")

    deleted_files: list[str] = []
    errors: list[str] = []

    # 1. Delete the original media file
    if source_path.is_file():
        try:
            source_path.unlink()
            deleted_files.append(str(source_path))
        except OSError as exc:
            errors.append(f"Failed to delete source file: {exc}")
    else:
        errors.append(f"Source file not found on disk: {source_path}")

    # 2. Delete all associated caches via HLS service
    try:
        hls_service.delete_media_cache(media_id)
        deleted_files.append(f"cache/{media_id}/*")
    except Exception as exc:
        errors.append(f"Cache deletion error: {exc}")

    # 3. Rescan library
    try:
        await scanner_service.scan()
    except Exception as exc:
        errors.append(f"Rescan failed: {exc}")

    # 4. Notify connected clients
    try:
        await event_service.broadcast("library_updated")
    except Exception as exc:
        errors.append(f"SSE broadcast failed: {exc}")

    status = "partial" if errors else "success"
    return JSONResponse(
        status_code=200,
        content={
            "status": status,
            "media_id": media_id,
            "deleted": deleted_files,
            "errors": errors,
        },
    )
