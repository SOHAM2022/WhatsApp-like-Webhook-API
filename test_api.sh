#!/bin/bash

# Test script for the Webhook API
# This script tests all the main endpoints

set -e  # Exit on error

BASE_URL="http://localhost:8000"
SECRET="testsecret"

echo "======================================"
echo "Testing Webhook API"
echo "======================================"
echo

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to compute HMAC signature
compute_signature() {
    local body="$1"
    echo -n "$body" | openssl dgst -sha256 -hmac "$SECRET" | sed 's/^.* //'
}

# Function to test endpoint
test_endpoint() {
    local name="$1"
    local expected_status="$2"
    shift 2
    local curl_args=("$@")
    
    echo -n "Testing $name... "
    status=$(curl -s -o /dev/null -w "%{http_code}" "${curl_args[@]}")
    
    if [ "$status" = "$expected_status" ]; then
        echo -e "${GREEN}✓ PASS${NC} (status: $status)"
        return 0
    else
        echo -e "${RED}✗ FAIL${NC} (expected: $expected_status, got: $status)"
        return 1
    fi
}

echo "1. Testing Health Endpoints"
echo "----------------------------"
test_endpoint "Liveness" "200" "$BASE_URL/health/live"
test_endpoint "Readiness" "200" "$BASE_URL/health/ready"
echo

echo "2. Testing Webhook Signature Validation"
echo "---------------------------------------"
BODY1='{"message_id":"m1","from":"+919876543210","to":"+14155550100","ts":"2025-01-15T10:00:00Z","text":"Hello World"}'

# Test invalid signature
test_endpoint "Invalid signature" "401" \
    -X POST "$BASE_URL/webhook" \
    -H "Content-Type: application/json" \
    -H "X-Signature: invalid" \
    -d "$BODY1"

# Test missing signature
test_endpoint "Missing signature" "401" \
    -X POST "$BASE_URL/webhook" \
    -H "Content-Type: application/json" \
    -d "$BODY1"

echo

echo "3. Testing Valid Message Ingestion"
echo "-----------------------------------"
SIG1=$(compute_signature "$BODY1")
test_endpoint "Valid message insert" "200" \
    -X POST "$BASE_URL/webhook" \
    -H "Content-Type: application/json" \
    -H "X-Signature: $SIG1" \
    -d "$BODY1"

# Test idempotency (duplicate)
test_endpoint "Duplicate message (idempotent)" "200" \
    -X POST "$BASE_URL/webhook" \
    -H "Content-Type: application/json" \
    -H "X-Signature: $SIG1" \
    -d "$BODY1"

echo

echo "4. Testing Validation Errors"
echo "----------------------------"
# Invalid phone format
INVALID_BODY='{"message_id":"m2","from":"invalid","to":"+14155550100","ts":"2025-01-15T10:00:00Z","text":"Test"}'
INVALID_SIG=$(compute_signature "$INVALID_BODY")
test_endpoint "Invalid phone format" "422" \
    -X POST "$BASE_URL/webhook" \
    -H "Content-Type: application/json" \
    -H "X-Signature: $INVALID_SIG" \
    -d "$INVALID_BODY"

echo

echo "5. Inserting More Test Messages"
echo "--------------------------------"
# Insert more messages for testing filtering
BODY2='{"message_id":"m2","from":"+919876543210","to":"+14155550100","ts":"2025-01-15T09:00:00Z","text":"Earlier message"}'
SIG2=$(compute_signature "$BODY2")
test_endpoint "Message m2" "200" \
    -X POST "$BASE_URL/webhook" \
    -H "Content-Type: application/json" \
    -H "X-Signature: $SIG2" \
    -d "$BODY2"

BODY3='{"message_id":"m3","from":"+911234567890","to":"+14155550100","ts":"2025-01-15T11:00:00Z","text":"Different sender"}'
SIG3=$(compute_signature "$BODY3")
test_endpoint "Message m3" "200" \
    -X POST "$BASE_URL/webhook" \
    -H "Content-Type: application/json" \
    -H "X-Signature: $SIG3" \
    -d "$BODY3"

BODY4='{"message_id":"m4","from":"+919876543210","to":"+14155550100","ts":"2025-01-15T12:00:00Z","text":"Latest message"}'
SIG4=$(compute_signature "$BODY4")
test_endpoint "Message m4" "200" \
    -X POST "$BASE_URL/webhook" \
    -H "Content-Type: application/json" \
    -H "X-Signature: $SIG4" \
    -d "$BODY4"

echo

echo "6. Testing Messages Endpoint"
echo "----------------------------"
echo "Getting all messages:"
curl -s "$BASE_URL/messages" | jq '.data | length, .[0]'

echo
echo "Testing pagination (limit=2, offset=0):"
curl -s "$BASE_URL/messages?limit=2&offset=0" | jq '{total, limit, offset, count: (.data | length)}'

echo
echo "Filtering by sender (+919876543210):"
curl -s "$BASE_URL/messages?from=%2B919876543210" | jq '{total, messages: [.data[].message_id]}'

echo
echo "Filtering by since (2025-01-15T10:00:00Z):"
curl -s "$BASE_URL/messages?since=2025-01-15T10:00:00Z" | jq '{total, messages: [.data[].message_id]}'

echo
echo "Text search (q=World):"
curl -s "$BASE_URL/messages?q=World" | jq '{total, messages: [.data[].message_id]}'

echo

echo "7. Testing Stats Endpoint"
echo "-------------------------"
curl -s "$BASE_URL/stats" | jq '.'

echo

echo "8. Testing Metrics Endpoint"
echo "---------------------------"
echo "Checking metrics are exposed:"
curl -s "$BASE_URL/metrics" | head -20

echo
echo "Verifying required metrics exist:"
if curl -s "$BASE_URL/metrics" | grep -q "http_requests_total"; then
    echo -e "${GREEN}✓${NC} http_requests_total found"
else
    echo -e "${RED}✗${NC} http_requests_total NOT found"
fi

if curl -s "$BASE_URL/metrics" | grep -q "webhook_requests_total"; then
    echo -e "${GREEN}✓${NC} webhook_requests_total found"
else
    echo -e "${RED}✗${NC} webhook_requests_total NOT found"
fi

echo
echo "======================================"
echo "Testing Complete!"
echo "======================================"
echo
echo "To view JSON logs, run:"
echo "  docker compose logs api | grep '{' | jq '.'"
