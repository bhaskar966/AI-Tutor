"""Database interaction tools."""
from google.adk.tools.tool_context import ToolContext
import uuid
import os
from ai_tutor_agent.utils.db_manager import db_manager

def check_user(user_id: str, tool_context: ToolContext) -> dict:
    """Check if user exists and load their profile to context."""
    user = db_manager.get_user(user_id)
    
    if user:
        tool_context.state[f"user:{user_id}_name"] = user["name"]
        tool_context.state["current_user_id"] = user_id
        tool_context.state["authenticated"] = True
        return {
            "exists": True,
            "user_id": user_id,
            "name": user["name"],
            "message": f"User {user['name']} found and loaded"
        }
    
    return {
        "exists": False,
        "user_id": user_id,
        "message": "User not found in database"
    }

def create_user(user_id: str, name: str, tool_context: ToolContext) -> dict:
    """Create a new user account in the database."""
    

    if user_id.lower() == "guest" or user_id.startswith("guest_"):
        user_id = f"guest_{uuid.uuid4().hex[:6]}"
    
    result = db_manager.create_user(user_id, name)
    
    if result["success"]:
        tool_context.state["current_user_id"] = user_id
        tool_context.state[f"user:{user_id}_name"] = name
        tool_context.state["authenticated"] = True
        

        if user_id.startswith("guest_"):
            tool_context.state["is_guest"] = True
        
        return {
            "success": True,
            "user_id": user_id,
            "name": name,
            "message": f"Account created successfully for {name} (ID: {user_id})"
        }
    
    return {
        "success": False,
        "message": f"Failed to create account: {result.get('error', 'Unknown error')}"
    }

def log_conversation(agent_name: str, query: str, response: str, tool_context: ToolContext) -> dict:
    """Log the conversation to database for persistence."""
    user_id = tool_context.state.get("current_user_id", "anonymous")
    session_id = getattr(tool_context, 'session_id', None)
    if not session_id:
        session_id = tool_context.state.get("session_id", "default_session")
    
    success = db_manager.log_interaction(
        session_id=session_id,
        user_id=user_id,
        agent_name=agent_name,
        query=query,
        response=response
    )
    
    return {
        "logged": success,
        "agent": agent_name,
        "user_id": user_id
    }



def delete_guest_user(user_id: str, tool_context: ToolContext) -> dict:
    """Delete a guest user from the database."""
    if not user_id.startswith("guest_"):
        return {"success": False, "message": "Can only delete guest users"}
    
    from utils.db_manager import db_manager, User
    session = db_manager.get_session()
    try:
        session.query(User).filter_by(user_id=user_id).delete()
        session.commit()
        return {"success": True, "message": f"Guest user {user_id} deleted"}
    except:
        session.rollback()
        return {"success": False}
    finally:
        session.close()

def get_user_history(tool_context: ToolContext) -> dict:
    """Get recent chat history for the current user."""
    user_id = tool_context.state.get("current_user_id")
    if not user_id:
        return {"error": "No user logged in"}
    
    session_id = getattr(tool_context, 'session_id', None)
    if not session_id:
        session_id = tool_context.state.get("session_id")
        
    history = db_manager.get_chat_history(user_id, session_id=session_id)
    return {"history": history}

def get_student_profile(subject: str, tool_context: ToolContext) -> dict:
    """Get the student's profile/level for a specific subject."""
    user_id = tool_context.state.get("current_user_id")
    if not user_id:
        return {"error": "No user logged in"}
    
    profile = db_manager.get_student_profile(user_id, subject)
    if profile:
        return {"found": True, "profile": profile}
    return {"found": False, "message": f"No profile found for {subject}"}

def update_student_profile(subject: str, level: str, details: str, tool_context: ToolContext) -> dict:
    """Update the student's profile/level for a specific subject."""
    user_id = tool_context.state.get("current_user_id")
    if not user_id:
        return {"error": "No user logged in"}
    
    success = db_manager.update_student_profile(user_id, subject, level, details)
    return {
        "success": success,
        "message": f"Updated {subject} level to {level}" if success else "Failed to update"
    }

def update_learning_path_details(syllabus: str, tool_context: ToolContext) -> dict:
    """
    Update the syllabus/details for the CURRENT learning path (session).
    Use this to save the specific plan for this chat session.
    
    Args:
        syllabus: JSON string containing the 'syllabus' and 'current_topic'.
                  Example: '{"syllabus": [...], "current_topic": "..."}'
    """
    session_id = getattr(tool_context, 'session_id', None)
    if not session_id:
        session_id = tool_context.state.get("session_id")
        
    if not session_id:
         return {"success": False, "message": "No active session found"}

    success = db_manager.update_learning_path_details(session_id, syllabus)
    return {
        "success": success,
        "message": "Syllabus saved to Learning Path." if success else "Failed to save syllabus."
    }