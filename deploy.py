import os
import sys
import json
import logging
import requests
from datetime import datetime
from requests.auth import HTTPBasicAuth

# --- Vertex AI and ADK Imports ---
import vertexai
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from vertexai.preview.reasoning_engines import AdkApp
from vertexai import agent_engines

# ==============================================================================
# ==== 1. CONFIGURATION & SECRETS ====
# ==============================================================================
print("🚀 Starting Darwinbox HR Agent deployment process...")
load_dotenv() # Loads environment variables from a .env file

# --- Vertex AI Project Configuration ---
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-pro")

# --- Darwinbox API Credentials (loaded from environment variables) ---
# ❗️ SECURITY BEST PRACTICE: Store these in a .env file or a secret manager.
DOMAIN = os.getenv("DARWINBOX_DOMAIN")
USERNAME = os.getenv("DARWINBOX_USERNAME")
PASSWORD = os.getenv("DARWINBOX_PASSWORD")
LEAVE_API_KEY = os.getenv("DARWINBOX_LEAVE_API_KEY")
EMP_API_KEY = os.getenv("DARWINBOX_EMP_API_KEY")
EMP_DATASET_KEY = os.getenv("DARWINBOX_EMP_DATASET_KEY")
ATTENDANCE_API_KEY = os.getenv("DARWINBOX_ATTENDANCE_API_KEY")

# A GCS bucket is required for staging the agent artifacts during deployment.
# Ensure this bucket exists in your project.
STAGING_BUCKET = f"gs://{PROJECT_ID}-doing-engine-staging"

# --- Validation ---
if not all([PROJECT_ID, LOCATION, DOMAIN, USERNAME, PASSWORD, LEAVE_API_KEY, EMP_API_KEY, EMP_DATASET_KEY, ATTENDANCE_API_KEY]):
    print("❌ Error: Missing required environment variables. Please check your .env file.", file=sys.stderr)
    sys.exit(1)

print(f"✅ Configuration loaded for project '{PROJECT_ID}'")

# Initialize Vertex AI with the project, location, and staging bucket.
vertexai.init(project=PROJECT_ID, location=LOCATION, staging_bucket=STAGING_BUCKET)

# --- Logger Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ==============================================================================
# ==== 2. PYTHON FUNCTIONS (TOOLS) ====
# These are the functions the LLM Agent will call.
# Docstrings are crucial as they become the tool's description for the model.
# ==============================================================================
print("🛠️ Defining the Darwinbox tools...")

def convert_date_format(date_string: str, from_format: str = '%Y-%m-%d', to_format: str = '%d-%m-%Y') -> str:
    """Converts a date string from YYYY-MM-DD to DD-MM-YYYY format for the API."""
    try:
        date_obj = datetime.strptime(date_string, from_format)
        return date_obj.strftime(to_format)
    except ValueError:
        raise ValueError(f"Invalid date format: {date_string}. Expected YYYY-MM-DD.")

def get_leave_report(employee_id: str, start_date: str, end_date: str) -> str:
    """Retrieves approved leave records for a specific employee within a date range."""
    logger.info(f"Tool call: get_leave_report(emp_id={employee_id}, start={start_date}, end={end_date})")
    try:
        url = f"{DOMAIN}/leavesactionapi/leaveActionTakenLeaves"
        payload = {
            "api_key": LEAVE_API_KEY, "from": convert_date_format(start_date), "to": convert_date_format(end_date),
            "action": "2", "action_from": convert_date_format(start_date), "employee_no": [employee_id.strip()]
        }
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        response = requests.post(url, json=payload, headers=headers, auth=HTTPBasicAuth(USERNAME, PASSWORD), timeout=30)
        response.raise_for_status()
        return json.dumps(response.json(), indent=2)
    except Exception as e:
        logger.error(f"Error in get_leave_report: {e}")
        return json.dumps({"error": f"An unexpected error occurred: {str(e)}"})

def get_employee_info(employee_ids: list[str]) -> str:
    """Gets profile data for one or more specific employees using their exact employee IDs."""
    logger.info(f"Tool call: get_employee_info(employee_ids={employee_ids})")
    try:
        url = f"{DOMAIN}/masterapi/employee"
        payload = {"api_key": EMP_API_KEY, "datasetKey": EMP_DATASET_KEY, "employee_ids": employee_ids}
        headers = {"Content-Type": "application/json"}
        response = requests.post(url, json=payload, headers=headers, auth=HTTPBasicAuth(USERNAME, PASSWORD), timeout=15)
        response.raise_for_status()
        return json.dumps(response.json(), indent=2)
    except Exception as e:
        logger.error(f"Error in get_employee_info: {e}")
        return json.dumps({"error": f"An unexpected error occurred: {str(e)}"})

