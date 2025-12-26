"""
Prometheus metrics tracking for the API.
"""
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Response


# Define metrics
http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests by path and status",
    ["path", "status"]
)

webhook_requests_total = Counter(
    "webhook_requests_total",
    "Total webhook requests by result",
    ["result"]
)

request_latency_ms = Histogram(
    "request_latency_ms",
    "Request latency in milliseconds",
    buckets=[10, 25, 50, 100, 250, 500, 1000, 2500, 5000]
)


def track_http_request(path: str, status: int):
    """Track HTTP request metric."""
    http_requests_total.labels(path=path, status=status).inc()


def track_webhook_request(result: str):
    """Track webhook request metric."""
    webhook_requests_total.labels(result=result).inc()


def track_latency(latency_ms: float):
    """Track request latency metric."""
    request_latency_ms.observe(latency_ms)


def get_metrics() -> Response:
    """Generate Prometheus metrics in text format."""
    metrics_data = generate_latest()
    return Response(
        content=metrics_data,
        media_type=CONTENT_TYPE_LATEST
    )
