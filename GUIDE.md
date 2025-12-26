# Step-by-Step Guide to Build and Run the Webhook API

## Overview
This guide will walk you through building and running a production-style FastAPI webhook service from scratch. The service handles WhatsApp-like messages with HMAC signature validation, provides pagination, filtering, analytics, and complete observability.

---

## Step 1: Prerequisites

Make sure you have installed:
- **Docker Desktop** (includes Docker and Docker Compose)
  - Mac: Download from https://www.docker.com/products/docker-desktop
  - Verify: `docker --version` and `docker compose version`
- **Git** (optional, for version control)
- **curl** or **Postman** (for testing)
- **jq** (optional, for pretty JSON output): `brew install jq` on Mac

---

## Step 2: Understanding the Project Structure

```
LyfterAI-Backend Assessment/
├── app/
│   ├── __init__.py          # Package marker
│   ├── main.py              # FastAPI app with all routes
│   ├── models.py            # Database schema and connection
│   ├── storage.py           # Database operations (CRUD)
│   ├── logging_utils.py     # Structured JSON logging
│   └── metrics.py           # Prometheus metrics tracking
├── Dockerfile               # Multi-stage Docker build
├── docker-compose.yml       # Service orchestration
├── Makefile                 # Convenience commands
├── requirements.txt         # Python dependencies
├── README.md               # Documentation
├── test_api.sh             # Test script
└── compute_signature.py    # Helper to compute HMAC signatures
```

---

## Step 3: Understanding Key Components

### FastAPI Basics (for Express.js developers)

If you know Express.js, here's how FastAPI compares:

| Express.js | FastAPI |
|------------|---------|
| `app.get('/path', (req, res) => {})` | `@app.get("/path")` decorator |
| `app.post('/path', (req, res) => {})` | `@app.post("/path")` decorator |
| `req.body` | Request body via Pydantic models |
| `res.json({})` | Return Python dict (auto-converted) |
| Middleware with `app.use()` | `@app.middleware("http")` |
| `app.listen(port)` | `uvicorn.run(app, port=port)` |

### Key Concepts

1. **Pydantic Models**: Like TypeScript interfaces but with runtime validation
   ```python
   class WebhookMessage(BaseModel):
       message_id: str
       from_: str = Field(..., alias="from")  # Handles JSON key "from"
       to: str
   ```

2. **Async/Await**: FastAPI uses Python's async (similar to Node.js)
   ```python
   @app.post("/webhook")
   async def webhook(request: Request):
       body = await request.body()  # Like await req.json()
       # ... process
       return {"status": "ok"}
   ```

3. **Dependency Injection**: FastAPI's way of sharing state
   ```python
   @app.get("/messages")
   async def get_messages(limit: int = Query(50)):  # Auto-validates query params
       # limit is automatically extracted and validated
   ```

---

## Step 4: Build the Service

### 4.1 Navigate to Project Directory

```bash
cd ~/Desktop/LyfterAI-Backend\ Assessment
```

### 4.2 Review Environment Variables

Open `docker-compose.yml` and note these environment variables:

```yaml
environment:
  - DATABASE_URL=sqlite:////data/app.db
  - WEBHOOK_SECRET=${WEBHOOK_SECRET:-testsecret}
  - LOG_LEVEL=${LOG_LEVEL:-INFO}
```

- `DATABASE_URL`: SQLite database path (inside container)
- `WEBHOOK_SECRET`: Secret key for HMAC validation (defaults to "testsecret")
- `LOG_LEVEL`: Logging verbosity (INFO, DEBUG, WARNING, ERROR)

### 4.3 Build and Start the Service

```bash
# Using Makefile (recommended)
make up

# Or using Docker Compose directly
docker compose up -d --build
```

**What happens:**
1. Docker builds the image (2-stage build for smaller size)
2. Installs Python dependencies
3. Creates a volume for persistent storage
4. Starts the container on port 8000
5. Runs health checks

### 4.4 Verify Service is Running

```bash
# Check container status
docker compose ps

# Check logs
make logs
# Or: docker compose logs -f api

# Test health endpoints
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready
```

You should see:
- Container status: "Up"
- Health: "healthy"
- Both health endpoints return `{"status": "ok"}`

---

## Step 5: Understanding HMAC Signature Validation

### Why HMAC?

