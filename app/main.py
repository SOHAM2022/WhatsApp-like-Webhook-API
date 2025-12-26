"""
Main FastAPI application with webhook and API endpoints.
"""
import os
import hmac
import hashlib
import uuid
import time
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Request, Response, HTTPException, Query
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field, field_validator

from app.models import db
from app.storage import insert_message, get_messages, get_stats
from app.logging_utils import setup_logging, log_request
from app.metrics import (
    track_http_request,
    track_webhook_request,
    track_latency,
    get_metrics
)


# Environment configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:////data/app.db")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Initialize logger
logger = setup_logging(LOG_LEVEL)


# Pydantic models for validation
class WebhookMessage(BaseModel):
    """Webhook message payload schema."""
    
    message_id: str = Field(..., min_length=1, description="Unique message identifier")
    from_: str = Field(..., alias="from", description="Sender phone number in E.164 format")
    to: str = Field(..., description="Recipient phone number in E.164 format")
    ts: str = Field(..., description="Message timestamp in ISO-8601 UTC format")
    text: Optional[str] = Field(None, max_length=4096, description="Message text")
    
    @field_validator("from_", "to")
    @classmethod
    def validate_e164(cls, v: str) -> str:
        """Validate phone number is in E.164 format."""
        if not v.startswith("+"):
            raise ValueError("Phone number must be in E.164 format (start with +)")
        if not v[1:].isdigit():
            raise ValueError("Phone number must contain only digits after +")
        return v
    
    @field_validator("ts")
    @classmethod
    def validate_iso8601(cls, v: str) -> str:
        """Validate timestamp is in ISO-8601 format."""
        # Simple validation - just check format
        if "T" not in v:
            raise ValueError("Timestamp must be in ISO-8601 format")
        return v


class MessagesResponse(BaseModel):
    """Response model for GET /messages."""
    data: list
    total: int
    limit: int
    offset: int


# Application lifespan manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    # Startup: Check WEBHOOK_SECRET and initialize database
    if not WEBHOOK_SECRET:
        logger.error("WEBHOOK_SECRET environment variable not set", extra={})
        raise RuntimeError("WEBHOOK_SECRET must be set")
    
    await db.connect(DATABASE_URL)
    logger.info("Application started", extra={})
    
    yield
    
    # Shutdown: Close database
    await db.close()
    logger.info("Application shutdown", extra={})


# Create FastAPI app
app = FastAPI(
    title="Webhook API",
    description="Production-style FastAPI webhook service",
    version="1.0.0",
    lifespan=lifespan
)


# Middleware for request ID and logging
@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    """Add request ID and log all requests."""
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    
    start_time = time.time()
    
    try:
        response = await call_next(request)
        latency_ms = (time.time() - start_time) * 1000
        
        log_request(
            logger,
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            latency_ms=latency_ms
        )
        
        # Track metrics
        track_http_request(request.url.path, response.status_code)
        track_latency(latency_ms)
        
        return response
    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        
        log_request(
            logger,
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status=500,
            latency_ms=latency_ms
        )
        
        # Track metrics
        track_http_request(request.url.path, 500)
        track_latency(latency_ms)
        
        raise


def verify_signature(body: bytes, signature: str) -> bool:
    """
    Verify HMAC-SHA256 signature.
    
    Args:
        body: Raw request body
        signature: Hex-encoded HMAC signature from X-Signature header
    
    Returns:
        True if signature is valid
    """
    if not WEBHOOK_SECRET:
        return False
    
    expected = hmac.new(
        WEBHOOK_SECRET.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(expected, signature)


@app.post("/webhook")
async def webhook(request: Request):
    """
    Ingest WhatsApp-like messages with HMAC validation.
    
    Validates signature, checks payload, and stores message idempotently.
    """
    start_time = time.time()
    request_id = request.state.request_id
    
    # Get raw body for signature verification
    body = await request.body()
    
    # Check X-Signature header
    signature = request.headers.get("X-Signature")
    if not signature:
        latency_ms = (time.time() - start_time) * 1000
        track_webhook_request("invalid_signature")
        log_request(
            logger,
            request_id=request_id,
            method="POST",
            path="/webhook",
            status=401,
            latency_ms=latency_ms,
            extra={"result": "invalid_signature", "dup": False}
        )
        raise HTTPException(status_code=401, detail="invalid signature")
    
    # Verify signature
    if not verify_signature(body, signature):
        latency_ms = (time.time() - start_time) * 1000
        track_webhook_request("invalid_signature")
        log_request(
            logger,
            request_id=request_id,
            method="POST",
            path="/webhook",
            status=401,
            latency_ms=latency_ms,
            extra={"result": "invalid_signature", "dup": False}
        )
        raise HTTPException(status_code=401, detail="invalid signature")
    
    # Parse and validate payload
    try:
        import json
        payload = json.loads(body)
        message = WebhookMessage(**payload)
    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        track_webhook_request("validation_error")
        log_request(
            logger,
            request_id=request_id,
            method="POST",
            path="/webhook",
            status=422,
            latency_ms=latency_ms,
            extra={"result": "validation_error", "dup": False}
        )
        raise HTTPException(status_code=422, detail=str(e))
    
    # Insert message (idempotent)
    is_new = await insert_message(
        message_id=message.message_id,
        from_msisdn=message.from_,
        to_msisdn=message.to,
        ts=message.ts,
        text=message.text
    )
    
    latency_ms = (time.time() - start_time) * 1000
    result = "created" if is_new else "duplicate"
    
    log_request(
        logger,
        request_id=request_id,
        method="POST",
        path="/webhook",
        status=200,
        latency_ms=latency_ms,
        extra={
            "message_id": message.message_id,
            "dup": not is_new,
            "result": result
        }
    )
    
    # Track webhook metric
    track_webhook_request(result)
    
    return {"status": "ok"}


@app.get("/messages", response_model=MessagesResponse)
async def get_messages_endpoint(
    limit: int = Query(50, ge=1, le=100, description="Number of messages to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    from_: Optional[str] = Query(None, alias="from", description="Filter by sender"),
    since: Optional[str] = Query(None, description="Filter messages since timestamp"),
    q: Optional[str] = Query(None, description="Search in message text")
):
    """
    Get paginated and filtered messages.
    
    Returns list of messages ordered by timestamp ascending.
    """
    messages, total = await get_messages(
        limit=limit,
        offset=offset,
        from_filter=from_,
        since=since,
        q=q
    )
    
    return {
        "data": messages,
        "total": total,
        "limit": limit,
        "offset": offset
    }


@app.get("/stats")
async def get_stats_endpoint():
    """
    Get message statistics.
    
    Returns total messages, sender count, top senders, and timestamp range.
    """
    stats = await get_stats()
    return stats


@app.get("/health/live")
async def liveness():
    """
    Liveness probe - always returns 200.
    
    Indicates the service is running.
    """
    return {"status": "ok"}


@app.get("/health/ready")
async def readiness():
    """
    Readiness probe - returns 200 if database is healthy and secret is set.
    
    Indicates the service is ready to accept requests.
    """
    if not WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="WEBHOOK_SECRET not configured")
    
    is_healthy = await db.is_healthy()
    if not is_healthy:
        raise HTTPException(status_code=503, detail="database not ready")
    
    return {"status": "ok"}


@app.get("/metrics")
async def metrics():
    """
    Prometheus metrics endpoint (optional).
    
    Returns metrics in Prometheus text format.
    """
    return get_metrics()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
