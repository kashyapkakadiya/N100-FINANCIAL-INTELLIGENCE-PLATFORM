"""
src/api/main.py — Module 11, Day 38: FastAPI application entry point.

Run with: uvicorn src.api.main:app --port 8000
Docs at: http://localhost:8000/docs
"""
from __future__ import annotations
import logging
import time
import sys
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.routers import health, companies, screener, sectors, peers, valuation, portfolio, documents

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
logger = logging.getLogger("api")

app = FastAPI(
    title="Nifty 100 Financial Intelligence Platform API",
    description="Read-only REST API over the Nifty 100 analytics database. Internal use only.",
    version="1.0.0",
)

# CORS - internal tool, allow all origins per spec
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Logs method, path, and response time for every request."""
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.info(f"{request.method} {request.url.path} - {response.status_code} - {elapsed_ms:.1f}ms")
    return response


app.include_router(health.router, prefix="/api/v1")
app.include_router(companies.router, prefix="/api/v1")
app.include_router(screener.router, prefix="/api/v1")
app.include_router(sectors.router, prefix="/api/v1")
app.include_router(peers.router, prefix="/api/v1")
app.include_router(valuation.router, prefix="/api/v1")
app.include_router(portfolio.router, prefix="/api/v1")
app.include_router(documents.router, prefix="/api/v1")


@app.get("/")
def root():
    """Redirect hint - API root, see /docs for full documentation."""
    return {"message": "Nifty 100 API - see /docs for endpoint documentation"}