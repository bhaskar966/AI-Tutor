"""Response parser callback for cleaning agent outputs."""
import json
from typing import Optional


def parse_agent_response(response_content, tool_context):
    """
    After-agent callback to parse and format structured responses.
    
    Args:
        response_content: The response content from the agent
        tool_context: The tool context object
    
    Returns:
        Cleaned/formatted response content
    """
    
    # Handle None or empty responses
    if not response_content:
        return response_content
    
    # If it's a string, try to parse JSON
    if isinstance(response_content, str):
        cleaned = try_parse_json_wrapper(response_content)
        return cleaned if cleaned else response_content
    
    # Return as-is if not a string
    return response_content


def try_parse_json_wrapper(text: str) -> Optional[str]:
    """
    Try to extract content from JSON-wrapped responses.
    Returns cleaned text if JSON found, None otherwise.
    """
    
    text = text.strip()
    
    # Check if it looks like JSON
    if not (text.startswith('{') and text.endswith('}')):
        return None
    
    try:
        data = json.loads(text)
        
        # Pattern 1: {"dsa_agent_response": {"explanation": "..."}}
        if 'dsa_agent_response' in data:
            content = data['dsa_agent_response']
            if isinstance(content, dict):
                if 'explanation' in content:
                    return content['explanation']
                if 'code' in content:
                    return format_code_response(content)
            return str(content)
        
        # Pattern 2: {"developer_agent_response": "..."}
        if 'developer_agent_response' in data:
            return str(data['developer_agent_response'])
        
        # Pattern 3: {"system_design_agent_response": "..."}
        if 'system_design_agent_response' in data:
            return str(data['system_design_agent_response'])
        
        # Pattern 4: Generic {"response": "..."}
        if 'response' in data and len(data) == 1:
            return str(data['response'])
        
        # Pattern 5: Any key ending with "_response"
        for key, value in data.items():
            if key.endswith('_response'):
                if isinstance(value, dict) and 'explanation' in value:
                    return value['explanation']
                return str(value)
        
        # No recognizable pattern, return pretty JSON
        return json.dumps(data, indent=2)
        
    except json.JSONDecodeError:
        # Not valid JSON
        return None


def format_code_response(data: dict) -> str:
    """Format code-heavy responses with clear sections."""
    
    output = []
    
    if 'explanation' in data:
        output.append(data['explanation'])
    
    if 'code' in data:
        lang = data.get('language', 'python')
        output.append(f"``````")
    
    if 'complexity' in data:
        output.append(f"**Complexity Analysis:**\n{data['complexity']}")
    
    return '\n\n'.join(output)
