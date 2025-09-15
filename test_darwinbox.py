import requests
from requests.auth import HTTPBasicAuth
import json

# ==== CONFIG ====
DOMAIN = "https://gommt.stage.darwinbox.io"
USERNAME = "Salesforce"
PASSWORD = "J&$a764%#$76"      # Using the password you just provided for Basic Auth

# --- Keys for the JSON Payload (from Ram's email) ---
LEAVE_API_KEY = "049f914e0cfe2518989efc0ebfc2d8b39572cedb0825dc274755d3fc93cc360425213dea9d1c3f76eaffe52b9a9fd5448c851d0c2c9d3765eb51d9847db4a627"

# === Parameters for the Leave Report ===
TEST_EMPLOYEE_ID = "MMT6765" # Using the same test employee

# ==== CORRECTED API CALL ====

# 1. Using the FULL URL path you provided
url = f"{DOMAIN}/leavesactionapi/leaveActionTakenLeaves"

# 2. UPDATED PAYLOAD: Using the exact structure and keys you just provided.
# This uses the 'dd-MM-yyyy' date format and includes the 'action' fields.
payload = {
    "api_key": LEAVE_API_KEY,
    "from": "23-09-2025",
    "to": "23-09-2025",
    "action": "2",
    "action_from": "01-09-2025",
    "employee_no": [TEST_EMPLOYEE_ID]
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
    
    # Try to print the JSON response, but handle errors if it's not valid JSON
    try:
        print("\nAs JSON:\n", resp.json())
    except requests.exceptions.JSONDecodeError:
        print("\nNote: Response was not valid JSON.")

except Exception as e:
    print("\n--- ERROR DURING REQUEST ---")
    print(e)