def get_all_employees() -> str:
    """Retrieves master data for ALL employees. Use this when you need to find an employee by name."""
    logger.info("Tool call: get_all_employees()")
    try:
        url = f"{DOMAIN}/masterapi/employee"
        payload = {"api_key": EMP_API_KEY, "datasetKey": EMP_DATASET_KEY}
        headers = {"Content-Type": "application/json"}
        response = requests.post(url, json=payload, headers=headers, auth=HTTPBasicAuth(USERNAME, PASSWORD), timeout=60)
        response.raise_for_status()
        return json.dumps(response.json(), indent=2)
    except Exception as e:
        logger.error(f"Error in get_all_employees: {e}")
        return json.dumps({"error": f"An unexpected error occurred: {str(e)}"})

def get_attendance_report(employee_ids: list[str], from_date: str, to_date: str) -> str:
    """Retrieves daily attendance data for employees within a date range."""
    logger.info(f"Tool call: get_attendance_report(emp_ids={employee_ids}, from={from_date}, to={to_date})")
    try:
        url = f"{DOMAIN}/attendanceDataApi/DailyAttendanceRoster"
        payload = {"api_key": ATTENDANCE_API_KEY, "emp_number_list": employee_ids, "from_date": from_date, "to_date": to_date}
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        response = requests.post(url, json=payload, headers=headers, auth=HTTPBasicAuth(USERNAME, PASSWORD), timeout=30)
        response.raise_for_status()
        return json.dumps(response.json(), indent=2)
    except Exception as e:
        logger.error(f"Error in get_attendance_report: {e}")
        return json.dumps({"error": f"An unexpected error occurred: {str(e)}"})

# ==============================================================================
# ==== 3. DEFINE YOUR AGENT ====
# ==============================================================================
print("🤖 Defining the Darwinbox Agent logic...")

# The ADK automatically creates schemas from the function docstrings and type hints.
darwinbox_tools = [
    get_leave_report,
    get_employee_info,
    get_all_employees,
    get_attendance_report,
]

# This is the system prompt that instructs the agent on how to behave.
today_str = datetime.now().strftime('%Y-%m-%d')
system_prompt = f"""You are an AI HR assistant for the Darwinbox HRMS. Today's date is {today_str}.
Your primary function is to use the available tools to answer user questions about employee leaves, profiles, and attendance.
**CRITICAL INSTRUCTIONS:**
1.  **Analyze the User's Goal:** Understand what the user wants to achieve.
2.  **ID vs. Name Distinction:** The tools `get_leave_report`, `get_employee_info`, and `get_attendance_report` require a precise `employee_id`. They DO NOT work with employee names.
3.  **Multi-Step Process for Names:** If a user asks a question using an employee's name (e.g., "what is the role of Sonli Garg?"), you MUST follow this two-step process:
    a. First, call the `get_all_employees` tool to retrieve the complete employee list.
    b. Second, once you have the data, search within that data for the requested name to find their details and answer the original question.
4.  **Parameter Extraction:** You must extract all required parameters (like `employee_id` and dates) from the user's query. If a date is missing, infer it from context (e.g., "last month"). If an ID is missing, follow the multi-step process for names.
5.  **Date Format:** All dates provided to tools MUST be in `YYYY-MM-DD` format.
6.  **Summarize Results:** Do not just dump raw JSON. Present the information from the tools in a clear, user-friendly format (e.g., a summary sentence or a markdown table).
"""

# Define the LlmAgent that will use the tools and instructions.
darwinbox_agent = LlmAgent(
    name="darwinbox_hr_agent",
    model=GEMINI_MODEL,
    instruction=system_prompt,
    tools=darwinbox_tools,
)
print("✅ Agent definition complete.")

# ==============================================================================
# ==== 4. PACKAGE AND DEPLOY ====
# ==============================================================================
print("📦 Packaging agent with AdkApp...")
app = AdkApp(
    agent=darwinbox_agent,
    enable_tracing=True, # Recommended for debugging
)

# Explicitly define all necessary Python packages for the deployment environment.
# This prevents dependency errors during startup.
deployment_requirements = [
    "google-cloud-aiplatform[agent_engines,adk]>=1.55.0",
    "google-adk>=0.1.0",
    "python-dotenv>=1.0.0",
    "requests>=2.31.0", # Added for your API calls
]

print("🚢 Deploying to Vertex AI Agent Engine... (This may take 15-20 minutes)")

try:
    # The create() function handles packaging, uploading, and deployment.
    remote_app = agent_engines.create(
        app,
        display_name="darwinbox-hr-agent",
        description="Agent to query Darwinbox for employee, leave, and attendance data",
        requirements=deployment_requirements
    )
    print("\n🎉 Deployment successful!")
    print("Agent Resource Name:", remote_app.resource_name)
    print(remote_app)

except Exception as e:
    print(f"\n❌ Deployment failed: {e}", file=sys.stderr)
    # You can add more detailed error inspection here if needed
    # For example, check for permission errors or invalid configurations.
    sys.exit(1)