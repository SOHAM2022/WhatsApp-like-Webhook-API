#!/usr/bin/env python3
"""
Helper script to compute HMAC signatures for testing the webhook API.
"""

import hmac
import hashlib
import sys
import json


def compute_signature(secret: str, body: str) -> str:
    """Compute HMAC-SHA256 signature."""
    return hmac.new(
        secret.encode(),
        body.encode(),
        hashlib.sha256
    ).hexdigest()


def main():
    if len(sys.argv) < 2:
        print("Usage: python compute_signature.py '<json_body>' [secret]")
        print("\nExample:")
        print('  python compute_signature.py \'{"message_id":"m1","from":"+919876543210","to":"+14155550100","ts":"2025-01-15T10:00:00Z","text":"Hello"}\'')
        sys.exit(1)
    
    body = sys.argv[1]
    secret = sys.argv[2] if len(sys.argv) > 2 else "testsecret"
    
    # Validate JSON
    try:
        json.loads(body)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON - {e}")
        sys.exit(1)
    
    signature = compute_signature(secret, body)
    
    print(f"Body: {body}")
    print(f"Secret: {secret}")
    print(f"Signature: {signature}")
    print("\nCurl command:")
    print(f'curl -X POST http://localhost:8000/webhook \\')
    print(f'  -H "Content-Type: application/json" \\')
    print(f'  -H "X-Signature: {signature}" \\')
    print(f"  -d '{body}'")


if __name__ == "__main__":
    main()
