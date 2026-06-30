"""Helpers for streaming responses."""

from __future__ import annotations

import gzip
from pathlib import Path

from fastapi import Request
from fastapi.responses import FileResponse, Response

try:
    import brotli
except Exception:  # pragma: no cover - optional dependency
    brotli = None  # type: ignore[assignment]


def playlist_response(
    request: Request,
    content: str,
    *,
    max_age: int = 5,
    immutable: bool = False,
) -> Response:
    headers = {
        "Cache-Control": f"public, max-age={max_age}" + (", immutable" if immutable else ""),
        "Access-Control-Allow-Origin": "*",
        "X-Accel-Buffering": "no",
        "Vary": "Accept-Encoding",
        "Content-Type": "application/vnd.apple.mpegurl",
    }
    accept_encoding = request.headers.get("accept-encoding", "").lower()
    raw = content.encode("utf-8")
    if "br" in accept_encoding and brotli is not None and len(raw) >= 512:
        headers["Content-Encoding"] = "br"
        return Response(content=brotli.compress(raw), media_type="application/vnd.apple.mpegurl", headers=headers)
    if "gzip" in accept_encoding and len(raw) >= 512:
        headers["Content-Encoding"] = "gzip"
        return Response(content=gzip.compress(raw), media_type="application/vnd.apple.mpegurl", headers=headers)
    return Response(content=raw, media_type="application/vnd.apple.mpegurl", headers=headers)


def segment_response(path: Path, media_type: str, *, max_age: int = 31_536_000) -> FileResponse:
    return FileResponse(
        path=path,
        media_type=media_type,
        headers={
            "Cache-Control": f"public, max-age={max_age}, immutable",
            "Access-Control-Allow-Origin": "*",
            "X-Accel-Buffering": "no",
            "Accept-Ranges": "bytes",
        },
    )
