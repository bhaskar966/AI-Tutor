"""DSA agent - solves algorithm problems with iterative code review."""
from google.adk.agents import Agent, LoopAgent
from google.adk.tools import FunctionTool
from .tools import review_code, exit_loop

# Code Generator
code_generator = Agent(
    name="code_generator",
    model="gemini-2.0-flash",
    description="Generates optimized DSA solutions",
    instruction="""Generate optimal, well-commented code for DSA problems.

Provide complete response with:
1. Algorithm explanation
2. Working code with comments
3. Time complexity
4. Space complexity

Store everything in the output.""",
    output_key="generated_code"
)

# Code Reviewer - FIXED
code_reviewer = Agent(
    name="code_reviewer",
    model="gemini-2.0-flash",
    description="Reviews code for optimization",
    instruction="""Review the code from {{generated_code}}.

Check:
- Optimal complexity
- Edge cases
- Clean code

**If code is optimal:**
- Call exit_loop tool
- Then OUTPUT THE FULL CODE from {{generated_code}} in your response
- This ensures user sees the final code

**If needs improvement:**
- Call review_code with feedback
- Still output current code so user can see progress

ALWAYS show the code in your response, whether exiting loop or providing feedback.""",
    tools=[
        FunctionTool(review_code),
        FunctionTool(exit_loop)
    ],
    output_key="reviewed_code"
)

# DSA Loop Agent
dsa_agent = LoopAgent(
    name="dsa_agent",
    description="Solves DSA problems with iterative code review",
    sub_agents=[code_generator, code_reviewer],
    max_iterations=3
)
