from webullsdktrade.api import API
from webullsdkcore.client import ApiClient
from webullsdkcore.common.region import Region

your_app_key = "dbd57aedd92f789880c7741e0a7f3b28"
your_app_secret = "d73d1820ae93215c79275ea5ec6a9a5c"

client = ApiClient(your_app_key, your_app_secret, Region.US.value)
api = API(client)

for obj_name in ["instrument", "trade_instrument"]:
    obj = getattr(api, obj_name)
    print(f"\nMethods in api.{obj_name}:")
    print([m for m in dir(obj) if not m.startswith("_")])
