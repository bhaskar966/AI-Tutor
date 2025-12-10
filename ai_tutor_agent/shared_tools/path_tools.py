from google.adk.tools.tool_context import ToolContext
import sys
import os

# Add project root to sys.path to ensure imports work
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from ai_tutor_agent.utils.db_manager import db_manager

def create_learning_path_tool(subject: str, title: str = None, tool_context: ToolContext = None) -> dict:
    """
    Creates a new Learning Path (persistent chat) for a specific subject.
    Use this when the user starts learning a new topic or wants to continue a specific subject.
    
    Args:
        subject: The subject matter ID (e.g., 'dsa', 'python', 'system_design').
        title: Optional display title for the path (e.g., 'DSA Basics', 'Advanced Python'). 
               If not provided, defaults to the subject name.
    """
    if not tool_context:
        return {"error": "Tool context missing"}

    user_id = tool_context.state.get("current_user_id")
    session_id = getattr(tool_context, 'session_id', None)
    
    # Fallback: Check state for session_id (if injected by streamlit app)
    if not session_id:
        session_id = tool_context.state.get("session_id")

    if not user_id or not session_id:
        return {"error": f"Context Missing. UserID: {user_id}, SessionID: {session_id}"}

    if not title:
        title = subject.replace("_", " ").title()

    # 1. Create the path record
    success = db_manager.create_learning_path(user_id, session_id, subject, title)
    
    if not success:
        return {"error": "Failed to create learning path record."}
        
    # 2. Fetch existing profile to provide context
    # This implements the "Inheritance" logic - user gets credit for past progress
    profile = db_manager.get_student_profile(user_id, subject)
    
    response = {
        "success": True,
        "path_created": True,
        "subject": subject,
        "title": title,
        "message": f"Learning Path '{title}' created."
    }
    
    if profile:
        response["message"] += f" Found existing progress: Level {profile.get('level')}."
        response["existing_profile"] = profile
    else:
        # Bootstrap a fresh profile so UI shows something immediately
        initial_details = {
            "current_topic": "Introduction",
            "syllabus": [
                {"module": "Getting Started", "status": "in_progress", "subtopics": ["Course Overview"]}
            ]
        }
        import json
        db_manager.update_student_profile(user_id, subject, "Beginner", json.dumps(initial_details))
        
        response["message"] += " Starting fresh for this subject."
        response["existing_profile"] = {
            "subject": subject,
            "level": "Beginner",
            "details": json.dumps(initial_details)
        }
        
    return response

def get_learning_paths_tool(tool_context: ToolContext = None) -> dict:
    """Get all learning paths for the current user."""
    if not tool_context:
        return {"error": "Tool context missing"}
        
    user_id = tool_context.state.get("current_user_id")
    if not user_id:
        return {"error": "User ID missing"}
        
    paths = db_manager.get_learning_paths(user_id)
    
    # Identify current session context
    current_session_id = getattr(tool_context, 'session_id', None)
    if not current_session_id:
        current_session_id = tool_context.state.get("session_id")

    for p in paths:
        if p['session_id'] == current_session_id:
            p['is_current'] = True
            p['title'] = f"{p['title']} (CURRENT)"
            # Ensure syllabus is present and parsed if string
            if isinstance(p.get('syllabus'), str) and p.get("syllabus") == "{}":
                 p['syllabus'] = None # Explicitly show empty if empty
        else:
            p['is_current'] = False
            # CRITICAL: Redact syllabus of other paths to prevent hallucination
            if 'syllabus' in p:
                del p['syllabus'] 
            
    return {"paths": paths}

def get_current_learning_path_context(tool_context: ToolContext) -> dict:
    """
    Get DETAILED context for the CURRENT learning path (session).
    This includes the persistent Syllabus, Subject, and Title.
    Use this to understand "Where are we?" in the course.
    """
    session_id = getattr(tool_context, 'session_id', None)
    if not session_id:
        session_id = tool_context.state.get("session_id")
        
    if not session_id:
        return {"error": "No active session ID found."}
        
    paths = db_manager.get_learning_paths(tool_context.state.get("current_user_id"))
    current_path = next((p for p in paths if p['session_id'] == session_id), None)
    
    if current_path:
        return {
            "found": True,
            "title": current_path['title'],
            "subject": current_path['subject'],
            "syllabus_json": current_path.get('syllabus', '{}'),
            "message": "Found active learning path."
        }
    
    return {"found": False, "message": "No specific learning path created for this chat session yet."}
