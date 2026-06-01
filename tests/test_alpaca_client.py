import pytest
import respx
import httpx
import polars as pl
from src.execution.alpaca_client import AlpacaClient

@pytest.fixture
def client():
    return AlpacaClient(api_key="test_key", secret_key="test_secret")

@pytest.mark.asyncio
@respx.mock
async def test_get_account(client):
    respx.get("https://paper-api.alpaca.markets/v2/account").mock(
        return_value=httpx.Response(200, json={"account_number": "12345"})
    )
    res = await client.get_account()
    assert res["account_number"] == "12345"

@pytest.mark.asyncio
@respx.mock
async def test_get_position(client):
    respx.get("https://paper-api.alpaca.markets/v2/positions/SPLG").mock(
        return_value=httpx.Response(200, json={"qty": "10"})
    )
    res = await client.get_position("SPLG")
    assert res == 10.0

@pytest.mark.asyncio
@respx.mock
async def test_get_position_not_found(client):
    respx.get("https://paper-api.alpaca.markets/v2/positions/SPLG").mock(
        return_value=httpx.Response(404)
    )
    res = await client.get_position("SPLG")
    assert res == 0.0

@pytest.mark.asyncio
@respx.mock
async def test_place_order(client):
    respx.post("https://paper-api.alpaca.markets/v2/orders").mock(
        return_value=httpx.Response(200, json={"id": "order_id_1"})
    )
    res = await client.place_order("SPLG", 5.0, "BUY", limit_price=60.0, order_type="limit")
    assert res["id"] == "order_id_1"

@pytest.mark.asyncio
@respx.mock
async def test_get_last_price(client):
    respx.get("https://data.alpaca.markets/v2/stocks/trades/latest").mock(
        return_value=httpx.Response(200, json={"trades": {"SPLG": {"p": 79.99}}})
    )
    res = await client.get_last_price("SPLG")
    assert res == 79.99

@pytest.mark.asyncio
@respx.mock
async def test_get_bars(client):
    respx.get("https://data.alpaca.markets/v2/stocks/bars").mock(
        return_value=httpx.Response(200, json={
            "bars": {
                "SPLG": [
                    {"t": "2026-06-01T10:00:00Z", "o": 79.5, "h": 80.0, "l": 79.0, "c": 79.8, "v": 1000}
                ]
            }
        })
    )
    res = await client.get_bars("SPLG")
    assert isinstance(res, pl.DataFrame)
    assert not res.is_empty()
    assert res["close"][0] == 79.8

@pytest.mark.asyncio
@respx.mock
async def test_request_204_no_content(client):
    # Tests safe handling of 204 No Content status
    respx.delete("https://paper-api.alpaca.markets/v2/orders").mock(
        return_value=httpx.Response(204)
    )
    res = await client._request("DELETE", "https://paper-api.alpaca.markets/v2/orders")
    assert res == {}
