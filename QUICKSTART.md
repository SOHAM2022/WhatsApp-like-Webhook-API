# Quick Start Instructions

## Prerequisites Check

Before starting, ensure you have:

1. **Docker Desktop installed and RUNNING**
   - Download from: https://www.docker.com/products/docker-desktop
   - **IMPORTANT**: Open Docker Desktop app and make sure it's running
   - Verify: `docker ps` should work without errors

2. **Terminal/Command Line access**
   - macOS: Terminal app or iTerm2

## Step-by-Step Execution

### Step 1: Start Docker Desktop

**CRITICAL**: Open Docker Desktop application on your Mac and wait for it to fully start (whale icon in menu bar should be steady, not animated).

Verify Docker is running:
```bash
docker ps
```

If you see an error about Docker daemon, start Docker Desktop first!

### Step 2: Navigate to Project Directory

```bash
cd ~/Desktop/LyfterAI-Backend\ Assessment
```

Or:
```bash
cd "/Users/soham/Desktop/LyfterAI-Backend Assessment"
```

### Step 3: Review the Files

Your project should have these files:
```
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── models.py
│   ├── storage.py
│   ├── logging_utils.py
│   └── metrics.py
├── Dockerfile
├── docker-compose.yml
├── Makefile
├── requirements.txt
├── README.md
├── GUIDE.md
├── test_api.sh
└── compute_signature.py
```

List files to verify:
```bash
ls -la
```

### Step 4: Build and Start the Service

```bash
make up
```

This will:
- Build the Docker image (first time takes ~2-3 minutes)
- Create a data volume for SQLite
- Start the service on http://localhost:8000
- Run health checks

**Expected output:**
```
[+] Building ...
[+] Running 2/2
Container webhook-api  Started
```

Wait about 10 seconds for the service to fully initialize.

### Step 5: Verify Service is Running

```bash
# Check health endpoints
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready
```

**Expected output for both:**
```json
{"status":"ok"}
```

If you get connection errors, wait a few more seconds and try again.

### Step 6: Run the Test Suite

```bash
./test_api.sh
```

This comprehensive test script will:
1. Test health endpoints
2. Validate HMAC signature checking
3. Insert test messages
4. Test idempotency (duplicates)
5. Test validation errors
6. Test pagination and filtering
7. Test analytics endpoint
8. Verify Prometheus metrics

**Expected**: All tests should pass with PASS marks

### Step 7: View Logs

```bash
make logs
```

You should see structured JSON logs like:
```json
{"ts":"2025-12-26T...","level":"INFO","message":"POST /webhook 200","request_id":"...","method":"POST","path":"/webhook","status":200,"latency_ms":12.34,"message_id":"m1","dup":false,"result":"created"}
```

Press `Ctrl+C` to stop following logs.

### Step 8: Manual Testing (Optional)

Test sending a message manually:

```bash
# Compute signature
BODY='{"message_id":"test1","from":"+919876543210","to":"+14155550100","ts":"2025-12-26T10:00:00Z","text":"Hello from manual test"}'
SIG=$(echo -n "$BODY" | openssl dgst -sha256 -hmac "testsecret" | sed 's/^.* //')

# Send request
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -H "X-Signature: $SIG" \
  -d "$BODY"
```

**Expected output:**
```json
{"status":"ok"}
```

View the message:
```bash
curl http://localhost:8000/messages | jq '.'
```

### Step 9: Access All Endpoints

```bash
# List messages
curl http://localhost:8000/messages

# Get statistics
curl http://localhost:8000/stats

# Get metrics
curl http://localhost:8000/metrics

# Health probes
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready
```

### Step 10: Stop the Service

```bash
make down
```

This stops and removes containers and volumes (clean slate).

To keep data:
```bash
docker compose down
```

To restart:
```bash
make up
```

---

## Troubleshooting

### Issue: "Cannot connect to Docker daemon"

**Solution:**
1. Open Docker Desktop application
2. Wait for it to fully start (whale icon steady in menu bar)
3. Try again: `docker ps`

### Issue: "Port 8000 already in use"

**Solution:**
```bash
# Find what's using the port
lsof -i :8000

# Stop that process or change port in docker-compose.yml
```

### Issue: Service won't start

**Check logs:**
```bash
docker compose logs api
```

**Common causes:**
- Docker not running → Start Docker Desktop
- Build errors → Check Dockerfile syntax
- Missing files → Ensure all files are present

### Issue: 503 from /health/ready

**Solution:**
- Wait 10 seconds for database initialization
- Check logs: `docker compose logs api`
- Verify WEBHOOK_SECRET is set

### Issue: Tests failing

**Check:**
1. Service is running: `curl http://localhost:8000/health/live`
2. No other service on port 8000: `lsof -i :8000`
3. View logs for errors: `make logs`

---

## Quick Command Reference

```bash
# Start service
make up

# Stop service (remove data)
make down

# View logs
make logs

# Run tests
./test_api.sh

# Compute signature
python compute_signature.py '<json_body>'

# Access database
docker compose exec api sqlite3 /data/app.db

# Restart service
make down && make up

# View container status
docker compose ps

# Clean everything
docker compose down -v
docker system prune -f
```

---

## What to Submit

1. **Push to GitHub**:
   ```bash
   git init
   git add .
   git commit -m "Complete webhook API implementation"
   git remote add origin https://github.com/YOUR_USERNAME/webhook-api.git
   git push -u origin main
   ```

2. **Email to careers@lyftr.ai**:
   - Subject: Backend Assignment – [Your Name]
   - Include: GitHub repository link
   - Mention: All tests passing

---

## Success Checklist

Before submitting, verify:

- [x] `make up` starts without errors
- [x] `curl http://localhost:8000/health/ready` returns 200
- [x] `./test_api.sh` passes all tests
- [x] Logs are valid JSON
- [x] `/metrics` endpoint works
- [x] README.md is complete
- [x] Code is pushed to GitHub

---

**If everything works, you're ready to submit!**

For detailed explanations, see [GUIDE.md](GUIDE.md)