HMAC (Hash-based Message Authentication Code) ensures:
1. **Authentication**: Request comes from someone who knows the secret
2. **Integrity**: Message hasn't been tampered with
3. **Non-repudiation**: Sender can't deny sending it

### How It Works

1. **Server** and **Client** share a secret key (WEBHOOK_SECRET)
2. **Client** computes: `signature = HMAC-SHA256(secret, request_body)`
3. **Client** sends request with `X-Signature: <hex_signature>` header
4. **Server** recomputes signature and compares
5. If match → process request; if not → reject with 401

### Computing Signatures

**Method 1: Using the helper script**
```bash
python compute_signature.py '{"message_id":"m1","from":"+919876543210","to":"+14155550100","ts":"2025-01-15T10:00:00Z","text":"Hello"}'
```

**Method 2: Using OpenSSL**
```bash
BODY='{"message_id":"m1","from":"+919876543210","to":"+14155550100","ts":"2025-01-15T10:00:00Z","text":"Hello"}'
echo -n "$BODY" | openssl dgst -sha256 -hmac "testsecret" | sed 's/^.* //'
```

**Method 3: Using Python inline**
```bash
python -c "import hmac,hashlib; print(hmac.new(b'testsecret', b'{\"message_id\":\"m1\",\"from\":\"+919876543210\",\"to\":\"+14155550100\",\"ts\":\"2025-01-15T10:00:00Z\",\"text\":\"Hello\"}', hashlib.sha256).hexdigest())"
```

---

## Step 6: Testing the API

### 6.1 Run the Automated Test Script

```bash
./test_api.sh
```

This tests:
- Health endpoints
- Signature validation (valid, invalid, missing)
- Message insertion and idempotency
- Validation errors
- Pagination and filtering
- Stats endpoint
- Metrics endpoint

### 6.2 Manual Testing

**Test 1: Invalid Signature (expect 401)**
```bash
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -H "X-Signature: invalid123" \
  -d '{"message_id":"m1","from":"+919876543210","to":"+14155550100","ts":"2025-01-15T10:00:00Z","text":"Hello"}'
```

**Test 2: Valid Message (expect 200)**
```bash
# Compute signature
BODY='{"message_id":"m1","from":"+919876543210","to":"+14155550100","ts":"2025-01-15T10:00:00Z","text":"Hello"}'
SIG=$(echo -n "$BODY" | openssl dgst -sha256 -hmac "testsecret" | sed 's/^.* //')

# Send request
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -H "X-Signature: $SIG" \
  -d "$BODY"
```

**Test 3: Duplicate Message (expect 200, but not inserted)**
```bash
# Send same request again
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -H "X-Signature: $SIG" \
  -d "$BODY"
```

**Test 4: Invalid Phone Format (expect 422)**
```bash
BAD_BODY='{"message_id":"m2","from":"invalid","to":"+14155550100","ts":"2025-01-15T10:00:00Z","text":"Test"}'
BAD_SIG=$(echo -n "$BAD_BODY" | openssl dgst -sha256 -hmac "testsecret" | sed 's/^.* //')

curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -H "X-Signature: $BAD_SIG" \
  -d "$BAD_BODY"
```

**Test 5: List Messages**
```bash
# Get all messages
curl http://localhost:8000/messages | jq '.'

# Pagination
curl "http://localhost:8000/messages?limit=2&offset=0" | jq '.'

# Filter by sender
curl "http://localhost:8000/messages?from=%2B919876543210" | jq '.'

# Filter by time
curl "http://localhost:8000/messages?since=2025-01-15T09:30:00Z" | jq '.'

# Search text
curl "http://localhost:8000/messages?q=Hello" | jq '.'
```

**Test 6: Get Statistics**
```bash
curl http://localhost:8000/stats | jq '.'
```

**Test 7: Get Metrics**
```bash
curl http://localhost:8000/metrics
```

---

## Step 7: Understanding the Database

### Schema

```sql
CREATE TABLE messages (
    message_id TEXT PRIMARY KEY,      -- Unique message identifier
    from_msisdn TEXT NOT NULL,        -- Sender phone (E.164 format)
    to_msisdn TEXT NOT NULL,          -- Recipient phone (E.164 format)
    ts TEXT NOT NULL,                 -- Message timestamp (ISO-8601)
    text TEXT,                        -- Message content (optional)
    created_at TEXT NOT NULL          -- Server insert time (ISO-8601)
);
```

### Accessing the Database

