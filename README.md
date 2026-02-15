# WhatsApp-like Webhook API

A production-style FastAPI service for ingesting WhatsApp-like messages with HMAC signature validation, pagination, filtering, and observability features.

## Features

- **HMAC-SHA256 Signature Validation**: Secure webhook endpoint with signature verification
- **Idempotent Message Ingestion**: Duplicate messages handled gracefully
- **Pagination & Filtering**: Query messages with flexible filters
- **Analytics Endpoint**: Get message statistics and top senders
- **Health Probes**: Kubernetes-style liveness and readiness checks
- **Prometheus Metrics**: Production-ready observability
- **Structured JSON Logging**: Every request logged with unique request ID
- **12-Factor App**: All configuration via environment variables
- **SQLite Storage**: Lightweight, persistent storage with Docker volumes

## Quick Start

### Prerequisites

- Docker and Docker Compose installed
- Make (optional, but recommended)

### Running the Service

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd LyfterAI-Backend\ Assessment
   ```

2. **Set environment variables** (optional - defaults are provided)
   ```bash
   export WEBHOOK_SECRET="your-secret-key"
   export LOG_LEVEL="INFO"
   ```

3. **Start the service**
   ```bash
   make up
   ```
   
   Or without make:
   ```bash
   docker compose up -d --build
   ```

4. **Check the service is running**
   ```bash
   curl http://localhost:8000/health/live
   curl http://localhost:8000/health/ready
   ```

5. **View logs**
   ```bash
   make logs
   ```

6. **Stop the service**
   ```bash
   make down
   ```

## API Endpoints

### POST /webhook

Ingest a new message with HMAC signature validation.

**Request:**
```bash
# Compute HMAC signature
BODY='{"message_id":"m1","from":"+919876543210","to":"+14155550100","ts":"2025-01-15T10:00:00Z","text":"Hello"}'
SIGNATURE=$(echo -n "$BODY" | openssl dgst -sha256 -hmac "testsecret" | sed 's/^.* //')

# Send request
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -H "X-Signature: $SIGNATURE" \
  -d "$BODY"
```

**Response:**
```json
{"status": "ok"}
```

**Validation Rules:**
- `message_id`: Non-empty string
- `from` / `to`: E.164 format (starts with +, followed by digits)
- `ts`: ISO-8601 UTC timestamp with Z suffix
- `text`: Optional, max 4096 characters

**Behavior:**
- First request with valid signature: Inserts message, returns 200
- Duplicate message_id: Returns 200 without inserting (idempotent)
- Invalid signature: Returns 401
- Invalid payload: Returns 422

### GET /messages

List stored messages with pagination and filtering.

**Query Parameters:**
- `limit` (optional, default: 50, max: 100): Number of messages to return
- `offset` (optional, default: 0): Offset for pagination
- `from` (optional): Filter by exact sender phone number
- `since` (optional): ISO-8601 timestamp - return messages after this time
- `q` (optional): Search text (case-insensitive substring match)

**Example:**
```bash
# Get all messages
curl "http://localhost:8000/messages"

# Pagination
curl "http://localhost:8000/messages?limit=10&offset=0"

# Filter by sender
curl "http://localhost:8000/messages?from=%2B919876543210"

# Filter by time
curl "http://localhost:8000/messages?since=2025-01-15T09:00:00Z"

# Search text
curl "http://localhost:8000/messages?q=Hello"

