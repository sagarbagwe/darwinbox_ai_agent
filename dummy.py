import requests
import google.generativeai as genai
from requests.auth import HTTPBasicAuth
import json
import os
from datetime import datetime

# ==== 1. CONFIGURATION ====

# --- Darwinbox API Credentials ---
DOMAIN = "https://gommt.stage.darwinbox.io"
USERNAME = "Salesforce"
PASSWORD = "J&$a764%#$76"

# --- API Keys for Tools ---
# Key for the Leave Report API
LEAVE_API_KEY = "049f914e0cfe2518989efc0ebfc2d8b39572cedb0825dc274755d3fc93cc360425213dea9d1c3f76eaffe52b9a9fd5448c851d0c2c9d3765eb51d9847db4a627"

# Keys for the Master Employee API
EMP_API_KEY = "429bdea4387c3cc0b5ecbc81eb8398ad0882a6ab0db078b226ee5481bc84cc78b6bedcdcc49c7a800bff1cce078183516a67ff8b61360078dc14d94bb29cc508"
EMP_DATASET_KEY = "f29b5257bb9c19b1794546952dc83c4577c02f9fb74e4a5c64ea21198afede83800cdea87553dce3a2bbb9bb5991d213d9169872c89601f077694e927e45c6ae"


# --- Gemini API Configuration ---
# Set your Gemini API Key as an environment variable
# export GEMINI_API_KEY="YOUR_GEMINI_KEY_HERE"
try:
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
except KeyError:
    print("="*50)
    print("ERROR: GEMINI_API_KEY environment variable not set.")
    print("Please set your API key: export GEMINI_API_KEY='your_key_here'")
    print("="*50)
    exit()

# ==== 2. PYTHON FUNCTIONS (THE "TOOLS") ====

def get_leave_report(employee_id: str, start_date: str, end_date: str) -> str:
    """
    Tool 1: Fetches the 'action taken' leave report for a specific employee and date range.
    Args:
        employee_id: The employee number (e.g., "MMT6765")
        start_date: The query start date in YYYY-MM-DD format.
        end_date: The query end date in YYYY-MM-DD format.
    """
    print(f"--- [Tool Called: get_leave_report] ---")
    print(f"Params: emp_id={employee_id}, start={start_date}, end={end_date}")
    
    try:
        # --- Date Conversion ---
        start_date_obj = datetime.strptime(start_date, '%Y-%m-%d')
        end_date_obj = datetime.strptime(end_date, '%Y-%m-%d')
        from_str = start_date_obj.strftime('%d-%m-%Y')
        to_str = end_date_obj.strftime('%d-%m-%Y')
        
        # --- API Call Setup ---
        url = f"{DOMAIN}/leavesactionapi/leaveActionTakenLeaves"
        payload = {
            "api_key": LEAVE_API_KEY,
            "from": from_str,
            "to": to_str,
            "action": "2",  # Hard-coding "action: 2" as per your API spec
            "action_from": from_str, 
            "employee_no": [employee_id] 
        }
        
        print(f"Calling Darwinbox API with payload:\n{json.dumps(payload, indent=2)}")
        headers = {"Content-Type": "application/json"}

        resp = requests.post(
            url,
            json=payload,
            headers=headers,
            auth=HTTPBasicAuth(USERNAME, PASSWORD),
            timeout=15
        )
        resp.raise_for_status() 
        api_data = resp.json()
        return json.dumps(api_data)

    except requests.exceptions.HTTPError as http_err:
        error_msg = f"HTTP error occurred: {http_err} - Response: {resp.text}"
        print(error_msg)
        return error_msg
    except Exception as e:
        error_msg = f"An unexpected error occurred: {e}"
        print(error_msg)
        return error_msg

def get_employee_info(employee_ids: list[str]) -> str:
    """
    Tool 2: Fetches core master profile data for one or more employees.
    Args:
        employee_ids: A list of one or more employee numbers (e.g., ["MMT6765"])
    """
    print(f"--- [Tool Called: get_employee_info] ---")
    print(f"Params: employee_ids={employee_ids}")
    
    try:
        url = f"{DOMAIN}/masterapi/employee"
        
        # Build the payload using the keys you provided
        payload = {
            "api_key": EMP_API_KEY,
            "datasetKey": EMP_DATASET_KEY, # Using 'datasetKey' (camelCase) as in your example
            "employee_ids": employee_ids
        }
        
        print(f"Calling Darwinbox API with payload:\n{json.dumps(payload, indent=2)}")
        headers = {"Content-Type": "application/json"}

        # Make the API request with dual-auth
        resp = requests.post(
            url,
            json=payload,
            headers=headers,
            auth=HTTPBasicAuth(USERNAME, PASSWORD),
            timeout=15
        )
        resp.raise_for_status()
        api_data = resp.json()
        
        # Return the raw JSON data as a string
        return json.dumps(api_data)

    except requests.exceptions.HTTPError as http_err:
        error_msg = f"HTTP error occurred: {http_err} - Response: {resp.text}"
        print(error_msg)
        return error_msg
    except Exception as e:
        error_msg = f"An unexpected error occurred: {e}"
        print(error_msg)
        return error_msg

