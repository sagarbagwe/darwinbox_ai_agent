import streamlit as st
import requests
import vertexai
from vertexai.generative_models import GenerativeModel, Tool, FunctionDeclaration, Part
from requests.auth import HTTPBasicAuth
import json
import os
from datetime import datetime, timedelta
import logging
import traceback
import pandas as pd

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ==== STREAMLIT PAGE CONFIG ====
st.set_page_config(
    page_title="Darwinbox HR Agent",
    page_icon="🏢",
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
EMP_API_KEY = "429bdea4387c3cc0b5ecbc81eb8398ad0882a6ab0db078b226ee5481bc84cc78b6bedcdcc49c7a800bff1cce078183516a67ff8b61360078dc14d94bb29cc508"
EMP_DATASET_KEY = "f29b5257bb9c19b1794546952dc83c4577c02f9fb74e4a5c64ea21198afede83800cdea87553dce3a2bbb9bb5991d213d9169872c89601f077694e927e45c6ae"
ATTENDANCE_API_KEY = "6558717cbd5130b5463fba577d39ea6ebdacf9719917fc8facb4c2e637e810087d7fb5437cce65d12816a0215150a2198a2a853840883106fa6772a25a507565"

# ==== UTILITY FUNCTIONS ====
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

def search_employee_by_name(name: str) -> dict:
    """Search for employees by name (fuzzy matching)"""
    try:
        if not name or not isinstance(name, str):
            return {"error": "Name must be provided as a string"}
        
        search_name = name.strip().lower()
        if len(search_name) < 2:
            return {"error": "Name must be at least 2 characters long"}
        
        # First, get all employees
        all_employees_result = get_all_employees()
        if "error" in all_employees_result:
            return {"error": f"Failed to fetch employee directory: {all_employees_result['error']}"}
        
        employees_data = all_employees_result.get("data", {})
        if "data" not in employees_data:
            return {"error": "No employee data found"}
        
        employees_list = employees_data["data"]
        matching_employees = []
        
        # Debug: Log the first few employees to understand the data structure
        logger.info(f"Searching for: {search_name}")
        logger.info(f"Total employees to search: {len(employees_list)}")
        
        # Search through employees
        for employee in employees_list:
            # Get various name fields to search in - try different possible field names
            full_name = str(employee.get("full_name", employee.get("employee_name", employee.get("name", "")))).lower()
            first_name = str(employee.get("first_name", employee.get("firstName", ""))).lower()
            last_name = str(employee.get("last_name", employee.get("lastName", ""))).lower()
            preferred_name = str(employee.get("preferred_name", employee.get("preferredName", ""))).lower()
            
            # Create a list of all possible name variations to search
            name_fields = [full_name, first_name, last_name, preferred_name]
            name_fields = [field for field in name_fields if field and field != "none" and field != ""]
            
            # Split search name into parts for better matching
            search_parts = search_name.split()
            
            # Check if search name matches any name field
            match_found = False
            
            # Direct substring matching
            for field in name_fields:
                if search_name in field:
                    match_found = True
                    break
            
            # Part-by-part matching (for "sonali garg" matching "Sonali Garg")
            if not match_found and len(search_parts) > 1:
                for field in name_fields:
                    field_parts = field.split()
                    if all(any(search_part in field_part for field_part in field_parts) for search_part in search_parts):
                        match_found = True
                        break
            
            # Individual word matching
            if not match_found:
                for search_part in search_parts:
                    for field in name_fields:
                        if search_part in field or any(search_part in field_part for field_part in field.split()):
                            match_found = True
                            break
                    if match_found:
                        break
            
            if match_found:
                # Extract employee details with fallback field names
                employee_data = {
                    "employee_id": employee.get("employee_number", employee.get("employeeNumber", employee.get("emp_id", "N/A"))),
                    "full_name": employee.get("full_name", employee.get("employee_name", employee.get("name", "N/A"))),
                    "first_name": employee.get("first_name", employee.get("firstName", "N/A")),
                    "last_name": employee.get("last_name", employee.get("lastName", "N/A")),
                    "email": employee.get("company_email_id", employee.get("email", employee.get("companyEmail", "N/A"))),
                    "designation": employee.get("designation_name", employee.get("designation", employee.get("role", "N/A"))),
                    "department": employee.get("department_name", employee.get("department", employee.get("function", "N/A"))),
                    "office_city": employee.get("office_city", employee.get("city", employee.get("location", "N/A"))),
                    "employee_status": employee.get("employee_status", employee.get("status", "N/A")),
                    "company": employee.get("company_name", employee.get("company", "N/A")),
                    "joining_date": employee.get("date_of_joining", employee.get("joiningDate", "N/A"))
                }
                matching_employees.append(employee_data)
        
        logger.info(f"Found {len(matching_employees)} matches")
        
        if not matching_employees:
            return {
                "status": "no_matches",
                "search_query": name,
                "message": f"No employees found matching '{name}'. Please check the spelling or try a different name.",
                "debug_info": f"Searched through {len(employees_list)} employees"
            }
        
        return {
            "status": "success",
            "search_query": name,
            "matches_found": len(matching_employees),
            "employees": matching_employees,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Name search error: {str(e)}")
        return {"error": f"Name search failed: {str(e)}"}

def get_employee_details_by_name(name: str) -> dict:
    """Get detailed employee information by searching with name"""
    try:
        # First search for the employee by name
        search_result = search_employee_by_name(name)
        
        if "error" in search_result:
            return search_result
        
        if search_result["status"] == "no_matches":
            return search_result
        
        # If exactly one match, get detailed info
        if search_result["matches_found"] == 1:
            employee_id = search_result["employees"][0]["employee_id"]
            detailed_info = get_employee_info([employee_id])
            
            return {
                "status": "success",
                "search_query": name,
                "employee_found": search_result["employees"][0],
                "detailed_info": detailed_info,
                "timestamp": datetime.now().isoformat()
            }
        
        # If multiple matches, return the search results for user to choose
        else:
            return {
                "status": "multiple_matches",
                "search_query": name,
                "matches_found": search_result["matches_found"],
                "employees": search_result["employees"],
                "message": f"Found {search_result['matches_found']} employees matching '{name}'. Please specify which one you meant.",
                "timestamp": datetime.now().isoformat()
            }
            
    except Exception as e:
        return {"error": f"An unexpected error occurred: {str(e)}"}

# ==== API FUNCTIONS ====
def get_leave_report(employee_id: str, start_date: str, end_date: str) -> dict:
    """Fetch leave report for an employee"""
    try:
        if not validate_employee_id(employee_id):
            return {"error": "Invalid employee ID format"}
        
        if not validate_date_format(start_date) or not validate_date_format(end_date):
            return {"error": "Invalid date format. Expected YYYY-MM-DD"}
        
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        
        if start_dt > end_dt:
            return {"error": "Start date cannot be after end date"}
        
        from_str = convert_date_format(start_date)
        to_str = convert_date_format(end_date)
        
        url = f"{DOMAIN}/leavesactionapi/leaveActionTakenLeaves"
        
        payload = {
            "api_key": LEAVE_API_KEY,
            "from": from_str,
            "to": to_str,
            "action": "2",
            "action_from": from_str,
            "employee_no": [employee_id.strip()]
        }
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            auth=HTTPBasicAuth(USERNAME, PASSWORD),
            timeout=30,
            verify=True
        )
        
        if response.status_code == 200:
            try:
                api_data = response.json()
                return {
                    "status": "success",
                    "employee_id": employee_id,
                    "query_period": f"{start_date} to {end_date}",
                    "data": api_data,
                    "timestamp": datetime.now().isoformat()
                }
            except json.JSONDecodeError:
                return {"error": "Invalid JSON response from API"}
        else:
            return {"error": f"API request failed with status code: {response.status_code}"}
            
    except Exception as e:
        return {"error": f"An unexpected error occurred: {str(e)}"}

def get_employee_info(employee_ids: list) -> dict:
    """Fetch employee information"""
    try:
        if not employee_ids or not isinstance(employee_ids, list):
            return {"error": "Employee IDs must be provided as a list"}
        
        valid_ids = []
        for emp_id in employee_ids:
            if not validate_employee_id(emp_id):
                return {"error": f"Invalid employee ID: {emp_id}"}
            valid_ids.append(emp_id.strip())
        
        url = f"{DOMAIN}/masterapi/employee"
        
        payload = {
            "api_key": EMP_API_KEY,
            "datasetKey": EMP_DATASET_KEY,
            "employee_ids": valid_ids
        }
        
        headers = {"Content-Type": "application/json"}
        
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            auth=HTTPBasicAuth(USERNAME, PASSWORD),
            timeout=15
        )
        
        if response.status_code == 200:
            try:
                api_data = response.json()
                return {
                    "status": "success",
                    "requested_employee_ids": employee_ids,
                    "data": api_data,
                    "timestamp": datetime.now().isoformat()
                }
            except json.JSONDecodeError:
                return {"error": "Invalid JSON response from API"}
        else:
            return {"error": f"API request failed with status code: {response.status_code}"}
            
    except Exception as e:
        return {"error": f"An unexpected error occurred: {str(e)}"}

