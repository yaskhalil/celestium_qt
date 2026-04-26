from webullsdkcore.client import ApiClient
from webullsdkcore.common.region import Region

app_key = "dbd57aedd92f789880c7741e0a7f3b28"
app_secret = "d73d1820ae93215c79275ea5ec6a9a5c"

client = ApiClient(app_key, app_secret, Region.US.value)

print("Methods in ApiClient:")
for attr in dir(client):
    if not attr.startswith("_"):
        print(f" - {attr}")