# Combined filters
curl "http://localhost:8000/messages?from=%2B919876543210&limit=5&q=test"
```

**Response:**
```json
{
  "data": [
    {
      "message_id": "m1",
      "from": "+919876543210",
      "to": "+14155550100",
      "ts": "2025-01-15T10:00:00Z",
      "text": "Hello"
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

**Ordering:** Messages are sorted by timestamp ascending, then message_id ascending.

### GET /stats

Get message analytics.

**Example:**
```bash
curl http://localhost:8000/stats
```

**Response:**
```json
{
  "total_messages": 123,
  "senders_count": 10,
  "messages_per_sender": [
    {"from": "+919876543210", "count": 50},
    {"from": "+911234567890", "count": 30}
  ],
  "first_message_ts": "2025-01-10T09:00:00Z",
  "last_message_ts": "2025-01-15T10:00:00Z"
}
```

### GET /health/live

Liveness probe - always returns 200 when service is running.

```bash
curl http://localhost:8000/health/live
```

### GET /health/ready

Readiness probe - returns 200 when:
- Database is reachable
- WEBHOOK_SECRET is configured

```bash
curl http://localhost:8000/health/ready
```

### GET /metrics

Prometheus-style metrics endpoint.

```bash
curl http://localhost:8000/metrics
```

**Metrics exposed:**
- `http_requests_total{path, status}`: Total HTTP requests by path and status code
- `webhook_requests_total{result}`: Webhook outcomes (created, duplicate, invalid_signature, validation_error)
- `request_latency_ms`: Request latency histogram with buckets

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | SQLite database path | `sqlite:////data/app.db` |
| `WEBHOOK_SECRET` | HMAC secret for signature validation | **Required** |
| `LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) | `INFO` |

## Design Decisions

### HMAC Signature Verification

The webhook endpoint uses HMAC-SHA256 for request validation:

1. **Signature Computation**: `HMAC-SHA256(WEBHOOK_SECRET, raw_request_body)`
2. **Header**: Client sends hex-encoded signature in `X-Signature` header
3. **Verification**: Server recomputes signature and compares using constant-time comparison (`hmac.compare_digest`)
4. **Security**: 
   - Secret must be set at startup or service fails
   - Invalid/missing signatures return 401 before any database operations
   - Timing-safe comparison prevents timing attacks

### Idempotency

Messages are deduplicated using database-level constraints:

1. **Primary Key**: `message_id` is the table's PRIMARY KEY
2. **Insert Logic**: 
   - First insert succeeds, returns `True`
   - Duplicate insert fails with UNIQUE constraint error, caught and returns `False`
3. **Response**: Both cases return 200 with `{"status": "ok"}`
4. **Logging**: Duplicate requests logged with `"dup": true`

### Pagination Contract

The `/messages` endpoint implements offset-based pagination:

1. **Parameters**:
   - `limit`: Number of records (1-100, default 50)
   - `offset`: Skip N records (default 0)
2. **Ordering**: Deterministic sort by `(ts ASC, message_id ASC)`
3. **Total Count**: Always reflects total matching records, not just current page
4. **Filters**: Applied before pagination:
   - `from`: Exact match on sender
   - `since`: Messages with `ts >= since`
   - `q`: Case-insensitive substring search in `text`

### Statistics Endpoint

The `/stats` endpoint provides aggregated analytics:

1. **Total Messages**: `COUNT(*)` from messages table
2. **Unique Senders**: `COUNT(DISTINCT from_msisdn)`
3. **Top Senders**: Top 10 senders by message count, sorted descending
4. **Timestamp Range**: MIN/MAX of `ts` column (null if no messages)
5. **Performance**: Uses SQL aggregation functions for efficiency

### Metrics Definition

Prometheus metrics track:

1. **http_requests_total**:
   - Labels: `path`, `status`
   - Type: Counter
   - Incremented by middleware for all requests

2. **webhook_requests_total**:
   - Labels: `result` (created, duplicate, invalid_signature, validation_error)
   - Type: Counter
   - Tracks webhook-specific outcomes

3. **request_latency_ms**:
   - Type: Histogram
   - Buckets: [10, 25, 50, 100, 250, 500, 1000, 2500, 5000]
   - Measures end-to-end request time

### Structured Logging

Every request generates a JSON log line with:

**Standard Fields:**
- `ts`: Server timestamp (ISO-8601 UTC)
- `level`: Log level (INFO, ERROR)
- `request_id`: Unique UUID per request
- `method`: HTTP method
- `path`: Request path
- `status`: HTTP status code
- `latency_ms`: Request duration

**Webhook-Specific Fields:**
- `message_id`: From payload
- `dup`: Boolean - true if duplicate
- `result`: Outcome (created, duplicate, invalid_signature, validation_error)

### Database Schema

```sql
CREATE TABLE messages (
    message_id TEXT PRIMARY KEY,
    from_msisdn TEXT NOT NULL,
    to_msisdn TEXT NOT NULL,
    ts TEXT NOT NULL,
    text TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX idx_messages_ts ON messages(ts, message_id);
CREATE INDEX idx_messages_from ON messages(from_msisdn);
```

**Design choices:**
- `message_id` as PRIMARY KEY enforces uniqueness
- Indexes on `(ts, message_id)` support efficient ordering
- Index on `from_msisdn` optimizes sender filtering
- ISO-8601 text format for timestamps (SQLite best practice)

## Project Structure

```
.
├── app/
│   ├── __init__.py
│   ├── main.py           # FastAPI app, routes, middleware
│   ├── models.py         # Database connection and schema
│   ├── storage.py        # Database operations
│   ├── logging_utils.py  # JSON logging setup
│   └── metrics.py        # Prometheus metrics
├── Dockerfile            # Multi-stage production image
├── docker-compose.yml    # Service orchestration
├── Makefile             # Convenience commands
├── requirements.txt      # Python dependencies
└── README.md            # This file
```

## Development

### Local Development (without Docker)

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export WEBHOOK_SECRET="testsecret"
export DATABASE_URL="sqlite:///./app.db"
export LOG_LEVEL="DEBUG"

# Run the application
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Testing Signature Generation

**Using Python:**
```python
import hmac
import hashlib

secret = "testsecret"
body = '{"message_id":"m1","from":"+919876543210","to":"+14155550100","ts":"2025-01-15T10:00:00Z","text":"Hello"}'
signature = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
print(signature)
```

**Using OpenSSL:**
```bash
echo -n '{"message_id":"m1","from":"+919876543210","to":"+14155550100","ts":"2025-01-15T10:00:00Z","text":"Hello"}' | \
  openssl dgst -sha256 -hmac "testsecret" | sed 's/^.* //'
```

### Viewing Logs

```bash
# Follow all logs
make logs

# View specific number of lines
docker compose logs --tail=100 api

# Pipe through jq for pretty JSON
docker compose logs api | grep '{' | jq '.'
```

## Setup Used

**Development Environment:**
- VSCode with GitHub Copilot
- Cursor AI for code assistance
- Occasional ChatGPT prompts for best practices

## Troubleshooting

### Service won't start

1. Check WEBHOOK_SECRET is set:
   ```bash
   docker compose logs api | grep -i secret
   ```

2. Verify database directory permissions:
   ```bash
   docker compose exec api ls -la /data
   ```

### Invalid signature errors

1. Ensure body is sent as raw bytes (no extra whitespace)
2. Verify WEBHOOK_SECRET matches between client and server
3. Check signature is hex-encoded (lowercase)

### Database locked errors

SQLite doesn't handle high concurrency well. For production, consider:
- Using PostgreSQL instead
- Implementing connection pooling
- Adding write-ahead logging (WAL) mode


