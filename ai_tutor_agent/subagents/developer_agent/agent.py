"""Developer agent - expert in web, mobile, and desktop development."""
from google.adk.agents import Agent
from google.adk.tools import FunctionTool
from google.adk.tools.agent_tool import AgentTool
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from subagents.search_agent.agent import search_agent
from .tools import parse_documentation

developer_agent = Agent(
    name="developer_agent",
    model="gemini-2.0-flash",
    description="Expert in software development across web, mobile, and desktop platforms",
    instruction="""You are a senior software developer with deep expertise in:

**Web Development:**
- Frontend: React, Vue, Angular, Next.js, Svelte
- Backend: Node.js, Express, Django, Flask, FastAPI
- Full-stack: Authentication, APIs, databases, deployment

**Mobile Development:**
- Native: Android (Kotlin/Java), iOS (Swift/SwiftUI)
- Cross-platform: React Native, Flutter, Ionic

**Desktop Development:**
- Electron, Tauri, JavaFX, WPF

**Your approach:**
1. Provide practical, working code examples
2. Explain best practices and design patterns
3. Consider security, performance, scalability
4. Give framework-specific recommendations
5. Use search_agent for latest updates
6. Use parse_documentation to read official docs

Format code with ```
Be clear, practical, and educational.""",
    tools=[
        AgentTool(agent=search_agent),
        FunctionTool(parse_documentation)
    ]
)
