"""Dubai residential valuation and market-intelligence API."""

from __future__ import annotations

import logging
import time
from collections import defaultdict, deque

import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.routes.market import router as market_router
from api.routes.valuation import router as valuation_router
from api.state import get_runtime

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("dubai.api")

app = FastAPI(
    title="Dubai Real Estate Intelligence API",
    version="1.0.0",
    description=(
        "Statistical residential valuation and community analytics. "
        "Outputs are not appraisals, offers, or investment recommendations."
    ),
)
app.include_router(valuation_router, prefix="/api")
app.include_router(market_router, prefix="/api")
_origins = [origin.strip() for origin in os.environ.get("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

_HITS: dict[str, deque] = defaultdict(deque)
_LIMIT = 60


@app.on_event("startup")
def startup():
    app.state.runtime = get_runtime()
    if not app.state.runtime.ready:
        logger.warning("Runtime not ready: %s", app.state.runtime.error)


@app.middleware("http")
async def rate_limit(request: Request, call_next):
    now = time.time()
    ip = request.client.host if request.client else "unknown"
    bucket = _HITS[ip]
    while bucket and now - bucket[0] > 60:
        bucket.popleft()
    if len(bucket) >= _LIMIT:
        return JSONResponse(status_code=429, content={"error": {"code": "rate_limited", "message": "60 requests per minute exceeded."}})
    bucket.append(now)
    return await call_next(request)


@app.exception_handler(RequestValidationError)
async def validation_error(_request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"error": {"code": "invalid_request", "message": "Request validation failed.", "details": exc.errors()}})


@app.exception_handler(HTTPException)
async def http_error(_request: Request, exc: HTTPException):
    detail = exc.detail
    if isinstance(detail, dict) and "code" in detail:
        payload = {"code": detail["code"], "message": detail.get("message", ""), "details": detail.get("details")}
    else:
        payload = {"code": "http_error", "message": str(detail), "details": None}
    return JSONResponse(status_code=exc.status_code, content={"error": payload})


@app.get("/health")
def health():
    runtime = app.state.runtime
    return {"status": "ready" if runtime.ready else "degraded", "model_version": None if not runtime.ready else runtime.bundle.get("model_version")}
