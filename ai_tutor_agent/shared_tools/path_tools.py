from google.adk.tools.tool_context import ToolContext
import sys
import os

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
    
    # Check state for session_id (if injected by streamlit app)
    if not session_id:
        session_id = tool_context.state.get("session_id")

    if not user_id or not session_id:
        return {"error": f"Context Missing. UserID: {user_id}, SessionID: {session_id}"}

    if not title:
        title = subject.replace("_", " ").title()

    success = db_manager.create_learning_path(user_id, session_id, subject, title)
    
    if not success:
        return {"error": "Failed to create learning path record."}
        
    # Implement "Inheritance" logic - user gets credit for past progress
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
        # Bootstrap a fresh profile with EMPTY syllabus to trigger agent assessment
        initial_details = {
            "current_topic": None,
            "syllabus": []  # Empty syllabus triggers "New User" logic in agents
        }
        import json
        db_manager.update_student_profile(user_id, subject, "Unknown", json.dumps(initial_details))
        
        response["message"] += " Starting fresh. Please assess the student's level."
        response["existing_profile"] = {
            "subject": subject,
            "level": "Unknown",
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
        return {"context": "No syllabus context found for the current path."}
        
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

def trigger_topic_quiz(topic_name: str, tool_context: ToolContext = None) -> dict:
    """
    Triggers the interactive Quiz Engine overlay for the current topic.
    MUST be called before advancing a student to a new topic to verify mastery.
    The quiz is enforced server-side — the student's chat will be locked until they complete it.
    
    Args:
        topic_name: The name of the topic the user just finished learning.
    """
    import json
    session_id = getattr(tool_context, 'session_id', None) if tool_context else None
    if not session_id and tool_context:
        session_id = tool_context.state.get("session_id")
        
    if session_id:
        if db_manager.get_quiz_pending(session_id) is not None:
            return {
                "error": "A quiz is already currently pending. You cannot trigger another one."
            }
            
        paths = db_manager.get_learning_paths(tool_context.state.get("current_user_id"))
        current_path = next((p for p in paths if p['session_id'] == session_id), None)
        if current_path and current_path.get('syllabus'):
            try:
                syllabus_data = json.loads(current_path['syllabus'])
                syllabus_list = syllabus_data.get("syllabus", syllabus_data.get("modules", syllabus_data)) if isinstance(syllabus_data, dict) else syllabus_data
                for module in syllabus_list:
                    if topic_name in module.get("completed_topics", []):
                        return {
                            "error": f"The quiz for '{topic_name}' has ALREADY BEEN COMPLETED by the user. DO NOT trigger it again. Your task is to teach the next pending topic in the syllabus."
                        }
            except:
                pass
                
    return {
        "status": "quiz_triggered",
        "message": f"A mandatory quiz for '{topic_name}' has been activated. The student's chat is now locked until they complete the quiz. Do NOT teach any new content until the quiz is completed and you receive a system message confirming the results.",
        "_internal_action": "open_quiz"
    }

def mark_topic_taught(topic_name: str, tool_context: ToolContext = None) -> dict:
    """
    Marks a topic as taught in the syllabus.
    Call this ONLY when you have finished explaining a topic and the user has no more questions.
    After calling this, you can proceed to call the assessment_agent to trigger a quiz.
    
    Args:
        topic_name: The name of the topic the user just finished learning.
    """
    import json
    session_id = getattr(tool_context, 'session_id', None) if tool_context else None
    if not session_id and tool_context:
        session_id = tool_context.state.get("session_id")
        
    if not session_id:
        return {"error": "No session ID found."}
        
    user_id = tool_context.state.get("current_user_id")
    paths = db_manager.get_learning_paths(user_id)
    current_path = next((p for p in paths if p['session_id'] == session_id), None)
    
    if not current_path or not current_path.get('syllabus'):
        return {"error": "Syllabus not found."}
        
    try:
        syllabus_data = json.loads(current_path['syllabus'])
        syllabus_list = syllabus_data.get("syllabus", syllabus_data.get("modules", syllabus_data)) if isinstance(syllabus_data, dict) else syllabus_data
        
        found = False
        for module in syllabus_list:
            for t in module.get("topics", []):
                if isinstance(t, dict):
                    t_title = t.get('title', '')
                    if topic_name.lower() in t_title.lower() or t_title.lower() in topic_name.lower():
                        t["taught"] = True
                        found = True
                        break
            if found:
                break
                
        if found:
            # Re-wrap
            if isinstance(syllabus_data, dict) and "syllabus" in syllabus_data:
                syllabus_data["syllabus"] = syllabus_list
            elif isinstance(syllabus_data, dict) and "modules" in syllabus_data:
                syllabus_data["modules"] = syllabus_list
            else:
                syllabus_data = syllabus_list
                
            db_manager.update_learning_path_details(session_id, json.dumps(syllabus_data))
            return {
                "success": True,
                "message": f"Successfully marked '{topic_name}' as taught. You may now trigger the quiz by transferring to assessment_agent."
            }
        else:
            return {"error": f"Topic '{topic_name}' not found in syllabus."}
            
    except Exception as e:
        return {"error": f"Failed to parse syllabus: {str(e)}"}
