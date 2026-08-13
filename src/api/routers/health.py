"""
src/api/routers/health.py — GET /api/v1/health
"""
from __future__ import annotations
import time
from fastapi import APIRouter

from api.db import get_db_row_counts

router = APIRouter(tags=["health"])

_START_TIME = time.time()
_VERSION = "1.0.0"


@router.get("/health")
def health_check():
    """Server health check: status, per-table row counts, uptime, version."""
    return {
        "status": "ok",
        "db_row_counts": get_db_row_counts(),
        "uptime_seconds": round(time.time() - _START_TIME, 1),
        "version": _VERSION,
    }