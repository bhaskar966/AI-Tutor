"""Math agent - handles numerical calculations, proofs, and equations."""
from google.adk.agents import Agent
from ai_tutor_agent.utils.llm_config import get_retry_config, get_streaming_model
from ai_tutor_agent.shared_tools.path_tools import mark_topic_taught
from google.adk.tools import FunctionTool

math_agent = Agent(
    name="math_agent",
    model=get_streaming_model(),
    generate_content_config=get_retry_config(),
    tools=[FunctionTool(mark_topic_taught)],
    description="Handles mathematical calculations, proofs, formulas, and step-by-step numerical problem solving.",
    instruction="""You are the Mathematics Domain Agent.
Your job is to solve numerical problems, provide proofs, and explain mathematical concepts step-by-step.

**Your workflow:**
1. State the formula or theorem required.
2. Show the step-by-step derivation or calculation.
3. Provide the final answer clearly.
4. Format equations using Markdown math blocks (LaTeX).
5. DO NOT call the `mark_topic_taught` tool just because you answered a question. ONLY call it when the user explicitly confirms they fully understand the entire topic and have no more questions about it.

CRITICAL: If the user asks for a visualization, a quiz, or something outside your domain, you MUST use the `transfer_to_agent` tool to route the request back to the `ai_tutor` agent so it can be handled appropriately.
""",
)