def get_all_employees() -> dict:
    """Fetch all employee master data from the organization"""
    try:
        url = f"{DOMAIN}/masterapi/employee"
        
        # Payload without employee_ids to get all employees
        payload = {
            "api_key": EMP_API_KEY,
            "datasetKey": EMP_DATASET_KEY
            # No employee_ids parameter = fetch all employees
        }
        
        headers = {"Content-Type": "application/json"}
        
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            auth=HTTPBasicAuth(USERNAME, PASSWORD),
            timeout=60  # Increased timeout for potentially large response
        )
        
        if response.status_code == 200:
            try:
                api_data = response.json()
                
                # Count employees for summary
                employee_count = 0
                if isinstance(api_data, dict) and "data" in api_data:
                    if isinstance(api_data["data"], list):
                        employee_count = len(api_data["data"])
                elif isinstance(api_data, list):
                    employee_count = len(api_data)
                
                return {
                    "status": "success",
                    "request_type": "all_employees",
                    "employee_count": employee_count,
                    "data": api_data,
                    "timestamp": datetime.now().isoformat()
                }
            except json.JSONDecodeError:
                return {"error": "Invalid JSON response from API"}
        else:
            return {"error": f"API request failed with status code: {response.status_code}"}
            
    except Exception as e:
        return {"error": f"An unexpected error occurred: {str(e)}"}

