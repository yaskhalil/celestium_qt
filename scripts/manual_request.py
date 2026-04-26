import json
from webullsdkcore.client import ApiClient
from webullsdkcore.common.region import Region
from webullsdkcore.request import ApiRequest

your_app_key = "dbd57aedd92f789880c7741e0a7f3b28"
your_app_secret = "d73d1820ae93215c79275ea5ec6a9a5c"

client = ApiClient(your_app_key, your_app_secret, Region.US.value)

try:
    print("Trying manual request to /openapi/account/list via ApiRequest...")
    # ApiRequest(request_path, version=None, method='POST', ...)
    req = ApiRequest("/openapi/account/list", version="v2", method="GET")
    
    # get_response expects an ApiRequest object
    res = client.get_response(req)
    
    print(f"Status Code: {res.status_code}")
    print(f"Response Body: {res.text}")
    
    if res.status_code == 200:
        data = res.json()
        print(f"Parsed JSON: {json.dumps(data, indent=2)}")
except Exception as e:
    print(f"Error: {e}")