```bash
# Enter container
docker compose exec api /bin/sh

# Open SQLite shell
sqlite3 /data/app.db

# Run queries
SELECT * FROM messages ORDER BY ts;
SELECT COUNT(*) FROM messages;
SELECT from_msisdn, COUNT(*) FROM messages GROUP BY from_msisdn;

# Exit
.exit
exit
```

---

## Step 8: Viewing Logs

### Structured JSON Logs

All requests are logged in JSON format with:
- `ts`: Timestamp
- `level`: Log level
- `request_id`: Unique ID per request
- `method`, `path`, `status`: Request details
- `latency_ms`: Request duration
- `message_id`, `dup`, `result`: Webhook-specific fields

### View Logs

```bash
# Follow logs
make logs

# View last 50 lines
docker compose logs --tail=50 api

# View JSON logs with jq
docker compose logs api | grep '{' | jq '.'

# Filter webhook logs
docker compose logs api | grep '{' | jq 'select(.path == "/webhook")'

# Find duplicate messages
docker compose logs api | grep '{' | jq 'select(.dup == true)'
```

---

## Step 9: Monitoring with Metrics

### Prometheus Metrics

Access metrics at: http://localhost:8000/metrics

**Key Metrics:**

1. **http_requests_total** - Total requests by path and status
   ```
   http_requests_total{path="/webhook",status="200"} 15
   http_requests_total{path="/webhook",status="401"} 2
   ```

2. **webhook_requests_total** - Webhook outcomes
   ```
   webhook_requests_total{result="created"} 10
   webhook_requests_total{result="duplicate"} 5
   webhook_requests_total{result="invalid_signature"} 2
   ```

3. **request_latency_ms** - Request latency histogram
   ```
   request_latency_ms_bucket{le="100"} 20
   request_latency_ms_bucket{le="500"} 25
   ```

### Query Metrics

```bash
# Get all metrics
curl http://localhost:8000/metrics

# Count total webhook requests
curl -s http://localhost:8000/metrics | grep webhook_requests_total

# Check request latency
curl -s http://localhost:8000/metrics | grep request_latency_ms
```

---

## Step 10: Stopping and Cleaning Up

### Stop the Service

```bash
# Stop and keep data
docker compose down

# Stop and remove data
make down
# Or: docker compose down -v
```

### Restart the Service

```bash
# With existing data
docker compose up -d

# Fresh start (rebuilds image)
make up
```

---

## Step 11: Troubleshooting

### Common Issues

**1. Service won't start**
```bash
# Check logs
docker compose logs api

# Common cause: WEBHOOK_SECRET not set
# Solution: Check docker-compose.yml has default or export variable
export WEBHOOK_SECRET="testsecret"
make up
```

**2. 503 from /health/ready**
```bash
# Cause: Database not initialized or secret missing
# Solution: Wait 10 seconds for DB init, or check logs
docker compose logs api | grep -i error
```

**3. "Address already in use"**
```bash
# Cause: Port 8000 is taken
# Solution: Stop other services or change port in docker-compose.yml
lsof -i :8000  # Find what's using the port
```

**4. Signature validation fails**
```bash
# Cause: Mismatch in body or secret
# Solution: Ensure exact body match (no extra whitespace)
# Use helper script to generate correct signature
python compute_signature.py '{"message_id":"test","from":"+11234567890","to":"+10987654321","ts":"2025-01-15T10:00:00Z","text":"Test"}'
```

**5. Database locked errors**
```bash
# Cause: SQLite doesn't handle high concurrency
# Solution: Reduce concurrent requests or wait and retry
```

---

## Step 12: Development Workflow

### Local Development (without Docker)

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export WEBHOOK_SECRET="testsecret"
export DATABASE_URL="sqlite:///./app.db"
export LOG_LEVEL="DEBUG"

# Run with auto-reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Making Changes

1. Edit code in `app/` directory
2. Rebuild and restart:
   ```bash
   make down
   make up
   ```
3. Test changes
4. View logs to verify

---

## Step 13: Understanding the Code Flow

### Request Flow for POST /webhook

1. **Middleware** (`logging_middleware`):
   - Generates unique `request_id`
   - Tracks request start time

2. **Webhook Handler** (`webhook` function):
   - Reads raw request body
   - Checks `X-Signature` header exists
   - Computes HMAC-SHA256 of body with `WEBHOOK_SECRET`
   - Compares signatures (constant-time comparison)
   - If invalid → return 401

