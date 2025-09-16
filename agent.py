import requests
import google.generativeai as genai
from requests.auth import HTTPBasicAuth
import json
import os
from datetime import datetime, timedelta
import logging
import traceback

# Set up logging for better debugging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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

# Key for the Attendance Report API
ATTENDANCE_API_KEY = "6558717cbd5130b5463fba577d39ea6ebdacf9719917fc8facb4c2e637e810087d7fb5437cce65d12816a0215150a2198a2a853840883106fa6772a25a507565"

# --- Gemini API Configuration ---
def setup_gemini_api():
    """Setup Gemini API with proper error handling"""
    try:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            logger.error("GEMINI_API_KEY environment variable not set")
            print("="*50)
            print("ERROR: GEMINI_API_KEY environment variable not set.")
            print("Please set your API key: export GEMINI_API_KEY='your_key_here'")
            print("="*50)
            return False
        
        genai.configure(api_key=api_key)
        logger.info("Gemini API configured successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to configure Gemini API: {e}")
        return False

# ==== 2. UTILITY FUNCTIONS ====

def validate_date_format(date_string: str) -> bool:
    """Validate if date is in YYYY-MM-DD format"""
    try:
        datetime.strptime(date_string, '%Y-%m-%d')
        return True
    except ValueError:
        return False

def validate_employee_id(employee_id: str) -> bool:
    """Basic validation for employee ID"""
    if not employee_id or not isinstance(employee_id, str):
        return False
    stripped_id = employee_id.strip()
    if len(stripped_id) < 3:
        return False
    return True

def convert_date_format(date_string: str, from_format: str = '%Y-%m-%d', to_format: str = '%d-%m-%Y') -> str:
    """Convert date from one format to another"""
    try:
        date_obj = datetime.strptime(date_string, from_format)
        return date_obj.strftime(to_format)
    except ValueError as e:
        logger.error(f"Date conversion failed: {e}")
        raise ValueError(f"Invalid date format: {date_string}")

# ==== 3. PYTHON FUNCTIONS (THE "TOOLS") ====

