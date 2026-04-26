from webullsdktrade.api import API
from webullsdkcore.client import ApiClient
from webullsdkcore.common.region import Region

your_app_key = "dbd57aedd92f789880c7741e0a7f3b28"
your_app_secret = "d73d1820ae93215c79275ea5ec6a9a5c"

# Initialize client
# Note: Using Region.US.value as the SDK usually expects the string ID
client = ApiClient(your_app_key, your_app_secret, Region.US.value)
api = API(client)

try:
    # Retrieve account list - Updated to v2 as per SDK inspection
    res = api.account_v2.get_account_list()
    
    if hasattr(res, 'status_code') and res.status_code == 200:
        accounts = res.json()
        # Your API Account ID is here
        api_account_id = accounts[0]['account_id']
        print(f"Your API Account ID: {api_account_id}")
    else:
        # If the SDK returns the object directly instead of a Response object
        accounts = res
        api_account_id = accounts[0]['account_id']
        print(f"Your API Account ID: {api_account_id}")
except AttributeError:
    print("Error: 'api.account' does not have 'get_account_list'.")
    print("Searching for similar methods in api.account...")
    print([m for m in dir(api.account) if not m.startswith("_")])
except Exception as e:
    print(f"An error occurred: {e}")
