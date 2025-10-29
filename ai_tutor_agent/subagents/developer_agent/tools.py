"""Developer agent tools for documentation parsing."""
import requests
from bs4 import BeautifulSoup
from google.adk.tools.tool_context import ToolContext

def parse_documentation(url: str, tool_context: ToolContext) -> dict:
    """Parse text content from documentation URLs."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        for tag in soup(["script", "style", "nav", "footer", "aside", "header"]):
            tag.decompose()
        
        text = soup.get_text(separator='\n', strip=True)
        limited_text = text[:8000]
        
        tool_context.state["temp:parsed_documentation"] = limited_text
        
        return {
            "success": True,
            "url": url,
            "content_preview": limited_text[:300] + "..." if len(limited_text) > 300 else limited_text,
            "total_length": len(text),
            "stored_length": len(limited_text)
        }
    except requests.exceptions.Timeout:
        return {"success": False, "error": "Request timed out", "url": url}
    except Exception as e:
        return {"success": False, "error": f"Error: {str(e)}", "url": url}
