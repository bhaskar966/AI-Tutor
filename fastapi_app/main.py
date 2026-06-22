import asyncio
import os
import json
import uuid
from typing import Optional
from contextlib import asynccontextmanager

# Disable OpenTelemetry tracing — fixes RecursionError in Python 3.14
# caused by contextlib.__aexit__ incompatibility with OTEL span generators
os.environ.setdefault("OTEL_SDK_DISABLED", "true")

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import StreamingResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

from ai_tutor_agent.agent import root_agent
from ai_tutor_agent.utils.db_manager import db_manager
from google.adk.sessions import DatabaseSessionService
from google.genai import types

load_dotenv(".env")                              # root .env — DATABASE_URI, ACTIVE_MODE, model config
load_dotenv("ai_tutor_agent/.env", override=True) # agent .env — can override if needed


db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'ai_tutor.db'))
db_url = os.getenv("DATABASE_URI", f"sqlite:///{db_path}")
if db_url.startswith("sqlite:///"):
    adk_db_url = db_url.replace("sqlite:///", "sqlite+aiosqlite:///")
else:
    adk_db_url = db_url

session_service = DatabaseSessionService(db_url=adk_db_url)

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await session_service.init_db()
    except AttributeError:
        pass
    yield

app = FastAPI(title="AI Tutor API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ======== MODELS ========
class LoginRequest(BaseModel):
    user_id: str

class SignupRequest(BaseModel):
    user_id: str
    name: str

class OnboardingStartRequest(BaseModel):
    user_id: str

class OnboardingChatRequest(BaseModel):
    user_id: str
    answer: str
    history: list[dict] = []

class CreatePathRequest(BaseModel):
    user_id: str
    session_id: str
    subject: str
    title: str
    syllabus: str

class ModelSettingRequest(BaseModel):
    mode: str

class QuizStartRequest(BaseModel):
    user_id: str
    session_id: str
    module_name: Optional[str] = None

class QuizAnswerRequest(BaseModel):
    user_id: str
    session_id: str
    history: list
    answer: str
    module_name: Optional[str] = None

# ======== AUTH ENDPOINTS ========

@app.post("/api/auth/login")
async def login(req: LoginRequest):
    user = db_manager.get_user(req.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@app.post("/api/auth/signup")
async def signup(req: SignupRequest):
    result = db_manager.create_user(req.user_id, req.name)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Signup failed"))
    return {"user_id": req.user_id, "name": req.name}

@app.post("/api/auth/guest")
async def guest_login():
    guest_id = f"guest_{uuid.uuid4().hex[:8]}"
    db_manager.create_user(guest_id, "Guest User")
    return {"user_id": guest_id, "name": "Guest User"}

# ======== PATHS ENDPOINTS ========

@app.get("/api/paths")
async def get_paths(user_id: str):
    return db_manager.get_learning_paths(user_id)

@app.get("/api/paths/{session_id}")
async def get_path_details(session_id: str, user_id: str):
    paths = db_manager.get_learning_paths(user_id)
    path = next((p for p in paths if p['session_id'] == session_id), None)
    if not path:
        raise HTTPException(status_code=404, detail="Path not found")
    
    profile = db_manager.get_student_profile(user_id, path['subject'])
    
    syllabus_json = {}
    if path.get('syllabus'):
        try:
            syllabus_json = json.loads(path['syllabus'])
        except:
            pass

    return {
        "path": path,
        "profile": profile,
        "syllabus": syllabus_json
    }

@app.post("/api/paths/onboarding/start")
async def onboarding_start(req: OnboardingStartRequest):
    return {
        "question": "Hello! I am your AI Tutor. What subject would you like to learn today?",
        "options": ["Python Programming", "Web Development", "iOS Development", "Data Science", "System Design", "Machine Learning"]
    }

from fastapi_app.syllabus_engine import handle_onboarding_chat

@app.post("/api/paths/onboarding/chat")
async def onboarding_chat(req: OnboardingChatRequest):
    result = handle_onboarding_chat(req.history, req.answer)
    return result

@app.post("/api/paths/create")
async def create_path(req: CreatePathRequest):
    success = db_manager.create_learning_path(req.user_id, req.session_id, req.subject, req.title)
    if success:
        db_manager.update_learning_path_details(req.session_id, req.syllabus)
        return {"success": True}
    raise HTTPException(status_code=500, detail="Failed to create path")

# ======== QUIZ ENDPOINTS ========

from fastapi_app.quiz_engine import generate_first_question, evaluate_and_generate_next

@app.get("/api/quiz/pending")
async def quiz_pending(session_id: str, user_id: str):
    """Check if a quiz is pending for this session (used on page refresh/reconnect)."""
    pending_module = db_manager.get_quiz_pending(session_id)
    if pending_module:
        return {"pending": True, "module_name": pending_module}
    return {"pending": False, "module_name": None}

@app.post("/api/quiz/start")
async def quiz_start(req: QuizStartRequest):
    paths = db_manager.get_learning_paths(req.user_id)
    path = next((p for p in paths if p['session_id'] == req.session_id), None)
    if not path or not path.get('syllabus'):
        raise HTTPException(status_code=400, detail="Syllabus not found")
    
    
    question = generate_first_question(path['syllabus'], req.module_name)
    return question

@app.post("/api/quiz/answer")
async def quiz_answer(req: QuizAnswerRequest):
    paths = db_manager.get_learning_paths(req.user_id)
    path = next((p for p in paths if p['session_id'] == req.session_id), None)
    if not path or not path.get('syllabus'):
        raise HTTPException(status_code=400, detail="Syllabus not found")
        
    result = evaluate_and_generate_next(path['syllabus'], req.history, req.answer, req.module_name)
    if result.get("status") == "complete":
        try:
            syllabus_json = json.loads(path['syllabus'])
            syllabus_updated = False
            
            if isinstance(syllabus_json, dict) and "syllabus" in syllabus_json:
                syllabus_list = syllabus_json["syllabus"]
            elif isinstance(syllabus_json, dict) and "modules" in syllabus_json:
                syllabus_list = syllabus_json["modules"]
            else:
                syllabus_list = syllabus_json if isinstance(syllabus_json, list) else []
                
            # 1. ALWAYS mark module as completed (pass or fail, student advances)
            # 2. Find insertion point: right after the completed module/topic's parent module
            insert_idx = len(syllabus_list)  # default: append at end
            if req.module_name:
                for i, m in enumerate(syllabus_list):
                    m_title = m.get("title", m.get("module", ""))
                    topics = m.get("topics", [])
                    
                    # Check if it matches the module title OR any topic inside it
                    match_found = False
                    if req.module_name.lower() in m_title.lower() or m_title.lower() in req.module_name.lower():
                        match_found = True
                        m["completed"] = True
                        m["status"] = "completed"
                        for idx_t, t in enumerate(topics):
                            if isinstance(t, str):
                                topics[idx_t] = {"title": t, "completed": True}
                            elif isinstance(t, dict):
                                t["completed"] = True
                        syllabus_updated = True
                    else:
                        for idx_t, t in enumerate(topics):
                            t_title = t.get("title", "") if isinstance(t, dict) else t
                            if req.module_name.lower() in t_title.lower() or t_title.lower() in req.module_name.lower():
                                match_found = True
                                if isinstance(t, str):
                                    topics[idx_t] = {"title": t, "completed": True}
                                elif isinstance(t, dict):
                                    t["completed"] = True
                                syllabus_updated = True
                                break
                                
                    if match_found:
                        # Add topic to completed_topics mapping
                        if "completed_topics" not in m:
                            m["completed_topics"] = []
                        if req.module_name not in m["completed_topics"]:
                            m["completed_topics"].append(req.module_name)
                            syllabus_updated = True
                            
                        # Check if all topics in this module are now completed
                        all_completed = True
                        for t in topics:
                            if isinstance(t, str):
                                if t not in m.get("completed_topics", []):
                                    all_completed = False
                                    break
                            elif isinstance(t, dict) and not t.get("completed"):
                                all_completed = False
                                break
                                
                        if all_completed and len(topics) > 0:
                            m["status"] = "completed"
                            m["completed"] = True
                            syllabus_updated = True
                            
                        # We don't mark the whole module as completed unless they finished the whole module,
                        # but for now, the user requested advancing to next topic, so we just set insert_idx
                        # to insert remedials right after this module.
                        insert_idx = i + 1
                        break
            
            # 3. Add a remedial topic for EACH wrong answer (per-question granularity)
            wrong_topics = result.get("final_review", {}).get("wrong_topics", [])
            remedials_added = 0
            for topic in wrong_topics:
                remedial_module = {
                    "module": f"Remedial: {topic}",
                    "title": f"Remedial: {topic}",
                    "status": "pending",
                    "completed": False,
                    "subtopics": [f"Review: {topic}", "Practice exercises"],
                    "topics": [
                        {"title": f"Review: {topic}", "completed": False}, 
                        {"title": "Practice exercises", "completed": False}
                    ]
                }
                syllabus_list.insert(insert_idx + remedials_added, remedial_module)
                remedials_added += 1
                syllabus_updated = True
            
            # 4. Fallback: if LLM returned needs_remedial but no wrong_topics list
            if not wrong_topics and result.get("final_review", {}).get("needs_remedial"):
                remedial_topic = result["final_review"].get("remedial_topic", "Review")
                syllabus_list.insert(insert_idx, {
                    "module": f"Remedial: {remedial_topic}",
                    "title": f"Remedial: {remedial_topic}",
                    "status": "pending",
                    "completed": False,
                    "subtopics": [f"Review: {remedial_topic}", "Practice exercises"],
                    "topics": [
                        {"title": f"Review: {remedial_topic}", "completed": False}, 
                        {"title": "Practice exercises", "completed": False}
                    ]
                })
                syllabus_updated = True
            
            if syllabus_updated:
                # Re-wrap in original structure
                if isinstance(syllabus_json, dict) and "syllabus" in syllabus_json:
                    syllabus_json["syllabus"] = syllabus_list
                elif isinstance(syllabus_json, dict) and "modules" in syllabus_json:
                    syllabus_json["modules"] = syllabus_list
                else:
                    syllabus_json = syllabus_list
                    
                new_syllabus_str = json.dumps(syllabus_json)
                db_manager.update_learning_path_details(req.session_id, new_syllabus_str)
                if result.get("final_review"):
                    result["final_review"]["syllabus_updated"] = True
            
            # 5. Clear the quiz_pending flag — student can now chat again
            db_manager.clear_quiz_pending(req.session_id)
                    
        except Exception as e:
            print("Error updating syllabus status:", e)
            # Still clear quiz pending even on error to avoid permanent lock
            db_manager.clear_quiz_pending(req.session_id)
    elif result.get("status") != "ongoing":
        # Malformed LLM response, clear lock to prevent permanent freeze
        db_manager.clear_quiz_pending(req.session_id)
            
    return result

@app.post("/api/quiz/clear")
async def quiz_clear(req: QuizStartRequest):
    db_manager.clear_quiz_pending(req.session_id)
    return {"success": True}

# ======== CHAT ENDPOINTS ========

@app.get("/api/chat/history/{session_id}")
async def get_chat_history(session_id: str, user_id: str):
    return db_manager.get_chat_history(user_id, session_id=session_id)

@app.post("/api/chat/settings/model")
async def update_model_settings(req: ModelSettingRequest):
    from ai_tutor_agent.utils.llm_config import switch_all_agents_model
    switch_all_agents_model(req.mode)
    return {"status": "updated", "mode": req.mode}

# ======== WEBSOCKET ========

@app.websocket("/ws/chat/{session_id}")
async def websocket_chat(websocket: WebSocket, session_id: str, user_id: str):
    await websocket.accept()
    
    # Ensure session exists in ADK
    session = await session_service.get_session(app_name="ai_tutor", user_id=user_id, session_id=session_id)
    if not session:
        await session_service.create_session(
            app_name="ai_tutor", 
            user_id=user_id, 
            session_id=session_id, 
            state={"current_user_id": user_id, "session_id": session_id, "authenticated": True}
        )

    from google.adk.runners import Runner
    runner = Runner(app_name="ai_tutor", agent=root_agent, session_service=session_service)

    # Inject Syllabus Context Logic
    paths = db_manager.get_learning_paths(user_id)
    current_path = next((p for p in paths if p['session_id'] == session_id), None)
    context_injected = False

    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            prompt = payload.get("prompt", "")

            hidden = payload.get("hidden", False)

            if not prompt:
                continue

            # SERVER-SIDE QUIZ ENFORCEMENT: Block all non-hidden messages while quiz is pending
            if not hidden:
                pending_module = db_manager.get_quiz_pending(session_id)
                if pending_module:
                    await websocket.send_json({
                        "type": "quiz_required",
                        "module": pending_module,
                        "content": f"You must complete the quiz for '{pending_module}' before continuing."
                    })
                    await websocket.send_json({"type": "done"})
                    continue

            # Log user query if not hidden
            if not hidden:
                db_manager.log_interaction(session_id, user_id, "user", prompt, "")

            # ✅ SKIP/JUMP PREVENTION: Intercept before LLM if user is trying to jump ahead
            if not hidden:
                _skip_keywords = [
                    "skip", "jump", "move to next", "next module", "next topic",
                    "go to next", "move on", "proceed to", "start next", "let's move",
                    "can we go to", "go ahead to", "advance to", "switch to next"
                ]
                prompt_lower = prompt.lower()
                is_skip_request = any(kw in prompt_lower for kw in _skip_keywords)
                
                if is_skip_request:
                    # Find first incomplete (not completed, not taught) topic
                    paths = db_manager.get_learning_paths(user_id)
                    current_path = next((p for p in paths if p['session_id'] == session_id), None)
                    _first_pending = None
                    if current_path and current_path.get('syllabus'):
                        try:
                            _syl = json.loads(current_path['syllabus'])
                            _syl_list = _syl.get("syllabus", _syl.get("modules", _syl)) if isinstance(_syl, dict) else _syl
                            for _mod in (_syl_list if isinstance(_syl_list, list) else []):
                                for _t in _mod.get("topics", []):
                                    if isinstance(_t, dict) and not _t.get("completed") and not _t.get("taught"):
                                        _first_pending = _t.get("title", "the current topic")
                                        break
                                    elif isinstance(_t, str) and _t not in _mod.get("completed_topics", []):
                                        _first_pending = _t
                                        break
                                if _first_pending:
                                    break
                        except Exception:
                            pass
                    
                    if _first_pending:
                        restriction_msg = (
                            f"⚠️ **You are trying to move forward.**\n\n"
                            f"To advance past **\"{_first_pending}\"**, you must first pass its mandatory assessment. "
                            f"I am generating the quiz for you now. If you pass, the next topic will automatically unlock!"
                        )
                        await websocket.send_json({"type": "chunk", "content": restriction_msg, "author": "ai_tutor"})
                        await websocket.send_json({"type": "done"})
                        
                        # Auto-trigger the quiz to let them "test out" of the topic
                        db_manager.set_quiz_pending(session_id, _first_pending)
                        await websocket.send_json({"type": "status", "content": f"Preparing Mandatory Quiz for {_first_pending}..."})
                        await websocket.send_json({"type": "trigger_quiz", "module": _first_pending})
                        
                        db_manager.log_interaction(session_id, user_id, "ai_tutor", "", restriction_msg)
                        continue



            # Always fetch latest path to ensure syllabus updates are reflected
            paths = db_manager.get_learning_paths(user_id)
            current_path = next((p for p in paths if p['session_id'] == session_id), None)
            
            final_prompt = prompt
            if current_path and current_path.get('syllabus'):
                try:
                    syl_data = json.loads(current_path['syllabus'])
                    syl_list = syl_data.get("syllabus", syl_data.get("modules", syl_data))
                    syl_text = "Syllabus Outline:\n"
                    first_incomplete_topic = None
                    first_incomplete_status = None
                    for idx, mod in enumerate(syl_list if isinstance(syl_list, list) else []):
                        m_status = '[Completed]' if mod.get('completed') else '[Pending]'
                        syl_text += f"Module {idx+1}: {mod.get('title', mod.get('module', 'Unknown'))} {m_status}\n"
                        for t in mod.get('topics', []):
                            if isinstance(t, dict):
                                t_title = t.get('title', 'Unknown')
                                if t.get('completed'):
                                    t_status = '[Completed]'
                                elif t.get('taught'):
                                    t_status = '[Taught]'
                                else:
                                    t_status = '[Pending]'
                            else:
                                t_title = t
                                t_status = '[Completed]' if t in mod.get('completed_topics', []) else '[Pending]'
                                
                            syl_text += f"  - {t_title} {t_status}\n"
                            
                            if t_status in ('[Pending]', '[Taught]') and not first_incomplete_topic:
                                first_incomplete_topic = t_title
                                first_incomplete_status = t_status
                except Exception:
                    syl_text = current_path['syllabus'] # fallback
                    first_incomplete_topic = None
                    first_incomplete_status = None
                    
                enforcement_msg = ""
                # Skip enforcement injection if a quiz is already pending or if this is a hidden system action
                is_quiz_pending = db_manager.get_quiz_pending(session_id) is not None
                if not hidden and not is_quiz_pending and first_incomplete_topic:
                    if first_incomplete_status == '[Pending]':
                        enforcement_msg = f"\n\n<system_status>\nCurrent topic: '{first_incomplete_topic}' ([Pending]).\nGoal: Teach this topic. If the user asks a question, just answer it naturally. DO NOT call `mark_topic_taught` unless the user explicitly confirms they fully understand the entire topic and have no more questions about it.\n</system_status>"
                    elif first_incomplete_status == '[Taught]':
                        enforcement_msg = f"\n\n<system_status>\nCurrent topic: '{first_incomplete_topic}' ([Taught]).\nAction Required: The topic is marked as taught. You MUST immediately use the `transfer_to_agent` tool to transfer to the `assessment_agent` to start the mandatory quiz. Do not ask for permission.\n</system_status>"
                    
                final_prompt = f"[System: Active Syllabus context:\n{syl_text}{enforcement_msg}]\n\n{prompt}"

            message = types.Content(role="user", parts=[types.Part(text=final_prompt)])
            full_response = ""
            current_agent = "ai_tutor"
            marked_taught_topic = False

            try:
                async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=message):
                    func_calls = event.get_function_calls() if hasattr(event, 'get_function_calls') else []
                    func_calls = list(func_calls) if func_calls else []
                    
                    if hasattr(event, 'content') and event.content and hasattr(event.content, 'parts') and event.content.parts:
                        for part in event.content.parts:
                            if hasattr(part, 'function_call') and part.function_call:
                                if part.function_call not in func_calls:
                                    func_calls.append(part.function_call)

                    if func_calls:
                        for call in func_calls:
                            if call.name == "transfer_to_agent":
                                agent_name = call.args.get("agent_name", "specialist") if hasattr(call.args, 'get') else "specialist"
                                display_name = agent_name.replace("_", " ").title()
                                await websocket.send_json({"type": "status", "content": f"Consulting {display_name}..."})
                            elif call.name == "trigger_topic_quiz":
                                module_name = "Unknown Topic"
                                if hasattr(call, 'args'):
                                    if hasattr(call.args, 'get'):
                                        module_name = call.args.get("topic_name", call.args.get("module_name", "Unknown Topic"))
                                    elif hasattr(call.args, 'fields'):
                                        fields = call.args.fields
                                        topic = fields.get("topic_name") or fields.get("module_name")
                                        if topic:
                                            module_name = getattr(topic, 'string_value', "Unknown Topic")
                                # Set quiz pending in DB — this blocks future chat messages
                                db_manager.set_quiz_pending(session_id, module_name)
                                await websocket.send_json({"type": "status", "content": f"Preparing Mandatory Quiz for {module_name}..."})
                                await websocket.send_json({"type": "trigger_quiz", "module": module_name})
                            elif call.name == "mark_topic_taught":
                                marked_taught_topic = True
                                await websocket.send_json({"type": "status", "content": "Marking topic as completed..."})
                            else:
                                await websocket.send_json({"type": "status", "content": f"Running {call.name}..."})
                    
                    if hasattr(event, 'content') and event.content and hasattr(event.content, 'parts') and event.content.parts:
                        for part in event.content.parts:
                            if hasattr(part, 'function_call') and part.function_call:
                                continue # Skip to avoid Gemini SDK .text warning
                            try:
                                if hasattr(part, 'text') and part.text:
                                    # Only stream text from agents.
                                    author = event.author
                                    part_text = part.text
                                    
                                    # JSON LEAKAGE PROTECTOR: If the string starts building a JSON object, buffer it, don't stream.
                                    full_response += part_text
                                    _stripped = full_response.strip()
                                    
                                    if _stripped.startswith("{") and '"name"' in _stripped:
                                        # It is hallucinating a raw JSON tool call. Hold it back.
                                        pass
                                    else:
                                        await websocket.send_json({
                                            "type": "chunk", 
                                            "content": part_text,
                                            "author": author
                                        })
                                    current_agent = author
                            except Exception:
                                pass
            except Exception as e:
                await websocket.send_json({"type": "chunk", "content": f"\n\nError: {str(e)}", "author": "system"})

            # JSON SALVAGER: If we buffered a raw JSON object, extract its text and send it as one block now
            if full_response.strip().startswith("{") and '"name"' in full_response:
                import re
                try:
                    json_str = full_response.strip()
                    last_brace = json_str.rfind('}')
                    if last_brace != -1:
                        json_str = json_str[:last_brace+1]
                    data = json.loads(json_str)
                    
                    extracted = None
                    text_keys = ("description", "content", "text", "response", "answer", "message")
                    
                    for k in text_keys:
                        if isinstance(data.get(k), str) and data[k].strip():
                            extracted = data[k].strip()
                            break
                            
                    if not extracted:
                        for nested_key in ("parameters", "args"):
                            nested_obj = data.get(nested_key)
                            if isinstance(nested_obj, dict):
                                for k in text_keys:
                                    if isinstance(nested_obj.get(k), str) and nested_obj[k].strip():
                                        extracted = nested_obj[k].strip()
                                        break
                                if extracted: break
                                
                    if extracted:
                        await websocket.send_json({"type": "chunk", "content": extracted, "author": current_agent})
                        full_response = extracted  # Update for clean logging
                except Exception:
                    pass

            await websocket.send_json({"type": "done"})
            
            # Log final response
            if full_response:
                db_manager.log_interaction(session_id, user_id, current_agent, "", full_response)

            # FALLBACK: If this was a hidden quiz-completion message and the orchestrator
            # produced no visible output (it reasoned internally but didn't route to a sub-agent),
            # send a second, ultra-direct nudge so the next topic gets taught automatically.
            if hidden and not full_response:
                paths = db_manager.get_learning_paths(user_id)
                current_path = next((p for p in paths if p['session_id'] == session_id), None)
                next_topic = None
                if current_path and current_path.get('syllabus'):
                    try:
                        syl_data = json.loads(current_path['syllabus'])
                        syl_list = syl_data.get("syllabus", syl_data.get("modules", syl_data))
                        for mod in (syl_list if isinstance(syl_list, list) else []):
                            for t in mod.get('topics', []):
                                t_title = t.get('title', t) if isinstance(t, dict) else t
                                if isinstance(t, dict) and not t.get('completed') and not t.get('taught'):
                                    next_topic = t_title
                                    break
                                elif isinstance(t, str) and t not in mod.get('completed_topics', []):
                                    next_topic = t_title
                                    break
                            if next_topic:
                                break
                    except Exception:
                        pass

                nudge = f"SYSTEM: The quiz is done. {'Teach the next topic: ' + repr(next_topic) + '. ' if next_topic else ''}Transfer to theory_agent immediately. Do not output text first."
                nudge_msg = types.Content(role="user", parts=[types.Part(text=nudge)])
                nudge_response = ""
                nudge_agent = "ai_tutor"
                try:
                    async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=nudge_msg):
                        func_calls_n = event.get_function_calls() if hasattr(event, 'get_function_calls') else []
                        func_calls_n = list(func_calls_n) if func_calls_n else []
                        if hasattr(event, 'content') and event.content and hasattr(event.content, 'parts'):
                            for part in event.content.parts:
                                if hasattr(part, 'function_call') and part.function_call:
                                    if part.function_call not in func_calls_n:
                                        func_calls_n.append(part.function_call)
                        for call in func_calls_n:
                            if call.name == "transfer_to_agent":
                                agent_name = call.args.get("agent_name", "specialist") if hasattr(call.args, 'get') else "specialist"
                                await websocket.send_json({"type": "status", "content": f"Consulting {agent_name.replace('_',' ').title()}..."})
                        if hasattr(event, 'content') and event.content and hasattr(event.content, 'parts'):
                            for part in event.content.parts:
                                if hasattr(part, 'function_call') and part.function_call:
                                    continue
                                try:
                                    if hasattr(part, 'text') and part.text:
                                        author = event.author
                                        nudge_response += part.text
                                        await websocket.send_json({"type": "chunk", "content": part.text, "author": author})
                                        nudge_agent = author
                                except Exception:
                                    pass
                except Exception as e:
                    print("Nudge fallback error:", e)
                if nudge_response:
                    db_manager.log_interaction(session_id, user_id, nudge_agent, "", nudge_response)
                await websocket.send_json({"type": "done"})

            # FALLBACK 2: If mark_topic_taught was called but no transfer was initiated, nudge for quiz
            elif marked_taught_topic and not full_response:
                nudge = "SYSTEM: You just marked the topic as taught. IMMEDIATE ACTION REQUIRED: call transfer_to_agent to transfer to assessment_agent to trigger the quiz. Do not output any text."
                nudge_msg = types.Content(role="user", parts=[types.Part(text=nudge)])
                nudge_response = ""
                nudge_agent = "ai_tutor"
                try:
                    async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=nudge_msg):
                        func_calls_n = event.get_function_calls() if hasattr(event, 'get_function_calls') else []
                        func_calls_n = list(func_calls_n) if func_calls_n else []
                        if hasattr(event, 'content') and event.content and hasattr(event.content, 'parts'):
                            for part in event.content.parts:
                                if hasattr(part, 'function_call') and part.function_call:
                                    if part.function_call not in func_calls_n:
                                        func_calls_n.append(part.function_call)
                        for call in func_calls_n:
                            if call.name == "transfer_to_agent":
                                agent_name = call.args.get("agent_name", "specialist") if hasattr(call.args, 'get') else "specialist"
                                await websocket.send_json({"type": "status", "content": f"Consulting {agent_name.replace('_',' ').title()}..."})
                            elif call.name == "trigger_topic_quiz":
                                module_name = "Unknown Topic"
                                if hasattr(call, 'args'):
                                    if hasattr(call.args, 'get'):
                                        module_name = call.args.get("topic_name", call.args.get("module_name", "Unknown Topic"))
                                    elif hasattr(call.args, 'fields'):
                                        fields = call.args.fields
                                        topic = fields.get("topic_name") or fields.get("module_name")
                                        if topic:
                                            module_name = getattr(topic, 'string_value', "Unknown Topic")
                                db_manager.set_quiz_pending(session_id, module_name)
                                await websocket.send_json({"type": "status", "content": f"Preparing Mandatory Quiz for {module_name}..."})
                                await websocket.send_json({"type": "trigger_quiz", "module": module_name})
                        if hasattr(event, 'content') and event.content and hasattr(event.content, 'parts'):
                            for part in event.content.parts:
                                if hasattr(part, 'function_call') and part.function_call:
                                    continue
                                try:
                                    if hasattr(part, 'text') and part.text:
                                        author = event.author
                                        nudge_response += part.text
                                        await websocket.send_json({"type": "chunk", "content": part.text, "author": author})
                                        nudge_agent = author
                                except Exception:
                                    pass
                except Exception as e:
                    print("Quiz nudge fallback error:", e)
                if nudge_response:
                    db_manager.log_interaction(session_id, user_id, nudge_agent, "", nudge_response)
                await websocket.send_json({"type": "done"})

    except WebSocketDisconnect:
        pass

# Mount frontend
app.mount("/app", StaticFiles(directory="frontend/dist", html=True), name="frontend")

@app.get("/")
async def root():
    return RedirectResponse(url="/app/index.html")
