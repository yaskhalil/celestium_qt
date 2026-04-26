from webullsdkcore.client import ApiClient
from webullsdktrade.api import API
from webullsdkcore.common.region import Region

your_app_key = "dbd57aedd92f789880c7741e0a7f3b28"
your_app_secret = "d73d1820ae93215c79275ea5ec6a9a5c"
api_client = ApiClient(your_app_key, your_app_secret, Region.US.value)
api = API(api_client)

if __name__ == '__main__':
    try:
        print("Fetching app subscriptions...")
        res = api.account.get_app_subscriptions()
        account_id = None
        
        # Checking for response object attributes
        status_code = getattr(res, 'status_code', None)
        
        if status_code == 200:
            result = res.json()
            print('app subscriptions:', result)
            if isinstance(result, list) and len(result) > 0:
                account_id = result[0]['account_id']
                print("account id:", account_id)
            else:
                print("No subscriptions found in result.")
        else:
            print(f"Failed with status: {status_code}")
            # If the SDK returned the dict directly instead of a response object
            if isinstance(res, list) and len(res) > 0:
                account_id = res[0]['account_id']
                print("account id (direct):", account_id)
            else:
                print("Raw response:", res)

        if account_id is None:
            print("account id is null")
            
    except Exception as e:
        print(f"An error occurred: {e}")
