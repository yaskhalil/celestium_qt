import pytest
from src.execution.webull_client import WebullClient

def test_signature_generation():
    client = WebullClient(app_key="test_key", app_secret="test_secret")
    
    uri = "/api/v2/orders"
    params = {"symbol": "AAPL"}
    timestamp = "1713456000000"
    nonce = "test_nonce"
    
    # Manually trigger signature generation for testing
    signature = client._generate_signature(
        uri=uri,
        params=params,
        timestamp=timestamp,
        nonce=nonce
    )
    
    assert signature == "4krr1qiIfIZf4fxXb9p6JRYadwY="

def test_signature_with_body():
    # We should also test with a body to verify MD5 hashing
    client = WebullClient(app_key="test_key", app_secret="test_secret")
    
    uri = "/api/v2/orders"
    params = {}
    timestamp = "1713456000000"
    nonce = "test_nonce"
    body = '{"orderId": 123}'
    
    signature = client._generate_signature(
        uri=uri,
        params=params,
        timestamp=timestamp,
        nonce=nonce,
        body=body
    )
    assert signature == "/47jpEKqWFYlJihkPSuDvGOrib4="
