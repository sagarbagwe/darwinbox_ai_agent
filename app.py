import streamlit as st
import requests
import google.generativeai as genai
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

# ==== GEMINI SETUP ====
@st.cache_resource
def setup_gemini_model():
    """Setup Gemini model with caching"""
    try:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return None, "GEMINI_API_KEY environment variable not set"
        
        genai.configure(api_key=api_key)
        
        tools = [
            {
                "function_declarations": [
                    {
                        "name": "get_leave_report",
                        "description": "Retrieves approved/actioned leave records for a specific employee within a date range.",
                        "parameters": {
                            "type": "OBJECT",
                            "properties": {
                                "employee_id": {
                                    "type": "STRING",
                                    "description": "The unique employee identifier or number"
                                },
                                "start_date": {
                                    "type": "STRING",
                                    "description": "Start date in YYYY-MM-DD format"
                                },
                                "end_date": {
                                    "type": "STRING",
                                    "description": "End date in YYYY-MM-DD format"
                                }
                            },
                            "required": ["employee_id", "start_date", "end_date"]
                        }
                    },
                    {
                        "name": "get_employee_info",
                        "description": "Gets core master profile data for one or more employees.",
                        "parameters": {
                            "type": "OBJECT",
                            "properties": {
                                "employee_ids": {
                                    "type": "ARRAY",
                                    "description": "A list of employee numbers",
                                    "items": {"type": "STRING"}
                                }
                            },
                            "required": ["employee_ids"]
                        }
                    },
                    {
                        "name": "get_attendance_report",
                        "description": "Retrieves daily attendance roster data for employees within a date range.",
                        "parameters": {
                            "type": "OBJECT",
                            "properties": {
                                "employee_ids": {
                                    "type": "ARRAY",
                                    "description": "A list of employee numbers",
                                    "items": {"type": "STRING"}
                                },
                                "from_date": {
                                    "type": "STRING",
                                    "description": "Start date in YYYY-MM-DD format"
                                },
                                "to_date": {
                                    "type": "STRING",
                                    "description": "End date in YYYY-MM-DD format"
                                }
                            },
                            "required": ["employee_ids", "from_date", "to_date"]
                        }
                    }
                ]
            }
        ]
        
        system_prompt = f"""
        You are an AI HR assistant for Darwinbox HRMS system. Today's date is {datetime.now().strftime('%Y-%m-%d')}.
        
        You have three main tools available:
        1. get_leave_report: For questions about employee leaves, absences, or time-off history
        2. get_employee_info: For questions about employee profiles, managers, emails, designations, teams
        3. get_attendance_report: For questions about employee attendance, check-in/check-out times, work hours
        
        Always be helpful and provide clear, formatted responses. When presenting data, organize it in a user-friendly way.
        """
        
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            system_instruction=system_prompt,
            tools=tools,
            generation_config=genai.types.GenerationConfig(
                temperature=0.1,
                top_p=0.8,
                top_k=40,
                max_output_tokens=2048,
            )
        )
        
        return model, None
        
    except Exception as e:
        return None, str(e)

def handle_function_call(chat, fn_call):
    """Handle function calls from Gemini"""
    try:
        fn_name = fn_call.name
        
        # Convert Gemini args to Python args
        args = {}
        for key, value in fn_call.args.items():
            if hasattr(value, '__iter__') and not isinstance(value, str):
                args[key] = list(value)
            else:
                args[key] = value
        
        # Map function names to actual functions
        function_map = {
            "get_leave_report": get_leave_report,
            "get_employee_info": get_employee_info,
            "get_attendance_report": get_attendance_report
        }
        
        if fn_name in function_map:
            function_response_data = function_map[fn_name](**args)
            
            function_response = genai.protos.Part(
                function_response=genai.protos.FunctionResponse(
                    name=fn_name,
                    response={"content": json.dumps(function_response_data)}
                )
            )
            
            response = chat.send_message([function_response])
            return response.text
        else:
            return f"Error: Unknown function '{fn_name}' requested."
            
    except Exception as e:
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
        
        # API Status Check
        if st.button("🔍 Test API Connections"):
            with st.spinner("Testing APIs..."):
                # Test Employee API
                emp_result = get_employee_info(["MMT6765"])
                if "error" in emp_result:
                    st.error(f"Employee API: ❌ {emp_result['error']}")
                else:
                    st.success("Employee API: ✅ Working")
                
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
        if st.button("📋 Sample Leave Query"):
            st.session_state.sample_query = "Show me leaves for employee MMT6765 in January 2024"
        if st.button("👥 Sample Employee Query"):
            st.session_state.sample_query = "Who is the manager for MMT6765?"
        if st.button("⏰ Sample Attendance Query"):
            st.session_state.sample_query = "Show me attendance for MMT6765 last week"
    
    # Main content
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.header("💬 AI Assistant")
        
        # Initialize chat history
        if "messages" not in st.session_state:
            st.session_state.messages = []
        
        # Initialize Gemini model
        if "model" not in st.session_state:
            model, error = setup_gemini_model()
            if model:
                st.session_state.model = model
                st.session_state.chat = model.start_chat(enable_automatic_function_calling=False)
            else:
                st.error(f"Failed to initialize Gemini model: {error}")
                st.stop()
        
        # Display chat messages
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
        
        # Chat input
        query = st.chat_input("Ask me about leaves, employee info, or attendance...")
        
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
                            response.candidates[0].content.parts and 
                            hasattr(response.candidates[0].content.parts[0], 'function_call') and
                            response.candidates[0].content.parts[0].function_call):
                            
                            fn_call = response.candidates[0].content.parts[0].function_call
                            result = handle_function_call(st.session_state.chat, fn_call)
                            st.markdown(result)
                            st.session_state.messages.append({"role": "assistant", "content": result})
                        
                        else:
                            # Regular conversation
                            if response.candidates and response.candidates[0].content.parts:
                                response_text = response.candidates[0].content.parts[0].text
                                st.markdown(response_text)
                                st.session_state.messages.append({"role": "assistant", "content": response_text})
                            else:
                                error_msg = "I'm sorry, I didn't understand that. Could you please rephrase?"
                                st.markdown(error_msg)
                                st.session_state.messages.append({"role": "assistant", "content": error_msg})
                    
                    except Exception as e:
                        error_msg = f"An error occurred: {str(e)}"
                        st.error(error_msg)
                        st.session_state.messages.append({"role": "assistant", "content": error_msg})
    
    with col2:
        st.header("📊 Manual Tools")
        
        # Tool selection tabs
        tab1, tab2, tab3 = st.tabs(["📋 Leaves", "👥 Employee", "⏰ Attendance"])
        
        with tab1:
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
        
        with tab2:
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
        
        with tab3:
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
            🤖 Darwinbox HR Agent | Powered by Gemini AI
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