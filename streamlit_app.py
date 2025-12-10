import streamlit as st
import sys
import os
import uuid
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
if "sidebar_view" not in st.session_state:
    st.session_state.sidebar_view = "list" # 'list' or 'detail'

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
if "sidebar_view" not in st.session_state:
    st.session_state.sidebar_view = "list" # 'list' or 'detail'


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

    # Create session if it doesn't exist (e.g., server restart or new user)
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
                f"user:{st.session_state.user_id}_name": st.session_state.username,
                "session_id": st.session_state.session_id 
            }
        )
         # CRITICAL: If we had to recreate the session, the backend lost context.
         # We must resend the [System] login notification.
         st.session_state.agent_notified = False

    # 1. Identify Current Path from Session ID
    paths = db_manager.get_learning_paths(st.session_state.user_id)
    current_path = next((p for p in paths if p['session_id'] == st.session_state.session_id), None)

    # 2. Load history from DB if message are empty (reloading/switching)
    is_new_session = False
    if not st.session_state.messages:
        # Pass session_id to get relevant history!
        history = db_manager.get_chat_history(st.session_state.user_id, session_id=st.session_state.session_id, limit=30)
        if history:
            for h in history:
                st.session_state.messages.append({"role": "user", "content": h["query"]})
                st.session_state.messages.append({"role": "assistant", "content": h["response"]})
        else:
            is_new_session = True

    # 3. Sidebar: Navigation (Learning Paths)
    # 3. Sidebar: Navigation (Learning Paths)
    with st.sidebar:
        st.title(f"👤 {st.session_state.username}")
        if st.caption: st.caption(f"ID: {st.session_state.user_id}")
        if st.button("Logout"):
            st.session_state.clear()
            st.rerun()
            
        st.divider()
        
        # --- VIEW LOGIC ---
        # Determine effective view mode
        # If we have a current path, we default to detail view unless explicitly back in list mode
        # Actually, let's strictly follow the state variable, but sync it on first load if needed
        
        show_detail = False
        if current_path and st.session_state.sidebar_view == 'detail':
            show_detail = True
            
        if show_detail:
            # === DETAIL VIEW (Active Path) ===
            if st.button("🔙 Back to Paths", use_container_width=True):
                # Just change the view, DO NOT reset the session
                st.session_state.sidebar_view = 'list'
                st.rerun()

            st.markdown(f"### 📂 {current_path['title']}")
            
            # Fetch Progress
            profile = db_manager.get_student_profile(st.session_state.user_id, subject=current_path['subject'])
            
            if profile:
                st.caption(f"**Subject:** {profile['subject'].upper()}")
                
                # Progress Bar
                level_str = profile['level'].lower()
                progress_val = 0.1 if 'beginner' in level_str else 0.5 if 'intermediate' in level_str else 0.9
                st.progress(progress_val)
                st.caption(f"Level: {profile['level'].title()}")
                
                # Detailed Syllabus Rendering
                st.divider()
                st.markdown("**🎓 Course Syllabus**")
                
                # PREFER Path-specific syllabus, fallback to Profile (legacy)
                path_syllabus_raw = current_path.get('syllabus')
                if path_syllabus_raw and path_syllabus_raw != '{}':
                     details_raw = path_syllabus_raw
                else:
                     details_raw = profile.get('details', '{}')
                try:
                    import json
                    # Helper for recursive parsing
                    def try_parse_json(c, d=3):
                        if d==0: return c
                        if isinstance(c, str):
                            try: return try_parse_json(json.loads(c), d-1)
                            except: return c
                        return c
                    
                    data = try_parse_json(details_raw)
                    syllabus_list = None
                    
                    if isinstance(data, dict) and "syllabus" in data:
                        syllabus_list = data["syllabus"]
                    elif isinstance(data, list):
                        syllabus_list = data
                        
                    if syllabus_list:
                         for item in syllabus_list:
                            if isinstance(item, dict):
                                module_name = item.get("module", "Module")
                                status = item.get("status", "pending").lower()
                                subtopics = item.get("subtopics", [])
                                
                                icon = "🔵"
                                if status == "completed": icon = "🟢"
                                elif status == "in_progress": icon = "🟡"
                                
                                with st.expander(f"{icon} {module_name}"):
                                    if subtopics:
                                        for sub in subtopics:
                                            st.markdown(f"- {sub}")
                                    else:
                                        st.caption("No details")
                            else:
                                st.write(f"• {item}")
                    else:
                        st.info("Syllabus generating...")
                        
                except Exception as e:
                    st.caption("Parsing progress details...")
            else:
                st.info("Initializing progress...")

        else:
            # === ROOT VIEW (List Paths) ===
            if st.button("➕ New Chat", use_container_width=True):
                st.session_state.session_id = str(uuid.uuid4())
                st.session_state.messages = []
                st.session_state.agent_notified = False
                st.session_state.sidebar_view = 'list' # Stay in list view for new chat
                st.rerun()
                
            st.subheader("Learning Paths")
            
            if paths:
                for p in paths:
                    # Identify if this is the active path
                    is_active = p['session_id'] == st.session_state.session_id
                    
                    label = f"{'📂' if is_active else '📁'} {p['title']}"
                    
                    if st.button(label, key=p['id'], use_container_width=True, type="primary" if is_active else "secondary"):
                        # Only reload if it's a DIFFERENT session
                        if not is_active:
                            st.session_state.session_id = p['session_id']
                            st.session_state.messages = [] # Reload history
                            st.session_state.agent_notified = True
                        
                        # Always switch to Detail view
                        st.session_state.sidebar_view = 'detail'
                        st.rerun()
            else:
                st.info("Start chatting to create a path!")

    # 4. Auto-Login Notification (System Message)
    if not st.session_state.get("agent_notified", False):
        try:
             # Determine system message based on session type
            if is_new_session and not current_path:
                 sys_msg = (
                    f"[System] New user/guest '{st.session_state.username}' (ID: {st.session_state.user_id}) has joined in a blank session. "
                    "Greet them enthusiastically and ASK what they want to learn today (DSA, Dev, System Design?). "
                    "If they pick a topic, use `create_learning_path_tool`."
                )
            elif is_new_session and current_path:
                 sys_msg = f"[System] User resumed Learning Path '{current_path['title']}'. Welcome them back and check context."
            else:
                 # Just reconnected
                sys_msg = f"[System] User '{st.session_state.username}' connected."
            
            # Inject student profile summary if available? 
            # (Maybe not necessary if resuming path, agent has history. But good for new chat context inheritance if we implemented that logic. 
            # The tool will handle inheritance, so here we just notify.)
            
            # We run this silently to set context
            for event in runner.run(
                user_id=st.session_state.user_id,
                session_id=st.session_state.session_id,
                new_message=types.Content(role="user", parts=[types.Part(text=sys_msg)])
            ):
                # If it's a new session, we show the greeting
                if is_new_session and event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.text:
                            st.session_state.messages.append({"role": "assistant", "content": part.text})
                
            st.session_state.agent_notified = True
        except Exception as e:
            st.error(f"Failed to notify agent of login: {e}")

    # 5. Main Chat Area
    st.title("AI Tutor Assistant" if not current_path else current_path['title'])
    
    # Welcome Message / Capabilities (Only for blank new chats)
    if not st.session_state.messages and not current_path:
        st.markdown("""
        ### 👋 Welcome to AI Tutor!
        I'm here to help you master technical subjects. 
        
        **Start by picking a topic:**
        - 🧩 **DSA**: Algorithms, Data Structures
        - 💻 **Development**: Web, Mobile, React, Python
        - 🏗️ **System Design**: Architecture, Cloud
        
        *Ask me anything to get started!*
        """)

    # Display messages
    for msg in st.session_state.messages:
        role = msg["role"]
        content = msg["content"]
        sender_name = msg.get("sender_name")
        
        # Determine display name and avatar
        if role == "user":
            display_name = sender_name or st.session_state.username or "Student"
            avatar = "👤"
        else:
            # Map internal agent names to friendly titles
            agent_mapping = {
                "root_agent": "AI Tutor",
                "dsa_tutor": "DSA Tutor",
                "dsa_solver": "DSA Solver",
                "code_generator": "Code Generator",
                "code_reviewer": "Code Reviewer",
                "developer_tutor": "Developer Tutor",
                "system_design_tutor": "System Design Tutor",
                "search_agent": "Search Agent",
                "account_agent": "Account Manager"
            }
            raw_name = sender_name or "AI Tutor"
            display_name = agent_mapping.get(raw_name, raw_name.replace("_", " ").title())
            avatar = "🤖"

        with st.chat_message(name=display_name, avatar=avatar):
            st.write(f"**{display_name}**")
            st.markdown(content)

    if prompt := st.chat_input("Ask me anything about DSA, System Design, or Coding..."):
        # Add user message
        user_name = st.session_state.username or "Student"
        st.session_state.messages.append({
            "role": "user", 
            "content": prompt, 
            "sender_name": user_name
        })
        with st.chat_message(user_name, avatar="👤"):
            st.write(f"**{user_name}**")
            st.markdown(prompt)
        
        # Generate response
        with st.chat_message("AI Tutor", avatar="🤖"):
             with st.spinner("Thinking..."):
                try:
                    # Run agent via Runner
                    response_text = ""
                    last_author = "root_agent" 
                    
                    for event in runner.run(
                        user_id=st.session_state.user_id,
                        session_id=st.session_state.session_id,
                        new_message=types.Content(role="user", parts=[types.Part(text=prompt)])
                    ):
                        if event.content and event.content.parts:
                            if event.author:
                                last_author = event.author
                            for part in event.content.parts:
                                if part.text:
                                    response_text += part.text
                    
                    if response_text:
                        agent_mapping = {
                            "root_agent": "AI Tutor",
                            "dsa_tutor": "DSA Tutor",
                            "dsa_solver": "DSA Solver",
                            "code_generator": "Code Generator",
                            "code_reviewer": "Code Reviewer",
                            "developer_tutor": "Developer Tutor",
                            "system_design_tutor": "System Design Tutor",
                            "search_agent": "Search Agent",
                            "account_agent": "Account Manager"
                        }
                        final_display_name = agent_mapping.get(last_author, last_author.replace("_", " ").title())
                        
                        st.write(f"**{final_display_name}**")
                        st.markdown(response_text)
                        
                        st.session_state.messages.append({
                            "role": "assistant", 
                            "content": response_text,
                            "sender_name": last_author
                        })
                        
                        # Rerun to update Sidebar if path was created
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
