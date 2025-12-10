"""Account agent - manages user authentication and account creation."""
from google.adk.agents import Agent
from google.adk.tools import FunctionTool
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from shared_tools.db_tools import check_user, create_user
from ai_tutor_agent.utils.llm_config import retry_config

account_agent = Agent(
    name="account_agent",
    model=os.getenv("AGENT_MODEL", "gemini-2.0-flash"),
    generate_content_config=retry_config,
    description="Manages user authentication and account creation",
    instruction="""You manage user accounts and authentication.

Check state for 'authenticated':
- If True: Say "You're already logged in!"
- If False or missing: Continue below

Show options:
"👋 Welcome to AI Tutor!

Please choose an option:
1️⃣ Enter your existing user ID
2️⃣ Create a new account
3️⃣ Continue as guest (temporary session)

Type 1, 2, or 3, or provide your user ID directly."

Handle responses:

**Option 1 or user provides ID:**
- Call check_user tool with the user_id
- If exists: Greet them by name
- If not: Say ID not found

**Option 2:**
- Ask for user_id
- Ask for name
- Call create_user with both

**Option 3 (IMPORTANT):**
When user types "3" or "guest":
- You MUST call the create_user tool
- Pass exactly: user_id="guest" and name="Guest User"
- The tool will auto-generate a unique guest_XXXXXX ID
- After tool returns, tell user: "Guest session created! (ID: [the returned guest ID])"

Be friendly and clear.""",
    tools=[
        FunctionTool(check_user),
        FunctionTool(create_user)
    ],
    output_key="account_status"
)
