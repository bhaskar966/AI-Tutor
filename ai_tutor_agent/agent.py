"""Root tutor agent - orchestrates all specialized learning agents."""
import os
from google.adk.agents import Agent
from google.adk.tools.agent_tool import AgentTool
from google.adk.tools import FunctionTool
from .subagents import (
    account_agent,
    dsa_agent,
    developer_agent,
    system_design_agent,
    general_agent
)
from shared_tools.db_tools import log_conversation

root_agent = Agent(
    name="ai_tutor",
    model="gemini-2.0-flash",
    description="AI Tutor orchestrator",
    instruction="""You coordinate specialized AI agents for learning.

**First Message Only:**
If this is the user's first message and they haven't been authenticated yet, use account_agent to handle authentication.

**After Authentication:**
Route queries to the right specialist:
- DSA problems (algorithms, code, sorting, etc.) → dsa_agent
- Development (React, APIs, mobile, web) → developer_agent  
- System design (architecture, cloud, databases) → system_design_agent
- Other topics → general_agent

**Important:**
- Show the full response from specialist agents
- Don't wrap responses in JSON
- After showing the response, briefly ask if they need clarification
- Call log_conversation after each successful response""",
    tools=[
        AgentTool(agent=account_agent),
        AgentTool(agent=dsa_agent),
        AgentTool(agent=developer_agent),
        AgentTool(agent=system_design_agent),
        AgentTool(agent=general_agent),
        FunctionTool(log_conversation)
    ]
)
