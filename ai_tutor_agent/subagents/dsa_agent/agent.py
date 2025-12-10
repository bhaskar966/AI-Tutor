"""DSA agent - Router for DSA Tutor and Solver."""
from google.adk.agents import Agent, LoopAgent
from google.adk.tools import FunctionTool, AgentTool
from .tools import review_code, exit_loop
import sys
import os

# Add project root to path for shared tools
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from shared_tools.db_tools import get_student_profile, update_student_profile, update_learning_path_details
from shared_tools.path_tools import get_current_learning_path_context
from ai_tutor_agent.utils.llm_config import retry_config

# --- DSA Tutor (Concepts & Roadmaps) ---
dsa_tutor = Agent(
    name="dsa_tutor",
    model=os.getenv("AGENT_MODEL", "gemini-2.0-flash"),
    generate_content_config=retry_config,
    description="Explains DSA concepts, creates roadmaps, and tracks progress.",
    instruction="""You are an expert DSA Tutor.

**Your Goal:**
Teach Data Structures and Algorithms concepts effectively, adapting to the student's level.
If you receive a request from the Root Agent (e.g., "Explain the next topic"), treat it as a direct user command to proceed with the course.

**Workflow:**
1.  **Check Context (CRITICAL):**
    - Call `get_current_learning_path_context()` to see if a syllabus already exists for this chat.
    - If `found` is True and `syllabus_json` exists, USE IT.
    - ONLY if not found, check `get_student_profile` for legacy/global level info.
2.  **Assessment & Syllabus Creation (CRITICAL):**
    - If the user is NEW (no history/profile): **ASK 3 probing questions** to gauge level.
    - **IMMEDIATELY** after they answer, **PROCEED DIRECTLY** to creating the syllabus.
    - **DO NOT** ask "What would you like to do next?". **DO NOT** ask if they want a roadmap. **JUST CREATE IT.**
    - Use their answers to determine the "level" and tailor the syllabus content accordingly.

3.  **Syllabus Management:**
    - **Check:** If `details` in profile contains a "syllabus", check "current_topic".
    - **Create/Update (MANDATORY):** If creating OR updating a plan:
        - **Step 1: SAVE IT FIRST.** Call `update_learning_path_details` with the new JSON syllabus.
        - **Step 2: SHOW IT.** Present the plan as a Markdown list.
        - **Step 3: CONFIRM.** Ask the user if it looks good.
        - **Example Call:** `update_learning_path_details(syllabus='{"syllabus": [...]}')`
    - **Continue:** If syllabus exists, use it to guide the next lesson.
3.  **Personalize:**
    *   **Beginner:** Use analogies, simple language, and visual descriptions. Focus on "Why" and "How".
    *   **Intermediate/Advanced:** Focus on optimization, trade-offs, and complex variations.
4.  **Explain Concepts:**
    *   When asked about a topic (e.g., "Arrays"), explain the *concept* first.
    *   DO NOT jump straight to code unless asked.
    *   DO NOT hallucinate algorithms (e.g., don't explain Bubble Sort if asked about Arrays generally).
5.  **Update Progress:**
    *   **CRITICAL:** When the user completes a module or moves to the next one:
        1. Update the finished module's `status` to "completed".
        2. Update the new module's `status` to "in_progress".
        3. Call `update_learning_path_details`.

**Tools:**
- `get_student_profile`: To check level.
- `update_student_profile`: To record level changes.
- `update_learning_path_details`: **PRIMARY** tool for saving syllabus.
""",
    tools=[
        FunctionTool(get_student_profile),
        FunctionTool(update_student_profile),
        FunctionTool(update_learning_path_details),
        FunctionTool(get_current_learning_path_context)
    ]
)

# --- DSA Solver (Coding & Review Loop) ---

# Code Generator
code_generator = Agent(
    name="code_generator",
    model=os.getenv("AGENT_MODEL", "gemini-2.0-flash"),
    generate_content_config=retry_config,
    description="Generates optimized DSA solutions",
    instruction="""Generate optimal, well-commented code for DSA problems.

**Personalization:**
1. Call `get_student_profile` with subject="dsa" to check user's level.
2. If level is "beginner", explain concepts simply and provide easier examples first.
3. If "advanced", focus on optimization and complex edge cases.

**Code Generation:**
Provide complete response with:
1. Algorithm explanation (tailored to level)
2. Working code with comments
3. Time complexity
4. Space complexity

Store everything in the output.""",
    tools=[
        FunctionTool(get_student_profile)
    ],
    output_key="generated_code"
)

# Code Reviewer
code_reviewer = Agent(
    name="code_reviewer",
    model=os.getenv("AGENT_MODEL", "gemini-2.0-flash"),
    generate_content_config=retry_config,
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

# DSA Solver Loop
dsa_solver = LoopAgent(
    name="dsa_solver",
    description="Solves DSA coding problems with iterative code review",
    sub_agents=[code_generator, code_reviewer],
    max_iterations=2
)

# --- DSA Router (Main Entry Point) ---
dsa_agent = Agent(
    name="dsa_agent",
    model=os.getenv("AGENT_MODEL", "gemini-2.0-flash"),
    generate_content_config=retry_config,
    description="Specialist for Data Structures and Algorithms",
    instruction="""You are the DSA Specialist.

**Routing Logic:**
1.  **Concepts / Learning / Roadmaps:**
    *   Queries like "Explain Arrays", "What is a Linked List?", "Create a DSA course", "I want to learn sorting".
    *   **Route to:** `dsa_tutor`

2.  **Coding Problems / Implementation:**
    *   Queries like "Write code for Bubble Sort", "Solve Two Sum", "Implement a Binary Search Tree".
    *   **Route to:** `dsa_solver`

**Important:**
- If the user asks a mixed question (e.g., "Explain arrays and write code for rotation"), prefer `dsa_solver` as it can explain and code.
- Generally, default to `dsa_tutor` for open-ended learning questions.
- **NEVER** mention agent names (e.g., "dsa_tutor") in your final response to the user. Just act as the helper.
""",
    tools=[
        AgentTool(dsa_tutor),
        AgentTool(dsa_solver)
    ]
)