def get_attendance_report(employee_ids: list, from_date: str, to_date: str) -> dict:
    """Fetch attendance report for employees"""
    try:
        if not employee_ids or not isinstance(employee_ids, list):
            return {"error": "Employee IDs must be provided as a list"}
        
        valid_ids = []
        for emp_id in employee_ids:
            if not validate_employee_id(emp_id):
                return {"error": f"Invalid employee ID: {emp_id}"}
            valid_ids.append(emp_id.strip())
        
        if not validate_date_format(from_date) or not validate_date_format(to_date):
            return {"error": "Invalid date format. Expected YYYY-MM-DD"}
        
        start_dt = datetime.strptime(from_date, '%Y-%m-%d')
        end_dt = datetime.strptime(to_date, '%Y-%m-%d')
        
        if start_dt > end_dt:
            return {"error": "From date cannot be after to date"}
        
        url = f"{DOMAIN}/attendanceDataApi/DailyAttendanceRoster"
        
        payload = {
            "api_key": ATTENDANCE_API_KEY,
            "emp_number_list": valid_ids,
            "from_date": from_date,
            "to_date": to_date
        }
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            auth=HTTPBasicAuth(USERNAME, PASSWORD),
            timeout=30,
            verify=True
        )
        
        if response.status_code == 200:
            try:
                api_data = response.json()
                return {
                    "status": "success",
                    "employee_ids": employee_ids,
                    "query_period": f"{from_date} to {to_date}",
                    "data": api_data,
                    "timestamp": datetime.now().isoformat()
                }
            except json.JSONDecodeError:
                return {"error": "Invalid JSON response from API"}
        else:
            return {"error": f"API request failed with status code: {response.status_code}"}
            
    except Exception as e:
        return {"error": f"An unexpected error occurred: {str(e)}"}