def get_leave_report(employee_id: str, start_date: str, end_date: str) -> str:
    """
    Tool 1: Fetches the "action taken" leave report for a specific employee and date range.
    
    Args:
        employee_id: The employee number (e.g., "MMT6765")
        start_date: The query start date in YYYY-MM-DD format
        end_date: The query end date in YYYY-MM-DD format
        
    Returns:
        JSON string containing the leave report data or error message
    """
    logger.info(f"get_leave_report called with params: emp_id={employee_id}, start={start_date}, end={end_date}")
    
    try:
        # Input validation
        if not validate_employee_id(employee_id):
            return json.dumps({"error": "Invalid employee ID format"})
        
        if not validate_date_format(start_date):
            return json.dumps({"error": f"Invalid start_date format: {start_date}. Expected YYYY-MM-DD"})
        
        if not validate_date_format(end_date):
            return json.dumps({"error": f"Invalid end_date format: {end_date}. Expected YYYY-MM-DD"})
        
        # Check date logic
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        
        if start_dt > end_dt:
            return json.dumps({"error": "Start date cannot be after end date"})
        
        # Check if dates are not too far in the future
        today = datetime.now()
        if start_dt > today + timedelta(days=30):
            return json.dumps({"error": "Start date cannot be more than 30 days in the future"})
        
        # Convert dates to Darwinbox format (dd-MM-yyyy)
        from_str = convert_date_format(start_date)
        to_str = convert_date_format(end_date)
        
        logger.info(f"Converted dates: from={from_str}, to={to_str}")
        
        # API call setup
        url = f"{DOMAIN}/leavesactionapi/leaveActionTakenLeaves"
        
        payload = {
            "api_key": LEAVE_API_KEY,
            "from": from_str,
            "to": to_str,
            "action": "2",  # Action taken = 2 (approved leaves)
            "action_from": from_str,
            "employee_no": [employee_id.strip()]  # Ensure no whitespace
        }
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        logger.info(f"Making API request to: {url}")
        logger.info(f"Payload: {json.dumps(payload, indent=2)}")
        
        # Make API request with timeout and error handling
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            auth=HTTPBasicAuth(USERNAME, PASSWORD),
            timeout=30,  # Increased timeout
            verify=True  # SSL verification
        )
        
        logger.info(f"API Response Status: {response.status_code}")
        
        # Handle different response codes
        if response.status_code == 200:
            try:
                api_data = response.json()
                logger.info("Successfully retrieved leave report data")
                
                # Add some metadata to the response
                result = {
                    "status": "success",
                    "employee_id": employee_id,
                    "query_period": f"{start_date} to {end_date}",
                    "data": api_data,
                    "timestamp": datetime.now().isoformat()
                }
                
                return json.dumps(result, indent=2)
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {e}")
                return json.dumps({
                    "error": "Invalid JSON response from API",
                    "raw_response": response.text[:500]  # First 500 chars
                })
                
        elif response.status_code == 401:
            logger.error("Authentication failed")
            return json.dumps({"error": "Authentication failed. Please check credentials."})
            
        elif response.status_code == 404:
            logger.error("API endpoint not found")
            return json.dumps({"error": "API endpoint not found. Please check the URL."})
            
        elif response.status_code >= 500:
            logger.error(f"Server error: {response.status_code}")
            return json.dumps({"error": f"Server error: {response.status_code}. Please try again later."})
            
        else:
            logger.error(f"Unexpected status code: {response.status_code}")
            return json.dumps({
                "error": f"Unexpected response: {response.status_code}",
                "response_text": response.text[:500]
            })

    except requests.exceptions.Timeout:
        logger.error("Request timed out")
        return json.dumps({"error": "Request timed out. Please try again."})
        
    except requests.exceptions.ConnectionError:
        logger.error("Connection error")
        return json.dumps({"error": "Unable to connect to Darwinbox API. Please check your internet connection."})
        
    except requests.exceptions.HTTPError as http_err:
        logger.error(f"HTTP error: {http_err}")
        return json.dumps({"error": f"HTTP error: {http_err}"})
        
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return json.dumps({"error": f"An unexpected error occurred: {str(e)}"})

