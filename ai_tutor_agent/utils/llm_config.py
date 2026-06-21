import os
from dotenv import load_dotenv

load_dotenv()

def get_model_name():
    """Helper to get the current model string based on ACTIVE_MODE."""
    mode = os.getenv("ACTIVE_MODE", "online")
    if mode == "online":
        return os.getenv("ONLINE_MODEL", "gemini-2.5-flash")
    return os.getenv("LOCAL_MODEL", "ollama/llama3")

def get_model():
    """Return the correct model connector based on ACTIVE_MODE env var."""
    model_name = get_model_name()
    
    if model_name.startswith("ollama/") or "/" in model_name:
        from google.adk.models.lite_llm import LiteLlm, _ensure_litellm_imported
        import litellm
        _ensure_litellm_imported()
        class LocalToolLiteLlm(LiteLlm):
            async def generate_content_async(self, llm_request, stream=False, **kwargs):
                full_text = ""
                all_chunks = []

                async for chunk in super().generate_content_async(llm_request, stream=stream, **kwargs):
                    all_chunks.append(chunk)
                    try:
                        for candidate in chunk.candidates:
                            for part in candidate.content.parts:
                                if getattr(part, 'text', None):
                                    full_text += part.text
                    except Exception:
                        pass

                stripped = full_text.strip()
                import re, json

                # Build the set of *real* tool names from the request so we
                # never convert a hallucinated name (e.g. "explain_topic") into
                # a FunctionCall that ADK can't dispatch.
                valid_tool_names: set = set()
                try:
                    for tool in (llm_request.tools or []):
                        for decl in (getattr(tool, 'function_declarations', None) or []):
                            n = getattr(decl, 'name', None)
                            if n:
                                valid_tool_names.add(n)
                except Exception:
                    pass
                # Always allow the built-in ADK transfer call
                valid_tool_names.add("transfer_to_agent")

                json_match = re.search(r'\{\s*"name"\s*:', stripped)
                if json_match:
                    try:
                        json_str = stripped[json_match.start():]
                        
                        # Extract from the first '{' to the last '}' to strip trailing text/markdown
                        last_brace = json_str.rfind('}')
                        if last_brace != -1:
                            json_str = json_str[:last_brace+1]
                            
                        data = json.loads(json_str)
                        name = data.get("name")
                        args = data.get("parameters", data.get("args", {}))

                        # Only treat as a real tool call if the name is registered
                        if name and (not valid_tool_names or name in valid_tool_names):
                            from google.genai.types import FunctionCall, Part, GenerateContentResponse, Candidate, Content
                            fc_part = Part(function_call=FunctionCall(name=name, args=args))
                            yield GenerateContentResponse(
                                candidates=[Candidate(content=Content(parts=[fc_part], role="model"))]
                            )
                            return
                        
                        # Hallucinated tool OR structured JSON answer:
                        # Try to extract readable text from common response-field names,
                        # checking both the root object and nested parameters/args.
                        preamble = stripped[:json_match.start()].strip()
                        text_keys = ("description", "content", "text", "response",
                                     "answer", "result", "summary", "explanation", "message")
                        extracted = None
                        
                        # Check top level
                        for k in text_keys:
                            if isinstance(data.get(k), str) and data[k].strip():
                                extracted = data[k].strip()
                                break
                                
                        # Check inside parameters/args
                        if not extracted:
                            for nested_key in ("parameters", "args"):
                                nested_obj = data.get(nested_key)
                                if isinstance(nested_obj, dict):
                                    for k in text_keys:
                                        if isinstance(nested_obj.get(k), str) and nested_obj[k].strip():
                                            extracted = nested_obj[k].strip()
                                            break
                                    if extracted: break

                        if not extracted:
                            # Fall back: join all non-empty string values from top level and nested
                            vals = []
                            for v in data.values():
                                if isinstance(v, str): vals.append(v)
                                elif isinstance(v, dict):
                                    for sub_v in v.values():
                                        if isinstance(sub_v, str): vals.append(sub_v)
                            parts_text = " ".join(v for v in vals if v.strip())
                            if parts_text.strip():
                                extracted = parts_text.strip()

                    except Exception as e:
                        print("Local tool parse error, falling back to regex:", e)
                        # json.loads failed (likely unescaped newlines or cut off). Use regex to salvage text.
                        import re
                        text_match = re.search(r'"(?:text|message|response|description)"\s*:\s*"((?:[^"\\]|\\.)*)"', json_str)
                        if text_match:
                            extracted = text_match.group(1).replace('\\"', '"').replace('\\n', '\n')
                        else:
                            extracted = ""

                    output_text = "\n\n".join(filter(None, [preamble, extracted]))
                    if not output_text.strip():
                        output_text = "[SYSTEM: Intercepted broken JSON tool call but could not extract text. Raw: " + json_str[:50] + "...]"
                    
                    from google.genai.types import Part, GenerateContentResponse, Candidate, Content
                    yield GenerateContentResponse(
                        candidates=[Candidate(content=Content(parts=[Part(text=output_text)], role="model"))]
                    )
                    return  # Never emit raw JSON
                
                # If no json_match at all, stream the original chunks normally
                for chunk in all_chunks:
                    yield chunk

        return LocalToolLiteLlm(model=model_name)
    else:
        return model_name

def get_streaming_model():
    """Return the model connector with streaming enabled for specialist agents."""
    return get_model()

def get_retry_config():
    """Return retry config only for Gemini models. None for LiteLLM."""
    model_name = get_model_name()
    if "/" not in model_name:
        from google.genai import types
        return types.GenerateContentConfig(
            http_options=types.HttpOptions(
                retry_options=types.HttpRetryOptions(initial_delay=2, attempts=15)
            )
        )
    return None

def switch_all_agents_model(mode: str):
    """
    Dynamically switches the model for all running ADK agents
    and persists the setting in .env
    """
    # 1. Update ENV file to persist
    env_path = ".env"
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            lines = f.readlines()
        
        found = False
        for i, line in enumerate(lines):
            if line.startswith("ACTIVE_MODE="):
                lines[i] = f"ACTIVE_MODE={mode}\n"
                found = True
                break
        
        if not found:
            lines.append(f"ACTIVE_MODE={mode}\n")
            
        with open(env_path, "w") as f:
            f.writelines(lines)
    else:
        with open(env_path, "w") as f:
            f.write("ONLINE_MODEL=gemini-2.5-flash\n")
            f.write("LOCAL_MODEL=ollama/llama3\n")
            f.write(f"ACTIVE_MODE={mode}\n")
            
    # 2. Update current environment
    os.environ["ACTIVE_MODE"] = mode
    
    # 3. Reload models in running ADK agents
    new_model_instance = get_model()
    from ai_tutor_agent.agent import root_agent
    
    def set_model_recursive(agent, m):
        agent.model = m
        for sub in getattr(agent, 'sub_agents', []) or []:
            set_model_recursive(sub, m)
            
    set_model_recursive(root_agent, new_model_instance)
