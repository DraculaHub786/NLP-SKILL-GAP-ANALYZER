"""FastAPI app assembly: CORS, rate limiting, structured request logging,
and a catch-all exception handler so unhandled errors return clean JSON
instead of leaking stack traces to clients.
"""
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import router as v1_router
from app.core.config import settings
from app.utils.logging import get_logger
from app.utils.rate_limit import RateLimitMiddleware

logger = get_logger(__name__)

app = FastAPI(
    title="SkillGap AI",
    description="NLP-powered resume vs job description skill gap analyzer.",
    version="1.0.0",
)

# Privacy model: CORS restricted to the origins in config (never "*").
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RateLimitMiddleware)


@app.middleware("http")
async def log_request_details(request: Request, call_next):
    """Emits one structured JSON log per request: method, path, status, latency."""
    start = time.perf_counter()
    response = await call_next(request)
    latency_ms = round((time.perf_counter() - start) * 1000, 1)
    logger.info(
        "request_completed",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        latency_ms=latency_ms,
    )
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Last line of defense: unhandled exceptions become a clean 500 JSON body
    (with the real error logged server-side), never a raw traceback."""
    logger.error("unhandled_exception", path=request.url.path, error=str(exc), exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Something went wrong on our side. Please try again."},
    )


app.include_router(v1_router)
