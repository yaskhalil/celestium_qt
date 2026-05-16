import asyncio
import os
import hashlib
import hmac
import base64
import json
import uuid
from datetime import datetime, timezone
from urllib.parse import quote
import httpx

async def test_quotes_api():
    key = "test_key"
    secret = "test_secret"
    host = "usquotes-api.webullfintech.com"
    uri = "/openapi/market-data/snapshot"
    params = {"symbols": "AAPL", "category": "US_STOCK"}
    url = f"https://{host}{uri}"
    
    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    nonce = str(uuid.uuid4())
    
    sign_params = {
        "x-app-key": key,
        "x-timestamp": timestamp,
        "x-signature-version": "1.0",
        "x-signature-algorithm": "HMAC-SHA1",
        "x-signature-nonce": nonce,
        "host": host
    }
    for k, v in params.items():
        sign_params[k.lower()] = str(v)
        
    sorted_keys = sorted(sign_params.keys())
    sorted_params_str = "&".join([f"{k}={sign_params[k]}" for k in sorted_keys])
    
    body_str = ""
    body_md5 = hashlib.md5(body_str.encode("utf-8")).hexdigest().upper()
    
    source_string = f"{uri}&{sorted_params_str}&{body_md5}"
    encoded_string = quote(source_string, safe='')
    
    signing_key = (secret + "&").encode("utf-8")
    signature = base64.b64encode(hmac.new(signing_key, encoded_string.encode("utf-8"), hashlib.sha1).digest()).decode("utf-8")
    
    headers = {
        "x-app-key": key,
        "x-timestamp": timestamp,
        "x-signature-nonce": nonce,
        "x-signature-algorithm": "HMAC-SHA1",
        "x-signature-version": "1.0",
        "x-signature": signature,
        "x-version": "v2",
        "Content-Type": "application/json"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            res = await client.get(url, params=params, headers=headers)
            print(f"Status: {res.status_code}")
            print(f"Response: {res.text}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_quotes_api())
