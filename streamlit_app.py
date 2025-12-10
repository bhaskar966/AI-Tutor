import streamlit as st
import sys
import os
import uuid
import asyncio
from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.genai import types
from dotenv import load_dotenv

# Add current directory to path to ensure imports work
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
load_dotenv("ai_tutor_agent/.env", override=True)

from ai_tutor_agent.utils.db_manager import db_manager
from ai_tutor_agent.agent import root_agent

st.set_page_config(page_title="AI Tutor Platform", page_icon="🎓", layout="wide")

# Initialize session state
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "username" not in st.session_state:
    st.session_state.username = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

@st.cache_resource
def get_runner():
    session_service = InMemorySessionService()
    runner = Runner(
        app_name="ai_tutor",
        agent=root_agent,
        session_service=session_service
    )
    return runner

def login_page():
    st.title("🎓 AI Tutor Login")
    
    tab1, tab2, tab3 = st.tabs(["Login", "Sign Up", "Guest Access"])
    
    with tab1:
        with st.form("login_form"):
            user_id = st.text_input("User ID")
            submit = st.form_submit_button("Login")
            
            if submit and user_id:
                user = db_manager.get_user(user_id)
                if user:
                    st.session_state.authenticated = True
                    st.session_state.user_id = user["user_id"]
                    st.session_state.username = user["name"]
                    st.session_state.agent_notified = False  # Reset notification state
                    st.success(f"Welcome back, {user['name']}!")
                    st.rerun()
                else:
                    st.error("User ID not found.")
    
    with tab2:
        with st.form("signup_form"):
            new_user_id = st.text_input("Choose User ID")
            new_name = st.text_input("Your Name")
            submit = st.form_submit_button("Create Account")
            
            if submit and new_user_id and new_name:
                if db_manager.get_user(new_user_id):
                    st.error("User ID already exists.")
                else:
                    res = db_manager.create_user(new_user_id, new_name)
                    if res["success"]:
                        st.success("Account created! Please login.")
                    else:
                        st.error(f"Error: {res.get('error')}")
    
    with tab3:
        st.write("Continue as a guest to try out the platform.")
        if st.button("Continue as Guest"):
            guest_id = f"guest_{uuid.uuid4().hex[:6]}"
            res = db_manager.create_user(guest_id, "Guest User")
            if res["success"]:
                st.session_state.authenticated = True
                st.session_state.user_id = guest_id
                st.session_state.username = "Guest User"
                st.session_state.is_guest = True
                st.session_state.agent_notified = False  # Reset notification state
                st.rerun()