def get_employee_info(employee_ids) -> str:
    """
    Tool 2: Fetches core master profile data for one or more employees.
    
    Args:
        employee_ids: A list of one or more employee numbers (e.g., ["MMT6765"])
        
    Returns:
        JSON string containing the employee data or error message
    """
    logger.info(f"get_employee_info called with params: employee_ids={employee_ids}")
    logger.info(f"employee_ids type: {type(employee_ids)}")
    
    try:
        # FIXED: Handle Gemini's RepeatedComposite type by converting to list
        if hasattr(employee_ids, '__iter__') and not isinstance(employee_ids, str):
            # Convert RepeatedComposite or other iterable to list
            employee_ids = list(employee_ids)
            logger.info(f"Converted employee_ids to list: {employee_ids}")
        
        # FIXED: Improved input validation with better logging
        if not employee_ids:
            logger.error("Empty employee_ids list provided")
            return json.dumps({"error": "Employee IDs list cannot be empty."})
        
        if not isinstance(employee_ids, list):
            logger.error(f"employee_ids is not a list, got: {type(employee_ids)}")
            return json.dumps({"error": "Employee IDs must be provided as a list."})
        
        # FIXED: More detailed validation with logging
        valid_ids = []
        for emp_id in employee_ids:
            if not emp_id or not isinstance(emp_id, str):
                logger.error(f"Invalid employee ID (not string or empty): {emp_id}")
                return json.dumps({"error": f"Invalid employee ID: {emp_id}. Must be a non-empty string."})
            
            stripped_id = emp_id.strip()
            if len(stripped_id) < 3:
                logger.error(f"Employee ID too short: '{stripped_id}' (length: {len(stripped_id)})")
                return json.dumps({"error": f"Invalid employee ID: '{stripped_id}'. Must be at least 3 characters long."})
            
            valid_ids.append(stripped_id)
        
        logger.info(f"Validated employee IDs: {valid_ids}")
        
        # API call setup - Using the exact URL from your working test
        url = f"{DOMAIN}/masterapi/employee"
        
        # Using the exact payload structure from your working test
        payload = {
            "api_key": EMP_API_KEY,
            "datasetKey": EMP_DATASET_KEY,  # Keep camelCase as in working test
            "employee_ids": valid_ids
        }
        
        # Simplified headers to match working test
        headers = {"Content-Type": "application/json"}
        
        logger.info(f"Making API request to: {url}")
        logger.info(f"Payload: {json.dumps(payload, indent=2)}")
        
        # Match the exact request structure from your working test
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            auth=HTTPBasicAuth(USERNAME, PASSWORD),
            timeout=15
        )
        
        logger.info(f"API Response Status: {response.status_code}")
        
        # Handle different response codes
        if response.status_code == 200:
            try:
                api_data = response.json()
                logger.info("Successfully retrieved employee info data")
                
                # Add some metadata to the response
                result = {
                    "status": "success",
                    "requested_employee_ids": employee_ids,
                    "data": api_data,
                    "timestamp": datetime.now().isoformat()
                }
                
                return json.dumps(result, indent=2)
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {e}")
                return json.dumps({
                    "error": "Invalid JSON response from API",
                    "raw_response": response.text[:500],
                    "status_code": response.status_code
                })
                
        elif response.status_code == 401:
            logger.error("Authentication failed")
            return json.dumps({
                "error": "Authentication failed. Please check credentials.",
                "raw_response": response.text[:200]
            })
            
        elif response.status_code == 404:
            logger.error("API endpoint not found")
            return json.dumps({
                "error": "API endpoint not found. Please check the URL.",
                "raw_response": response.text[:200]
            })
            
        elif response.status_code >= 500:
            logger.error(f"Server error: {response.status_code}")
            return json.dumps({
                "error": f"Server error: {response.status_code}. Please try again later.",
                "raw_response": response.text[:200]
            })
            
        else:
            logger.error(f"Unexpected status code: {response.status_code}")
            return json.dumps({
                "error": f"Unexpected response: {response.status_code}",
                "raw_response": response.text[:500],
                "status_code": response.status_code
            })

    except requests.exceptions.Timeout:
        logger.error("Request timed out")
        return json.dumps({"error": "Request timed out. Please try again."})
        
    except requests.exceptions.ConnectionError:
        logger.error("Connection error")
        return json.dumps({"error": "Unable to connect to Darwinbox API. Please check your internet connection."})
        
    except requests.exceptions.HTTPError as http_err:
        logger.error(f"HTTP error: {http_err}")
        return json.dumps({"error": f"HTTP error: {http_err}"})
        
    except Exception as e:
        logger.error(f"Unexpected error in get_employee_info: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return json.dumps({"error": f"An unexpected error occurred: {str(e)}"})

def get_attendance_report(employee_ids, from_date: str, to_date: str) -> str:
    """
    Tool 3: Fetches daily attendance roster data for one or more employees within a date range.
    
    Args:
        employee_ids: A list of one or more employee numbers (e.g., ["MMT6765", "EMP001"])
        from_date: Start date in YYYY-MM-DD format
        to_date: End date in YYYY-MM-DD format
        
    Returns:
        JSON string containing the attendance report data or error message
    """
    logger.info(f"get_attendance_report called with params: employee_ids={employee_ids}, from_date={from_date}, to_date={to_date}")
    logger.info(f"employee_ids type: {type(employee_ids)}")
    
    try:
        # Handle Gemini's RepeatedComposite type by converting to list
        if hasattr(employee_ids, '__iter__') and not isinstance(employee_ids, str):
            employee_ids = list(employee_ids)
            logger.info(f"Converted employee_ids to list: {employee_ids}")
        
        # Input validation for employee_ids
        if not employee_ids:
            logger.error("Empty employee_ids list provided")
            return json.dumps({"error": "Employee IDs list cannot be empty."})
        
        if not isinstance(employee_ids, list):
            logger.error(f"employee_ids is not a list, got: {type(employee_ids)}")
            return json.dumps({"error": "Employee IDs must be provided as a list."})
        
        # Validate each employee ID
        valid_ids = []
        for emp_id in employee_ids:
            if not emp_id or not isinstance(emp_id, str):
                logger.error(f"Invalid employee ID (not string or empty): {emp_id}")
                return json.dumps({"error": f"Invalid employee ID: {emp_id}. Must be a non-empty string."})
            
            stripped_id = emp_id.strip()
            if len(stripped_id) < 3:
                logger.error(f"Employee ID too short: '{stripped_id}' (length: {len(stripped_id)})")
                return json.dumps({"error": f"Invalid employee ID: '{stripped_id}'. Must be at least 3 characters long."})
            
            valid_ids.append(stripped_id)
        
        # Date validation
        if not validate_date_format(from_date):
            return json.dumps({"error": f"Invalid from_date format: {from_date}. Expected YYYY-MM-DD"})
        
        if not validate_date_format(to_date):
            return json.dumps({"error": f"Invalid to_date format: {to_date}. Expected YYYY-MM-DD"})
        
        # Check date logic
        start_dt = datetime.strptime(from_date, '%Y-%m-%d')
        end_dt = datetime.strptime(to_date, '%Y-%m-%d')
        
        if start_dt > end_dt:
            return json.dumps({"error": "From date cannot be after to date"})
        
        # Check if dates are not too far in the future
        today = datetime.now()
        if start_dt > today + timedelta(days=30):
            return json.dumps({"error": "From date cannot be more than 30 days in the future"})
        
        logger.info(f"Validated employee IDs: {valid_ids}")
        logger.info(f"Date range: {from_date} to {to_date}")
        
        # API call setup
        url = f"{DOMAIN}/attendanceDataApi/DailyAttendanceRoster"
        
        # Payload structure based on API documentation
        payload = {
            "api_key": ATTENDANCE_API_KEY,
            "emp_number_list": valid_ids,
            "from_date": from_date,  # API expects yyyy-mm-dd format
            "to_date": to_date       # API expects yyyy-mm-dd format
        }
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        logger.info(f"Making API request to: {url}")
        logger.info(f"Payload: {json.dumps(payload, indent=2)}")
        
        # Make API request with timeout and error handling
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            auth=HTTPBasicAuth(USERNAME, PASSWORD),
            timeout=30,
            verify=True
        )
        
        logger.info(f"API Response Status: {response.status_code}")
        
        # Handle different response codes
        if response.status_code == 200:
            try:
                api_data = response.json()
                logger.info("Successfully retrieved attendance report data")
                
                # Add some metadata to the response
                result = {
                    "status": "success",
                    "employee_ids": employee_ids,
                    "query_period": f"{from_date} to {to_date}",
                    "data": api_data,
                    "timestamp": datetime.now().isoformat()
                }
                
                return json.dumps(result, indent=2)
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {e}")
                return json.dumps({
                    "error": "Invalid JSON response from API",
                    "raw_response": response.text[:500],
                    "status_code": response.status_code
                })
                
        elif response.status_code == 401:
            logger.error("Authentication failed")
            return json.dumps({
                "error": "Authentication failed. Please check credentials.",
                "raw_response": response.text[:200]
            })
            
        elif response.status_code == 404:
            logger.error("API endpoint not found")
            return json.dumps({
                "error": "API endpoint not found. Please check the URL.",
                "raw_response": response.text[:200]
            })
            
        elif response.status_code >= 500:
            logger.error(f"Server error: {response.status_code}")
            return json.dumps({
                "error": f"Server error: {response.status_code}. Please try again later.",
                "raw_response": response.text[:200]
            })
            
        else:
            logger.error(f"Unexpected status code: {response.status_code}")
            return json.dumps({
                "error": f"Unexpected response: {response.status_code}",
                "raw_response": response.text[:500],
                "status_code": response.status_code
            })

    except requests.exceptions.Timeout:
        logger.error("Request timed out")
        return json.dumps({"error": "Request timed out. Please try again."})
        
    except requests.exceptions.ConnectionError:
        logger.error("Connection error")
        return json.dumps({"error": "Unable to connect to Darwinbox API. Please check your internet connection."})
        
    except requests.exceptions.HTTPError as http_err:
        logger.error(f"HTTP error: {http_err}")
        return json.dumps({"error": f"HTTP error: {http_err}"})
        
    except Exception as e:
        logger.error(f"Unexpected error in get_attendance_report: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return json.dumps({"error": f"An unexpected error occurred: {str(e)}"})

# ==== 4. GEMINI MODEL CONFIGURATION ====

def setup_gemini_model():
    """Setup Gemini model with tools and proper configuration"""
    
    # Tool definition for Gemini - Updated to include attendance report
    tools = [
        {
            "function_declarations": [
                {
                    "name": "get_leave_report",
                    "description": "Retrieves approved/actioned leave records for a specific employee within a date range. Use this when users ask about leaves, absences, or time-off for an employee.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "employee_id": {
                                "type": "STRING",
                                "description": "The unique employee identifier or number (e.g., 'MMT6765', 'EMP001')"
                            },
                            "start_date": {
                                "type": "STRING",
                                "description": "Start date for the query in YYYY-MM-DD format (e.g., '2024-01-01')"
                            },
                            "end_date": {
                                "type": "STRING",
                                "description": "End date for the query in YYYY-MM-DD format (e.g., '2024-12-31')"
                            }
                        },
                        "required": ["employee_id", "start_date", "end_date"]
                    }
                },
                {
                    "name": "get_employee_info",
                    "description": "Gets core master profile data for one or more employees, such as their manager, email, team, designation, or other profile details. Use this for 'who-is-who' questions.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "employee_ids": {
                                "type": "ARRAY",
                                "description": "A list of one or more employee numbers, e.g., ['MMT6765', 'EMP001']",
                                "items": {"type": "STRING"}
                            }
                        },
                        "required": ["employee_ids"]
                    }
                },
                {
                    "name": "get_attendance_report",
                    "description": "Retrieves daily attendance roster data for one or more employees within a date range. Use this when users ask about attendance, check-in/check-out times, work hours, or presence data.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "employee_ids": {
                                "type": "ARRAY",
                                "description": "A list of one or more employee numbers, e.g., ['MMT6765', 'EMP001']",
                                "items": {"type": "STRING"}
                            },
                            "from_date": {
                                "type": "STRING",
                                "description": "Start date for the attendance query in YYYY-MM-DD format (e.g., '2024-01-01')"
                            },
                            "to_date": {
                                "type": "STRING",
                                "description": "End date for the attendance query in YYYY-MM-DD format (e.g., '2024-12-31')"
                            }
                        },
                        "required": ["employee_ids", "from_date", "to_date"]
                    }
                }
            ]
        }
    ]
    
    # Enhanced system prompt with better context - Updated to include attendance
    today_str = datetime.now().strftime('%Y-%m-%d')
    system_prompt = f"""
You are an AI HR assistant for Darwinbox HRMS system. Today's date is {today_str}.

You have three main tools available:
1. get_leave_report: Use this for questions about employee leaves, absences, or time-off history
2. get_employee_info: Use this for questions about employee profiles, managers, emails, designations, teams, or other master data
3. get_attendance_report: Use this for questions about employee attendance, check-in/check-out times, work hours, presence data, or daily attendance roster

Key guidelines:
1. When users ask about leaves/absences, extract employee ID and date range, then use get_leave_report
2. When users ask about employee details (who is X's manager, what's X's email, etc.), use get_employee_info
3. When users ask about attendance, check-in times, work hours, presence, etc., use get_attendance_report
4. For date interpretation:
   - "last month" = previous calendar month
   - "this month" = current calendar month  
   - "last week" = previous 7 days
   - "this year" = current calendar year
5. Always validate that you have required parameters before calling tools
6. If information is missing, ask clarifying questions
7. When presenting results, summarize the data in a user-friendly format
8. Handle errors gracefully and explain what went wrong
9. Be helpful and conversational while remaining professional
10. For employee_info and attendance_report, you can query multiple employees at once if needed

Important: When you receive function responses, carefully parse the JSON data. Each function returns:
- status: "success" if API call worked
- data: Contains the actual API response with relevant information
- Look for specific data fields in each API response and extract the information the user requested

For attendance reports, look for fields like:
- Check-in/check-out times
- Working hours
- Attendance status
- Date-wise attendance data

Remember: All dates must be in YYYY-MM-DD format for API calls.
"""

    try:
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",  # Updated to newer model
            system_instruction=system_prompt,
            tools=tools,
            generation_config=genai.types.GenerationConfig(
                temperature=0.1,  # Low temperature for consistent responses
                top_p=0.8,
                top_k=40,
                max_output_tokens=2048,
            )
        )
        
        return model, tools
        
    except Exception as e:
        logger.error(f"Failed to setup Gemini model: {e}")
        return None, None