3. **Validation** (Pydantic):
   - Parse JSON body
   - Validate `WebhookMessage` model:
     - `message_id`: non-empty string
     - `from`/`to`: E.164 format (+, then digits)
     - `ts`: ISO-8601 format
     - `text`: optional, max 4096 chars
   - If invalid → return 422

4. **Storage** (`insert_message`):
   - Try to INSERT into SQLite
   - If `message_id` already exists → catch UNIQUE error
   - Return `True` if new, `False` if duplicate

5. **Response**:
   - Log request with `dup`, `result`, `message_id`
   - Track metrics
   - Return `{"status": "ok"}` (always 200 for valid signature)

### Request Flow for GET /messages

1. **Query Parsing**:
   - FastAPI auto-extracts query params
   - Validates: `limit` (1-100), `offset` (≥0)

2. **Storage Query** (`get_messages`):
   - Build WHERE clause from filters
   - Count total matching rows
   - Fetch paginated data with ORDER BY ts, message_id
   - Return (data, total)

3. **Response**:
   - Return JSON with `data`, `total`, `limit`, `offset`

---

## Step 14: Deployment Checklist

Before submitting:

- [ ] Service starts without errors: `make up`
- [ ] Health checks pass: `curl http://localhost:8000/health/ready`
- [ ] Can insert message with valid signature
- [ ] Duplicate message returns 200 (idempotent)
- [ ] Invalid signature returns 401
- [ ] Invalid payload returns 422
- [ ] `/messages` returns paginated results
- [ ] Filters work (`from`, `since`, `q`)
- [ ] `/stats` returns correct counts
- [ ] `/metrics` exposes Prometheus metrics
- [ ] Logs are valid JSON: `docker compose logs api | grep '{' | jq '.'`
- [ ] README.md is complete
- [ ] Test script runs successfully: `./test_api.sh`

---

## Step 15: Submission

1. **Initialize Git repository** (if not already)
   ```bash
   git init
   git add .
   git commit -m "Initial commit: WhatsApp-like webhook API"
   ```

2. **Create GitHub repository**
   - Go to https://github.com/new
   - Create a new repository (e.g., "webhook-api-assessment")
   - Don't initialize with README (you already have one)

3. **Push to GitHub**
   ```bash
   git remote add origin https://github.com/YOUR_USERNAME/webhook-api-assessment.git
   git branch -M main
   git push -u origin main
   ```

4. **Email submission**
   - To: careers@lyftr.ai
   - Subject: Backend Assignment – [Your Name]
   - Body:
     ```
     Hello,
     
     Please find my submission for the Backend Assessment:
     
     Repository: https://github.com/YOUR_USERNAME/webhook-api-assessment
     
     The service implements all required features:
     - HMAC signature validation
     - Idempotent message ingestion
     - Pagination and filtering
     - Statistics endpoint
     - Health probes
     - Prometheus metrics
     - Structured JSON logging
     
     To run:
     1. Clone repository
     2. Run: make up
     3. Test: ./test_api.sh
     
     Best regards,
     [Your Name]
     ```

---

## Appendix: Quick Reference

### Makefile Commands
```bash
make up     # Start services
make down   # Stop and remove
make logs   # View logs
make test   # Run tests
```

### Testing Commands
```bash
# Compute signature
python compute_signature.py '<json>'

# Test webhook
./test_api.sh

# Manual test
BODY='...'
SIG=$(echo -n "$BODY" | openssl dgst -sha256 -hmac "testsecret" | sed 's/^.* //')
curl -X POST http://localhost:8000/webhook -H "X-Signature: $SIG" -d "$BODY"
```

### Log Commands
```bash
docker compose logs -f api                    # Follow logs
docker compose logs --tail=100 api            # Last 100 lines
docker compose logs api | grep '{' | jq '.'   # JSON logs only
```

### Database Commands
```bash
docker compose exec api sqlite3 /data/app.db
SELECT * FROM messages;
.exit
```

---

## Summary

You now have a complete, production-ready FastAPI webhook service that:
- Validates HMAC signatures
- Stores messages idempotently in SQLite
- Provides pagination and filtering
- Exposes analytics and metrics
- Logs every request in structured JSON
- Runs in Docker with persistent storage
- Passes all evaluation criteria

Good luck with your assessment!