# ==== VERTEX AI SETUP ====
@st.cache_resource
def setup_vertexai_model():
    """Setup Vertex AI model with caching"""
    try:
        # Initialize Vertex AI
        vertexai.init(project=PROJECT_ID, location=LOCATION)
        
        # Define function declarations for Vertex AI
        get_employee_details_by_name_func = FunctionDeclaration(
            name="get_employee_details_by_name",
            description="Get complete detailed employee information by searching with their name. This is the primary function to use when users ask for employee details by name. It combines name search with detailed profile data.",
            parameters={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The employee name to search for (can be first name, last name, or full name)"
                    }
                },
                "required": ["name"]
            }
        )
        
        search_employee_by_name_func = FunctionDeclaration(
            name="search_employee_by_name",
            description="Search for employees by their name to find employee IDs. Use this when you need to find multiple employees or just get basic search results.",
            parameters={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The employee name to search for (can be first name, last name, or full name)"
                    }
                },
                "required": ["name"]
            }
        )
        
        get_leave_report_func = FunctionDeclaration(
            name="get_leave_report",
            description="Retrieves approved/actioned leave records for a specific employee within a date range.",
            parameters={
                "type": "object",
                "properties": {
                    "employee_id": {
                        "type": "string",
                        "description": "The unique employee identifier or number"
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Start date in YYYY-MM-DD format"
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date in YYYY-MM-DD format"
                    }
                },
                "required": ["employee_id", "start_date", "end_date"]
            }
        )
        
        get_employee_info_func = FunctionDeclaration(
            name="get_employee_info",
            description="Gets core master profile data for one or more specific employees using their employee IDs.",
            parameters={
                "type": "object",
                "properties": {
                    "employee_ids": {
                        "type": "array",
                        "description": "A list of employee numbers",
                        "items": {"type": "string"}
                    }
                },
                "required": ["employee_ids"]
            }
        )
        
        get_all_employees_func = FunctionDeclaration(
            name="get_all_employees",
            description="Retrieves master data for ALL employees in the organization. Use this when users want to see all employees, get employee lists, count total employees, or search across the entire employee database.",
            parameters={
                "type": "object",
                "properties": {}
            }
        )
        
        get_attendance_report_func = FunctionDeclaration(
            name="get_attendance_report",
            description="Retrieves daily attendance roster data for employees within a date range.",
            parameters={
                "type": "object",
                "properties": {
                    "employee_ids": {
                        "type": "array",
                        "description": "A list of employee numbers",
                        "items": {"type": "string"}
                    },
                    "from_date": {
                        "type": "string",
                        "description": "Start date in YYYY-MM-DD format"
                    },
                    "to_date": {
                        "type": "string",
                        "description": "End date in YYYY-MM-DD format"
                    }
                },
                "required": ["employee_ids", "from_date", "to_date"]
            }
        )
        
        # Create tool with function declarations
        hr_tool = Tool(
            function_declarations=[
                get_employee_details_by_name_func,
                search_employee_by_name_func,
                get_leave_report_func,
                get_employee_info_func,
                get_all_employees_func,
                get_attendance_report_func
            ]
        )
        
        # System prompt
        system_instruction = f"""
        You are an AI HR assistant for Darwinbox HRMS system. Today's date is {datetime.now().strftime('%Y-%m-%d')}.
        
        You have six main tools available:
        1. get_employee_details_by_name: PRIMARY tool for when users ask for employee info by name (like "show me data of John Smith")
        2. search_employee_by_name: For finding employees when you need just search results or multiple matches
        3. get_leave_report: For questions about employee leaves, absences, or time-off history
        4. get_employee_info: For questions about specific employee profiles using employee IDs
        5. get_all_employees: For questions about ALL employees, employee lists, total employee count
        6. get_attendance_report: For questions about employee attendance, check-in/check-out times
        
        IMPORTANT: When users ask about an employee by name (like "Show me data of Sonali Garg" or "Who is John Smith"), 
        ALWAYS use get_employee_details_by_name first. This function will:
        - Search for the employee by name
        - If found uniquely, return complete detailed information
        - If multiple matches, show options for user to choose
        - Handle all the complexity of name searching and data retrieval
        
        Use get_employee_details_by_name when users ask:
        - "Show me data of [Name]"
        - "Show all details of [Name]"
        - "Who is [Name]?"
        - "Get info for [Name]"
        - "Find employee [Name]"
        
        Always be helpful and provide clear, formatted responses. When presenting data, organize it in a user-friendly way.
        """
        
        # Create the model
        model = GenerativeModel(
            model_name="gemini-2.5-pro",
            system_instruction=system_instruction,
            tools=[hr_tool],
            generation_config={
                "temperature": 0.1,
                "top_p": 0.8,
                "top_k": 40,
                "max_output_tokens": 2048,
            }
        )
        
        return model, None
        
    except Exception as e:
        logger.error(f"Vertex AI model setup error: {str(e)}")
        return None, str(e)

