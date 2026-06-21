import os
import json
import litellm
import re

litellm.set_verbose = False

def _get_litellm_model():
    from ai_tutor_agent.utils.llm_config import get_model_name
    model = get_model_name()
    if not model.startswith("ollama/") and "/" not in model:
        return f"gemini/{model}"
    return model

def _extract_json(text: str) -> dict:
    try:
        return json.loads(text.strip())
    except:
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        return {}

def handle_onboarding_chat(history: list[dict], user_answer: str) -> dict:
    """
    Evaluates the onboarding conversation.
    Returns either:
    {"status": "ongoing", "question": "...", "options": ["opt1", "opt2", ...]}
    or
    {"status": "complete", "syllabus": {...}, "subject": "...", "title": "..."}
    """
    model = _get_litellm_model()
    
    # Reconstruct conversation for LLM
    messages = [
        {"role": "system", "content": """You are an expert curriculum designer and AI Tutor.
Your goal is to create a highly personalized learning syllabus for the user.
You should ask 1 or 2 follow-up questions to understand their current skill level, their main goal, or specific areas of interest before generating the syllabus.

IMPORTANT: You MUST ALWAYS output ONLY valid JSON. Do not include markdown code blocks around the JSON.

If you DO NOT have enough information yet:
You MUST ask your question as a Multiple Choice question whenever possible to make it easy for the user.
Output this JSON schema:
{
  "status": "ongoing",
  "question": "Your question text here...",
  "options": ["Option 1", "Option 2", "Option 3"]
}
(Only omit the "options" array if a text input is absolutely strictly necessary).

If you HAVE enough information (e.g., they specified the topic and you know their rough level):
You MUST output this JSON schema:
{
  "status": "complete",
  "subject": "slugified_subject_name (e.g. ios_development)",
  "title": "Display Title (e.g. Advanced iOS Development)",
  "syllabus": {
    "modules": [
      {
        "title": "Module Name",
        "completed": false,
        "topics": [
          { "title": "Topic 1", "taught": false, "completed": false },
          { "title": "Topic 2", "taught": false, "completed": false }
        ]
      }
    ]
  }
}
}
"""}
    ]
    
    # Process history from frontend format
    for msg in history:
        role = "assistant" if msg.get("agent") == "ai_tutor" else "user"
        messages.append({"role": role, "content": msg.get("text", "")})
        
    # Append current user answer
    if user_answer.strip():
        messages.append({"role": "user", "content": user_answer})
        
    try:
        response = litellm.completion(
            model=model,
            messages=messages,
            temperature=0.7
        )
        
        content = response.choices[0].message.content.strip()
        parsed = _extract_json(content)
        
        if parsed.get("status") == "complete" and "syllabus" in parsed and "subject" in parsed:
            return {
                "status": "complete",
                "syllabus": parsed["syllabus"],
                "subject": parsed["subject"],
                "title": parsed.get("title", "Learning Path")
            }
        elif parsed.get("status") == "ongoing" and "question" in parsed:
            return parsed
            
        # Fallback if LLM forgets status key
        if "syllabus" in parsed:
            return {
                "status": "complete",
                "syllabus": parsed["syllabus"],
                "subject": parsed.get("subject", "general"),
                "title": parsed.get("title", "Learning Path")
            }
            
        return {
            "status": "ongoing",
            "question": parsed.get("question", "Could you elaborate on that?"),
            "options": parsed.get("options", [])
        }
        
    except Exception as e:
        print(f"Error in syllabus generation: {e}")
        return {"status": "ongoing", "question": "I had trouble understanding that. Could you tell me more about your goals?"}
