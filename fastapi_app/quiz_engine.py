import os
import json
import litellm
import re

litellm.set_verbose = False

def _get_litellm_model():
    model = os.getenv("AGENT_MODEL", "gemini-2.5-flash")
    # LiteLLM needs the provider prefix for gemini
    if not model.startswith("ollama/") and "/" not in model:
        return f"gemini/{model}"
    return model

def _extract_json(text: str) -> dict:
    try:
        # Try raw load first
        return json.loads(text.strip())
    except:
        # Try regex extract
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        return {}

def generate_first_question(syllabus: str, topic_name: str = None) -> dict:
    """Generate the first quiz question, focused on a specific topic if provided."""
    focus = ""
    if topic_name:
        focus = f"\nFocus ONLY on the topic titled \"{topic_name}\". Test knowledge specifically from this topic."
    
    prompt = f"""You are an expert AI Examiner.
Generate the very first quiz question to test the user based on the following syllabus.{focus}

Syllabus:
{syllabus}

Respond strictly in JSON format, with no markdown formatting outside the braces.
{{
    "question": "What is...",
    "type": "mcq", // strictly "mcq" or "short_answer"
    "options": ["A", "B", "C", "D"], // only include this array if type is "mcq"
    "topic": "The specific topic from syllabus being tested"
}}
"""
    model = _get_litellm_model()
    response = litellm.completion(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )
    content = response.choices[0].message.content
    return _extract_json(content)

def evaluate_and_generate_next(syllabus: str, history: list, answer: str, topic_name: str = None) -> dict:
    """Evaluate answer and generate next question. Tracks per-question correctness."""
    history_str = json.dumps(history, indent=2)
    
    focus = ""
    if topic_name:
        focus = f"\nFocus all questions on the topic titled \"{topic_name}\"."
    
    prompt = f"""You are an expert AI Examiner.
The user is learning based on this syllabus: {syllabus}{focus}
Here is the quiz history so far (each item has the question and the correct answer evaluated previously, but we are evaluating their LATEST answer now):
{history_str}

The user's latest answer to the last question was: "{answer}"
"""

    if len(history) >= 4: # 4 previous + 1 current = 5
        prompt += """
CRITICAL INSTRUCTION: This is the FINAL question. 
You MUST set "status": "complete".
DO NOT include "next_question".
You MUST include "final_review" object summarizing their performance across all questions.
"""
    else:
        prompt += """
Instruction: Generate the next question.
You MUST set "status": "ongoing".
You MUST include "next_question" object.
"""

    prompt += """
Respond strictly in JSON format:
{
    "evaluation": "Correct! Good job because...",
    "is_correct": true,
    "correct_answer": "The correct answer to the question (always include this, even if user was correct)",
    "status": "ongoing", // strictly "ongoing" or "complete"
    "next_question": { // Include ONLY if status is "ongoing"
        "question": "...",
        "type": "mcq",
        "options": ["A", "B", "C", "D"],
        "topic": "..."
    },
    "final_review": { // Include ONLY if status is "complete"
        "score": "4/5",
        "feedback": "Great overall, but you need to review X...",
        "wrong_topics": ["specific topic 1 they got wrong", "specific topic 2 they got wrong"],
        "needs_remedial": true,
        "remedial_topic": "Main weak area summary"
    }
}
"""
    model = _get_litellm_model()
    response = litellm.completion(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )
    content = response.choices[0].message.content
    return _extract_json(content)
