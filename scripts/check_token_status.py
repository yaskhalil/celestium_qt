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
from dotenv import load_dotenv

load_dotenv()

async def check_token_status():
    app_key = os.getenv("WEBULL_APP_KEY")
    app_secret = os.getenv("WEBULL_APP_SECRET")
    token = os.getenv("WEBULL_ACCESS_TOKEN")
    
    print(f"Checking Status for Token: {token}")
    
    url = "https://api.webull.com/openapi/auth/token/check"
    uri = "/openapi/auth/token/check"
    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    nonce = str(uuid.uuid4())
    
    # Body is required for this POST
    body = {"token": token}
    body_str = json.dumps(body, separators=(',', ':'))
    body_md5 = hashlib.md5(body_str.encode("utf-8")).hexdigest().upper()
    
    # Sign params
    sign_params = {
        "x-app-key": app_key,
        "x-timestamp": timestamp,
        "x-signature-version": "1.0",
        "x-signature-algorithm": "HMAC-SHA1",
        "x-signature-nonce": nonce,
        "host": "api.webull.com"
    }
    sorted_keys = sorted(sign_params.keys())
    sorted_params_str = "&".join([f"{k}={sign_params[k]}" for k in sorted_keys])
    
    source_string = f"{uri}&{sorted_params_str}&{body_md5}"
    encoded_string = quote(source_string, safe='')
    
    signing_key = (app_secret + "&").encode("utf-8")
    signature = base64.b64encode(hmac.new(signing_key, encoded_string.encode("utf-8"), hashlib.sha1).digest()).decode("utf-8")
    
    headers = {
        "Host": "api.webull.com",
        "x-app-key": app_key,
        "x-timestamp": timestamp,
        "x-signature-nonce": nonce,
        "x-signature-algorithm": "HMAC-SHA1",
        "x-signature-version": "1.0",
        "x-signature": signature,
        "x-version": "v2",
        "Content-Type": "application/json"
    }
    
    async with httpx.AsyncClient() as client:
        res = await client.post(url, content=body_str, headers=headers)
        print(f"Status: {res.status_code}")
        print(f"Response: {res.text}")

if __name__ == "__main__":
    asyncio.run(check_token_status())
