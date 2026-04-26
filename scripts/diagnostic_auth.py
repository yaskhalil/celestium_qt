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

async def try_secret(name, key, secret):
    print(f"\n--- Testing {name} ---")
    
    # Try multiple common path/host patterns
    scenarios = [
        ("Production", "api.webull.com", "/openapi/auth/token/create"),
        ("UAT", "us-openapi-alb.uat.webullbroker.com", "/openapi/auth/token/create"),
    ]
    
    for label, host, uri in scenarios:
        print(f"Scenario: {label} ({host}{uri})")
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
        sorted_keys = sorted(sign_params.keys())
        sorted_params_str = "&".join([f"{k}={sign_params[k]}" for k in sorted_keys])
        
        body = {}
        body_str = json.dumps(body, separators=(',', ':'))
        body_md5 = hashlib.md5(body_str.encode("utf-8")).hexdigest().upper()
        
        # URI & PARAMS & BODY_MD5
        source_string = f"{uri}&{sorted_params_str}&{body_md5}"
        encoded_string = quote(source_string, safe='')
        
        signing_key = (secret + "&").encode("utf-8")
        signature = base64.b64encode(hmac.new(signing_key, encoded_string.encode("utf-8"), hashlib.sha1).digest()).decode("utf-8")
        
        headers = {
            "Host": host,
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
                res = await client.post(url, content=body_str, headers=headers)
                print(f"Status: {res.status_code}")
                print(f"Response: {res.text}")
            except Exception as e:
                print(f"Error: {e}")

async def main():
    app_key = "dbd57aedd92f789880c7741e0a7f3b28"
    s1 = "d73d1820ae93215c79275ea5ec6a9a5c"
    s2 = "8c947b629d851c684e18333f08884650"
    
    await try_secret("Original Secret", app_key, s1)
    await try_secret("New Secret", app_key, s2)

if __name__ == "__main__":
    asyncio.run(main())
