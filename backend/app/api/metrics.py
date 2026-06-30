"""Operational metrics endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Response

from app.core.dependencies import MetricsServiceDep

router = APIRouter(tags=["metrics"])


@router.get("/metrics", summary="Prometheus-style metrics")
async def metrics(metrics_service: MetricsServiceDep) -> Response:
    content = await metrics_service.render_prometheus()
    return Response(content=content, media_type="text/plain; version=0.0.4")
