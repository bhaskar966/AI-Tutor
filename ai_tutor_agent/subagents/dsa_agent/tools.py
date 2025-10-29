"""Tools for DSA agent."""
from google.adk.tools.tool_context import ToolContext


def review_code(feedback: str, tool_context: ToolContext) -> dict:
    """Provide feedback on generated code for improvement."""
    tool_context.state["code_feedback"] = feedback
    
    return {
        "status": "needs_improvement",
        "feedback": feedback
    }


def exit_loop(tool_context: ToolContext) -> dict:
    """Exit the review loop when code is optimal."""
    return {
        "status": "complete",
        "message": "Code is optimal"
    }