def handle_function_call(chat, function_call):
    """Handle function calls from Vertex AI"""
    try:
        function_name = function_call.name
        args = function_call.args
        
        # Map function names to actual functions
        function_map = {
            "get_employee_details_by_name": get_employee_details_by_name,
            "search_employee_by_name": search_employee_by_name,
            "get_leave_report": get_leave_report,
            "get_employee_info": get_employee_info,
            "get_all_employees": get_all_employees,
            "get_attendance_report": get_attendance_report
        }
        
        if function_name in function_map:
            # Convert args to dictionary if needed
            if hasattr(args, '__iter__'):
                kwargs = dict(args)
            else:
                kwargs = args
            
            # Handle functions with no arguments (like get_all_employees)
            if not kwargs:
                function_response_data = function_map[function_name]()
            else:
                function_response_data = function_map[function_name](**kwargs)
            
            # Create function response part
            function_response = Part.from_function_response(
                name=function_name,
                response={
                    "content": function_response_data
                }
            )
            
            # Send function response to continue the conversation
            response = chat.send_message(function_response)
            return response.text
        else:
            return f"Error: Unknown function '{function_name}' requested."
            
    except Exception as e:
        logger.error(f"Function call error: {str(e)}")
        return f"Error executing function: {str(e)}"

# ==== STREAMLIT APP ====
def main():
    """Main Streamlit application"""
    
    # Header
    st.title("🏢 Darwinbox HR Agent")
    st.markdown("---")
    
    # Sidebar
    with st.sidebar:
        st.header("🔧 Configuration")
        
        # Show Vertex AI configuration
        st.info(f"**Vertex AI Configuration**\n\nProject ID: `{PROJECT_ID}`\n\nLocation: `{LOCATION}`")
        
        # API Status Check
        if st.button("🔍 Test API Connections"):
            with st.spinner("Testing APIs..."):
                # Test Employee API
                emp_result = get_employee_info(["MMT6765"])
                if "error" in emp_result:
                    st.error(f"Employee API: ❌ {emp_result['error']}")
                else:
                    st.success("Employee API: ✅ Working")
                
                # Test All Employees API
                with st.spinner("Testing All Employees API (may take longer)..."):
                    all_emp_result = get_all_employees()
                    if "error" in all_emp_result:
                        st.error(f"All Employees API: ❌ {all_emp_result['error']}")
                    else:
                        emp_count = all_emp_result.get("employee_count", "unknown")
                        st.success(f"All Employees API: ✅ Working ({emp_count} employees found)")
                
                # Test Name Search
                name_search_result = search_employee_by_name("Sonali")
                if "error" in name_search_result:
                    st.error(f"Name Search: ❌ {name_search_result['error']}")
                else:
                    matches = name_search_result.get("matches_found", 0)
                    st.success(f"Name Search: ✅ Working ({matches} matches for 'Sonali')")
                
                # Test Attendance API
                yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
                today = datetime.now().strftime('%Y-%m-%d')
                att_result = get_attendance_report(["MMT6765"], yesterday, today)
                if "error" in att_result:
                    st.error(f"Attendance API: ❌ {att_result['error']}")
                else:
                    st.success("Attendance API: ✅ Working")
        
        st.markdown("---")
        st.markdown("**Quick Actions:**")
        if st.button("🔍 Search by Name"):
            st.session_state.sample_query = "Show me data of Sonali Garg"
        if st.button("📋 Sample Leave Query"):
            st.session_state.sample_query = "Show me leaves for employee MMT6765 in January 2024"
        if st.button("👥 Sample Employee Query"):
            st.session_state.sample_query = "Who is the manager for MMT6765?"
        if st.button("🏢 Sample All Employees Query"):
            st.session_state.sample_query = "How many employees do we have in total?"
        if st.button("⏰ Sample Attendance Query"):
            st.session_state.sample_query = "Show me attendance for MMT6765 last week"
    
    # Main content
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.header("💬 AI Assistant")
        
        # Initialize chat history
        if "messages" not in st.session_state:
            st.session_state.messages = []
        
        # Initialize Vertex AI model
        if "model" not in st.session_state:
            model, error = setup_vertexai_model()
            if model:
                st.session_state.model = model
                st.session_state.chat = model.start_chat()
            else:
                st.error(f"Failed to initialize Vertex AI model: {error}")
                st.stop()
        
        # Display chat messages
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
        
        # Chat input
        query = st.chat_input("Ask me about employees by name, leaves, attendance, or any HR data...")
        
        # Handle sample query button
        if "sample_query" in st.session_state:
            query = st.session_state.sample_query
            del st.session_state.sample_query
        
        if query:
            # Add user message to chat history
            st.session_state.messages.append({"role": "user", "content": query})
            with st.chat_message("user"):
                st.markdown(query)
            
            # Get AI response
            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    try:
                        response = st.session_state.chat.send_message(query)
                        
                        # Check if model wants to call a function
                        if (response.candidates and 
                            response.candidates[0].content.parts):
                            
                            # Handle function calls
                            function_calls = []
                            text_parts = []
                            
                            for part in response.candidates[0].content.parts:
                                if hasattr(part, 'function_call') and part.function_call:
                                    function_calls.append(part.function_call)
                                elif hasattr(part, 'text') and part.text:
                                    text_parts.append(part.text)
                            
                            # Process function calls
                            if function_calls:
                                final_response = ""
                                for fn_call in function_calls:
                                    result = handle_function_call(st.session_state.chat, fn_call)
                                    final_response += result + "\n"
                                
                                st.markdown(final_response.strip())
                                st.session_state.messages.append({"role": "assistant", "content": final_response.strip()})
                            
                            # Process text responses
                            elif text_parts:
                                response_text = "\n".join(text_parts)
                                st.markdown(response_text)
                                st.session_state.messages.append({"role": "assistant", "content": response_text})
                            
                            else:
                                error_msg = "I'm sorry, I didn't understand that. Could you please rephrase?"
                                st.markdown(error_msg)
                                st.session_state.messages.append({"role": "assistant", "content": error_msg})
                        
                        else:
                            error_msg = "I'm sorry, I didn't get a proper response. Could you please try again?"
                            st.markdown(error_msg)
                            st.session_state.messages.append({"role": "assistant", "content": error_msg})
                    
                    except Exception as e:
                        error_msg = f"An error occurred: {str(e)}"
                        st.error(error_msg)
                        st.session_state.messages.append({"role": "assistant", "content": error_msg})
    
    with col2:
        st.header("📊 Manual Tools")
        
        # Tool selection tabs - Updated to include Name Search tab
        tab1, tab2, tab3, tab4, tab5 = st.tabs(["🔍 Name Search", "📋 Leaves", "👥 Employee", "🏢 All Employees", "⏰ Attendance"])
        
        with tab1:
            st.subheader("Search Employee by Name")
            with st.form("name_search_form"):
                emp_name = st.text_input("Employee Name", placeholder="e.g., Sonali Garg, John, Smith")
                st.info("💡 You can search using first name, last name, or full name. Partial matches are supported.")
                
                if st.form_submit_button("Search Employee"):
                    if emp_name:
                        with st.spinner("Searching for employee..."):
                            result = search_employee_by_name(emp_name)
                            if "error" in result:
                                st.error(result["error"])
                            elif result["status"] == "no_matches":
                                st.warning(result["message"])
                            else:
                                matches = result.get("matches_found", 0)
                                st.success(f"Found {matches} employee(s) matching '{emp_name}'")
                                
                                # Display results in a nice format
                                for i, employee in enumerate(result["employees"], 1):
                                    with st.expander(f"📋 {employee['full_name']} (ID: {employee['employee_id']})"):
                                        col_a, col_b = st.columns(2)
                                        with col_a:
                                            st.write(f"**Email:** {employee['email']}")
                                            st.write(f"**Designation:** {employee['designation']}")
                                            st.write(f"**Department:** {employee['department']}")
                                        with col_b:
                                            st.write(f"**Office City:** {employee['office_city']}")
                                            st.write(f"**Status:** {employee['employee_status']}")
                                            
                                            # Quick action buttons
                                            if st.button(f"Get Full Details", key=f"details_{i}"):
                                                detail_result = get_employee_info([employee['employee_id']])
                                                if "error" not in detail_result:
                                                    st.json(detail_result)
                                                else:
                                                    st.error(detail_result["error"])
                    else:
                        st.warning("Please enter an employee name")
        
        with tab2:
            st.subheader("Leave Report")
            with st.form("leave_form"):
                emp_id = st.text_input("Employee ID", placeholder="e.g., MMT6765")
                col_a, col_b = st.columns(2)
                with col_a:
                    start_date = st.date_input("Start Date", datetime.now() - timedelta(days=30))
                with col_b:
                    end_date = st.date_input("End Date", datetime.now())
                
                if st.form_submit_button("Get Leave Report"):
                    if emp_id:
                        with st.spinner("Fetching leave report..."):
                            result = get_leave_report(
                                emp_id,
                                start_date.strftime('%Y-%m-%d'),
                                end_date.strftime('%Y-%m-%d')
                            )
                            if "error" in result:
                                st.error(result["error"])
                            else:
                                st.success("Leave report retrieved successfully!")
                                st.json(result)
                    else:
                        st.warning("Please enter an employee ID")
        
        with tab3:
            st.subheader("Employee Information")
            with st.form("employee_form"):
                emp_ids_text = st.text_area(
                    "Employee IDs", 
                    placeholder="Enter one or more employee IDs (one per line)\ne.g.:\nMMT6765\nEMP001"
                )
                
                if st.form_submit_button("Get Employee Info"):
                    if emp_ids_text:
                        emp_ids = [id.strip() for id in emp_ids_text.split('\n') if id.strip()]
                        if emp_ids:
                            with st.spinner("Fetching employee information..."):
                                result = get_employee_info(emp_ids)
                                if "error" in result:
                                    st.error(result["error"])
                                else:
                                    st.success("Employee information retrieved successfully!")
                                    st.json(result)
                        else:
                            st.warning("Please enter at least one employee ID")
                    else:
                        st.warning("Please enter employee ID(s)")
        
        with tab4:
            st.subheader("All Employees Directory")
            with st.form("all_employees_form"):
                st.info("This will fetch data for ALL employees in the organization. This may take some time due to the large dataset.")
                
                if st.form_submit_button("Get All Employees"):
                    with st.spinner("Fetching all employee data... This may take a while..."):
                        result = get_all_employees()
                        if "error" in result:
                            st.error(result["error"])
                        else:
                            employee_count = result.get("employee_count", 0)
                            st.success(f"All employee data retrieved successfully! Found {employee_count} employees.")
                            
                            # Show summary before full data
                            st.subheader(f"📊 Summary: {employee_count} Total Employees")
                            
                            # Option to view full data or just summary
                            if st.checkbox("Show full employee data (may be large)"):
                                st.json(result)
                            else:
                                st.info("Check the box above to view the complete employee data.")
        
        with tab5:
            st.subheader("Attendance Report")
            with st.form("attendance_form"):
                emp_ids_att = st.text_area(
                    "Employee IDs", 
                    placeholder="Enter one or more employee IDs (one per line)\ne.g.:\nMMT6765\nEMP001"
                )
                col_c, col_d = st.columns(2)
                with col_c:
                    from_date = st.date_input("From Date", datetime.now() - timedelta(days=7))
                with col_d:
                    to_date = st.date_input("To Date", datetime.now())
                
                if st.form_submit_button("Get Attendance Report"):
                    if emp_ids_att:
                        emp_ids = [id.strip() for id in emp_ids_att.split('\n') if id.strip()]
                        if emp_ids:
                            with st.spinner("Fetching attendance report..."):
                                result = get_attendance_report(
                                    emp_ids,
                                    from_date.strftime('%Y-%m-%d'),
                                    to_date.strftime('%Y-%m-%d')
                                )
                                if "error" in result:
                                    st.error(result["error"])
                                else:
                                    st.success("Attendance report retrieved successfully!")
                                    st.json(result)
                        else:
                            st.warning("Please enter at least one employee ID")
                    else:
                        st.warning("Please enter employee ID(s)")
    
    # Footer
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: #666;'>
            🤖 Darwinbox HR Agent | Powered by Vertex AI | Now with Name Search Support
        </div>
        """, 
        unsafe_allow_html=True
    )
    
    # Clear chat button
    if st.button("🗑️ Clear Chat History"):
        st.session_state.messages = []
        st.rerun()

if __name__ == "__main__":
    main()