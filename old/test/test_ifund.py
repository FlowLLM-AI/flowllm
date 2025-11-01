import requests
import json

requestURL = "https://quantapi.51ifind.com/api/v1/basic_data_service"
requestHeaders = {"Content-Type":"application/json","access_token":""}
formData = {"codes":"601899.SH","indipara":[{"indicator":"ths_main_businuess_stock","indiparams":["2025-09-17"]}]}

thsResponse = requests.post(url=requestURL,json=formData,headers=requestHeaders)
print(json.dumps(thsResponse.json(), ensure_ascii=False, indent=2))