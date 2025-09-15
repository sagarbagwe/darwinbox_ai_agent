import requests
import google.generativeai as genai
from requests.auth import HTTPBasicAuth
import json
import os
from datetime import datetime, timedelta
import logging

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
    if not employee_id or len(employee_id.strip()) < 3:
        return False
    return True

def validate_employee_ids(employee_ids: list) -> bool:
    """Validate list of employee IDs"""
    if not employee_ids or not isinstance(employee_ids, list):
        return False
    return all(validate_employee_id(emp_id) for emp_id in employee_ids)

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

def get_employee_info(employee_ids: list) -> str:
    """
    Tool 2: Fetches core master profile data for one or more employees.
    
    Args:
        employee_ids: A list of one or more employee numbers (e.g., ["MMT6765"])
        
    Returns:
        JSON string containing the employee data or error message
    """
    logger.info(f"get_employee_info called with params: employee_ids={employee_ids}")
    
    try:
        # Input validation
        if not validate_employee_ids(employee_ids):
            return json.dumps({"error": "Invalid employee IDs format. Must be a non-empty list of valid employee IDs."})
        
        # Clean employee IDs (remove whitespace)
        clean_employee_ids = [emp_id.strip() for emp_id in employee_ids]
        
        # API call setup - FIXED: Use the exact URL from your working test
        url = f"{DOMAIN}/masterapi/employee"
        
        # FIXED: Match the exact payload structure from your working test
        payload = {
            "api_key": EMP_API_KEY,
            "datasetKey": EMP_DATASET_KEY,  # Keep camelCase as in working test
            "employee_ids": clean_employee_ids
        }
        
        # FIXED: Simplified headers to match working test
        headers = {"Content-Type": "application/json"}
        
        logger.info(f"Making API request to: {url}")
        logger.info(f"Payload: {json.dumps(payload, indent=2)}")
        
        # FIXED: Match the exact request structure from your working test
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            auth=HTTPBasicAuth(USERNAME, PASSWORD),  # This matches your working test
            timeout=15  # Reduced timeout to match working test
        )
        
        logger.info(f"API Response Status: {response.status_code}")
        logger.info(f"Raw response text: {response.text[:500]}")  # Log first 500 chars
        
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
        return json.dumps({"error": f"An unexpected error occurred: {str(e)}"})

# ==== 4. GEMINI MODEL CONFIGURATION ====

def setup_gemini_model():
    """Setup Gemini model with tools and proper configuration"""
    
    # Tool definition for Gemini
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
                }
            ]
        }
    ]
    
    # Enhanced system prompt with better context
    today_str = datetime.now().strftime('%Y-%m-%d')
    system_prompt = f"""
You are an AI HR assistant for Darwinbox HRMS system. Today's date is {today_str}.

You have two main tools available:
1. get_leave_report: Use this for questions about employee leaves, absences, or time-off history
2. get_employee_info: Use this for questions about employee profiles, managers, emails, designations, teams, or other master data

Key guidelines:
1. When users ask about leaves/absences, extract employee ID and date range, then use get_leave_report
2. When users ask about employee details (who is X's manager, what's X's email, etc.), use get_employee_info
3. For date interpretation:
   - "last month" = previous calendar month
   - "this month" = current calendar month  
   - "last week" = previous 7 days
   - "this year" = current calendar year
4. Always validate that you have required parameters before calling tools
5. If information is missing, ask clarifying questions
6. When presenting results, summarize the data in a user-friendly format
7. Handle errors gracefully and explain what went wrong
8. Be helpful and conversational while remaining professional
9. For employee_info, you can query multiple employees at once if needed

Important: When you receive function responses, carefully parse the JSON data. The get_employee_info function returns:
- status: "success" if API call worked
- data: Contains the actual API response with employee information
- Look for "employee_data" array in the API response which contains employee details like:
  - full_name, company_email_id, direct_manager_name, band, designation, etc.

Always extract and present the specific information the user requested from the function response data.

Remember: All dates must be in YYYY-MM-DD format for the leave API call.
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
    """Handle function calls with proper error handling"""
    try:
        fn_name = fn_call.name
        args = dict(fn_call.args)
        
        logger.info(f"Function call: {fn_name} with args: {args}")
        
        if fn_name in available_tools:
            # Call the actual Python function
            function_to_call = available_tools[fn_name]
            function_response_data = function_to_call(**args)
            
            # Send function response back to model
            response = chat.send_message([
                genai.protos.Part(
                    function_response=genai.protos.FunctionResponse(
                        name=fn_name,
                        response={"content": function_response_data}
                    )
                )
            ])
            
            return response.text
        else:
            return f"Error: Unknown function '{fn_name}' requested."
            
    except Exception as e:
        logger.error(f"Error handling function call: {e}")
        return f"Error executing function: {str(e)}"

# ==== 6. MAIN APPLICATION ====

def main():
    """Main application entry point"""
    print("="*60)
    print("🤖 DARWINBOX HR AGENT (Fixed Employee API)")
    print("="*60)
    
    # Setup Gemini API
    if not setup_gemini_api():
        return
    
    # Setup model and tools
    model, tools = setup_gemini_model()
    if not model:
        print("Failed to initialize Gemini model. Exiting.")
        return
    
    # Tool mapping
    available_tools = {
        "get_leave_report": get_leave_report,
        "get_employee_info": get_employee_info
    }
    
    # Start chat session
    try:
        chat = model.start_chat(enable_automatic_function_calling=False)
        logger.info("Chat session started successfully")
        
        print(f"📅 Today is {datetime.now().strftime('%Y-%m-%d')}")
        print("💡 Ask me about employee leave reports or employee information!")
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
        print("\n" + "="*60)
        
        # Test the employee API directly first
        print("\n🔧 Testing employee API connection...")
        test_result = get_employee_info(["MMT6765"])
        test_data = json.loads(test_result)
        if "error" in test_data:
            print(f"⚠️ Warning: Employee API test failed: {test_data['error']}")
        else:
            print("✅ Employee API test successful!")
        
        # Conversation loop
        while True:
            try:
                user_input = input("\n👤 You: ").strip()
                
                if user_input.lower() in ["exit", "quit", "bye", "goodbye"]:
                    print("👋 Goodbye! Have a great day!")
                    break
                
                if not user_input:
                    print("🤖 Agent: Please ask me something about employee leave reports or employee information.")
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
                print(f"🤖 Agent: I encountered an error: {str(e)}. Please try again.")
    
    except Exception as e:
        logger.error(f"Failed to start chat session: {e}")
        print(f"Failed to initialize chat: {e}")

if __name__ == "__main__":
    main()