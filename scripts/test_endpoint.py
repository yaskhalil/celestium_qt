from webullsdktrade.api import API
from webullsdkcore.client import ApiClient
from webullsdkcore.common.region import Region

your_app_key = "dbd57aedd92f789880c7741e0a7f3b28"
your_app_secret = "d73d1820ae93215c79275ea5ec6a9a5c"

client = ApiClient(your_app_key, your_app_secret, Region.US.value)
api = API(client)

try:
    print("Testing get_account_profile with dummy ID...")
    # This should return 401/403 or 'Account not found' if the endpoint is right
    res = api.account.get_account_profile(account_id="123456789")
    print(res)
except Exception as e:
    print(f"Result: {e}")
