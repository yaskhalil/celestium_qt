import json
from webullsdktrade.api import API
from webullsdkcore.client import ApiClient
from webullsdkcore.common.region import Region

your_app_key = "dbd57aedd92f789880c7741e0a7f3b28"
your_app_secret = "d73d1820ae93215c79275ea5ec6a9a5c"

client = ApiClient(your_app_key, your_app_secret, Region.US.value)
api = API(client)

try:
    print("Testing get_order_history_request...")
    # Attempting to fetch history to find account_id in the records
    res = api.order_v2.get_order_history_request()
    print(json.dumps(res, indent=2))
except Exception as e:
    print(f"Error: {e}")
