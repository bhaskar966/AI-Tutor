"""General agent - handles queries outside specialist domains."""
from google.adk.agents import Agent
from google.adk.tools.agent_tool import AgentTool
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from subagents.search_agent.agent import search_agent

general_agent = Agent(
    name="general_agent",
    model="gemini-2.0-flash",
    description="Handles queries outside specialist domains using web search",
    instruction="""You handle topics that don't fit specialist domains.

**IMPORTANT**: Always start with:
"I don't have a specialized agent for this topic yet, but I'll search for information to help you."

**Your workflow:**
1. Use search_agent to find relevant, current information
2. Synthesize findings into clear, concise answer
3. Cite sources when providing facts
4. Be honest about limitations
5. Suggest which specialist might help if query is unclear

Be helpful, accurate, and honest.
Encourage users to ask dev, DSA, or system design questions for deeper help.""",
    tools=[AgentTool(agent=search_agent)]
)
