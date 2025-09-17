import streamlit as st
import requests
import vertexai
from vertexai.generative_models import GenerativeModel, Part
from requests.auth import HTTPBasicAuth
import json
from datetime import datetime, timedelta
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ==== STREAMLIT PAGE CONFIG ====
st.set_page_config(
    page_title="Darwinbox HR Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==== CONFIGURATION ====
DOMAIN = "https://gommt.stage.darwinbox.io"
USERNAME = "Salesforce"
PASSWORD = "J&$a764%#$76"

# Vertex AI Configuration
PROJECT_ID = "sadproject2025"
LOCATION = "us-central1"

# API Keys
LEAVE_API_KEY = "049f914e0cfe2518989efc0ebfc2d8b39572cedb0825dc274755d3fc93cc360425213dea9d1c3f76eaffe52b9a9fd5448c851d0c2c9d3765eb51d9847db4a627"
EMP_API_KEY = "429bdea4387c3cc0b5ecbc81eb8398ad0882a6ab0db078b226ee5481bc84cc78b6bedcdcc49c7a800bff1cce078183516a67ff8b61360078dc14d94bb2c508"
EMP_DATASET_KEY = "f29b5257bb9c19b1794546952dc83c4577c02f9fb74e4a5c64ea21198afede83800cdea87553dce3a2bbb9bb5991d213d9169872c89601f077694e927e45c6ae"
ATTENDANCE_API_KEY = "6558717cbd5130b5463fba577d39ea6ebdacf9719917fc8facb4c2e637e810087d7fb5437cce65d12816a0215150a2198a2a853840883106fa6772a25a507565"

# ==== UTILITY FUNCTIONS ====
def validate_date_format(date_string: str) -> bool:
    try:
        datetime.strptime(date_string, '%Y-%m-%d')
        return True
    except ValueError:
        return False

def validate_employee_id(employee_id: str) -> bool:
    if not employee_id or not isinstance(employee_id, str):
        return False
    return len(employee_id.strip()) >= 3

def convert_date_format(date_string: str, from_format: str = '%Y-%m-%d', to_format: str = '%d-%m-%Y') -> str:
    try:
        date_obj = datetime.strptime(date_string, from_format)
        return date_obj.strftime(to_format)
    except ValueError as e:
        logger.error(f"Date conversion failed: {e}")
        raise ValueError(f"Invalid date format: {date_string}")

# ==== API FUNCTIONS (TOOLS) ====

@st.cache_data(ttl=600) # Cache all-employee data for 10 minutes
def get_all_employees() -> dict:
    """Fetch all employee master data from the organization"""
    try:
        url = f"{DOMAIN}/masterapi/employee"
        payload = {"api_key": EMP_API_KEY, "datasetKey": EMP_DATASET_KEY}
        headers = {"Content-Type": "application/json"}
        response = requests.post(url, json=payload, headers=headers, auth=HTTPBasicAuth(USERNAME, PASSWORD), timeout=60)
        
        if response.status_code == 200:
            api_data = response.json()
            if isinstance(api_data, dict) and "employee_data" in api_data and isinstance(api_data["employee_data"], list):
                employee_list = api_data["employee_data"]
            else:
                 return {"error": "API response format was unexpected.", "data": api_data}

            return {
                "status": "success",
                "employee_count": len(employee_list),
                "employees": employee_list
            }
        else:
            return {"error": f"API request failed with status {response.status_code}", "details": response.text[:500]}
    except Exception as e:
        logger.error(f"Error in get_all_employees: {e}")
        return {"error": f"An unexpected error occurred: {str(e)}"}

def search_employee_by_name(name: str) -> dict:
    """Search for employees by name (fuzzy matching)"""
    try:
        if not name or not isinstance(name, str) or len(name.strip()) < 2:
            return {"error": "Name must be provided and be at least 2 characters long"}
        
        search_name = name.strip().lower()
        all_employees_result = get_all_employees()
        
        if "error" in all_employees_result:
            return {"error": f"Failed to fetch employee directory: {all_employees_result['error']}"}

        employees_list = all_employees_result.get("employees", [])
        matching_employees = [
            emp for emp in employees_list 
            if search_name in str(emp.get("full_name", "")).lower()
        ]
        
        if not matching_employees:
            return {
                "status": "no_matches",
                "message": f"No employees found matching '{name}'. Please check the spelling."
            }
        
        return {
            "status": "success",
            "matches_found": len(matching_employees),
            "employees": matching_employees
        }
    except Exception as e:
        logger.error(f"Name search error: {e}")
        return {"error": f"Name search failed: {str(e)}"}

def get_employee_info(employee_ids: list) -> dict:
    """Fetch and clean employee information for the AI."""
    try:
        if not isinstance(employee_ids, list) or not employee_ids:
            return {"error": "Employee IDs must be provided as a non-empty list."}
        
        valid_ids = [emp_id.strip() for emp_id in employee_ids if validate_employee_id(emp_id)]
        if not valid_ids:
             return {"error": "No valid employee IDs provided."}

        url = f"{DOMAIN}/masterapi/employee"
        payload = {"api_key": EMP_API_KEY, "datasetKey": EMP_DATASET_KEY, "employee_ids": valid_ids}
        headers = {"Content-Type": "application/json"}
        
        response = requests.post(url, json=payload, headers=headers, auth=HTTPBasicAuth(USERNAME, PASSWORD), timeout=15)
        
        if response.status_code == 200:
            api_data = response.json()
            if api_data.get("status") == 1 and "employee_data" in api_data and isinstance(api_data["employee_data"], list):
                employee_records = api_data["employee_data"]
                
                if not employee_records:
                    return {
                        "status": "not_found", 
                        "message": f"No employee was found with the ID(s): {valid_ids}. Please verify the ID."
                    }
                return { "status": "success", "employee_details": employee_records }
            else:
                return {"error": "API response format was unexpected.", "raw_response": api_data}
        else:
            return {"error": f"API request failed with status {response.status_code}", "details": response.text[:500]}
            
    except Exception as e:
        logger.error(f"Error in get_employee_info: {e}")
        return {"error": f"An unexpected error occurred: {str(e)}"}

def get_employee_details_by_name(name: str) -> dict:
    """Get detailed employee information by searching with a name."""
    try:
        search_result = search_employee_by_name(name)
        if "error" in search_result or search_result.get("status") == "no_matches":
            return search_result

        if search_result.get("matches_found") == 1:
            employee = search_result["employees"][0]
            employee_id = employee.get("employee_number")
            if not employee_id:
                return {"error": "Found employee but could not determine their ID.", "data": employee}
            return get_employee_info([employee_id])
        else:
            summaries = [
                {
                    "full_name": emp.get("full_name"),
                    "employee_id": emp.get("employee_number"),
                    "designation": emp.get("designation_name")
                } for emp in search_result.get("employees", [])
            ]
            return {
                "status": "multiple_matches",
                "message": f"Found {len(summaries)} employees matching '{name}'. Please ask the user to be more specific.",
                "employee_summaries": summaries
            }
    except Exception as e:
        logger.error(f"Error in get_employee_details_by_name: {e}")
        return {"error": f"An unexpected error occurred: {str(e)}"}

def get_leave_report(employee_id: str, start_date: str, end_date: str) -> dict:
    """Fetch leave report for an employee"""
    try:
        if not all([validate_employee_id(employee_id), validate_date_format(start_date), validate_date_format(end_date)]):
            return {"error": "Invalid input. Check employee ID and date formats (YYYY-MM-DD)."}
        if datetime.strptime(start_date, '%Y-%m-%d') > datetime.strptime(end_date, '%Y-%m-%d'):
            return {"error": "Start date cannot be after end date."}

        from_str, to_str = convert_date_format(start_date), convert_date_format(end_date)
        url = f"{DOMAIN}/leavesactionapi/leaveActionTakenLeaves"
        payload = {
            "api_key": LEAVE_API_KEY, "from": from_str, "to": to_str, "action": "2",
            "action_from": from_str, "employee_no": [employee_id.strip()]
        }
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        response = requests.post(url, json=payload, headers=headers, auth=HTTPBasicAuth(USERNAME, PASSWORD), timeout=30)
        
        if response.status_code == 200:
            return {"status": "success", "data": response.json()}
        else:
            return {"error": f"API request failed with status {response.status_code}", "details": response.text[:500]}
    except Exception as e:
        logger.error(f"Error in get_leave_report: {e}")
        return {"error": f"An unexpected error occurred: {str(e)}"}

def get_attendance_report(employee_ids: list, from_date: str, to_date: str) -> dict:
    """Fetch attendance report for employees"""
    try:
        if not isinstance(employee_ids, list) or not employee_ids:
            return {"error": "Employee IDs must be a non-empty list."}
        if not all([validate_date_format(from_date), validate_date_format(to_date)]):
            return {"error": "Invalid date format. Expected YYYY-MM-DD."}

        url = f"{DOMAIN}/attendanceDataApi/DailyAttendanceRoster"
        payload = {
            "api_key": ATTENDANCE_API_KEY, "emp_number_list": employee_ids,
            "from_date": from_date, "to_date": to_date
        }
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        response = requests.post(url, json=payload, headers=headers, auth=HTTPBasicAuth(USERNAME, PASSWORD), timeout=30)

        if response.status_code == 200:
            return {"status": "success", "data": response.json()}
        else:
            return {"error": f"API request failed with status {response.status_code}", "details": response.text[:500]}
    except Exception as e:
        logger.error(f"Error in get_attendance_report: {e}")
        return {"error": f"An unexpected error occurred: {str(e)}"}

# ==== VERTEX AI SETUP (CORRECTED) ====
@st.cache_resource
def setup_vertexai_model():
    """Setup Vertex AI model with caching"""
    try:
        vertexai.init(project=PROJECT_ID, location=LOCATION)

        system_instruction = f"""
        You are a helpful and expertly trained AI HR assistant for the Darwinbox HRMS system. Today's date is {datetime.now().strftime('%Y-%m-%d')}.

        Your primary purpose is to answer user questions by calling the available tools. Follow these rules strictly:

        1.  **Prioritize by Name:** When a user asks for information about an employee using their name (e.g., "Show me Sonali Garg's details", "Who is John Smith?"), YOU MUST ALWAYS use the `get_employee_details_by_name` tool first. This is your primary tool for name-based queries.

        2.  **Handle Tool Responses:**
            * If a tool returns `"status": "success"`, use the data provided to answer the user's question clearly and concisely. Format the information for readability (e.g., using bullet points).
            * If `get_employee_details_by_name` returns `"status": "multiple_matches"`, it means you found several people. You MUST inform the user and present the `employee_summaries` so they can clarify who they meant. For example: "I found a few people named John. Which one did you mean? John Smith (MMT123, Engineer) or John Doe (MMT456, Analyst)?"
            * If a tool returns `"status": "not_found"` or `"status": "no_matches"`, politely inform the user that the employee could not be found and suggest they check the name or ID.
            * If a tool returns an `"error"`, inform the user that you encountered a technical problem and could not retrieve the data. Do not show them the raw error message.

        3.  **Clarify Ambiguity:** If a user's request is unclear (e.g., "Show me leaves"), you must ask for the necessary information (like employee ID or name, and a date range) before calling a tool.

        4.  **Be Conversational:** Maintain a helpful and professional tone.
        """
        
        model = GenerativeModel(
            model_name="gemini-1.5-pro-001",
            system_instruction=system_instruction,
            # THE FIX: Pass the list of Python functions DIRECTLY to the tools parameter.
            tools=[
                get_employee_details_by_name,
                search_employee_by_name,
                get_leave_report,
                get_employee_info,
                get_all_employees,
                get_attendance_report,
            ],
        )
        return model
        
    except Exception as e:
        st.error(f"Fatal Error: Could not initialize Vertex AI. Please check your project configuration. Details: {e}")
        logger.error(f"Vertex AI model setup error: {e}")
        return None

# ==== STREAMLIT APP ====
def main():
    st.title("🤖 Darwinbox HR Agent")

    # Initialize model and chat history
    if "model" not in st.session_state:
        st.session_state.model = setup_vertexai_model()
    if "chat" not in st.session_state and st.session_state.model:
        st.session_state.chat = st.session_state.model.start_chat()
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Chat input
    if prompt := st.chat_input("Ask about employees, leaves, attendance..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            if not st.session_state.get("chat"):
                st.error("Chat session is not initialized. Please check the Vertex AI setup.")
                return

            with st.spinner("Thinking..."):
                try:
                    function_map = {
                        "get_employee_details_by_name": get_employee_details_by_name,
                        "search_employee_by_name": search_employee_by_name,
                        "get_leave_report": get_leave_report,
                        "get_employee_info": get_employee_info,
                        "get_all_employees": get_all_employees,
                        "get_attendance_report": get_attendance_report,
                    }

                    response = st.session_state.chat.send_message(prompt)
                    
                    while response.candidates[0].content.parts[0].function_call.name:
                        function_call = response.candidates[0].content.parts[0].function_call
                        tool_name = function_call.name
                        tool_args = dict(function_call.args)

                        st.info(f"🧠 Calling tool: `{tool_name}` with args: `{tool_args}`")

                        if tool_name in function_map:
                            tool_result = function_map[tool_name](**tool_args)
                        else:
                            tool_result = {"error": f"Unknown tool '{tool_name}' requested."}

                        response = st.session_state.chat.send_message(
                            Part.from_function_response(name=tool_name, response=tool_result)
                        )

                    final_answer = response.text
                    st.markdown(final_answer)
                    st.session_state.messages.append({"role": "assistant", "content": final_answer})

                except Exception as e:
                    error_message = f"An unexpected error occurred: {str(e)}"
                    st.error(error_message)
                    logger.error(f"Conversation loop error: {e}")
                    st.session_state.messages.append({"role": "assistant", "content": error_message})
    
    if st.button("Clear Chat"):
        st.session_state.messages = []
        if st.session_state.get("model"):
            st.session_state.chat = st.session_state.model.start_chat()
        st.rerun()

if __name__ == "__main__":
    main()