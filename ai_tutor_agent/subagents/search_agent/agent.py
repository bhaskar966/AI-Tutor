"""Search agent - wraps Google Search for use by other agents."""
from google.adk.agents import Agent
from google.adk.tools import google_search

search_agent = Agent(
    name="search_agent",
    model="gemini-2.0-flash",
    description="Performs Google searches and returns relevant, up-to-date information",
    instruction="""You are a search specialist agent.

Your role:
1. Use google_search tool to find accurate, current information
2. Return concise, relevant results with key facts
3. Cite sources when useful

Keep responses focused and factual.""",
    tools=[google_search]
)
