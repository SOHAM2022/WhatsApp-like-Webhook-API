"""
Structured JSON logging for the application.
"""
import json
import logging
import sys
from datetime import datetime
from typing import Optional, Dict, Any


class JSONFormatter(logging.Formatter):
    """Custom formatter to output logs in JSON format."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "message": record.getMessage()
        }
        
        # Add extra fields if present
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
        if hasattr(record, "method"):
            log_data["method"] = record.method
        if hasattr(record, "path"):
            log_data["path"] = record.path
        if hasattr(record, "status"):
            log_data["status"] = record.status
        if hasattr(record, "latency_ms"):
            log_data["latency_ms"] = record.latency_ms
        
        # Webhook-specific fields
        if hasattr(record, "message_id"):
            log_data["message_id"] = record.message_id
        if hasattr(record, "dup"):
            log_data["dup"] = record.dup
        if hasattr(record, "result"):
            log_data["result"] = record.result
        
        return json.dumps(log_data)


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """
    Setup structured JSON logger.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger("webhook_api")
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    
    # Remove existing handlers
    logger.handlers.clear()
    
    # Create console handler with JSON formatter
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)
    
    return logger


def log_request(
    logger: logging.Logger,
    request_id: str,
    method: str,
    path: str,
    status: int,
    latency_ms: float,
    extra: Optional[Dict[str, Any]] = None
):
    """
    Log HTTP request in structured JSON format.
    
    Args:
        logger: Logger instance
        request_id: Unique request identifier
        method: HTTP method
        path: Request path
        status: HTTP status code
        latency_ms: Request latency in milliseconds
        extra: Additional fields (message_id, dup, result for webhook)
    """
    extra_fields = {
        "request_id": request_id,
        "method": method,
        "path": path,
        "status": status,
        "latency_ms": round(latency_ms, 2)
    }
    
    if extra:
        extra_fields.update(extra)
    
    level = logging.INFO if status < 400 else logging.ERROR
    logger.log(level, f"{method} {path} {status}", extra=extra_fields)
