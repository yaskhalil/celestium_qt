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

async def activate_token():
    app_key = os.getenv("WEBULL_APP_KEY")
    app_secret = os.getenv("WEBULL_APP_SECRET")
    
    if not app_key or not app_secret:
        print("Error: WEBULL_APP_KEY and WEBULL_APP_SECRET must be in .env")
        return

    async with httpx.AsyncClient(base_url="https://api.webull.com") as client:
        # 1. Create Token
        print("\n[1/3] Requesting new token...")
        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        nonce = str(uuid.uuid4())
        uri = "/openapi/auth/token/create"
        
        sign_params = {
            "x-app-key": app_key,
            "x-timestamp": timestamp,
            "x-signature-version": "1.0",
            "x-signature-algorithm": "HMAC-SHA1",
            "x-signature-nonce": nonce,
            "host": "api.webull.com"
        }
        sorted_params = "&".join([f"{k}={sign_params[k]}" for k in sorted(sign_params.keys())])
        
        body = {}
        body_str = json.dumps(body, separators=(',', ':'))
        body_md5 = hashlib.md5(body_str.encode("utf-8")).hexdigest().upper()
        
        string_to_sign = f"{uri}&{sorted_params}&{body_md5}"
        encoded_str = quote(string_to_sign, safe='')
        signature = base64.b64encode(hmac.new((app_secret + "&").encode("utf-8"), encoded_str.encode("utf-8"), hashlib.sha1).digest()).decode("utf-8")
        
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
        
        res = await client.post(uri, content=body_str, headers=headers)
        if res.status_code != 200:
            print(f"Failed to create token: {res.text}")
            return
            
        token_data = res.json()
        token = token_data.get("token")
        print(f"Token created: {token}")
        print("Status: PENDING")
        print("\n>>> CHECK YOUR PHONE FOR A WEBULL SMS CODE <<<")
        
        # 2. Input SMS Code
        code = input("\nEnter the SMS verification code: ").strip()
        
        # 3. Activate Token (Verify)
        print("\n[3/3] Activating token...")
        uri_verify = "/openapi/auth/token/verify"
        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        nonce = str(uuid.uuid4())
        
        # Verify body usually requires the token and the code
        verify_body = {"token": token, "code": code}
        verify_body_str = json.dumps(verify_body, separators=(',', ':'))
        verify_body_md5 = hashlib.md5(verify_body_str.encode("utf-8")).hexdigest().upper()
        
        # Re-sign for verify endpoint
        v_sign_params = {
            "x-app-key": app_key,
            "x-timestamp": timestamp,
            "x-signature-version": "1.0",
            "x-signature-algorithm": "HMAC-SHA1",
            "x-signature-nonce": nonce,
            "host": "api.webull.com"
        }
        v_sorted_params = "&".join([f"{k}={v_sign_params[k]}" for k in sorted(v_sign_params.keys())])
        v_string_to_sign = f"{uri_verify}&{v_sorted_params}&{verify_body_md5}"
        v_encoded_str = quote(v_string_to_sign, safe='')
        v_signature = base64.b64encode(hmac.new((app_secret + "&").encode("utf-8"), v_encoded_str.encode("utf-8"), hashlib.sha1).digest()).decode("utf-8")
        
        v_headers = {
            "Host": "api.webull.com",
            "x-app-key": app_key,
            "x-timestamp": timestamp,
            "x-signature-nonce": nonce,
            "x-signature-algorithm": "HMAC-SHA1",
            "x-signature-version": "1.0",
            "x-signature": v_signature,
            "x-version": "v2",
            "Content-Type": "application/json"
        }
        
        v_res = await client.post(uri_verify, content=verify_body_str, headers=v_headers)
        if v_res.status_code == 200:
            print("\nSUCCESS! Token is now NORMAL (Active).")
            print("Update your .env with:")
            print(f"WEBULL_ACCESS_TOKEN={token}")
        else:
            print(f"Activation failed: {v_res.text}")

if __name__ == "__main__":
    asyncio.run(activate_token())