# ==== 3. GEMINI MODEL CONFIGURATION (THE "BRAIN") ====

# Define the "tools" that the AI model knows about.
tools = [
    {
        "function_declarations": [
            {
                "name": "get_leave_report",
                "description": "Gets the list of all approved/actioned leaves for an employee between two specific dates.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "employee_id": {
                            "type": "STRING",
                            "description": "The unique employee number, e.g., 'MMT6765'"
                        },
                        "start_date": {
                            "type": "STRING",
                            "description": "The first date of the query range, in YYYY-MM-DD format."
                        },
                        "end_date": {
                            "type": "STRING",
                            "description": "The last date of the query range, in YYYY-MM-DD format."
                        }
                    },
                    "required": ["employee_id", "start_date", "end_date"]
                }
            },
            {
                "name": "get_employee_info",
                "description": "Gets core master profile data for one or more employees, such as their manager, email, team, or designation.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "employee_ids": {
                            "type": "ARRAY",
                            "description": "A list of one or more employee numbers, e.g., ['MMT6765']",
                            "items": {"type": "STRING"}
                        }
                    },
                    "required": ["employee_ids"]
                }
            }
        ]
    }
]

# Map the tool names (strings) to the actual Python functions
available_tools = {
    "get_leave_report": get_leave_report,
    "get_employee_info": get_employee_info
}

# Get today's date to give context to the AI
today_str = datetime.now().strftime('%Y-%m-%d')
system_prompt = f"""
You are an HR assistant agent for Darwinbox.
Today's date is {today_str}.
You have two tools available:
1. get_leave_report: Use this for any questions about an employee's leave history or dates.
2. get_employee_info: Use this for any 'who-is-who' questions, like finding a manager, email, designation, or core profile details.
You must extract all required parameters from the user's query to use a tool.
Do not make up information. If you do not have enough information, ask follow-up questions.
When you get data back, summarize it clearly for the user.
"""

# Initialize the generative model
model = genai.GenerativeModel(
    model_name="gemini-2.5-flash",
    system_instruction=system_prompt,
    tools=tools
)

# Start a chat session
chat = model.start_chat(enable_automatic_function_calling=False)

print("--- Darwinbox Agent Initialized (Leave + Employee Info) ---")
print(f"Today is {today_str}. Ask me about leaves or employee details.")
print("Examples: 'Who is the manager for MMT6765?' or 'How many leaves did MMT6765 take last month?'")

# ==== 4. CONVERSATION LOOP ====
while True:
    user_prompt = input("\nYou: ")
    if user_prompt.lower() in ["exit", "quit"]:
        break

    try:
        # --- Step 1: Send user query to the model ---
        response = chat.send_message(user_prompt)
        
        # Check if the model wants to call a function
        if response.candidates and response.candidates[0].content.parts[0].function_call:
            fn_call = response.candidates[0].content.parts[0].function_call
            fn_name = fn_call.name
            args = fn_call.args
            
            if fn_name in available_tools:
                # --- Step 2: Call the actual Python function ---
                function_to_call = available_tools[fn_name]
                
                # Dynamically call the function with the args the model provided
                function_response_data = function_to_call(**args)
                
                # --- Step 3: Send the function's output back to the model ---
                response = chat.send_message(
                    [
                        {"function_response": {
                            "name": fn_name,
                            "response": {"content": function_response_data}
                        }}
                    ]
                )
                
                # The model will now generate a natural language summary
                print(f"Agent: {response.candidates[0].content.parts[0].text}")
                
            else:
                print(f"Error: Model tried to call unknown function '{fn_name}'")

        else:
            # The model is just making small talk (e.g., "Hello") or asking for clarification
            print(f"Agent: {response.candidates[0].content.parts[0].text}")

    except Exception as e:
        print(f"An error occurred in the chat loop: {e}")
