import requests
from requests.auth import HTTPBasicAuth
import json

# ==== CONFIG ====
DOMAIN = "https://gommt.stage.darwinbox.io"
USERNAME = "Salesforce"
PASSWORD = "J&$a764%#$76"      # Basic Auth password

# --- Keys for the JSON Payload (from Ram's email) ---
EMP_API_KEY = "429bdea4387c3cc0b5ecbc81eb8398ad0882a6ab0db078b226ee5481bc84cc78b6bedcdcc49c7a800bff1cce078183516a67ff8b61360078dc14d94bb29cc508"
EMP_DATASET_KEY = "f29b5257bb9c19b1794546952dc83c4577c02f9fb74e4a5c64ea21198afede83800cdea87553dce3a2bbb9bb5991d213d9169872c89601f077694e927e45c6ae"

# === Parameters for the API Call ===
TEST_EMPLOYEE_ID = "MMT6765" 

# ==== API CALL ====

# 1. Using the URL path you provided
url = f"{DOMAIN}/masterapi/employee"

# 2. Building the payload with the two required keys
payload = {
    "api_key": EMP_API_KEY,
    "datasetKey": EMP_DATASET_KEY, # Using datasetKey (camelCase) as in our agent
    "employee_ids": [TEST_EMPLOYEE_ID]
}

headers = {"Content-Type": "application/json"}

print(f"--- Attempting POST to: {url} ---")
print(f"Payload: {json.dumps(payload, indent=2)}\n")

try:
    resp = requests.post(
        url,
        json=payload,
        headers=headers,
        auth=HTTPBasicAuth(USERNAME, PASSWORD),  # Correctly handling Basic Auth
        timeout=15
    )
    
    # Print the result
    print("====================================")
    print(f"Request Status Code: {resp.status_code}")
    print("====================================")
    print("Raw Response Text:\n", resp.text)
    
    # Try to print the JSON response
    try:
        print("\nAs JSON:\n", resp.json())
    except requests.exceptions.JSONDecodeError:
        print("\nNote: Response was not valid JSON.")

except Exception as e:
    print("\n--- ERROR DURING REQUEST ---")
    print(e)
