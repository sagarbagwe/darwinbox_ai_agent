import streamlit as st
import requests
import google.generativeai as genai
from google.generativeai.types import generation_types
from requests.auth import HTTPBasicAuth
import json
import os
from datetime import datetime, timedelta
import logging
import traceback

# ==============================================================================
# ==== 0. STREAMLIT PAGE CONFIGURATION ====
# ==============================================================================

st.set_page_config(
    page_title="Darwinbox HR Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Set up logging for better debugging (will print to the console where Streamlit is running)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ==============================================================================
# ==== 1. CONFIGURATION ====
# ==============================================================================

# --- Darwinbox API Credentials ---
DOMAIN = "https://gommt.stage.darwinbox.io"
USERNAME = "Salesforce"
PASSWORD = "J&$a764%#$76"

# --- API Keys for Tools ---
LEAVE_API_KEY = "049f914e0cfe2518989efc0ebfc2d8b39572cedb0825dc274755d3fc93cc360425213dea9d1c3f76eaffe52b9a9fd5448c851d0c2c9d3765eb51d9847db4a627"
EMP_API_KEY = "429bdea4387c3cc0b5ecbc81eb8398ad0882a6ab0db078b226ee5481bc84cc78b6bedcdcc49c7a800bff1cce078183516a67ff8b61360078dc14d94bb29cc508"
EMP_DATASET_KEY = "f29b5257bb9c19b1794546952dc83c4577c02f9fb74e4a5c64ea21198afede83800cdea87553dce3a2bbb9bb5991d213d9169872c89601f077694e927e45c6ae"
ATTENDANCE_API_KEY = "6558717cbd5130b5463fba577d39ea6ebdacf9719917fc8facb4c2e637e810087d7fb5437cce65d12816a0215150a2198a2a853840883106fa6772a25a507565"

# ==============================================================================
# ==== 2. UTILITY FUNCTIONS ====
# ==============================================================================

def validate_date_format(date_string: str) -> bool:
    try:
        datetime.strptime(date_string, '%Y-%m-%d')
        return True
    except ValueError:
        return False

def validate_employee_id(employee_id: str) -> bool:
    if not employee_id or not isinstance(employee_id, str):
        return False
    stripped_id = employee_id.strip()
    if len(stripped_id) < 3:
        return False
    return True

def convert_date_format(date_string: str, from_format: str = '%Y-%m-%d', to_format: str = '%d-%m-%Y') -> str:
    try:
        date_obj = datetime.strptime(date_string, from_format)
        return date_obj.strftime(to_format)
    except ValueError as e:
        logger.error(f"Date conversion failed: {e}")
        raise ValueError(f"Invalid date format: {date_string}")

# ==============================================================================
# ==== 3. PYTHON FUNCTIONS (TOOLS) ====
# ==============================================================================

def get_leave_report(employee_id: str, start_date: str, end_date: str) -> str:
    # This function remains unchanged
    logger.info(f"get_leave_report called with params: emp_id={employee_id}, start={start_date}, end={end_date}")
    try:
        if not validate_employee_id(employee_id):
            return json.dumps({"error": "Invalid employee ID format"})
        if not validate_date_format(start_date):
            return json.dumps({"error": f"Invalid start_date format: {start_date}. Expected YYYY-MM-DD"})
        if not validate_date_format(end_date):
            return json.dumps({"error": f"Invalid end_date format: {end_date}. Expected YYYY-MM-DD"})
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        if start_dt > end_dt:
            return json.dumps({"error": "Start date cannot be after end date"})
        today = datetime.now()
        if start_dt > today + timedelta(days=30):
            return json.dumps({"error": "Start date cannot be more than 30 days in the future"})
        from_str = convert_date_format(start_date)
        to_str = convert_date_format(end_date)
        url = f"{DOMAIN}/leavesactionapi/leaveActionTakenLeaves"
        payload = {
            "api_key": LEAVE_API_KEY, "from": from_str, "to": to_str, "action": "2",
            "action_from": from_str, "employee_no": [employee_id.strip()]
        }
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        response = requests.post(url, json=payload, headers=headers, auth=HTTPBasicAuth(USERNAME, PASSWORD), timeout=30, verify=True)
        if response.status_code == 200:
            api_data = response.json()
            result = {"status": "success", "employee_id": employee_id, "query_period": f"{start_date} to {end_date}", "data": api_data, "timestamp": datetime.now().isoformat()}
            return json.dumps(result, indent=2)
        else:
            return json.dumps({"error": f"API Error {response.status_code}", "details": response.text[:500]})
    except Exception as e:
        logger.error(f"Error in get_leave_report: {e}\n{traceback.format_exc()}")
        return json.dumps({"error": f"An unexpected error occurred: {str(e)}"})

def get_employee_info(employee_ids) -> str:
    # This function remains unchanged
    logger.info(f"get_employee_info called with params: employee_ids={employee_ids}")
    try:
        if hasattr(employee_ids, '__iter__') and not isinstance(employee_ids, str):
            employee_ids = list(employee_ids)
        if not employee_ids or not isinstance(employee_ids, list):
            return json.dumps({"error": "Employee IDs must be a non-empty list."})
        valid_ids = [emp_id.strip() for emp_id in employee_ids if validate_employee_id(emp_id)]
        if len(valid_ids) != len(employee_ids):
             return json.dumps({"error": "One or more employee IDs are invalid."})
        url = f"{DOMAIN}/masterapi/employee"
        payload = {"api_key": EMP_API_KEY, "datasetKey": EMP_DATASET_KEY, "employee_ids": valid_ids}
        headers = {"Content-Type": "application/json"}
        response = requests.post(url, json=payload, headers=headers, auth=HTTPBasicAuth(USERNAME, PASSWORD), timeout=15)
        if response.status_code == 200:
            api_data = response.json()
            result = {"status": "success", "requested_employee_ids": employee_ids, "data": api_data, "timestamp": datetime.now().isoformat()}
            return json.dumps(result, indent=2)
        else:
            return json.dumps({"error": f"API Error {response.status_code}", "details": response.text[:500]})
    except Exception as e:
        logger.error(f"Error in get_employee_info: {e}\n{traceback.format_exc()}")
        return json.dumps({"error": f"An unexpected error occurred: {str(e)}"})

def get_all_employees() -> str:
    # This function remains unchanged
    logger.info("get_all_employees called")
    try:
        url = f"{DOMAIN}/masterapi/employee"
        payload = {"api_key": EMP_API_KEY, "datasetKey": EMP_DATASET_KEY}
        headers = {"Content-Type": "application/json"}
        response = requests.post(url, json=payload, headers=headers, auth=HTTPBasicAuth(USERNAME, PASSWORD), timeout=60)
        if response.status_code == 200:
            api_data = response.json()
            employee_count = len(api_data.get("data", [])) if isinstance(api_data, dict) else len(api_data)
            result = {"status": "success", "request_type": "all_employees", "employee_count": employee_count, "data": api_data, "timestamp": datetime.now().isoformat()}
            return json.dumps(result, indent=2)
        else:
            return json.dumps({"error": f"API Error {response.status_code}", "details": response.text[:500]})
    except Exception as e:
        logger.error(f"Error in get_all_employees: {e}\n{traceback.format_exc()}")
        return json.dumps({"error": f"An unexpected error occurred: {str(e)}"})

def get_attendance_report(employee_ids, from_date: str, to_date: str) -> str:
    # This function remains unchanged
    logger.info(f"get_attendance_report called: emp_ids={employee_ids}, from={from_date}, to={to_date}")
    try:
        if hasattr(employee_ids, '__iter__') and not isinstance(employee_ids, str):
            employee_ids = list(employee_ids)
        if not employee_ids or not isinstance(employee_ids, list):
            return json.dumps({"error": "Employee IDs must be a non-empty list."})
        valid_ids = [emp_id.strip() for emp_id in employee_ids if validate_employee_id(emp_id)]
        if len(valid_ids) != len(employee_ids):
             return json.dumps({"error": "One or more employee IDs are invalid."})
        if not validate_date_format(from_date) or not validate_date_format(to_date):
            return json.dumps({"error": "Invalid date format. Expected YYYY-MM-DD"})
        if datetime.strptime(from_date, '%Y-%m-%d') > datetime.strptime(to_date, '%Y-%m-%d'):
            return json.dumps({"error": "From date cannot be after to date"})
        url = f"{DOMAIN}/attendanceDataApi/DailyAttendanceRoster"
        payload = {"api_key": ATTENDANCE_API_KEY, "emp_number_list": valid_ids, "from_date": from_date, "to_date": to_date}
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        response = requests.post(url, json=payload, headers=headers, auth=HTTPBasicAuth(USERNAME, PASSWORD), timeout=30, verify=True)
        if response.status_code == 200:
            api_data = response.json()
            result = {"status": "success", "employee_ids": employee_ids, "query_period": f"{from_date} to {to_date}", "data": api_data, "timestamp": datetime.now().isoformat()}
            return json.dumps(result, indent=2)
        else:
            return json.dumps({"error": f"API Error {response.status_code}", "details": response.text[:500]})
    except Exception as e:
        logger.error(f"Error in get_attendance_report: {e}\n{traceback.format_exc()}")
        return json.dumps({"error": f"An unexpected error occurred: {str(e)}"})


# ==============================================================================
# ==== 4. GEMINI MODEL CONFIGURATION ====
# ==============================================================================

# ==============================================================================
# ==== 4. GEMINI MODEL CONFIGURATION ====
# ==============================================================================

@st.cache_resource
def setup_gemini_model():
    # This function is updated to improve name-based searches.
    try:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            st.error("GEMINI_API_KEY environment variable not set. Please set it and restart the app.", icon="🚨")
            st.stop()
        
        genai.configure(api_key=api_key)
        logger.info("Gemini API configured successfully")
    except Exception as e:
        st.error(f"Failed to configure Gemini API: {e}", icon="🚨")
        st.stop()
        
    tools = [
        {
            "function_declarations": [
                {
                    "name": "get_leave_report", "description": "Retrieves approved leave records for a specific employee within a date range.",
                    "parameters": {"type": "OBJECT", "properties": {"employee_id": {"type": "STRING"}, "start_date": {"type": "STRING"}, "end_date": {"type": "STRING"}}, "required": ["employee_id", "start_date", "end_date"]}
                },
                {
                    "name": "get_employee_info", "description": "Gets profile data for one or more specific employees using their exact employee IDs.",
                    "parameters": {"type": "OBJECT", "properties": {"employee_ids": {"type": "ARRAY", "items": {"type": "STRING"}}}, "required": ["employee_ids"]}
                },
                {
                    "name": "get_all_employees", "description": "Retrieves master data for ALL employees. Use this function when you need to find an employee by name or other attributes.",
                    "parameters": {"type": "OBJECT", "properties": {}}
                },
                {
                    "name": "get_attendance_report", "description": "Retrieves daily attendance data for employees within a date range.",
                    "parameters": {"type": "OBJECT", "properties": {"employee_ids": {"type": "ARRAY", "items": {"type": "STRING"}}, "from_date": {"type": "STRING"}, "to_date": {"type": "STRING"}}, "required": ["employee_ids", "from_date", "to_date"]}
                }
            ]
        }
    ]
    
    today_str = datetime.now().strftime('%Y-%m-%d')
    # --- START: MODIFIED SYSTEM PROMPT ---
    system_prompt = f"""You are an AI HR assistant for the Darwinbox HRMS. Today's date is {today_str}.
    Your primary function is to use the available tools to answer user questions about employee leaves, profiles, and attendance.
    **CRITICAL INSTRUCTIONS:**
    1.  **Analyze the User's Goal:** Understand what the user wants to achieve.
    2.  **ID vs. Name Distinction:** The tools `get_leave_report`, `get_employee_info`, and `get_attendance_report` require a precise `employee_id`. They DO NOT work with employee names.
    3.  **Multi-Step Process for Names:** If a user asks a question using an employee's name (e.g., "what is the role of Sonli Garg?") or any other non-ID attribute, you **MUST** follow this two-step process:
        a. First, call the `get_all_employees` tool to retrieve the complete employee list.
        b. Second, once you have the data, search within that data for the requested name to find their details and answer the original question.
    4.  **Parameter Extraction:** You must extract all required parameters (like `employee_id` and dates) from the user's query. If an ID is missing, follow the multi-step process above. If other details are missing, ask for clarification.
    5.  **Date Format:** All dates provided to tools MUST be in `YYYY-MM-DD` format.
    6.  **Summarize Results:** Do not just dump raw JSON. Present the information from the tools in a clear, user-friendly format (e.g., a summary sentence or a markdown table).
    """
    # --- END: MODIFIED SYSTEM PROMPT ---

    try:
        model = genai.GenerativeModel(
            model_name="gemini-2.5-pro",
            system_instruction=system_prompt,
            tools=tools,
            generation_config=genai.types.GenerationConfig(temperature=0.1)
        )
        return model
    except Exception as e:
        st.error(f"Failed to setup Gemini model: {e}", icon="🚨")
        st.stop()


# ==============================================================================
# ==== 5. STREAMLIT APPLICATION MAIN LOGIC ====
# ==============================================================================

def main():
    st.title("🤖 Darwinbox HR Agent")
    st.caption(f"Connected to Darwinbox | Today is {datetime.now().strftime('%B %d, %Y')}")

    # Sidebar remains unchanged
    with st.sidebar:
        st.header("📋 Agent Details")
        st.info("This agent connects to Darwinbox HRMS to fetch live data.")
        with st.expander("📝 Example Queries", expanded=True):
            st.markdown("""
            - `Show me leaves for MMT6765 in Jan 2024`
            - `Who is the manager for MMT6765?`
            - `Show me all employees`
            - `List the last 5 people who joined`
            - `Attendance for EMP001 last week?`
            """)
        st.header("🔧 API Connection Tests")
        if st.button("Run API Tests"):
            # This section remains unchanged
            with st.spinner("Testing API connections..."):
                test_results = ""
                emp_res = json.loads(get_employee_info(["MMT6765"]))
                emp_status = '✅ Success' if 'error' not in emp_res else f"❌ Failed: {emp_res['error']}"
                test_results += f"**Employee API:** {emp_status}\n\n"
                all_emp_res = json.loads(get_all_employees())
                if 'error' not in all_emp_res:
                    count = all_emp_res.get("employee_count", "N/A")
                    all_emp_status = f'✅ Success (Found {count} employees)'
                else:
                    all_emp_status = f"❌ Failed: {all_emp_res['error']}"
                test_results += f"**All Employees API:** {all_emp_status}\n\n"
                yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
                att_res = json.loads(get_attendance_report(["MMT6765"], yesterday, yesterday))
                att_status = '✅ Success' if 'error' not in att_res else f"❌ Failed: {att_res['error']}"
                test_results += f"**Attendance API:** {att_status}"
                st.success("API tests complete!")
                st.markdown(test_results)

    # Chat initialization remains unchanged
    model = setup_gemini_model()
    available_tools = {
        "get_leave_report": get_leave_report, "get_employee_info": get_employee_info,
        "get_all_employees": get_all_employees, "get_attendance_report": get_attendance_report,
    }
    if "chat_session" not in st.session_state:
        st.session_state.chat_session = model.start_chat(enable_automatic_function_calling=False)
    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "assistant", "content": "How can I help you today?"}]

    # Chat history display remains unchanged
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
    
    # --- HANDLE USER INPUT (WITH IMPROVED ERROR HANDLING) ---
    if prompt := st.chat_input("Ask about leaves, employees, attendance..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    response = st.session_state.chat_session.send_message(prompt)
                    
                    if (response.candidates and response.candidates[0].content.parts and 
                        hasattr(response.candidates[0].content.parts[0], 'function_call')):
                        
                        fn_call = response.candidates[0].content.parts[0].function_call
                        fn_name = fn_call.name
                        
                        if not fn_name:
                            final_text = "I'm sorry, I had trouble selecting the right tool. Could you please rephrase?"
                        else:
                            args = {}
                            if fn_call.args is not None:
                                args = {key: (list(value) if hasattr(value, '__iter__') and not isinstance(value, str) else value) for key, value in fn_call.args.items()}
                            
                            logger.info(f"Function call: {fn_name} with args: {args}")
                            
                            if fn_name in available_tools:
                                with st.spinner(f"Calling function `{fn_name}`..."):
                                    function_to_call = available_tools[fn_name]
                                    function_response_data = function_to_call(**args) if args else function_to_call()
                                
                                function_response = genai.protos.Part(
                                    function_response=genai.protos.FunctionResponse(
                                        name=fn_name,
                                        response={"content": function_response_data}
                                    )
                                )
                                with st.spinner("Processing API data..."):
                                    final_response = st.session_state.chat_session.send_message([function_response])
                                    final_text = final_response.text
                            else:
                                final_text = f"Error: Unknown function '{fn_name}' requested."
                    else:
                        final_text = response.text

                    st.markdown(final_text)
                    st.session_state.messages.append({"role": "assistant", "content": final_text})

                # --- START: IMPROVED EXCEPTION HANDLING ---
                except generation_types.StopCandidateException as e:
                    logger.error(f"Model generation stopped: {e}")
                    error_message = "I'm sorry, I had trouble processing that request. This can happen with complex queries. Could you please try rephrasing it?"
                    st.error(error_message, icon="⚠️")
                    st.session_state.messages.append({"role": "assistant", "content": error_message})
                
                except Exception as e:
                    logger.error(f"Error during conversation: {e}\n{traceback.format_exc()}")
                    error_message = f"An unexpected error occurred: {str(e)}. Please try again."
                    st.error(error_message, icon="🔥")
                    st.session_state.messages.append({"role": "assistant", "content": error_message})
                # --- END: IMPROVED EXCEPTION HANDLING ---

if __name__ == "__main__":
    main()