# ==== 5. CONVERSATION HANDLER ====

def handle_function_call(chat, fn_call, available_tools):
    """Handle function calls with proper error handling and Gemini type conversion"""
    try:
        fn_name = fn_call.name
        
        # FIXED: Properly convert Gemini's argument types to Python types
        args = {}
        for key, value in fn_call.args.items():
            # Handle RepeatedComposite (list-like) objects from Gemini
            if hasattr(value, '__iter__') and not isinstance(value, str):
                args[key] = list(value)  # Convert to regular Python list
            else:
                args[key] = value
        
        logger.info(f"Function call: {fn_name} with args: {args}")
        logger.info(f"Original args types: {[(k, type(v).__name__) for k, v in fn_call.args.items()]}")
        logger.info(f"Converted args types: {[(k, type(v).__name__) for k, v in args.items()]}")
        
        if fn_name in available_tools:
            # Call the actual Python function
            function_to_call = available_tools[fn_name]
            function_response_data = function_to_call(**args)
            
            logger.info(f"Function {fn_name} returned: {function_response_data[:200]}...")  # Log first 200 chars
            
            # Send function response back to model
            function_response = genai.protos.Part(
                function_response=genai.protos.FunctionResponse(
                    name=fn_name,
                    response={"content": function_response_data}
                )
            )
            
            response = chat.send_message([function_response])
            
            logger.info(f"Model response after function call: {response.text[:200]}...")
            return response.text
        else:
            return f"Error: Unknown function '{fn_name}' requested."
            
    except Exception as e:
        logger.error(f"Error handling function call: {e}")
        logger.error(f"Function name: {fn_name}")
        logger.error(f"Raw function call args: {dict(fn_call.args) if hasattr(fn_call, 'args') else 'No args'}")
        logger.error(f"Exception type: {type(e).__name__}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return f"Error executing function: {str(e)}"

# ==== 6. MAIN APPLICATION ====

def main():
    """Main application entry point"""
    print("="*60)
    print("🤖 DARWINBOX HR AGENT (With Attendance Report)")
    print("="*60)
    
    # Setup Gemini API
    if not setup_gemini_api():
        return
    
    # Setup model and tools
    model, tools = setup_gemini_model()
    if not model:
        print("Failed to initialize Gemini model. Exiting.")
        return
    
    # Tool mapping - Updated to include attendance report
    available_tools = {
        "get_leave_report": get_leave_report,
        "get_employee_info": get_employee_info,
        "get_attendance_report": get_attendance_report
    }
    
    # Start chat session
    try:
        chat = model.start_chat(enable_automatic_function_calling=False)
        logger.info("Chat session started successfully")
        
        print(f"📅 Today is {datetime.now().strftime('%Y-%m-%d')}")
        print("💡 Ask me about employee leave reports, employee information, or attendance data!")
        print("\nExample queries:")
        print("📋 Leave Reports:")
        print("• 'Show me leaves for employee MMT6765 in January 2024'")
        print("• 'How many leaves did EMP001 take last month?'")
        print("• 'Get leave report for MMT6765 from 2024-01-01 to 2024-03-31'")
        print("\n👥 Employee Information:")
        print("• 'Who is the manager for MMT6765?'")
        print("• 'What is the email address of employee EMP001?'")
        print("• 'Show me profile details for MMT6765'")
        print("• 'What is MMT6765's designation and team?'")
        print("\n⏰ Attendance Reports:")
        print("• 'Show me attendance for MMT6765 in January 2024'")
        print("• 'What were the check-in times for EMP001 last week?'")
        print("• 'Get attendance roster for MMT6765 from 2024-01-01 to 2024-01-31'")
        print("• 'How many hours did MMT6765 work yesterday?'")
        print("\n" + "="*60)
        
        # Test all APIs directly first
        print("\n🔧 Testing API connections...")
        
        # Test employee API
        test_result = get_employee_info(["MMT6765"])
        test_data = json.loads(test_result)
        if "error" in test_data:
            print(f"⚠️ Warning: Employee API test failed: {test_data['error']}")
        else:
            print("✅ Employee API test successful!")
        
        # Test attendance API (using a recent date range)
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        today = datetime.now().strftime('%Y-%m-%d')
        attendance_test_result = get_attendance_report(["MMT6765"], yesterday, today)
        attendance_test_data = json.loads(attendance_test_result)
        if "error" in attendance_test_data:
            print(f"⚠️ Warning: Attendance API test failed: {attendance_test_data['error']}")
        else:
            print("✅ Attendance API test successful!")
        
        # Conversation loop
        while True:
            try:
                user_input = input("\n👤 You: ").strip()
                
                if user_input.lower() in ["exit", "quit", "bye", "goodbye"]:
                    print("👋 Goodbye! Have a great day!")
                    break
                
                if not user_input:
                    print("🤖 Agent: Please ask me something about employee leave reports, employee information, or attendance data.")
                    continue
                
                # Send message to model
                response = chat.send_message(user_input)
                
                # Check if model wants to call a function
                if (response.candidates and 
                    response.candidates[0].content.parts and 
                    hasattr(response.candidates[0].content.parts[0], 'function_call') and
                    response.candidates[0].content.parts[0].function_call):
                    
                    fn_call = response.candidates[0].content.parts[0].function_call
                    result = handle_function_call(chat, fn_call, available_tools)
                    print(f"🤖 Agent: {result}")
                
                else:
                    # Regular conversation
                    if response.candidates and response.candidates[0].content.parts:
                        print(f"🤖 Agent: {response.candidates[0].content.parts[0].text}")
                    else:
                        print("🤖 Agent: I'm sorry, I didn't understand that. Could you please rephrase?")
                
            except KeyboardInterrupt:
                print("\n\n👋 Goodbye! (Interrupted by user)")
                break
                
            except Exception as e:
                logger.error(f"Error in conversation loop: {e}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                print(f"🤖 Agent: I encountered an error: {str(e)}. Please try again.")
    
    except Exception as e:
        logger.error(f"Failed to start chat session: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        print(f"Failed to initialize chat: {e}")

if __name__ == "__main__":
    main()