def chat_page():
    runner = get_runner()
    
    # Ensure session exists in runner
    try:
        runner.session_service.get_session_sync(
            app_name="ai_tutor",
            user_id=st.session_state.user_id,
            session_id=st.session_state.session_id
        )
    except Exception:
        pass # Session might not exist yet, will create if needed or handle below

    # Create session if it doesn't exist (using sync method for simplicity in Streamlit)
    if not runner.session_service.get_session_sync(
        app_name="ai_tutor",
        user_id=st.session_state.user_id,
        session_id=st.session_state.session_id
    ):
         session = runner.session_service.create_session_sync(
            app_name="ai_tutor",
            user_id=st.session_state.user_id,
            session_id=st.session_state.session_id,
            state={
                "authenticated": True,
                "current_user_id": st.session_state.user_id,
                f"user:{st.session_state.user_id}_name": st.session_state.username
            }

        )

    # Load history from DB if empty (first load) and determine is_new_session
    is_new_session = False
    if not st.session_state.messages:
        history = db_manager.get_chat_history(st.session_state.user_id, limit=20)
        if history:
            for h in history:
                st.session_state.messages.append({"role": "user", "content": h["query"]})
                st.session_state.messages.append({"role": "assistant", "content": h["response"]})
        else:
            is_new_session = True

    # Sidebar for Profile
    with st.sidebar:
        st.title(f"👤 {st.session_state.username}")
        st.caption(f"ID: {st.session_state.user_id}")
        
        if st.button("Logout"):
            st.session_state.clear()
            st.rerun()
        
        st.divider()
        st.subheader("📚 Learning Progress")
        
        # Fetch profiles
        profiles = db_manager.get_student_profile(st.session_state.user_id)
        if profiles:
            for p in profiles:
                st.write(f"**{p['subject'].upper()}**")
                # Case-insensitive level check
                level_str = p['level'].lower()
                progress_val = 0.1 if level_str == 'beginner' else 0.5 if level_str == 'intermediate' else 0.9
                st.progress(progress_val)
                st.caption(f"Level: {p['level']}")

                # Details Section
                details_raw = p['details']
                try:
                    import json
                    
                    # Helper for recursive parsing of nested JSON strings
                    def try_parse_json(content, max_depth=3):
                        if max_depth == 0: return content
                        if isinstance(content, str):
                            try:
                                parsed = json.loads(content)
                                return try_parse_json(parsed, max_depth - 1)
                            except:
                                return content
                        return content

                    data = try_parse_json(details_raw)
                    
                    # Custom Syllabus Rendering
                    syllabus_list = None
                    current_topic = "General"
                    
                    if isinstance(data, dict):
                        # Check for "syllabus" key
                        if "syllabus" in data and isinstance(data["syllabus"], list):
                            syllabus_list = data["syllabus"]
                            current_topic = data.get("current_topic", "General")
                    elif isinstance(data, list):
                        # Handle direct list
                        syllabus_list = data
                    
                    if syllabus_list:
                            st.markdown(f"**Course Plan** (Focus: {current_topic})")
                            
                            for item in syllabus_list:
                                if isinstance(item, dict):
                                    module_name = item.get("module", "Unknown Module")
                                    status = item.get("status", "pending").lower()
                                    subtopics = item.get("subtopics", [])
                                    
                                    icon = "🔵"
                                    if status == "completed":
                                        icon = "🟢"
                                    elif status == "in_progress":
                                        icon = "🟡"
                                    
                                    # Create expander for the module
                                    with st.expander(f"{icon} {module_name}"):
                                        if subtopics:
                                            for sub in subtopics:
                                                st.markdown(f"- {sub}")
                                        else:
                                            st.caption("No subtopics detailed")
                                else:
                                    st.markdown(f"• {str(item)}")
                    else:
                        # Fallback if structure is unknown but valid JSON
                        with st.expander("Raw Data"):
                            st.json(data)

                except Exception as e:
                    # Fallback: Render as Markdown if it's not JSON
                    with st.expander("Details"):
                        st.caption(f"Raw Data (Parse Error: {e})")
                        st.markdown(details_raw)

    # Auto-Login Notification (System Message)
    if not st.session_state.get("agent_notified", False):
        try:
             # Determine system message based on session type
            if is_new_session:
                 sys_msg = (
                    f"[System] New user/guest '{st.session_state.username}' (ID: {st.session_state.user_id}) has joined. "
                    "Greet them enthusiastically and PROVIDE A DETAILED EXPLANATION of your capabilities:\n"
                    "1. DSA Agent (Algorithms, LeetCode)\n"
                    "2. Developer Agent (Web, Mobile, System Design)\n"
                    "3. System Design Agent (Architecture, Cloud)\n"
                    "4. Search (General topics)\n"
                    "Tell them you can create personalized course syllabuses."
                )
            else:
                sys_msg = f"[System] User '{st.session_state.username}' (ID: {st.session_state.user_id}) has successfully authenticated. Welcome them back."
            
            # Inject student profile into system message context to reduce redundant tool calls
            dsa_profile = db_manager.get_student_profile(st.session_state.user_id, subject="dsa")
            if dsa_profile:
                sys_msg += f"\n[Context] User DSA Profile: Level={dsa_profile.get('level')}, Details={dsa_profile.get('details')}"
            
            # We run this silently to set context
            for event in runner.run(
                user_id=st.session_state.user_id,
                session_id=st.session_state.session_id,
                new_message=types.Content(role="user", parts=[types.Part(text=sys_msg)])
            ):
                # If it's a new session, we WANT to show the greeting response
                if is_new_session and event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.text:
                            st.session_state.messages.append({"role": "assistant", "content": part.text})
                            # Store system greeting in history without displaying immediately if needed
                
            st.session_state.agent_notified = True
        except Exception as e:
            st.error(f"Failed to notify agent of login: {e}")

    # Main Chat Area
    st.title("AI Tutor Assistant")
    
    # Welcome Message / Capabilities
    if not st.session_state.messages:
        st.markdown("""
        ### 👋 Welcome to AI Tutor!
        I'm here to help you master technical subjects. 
        
        **I have specialized agents for:**
        - 🧩 **DSA**: Algorithms, Data Structures, LeetCode problems.
        - 💻 **Development**: Web, Mobile, APIs, React, Python.
        - 🏗️ **System Design**: Architecture, Scalability, Cloud.
        
        **For everything else:**
        - 🌐 I can search the web to answer general questions.
        
        *Ask me anything to get started!*
        """)



    # Display messages
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat Input
    if prompt := st.chat_input("Ask me anything about DSA, System Design, or Coding..."):
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Generate response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    # Run agent via Runner
                    response_text = ""
                    for event in runner.run(
                        user_id=st.session_state.user_id,
                        session_id=st.session_state.session_id,
                        new_message=types.Content(role="user", parts=[types.Part(text=prompt)])
                    ):
                        if event.content and event.content.parts:
                            for part in event.content.parts:
                                if part.text:
                                    response_text += part.text
                    
                    if response_text:
                        st.markdown(response_text)
                        st.session_state.messages.append({"role": "assistant", "content": response_text})
                        # Rerun to update sidebar state immediately
                        st.rerun()
                    else:
                        st.warning("No response received from agent.")
                    
                except Exception as e:
                    st.error(f"An error occurred: {e}")

if __name__ == "__main__":
    if not st.session_state.authenticated:
        login_page()
    else:
        chat_page()
