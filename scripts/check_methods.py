import os
from webull.core.client import ApiClient
from webull.core.request import ApiRequest

async def check():
    api_client = ApiClient("key", "secret", "us")
    print(f"ApiClient Methods: {dir(api_client)}")

import asyncio
if __name__ == "__main__":
    asyncio.run(check())
