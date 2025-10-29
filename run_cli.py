"""CLI runner for the AI Tutor system."""
import os
import asyncio
import uuid
import sys
import warnings
import logging
import json
from typing import Optional

# Suppress warnings
warnings.filterwarnings("ignore")
logging.getLogger("google").setLevel(logging.ERROR)

# Paths
script_dir = os.path.dirname(os.path.abspath(__file__))
agent_dir = os.path.join(script_dir, 'ai_tutor_agent')
env_path = os.path.join(agent_dir, '.env')

# CRITICAL: Add PARENT of agent package to path (not agent_dir itself)
sys.path.insert(0, script_dir)  # This allows "import ai_tutor_agent"

# Load env
from dotenv import load_dotenv
load_dotenv(dotenv_path=env_path)

# Imports
from google.adk.runners import Runner
from google.adk.sessions import DatabaseSessionService
from google.genai import types

# Import as package (supports relative imports in agent.py)
from ai_tutor_agent.agent import root_agent


def clean_json_response(text: str) -> str:
    """Remove JSON wrappers."""
    text = text.strip()
    
    if text.startswith('{') and text.endswith('}'):
        try:
            data = json.loads(text)
            for key, value in data.items():
                if key.endswith('_response'):
                    if isinstance(value, dict) and 'explanation' in value:
                        return value['explanation']
                    return str(value)
            return json.dumps(data, indent=2)
        except:
            pass
    
    return text


async def main():
    """Run AI Tutor CLI."""
    
    db_url = os.getenv("DATABASE_URI", f"sqlite:///{os.path.join(script_dir, 'ai_tutor.db')}")
    session_service = DatabaseSessionService(db_url=db_url)
    
    runner = Runner(
        agent=root_agent,
        session_service=session_service,
        app_name="ai_tutor"
    )
    
    print("\n" + "="*70)
    print("🎓 AI TUTOR SYSTEM")
    print("="*70 + "\n")
    
    session_id = f"session_{uuid.uuid4().hex[:8]}"
    session = await session_service.create_session(
        app_name="ai_tutor",
        user_id=session_id
    )
    
    print("Type 'exit' to quit.\n" + "="*70 + "\n")
    
    is_guest = False
    guest_user_id: Optional[str] = None
    
    while True:
        try:
            query = input("You: ").strip()
            
            if not query:
                continue
            
            if query.lower() in ['exit', 'quit', 'bye']:
                if is_guest and guest_user_id:
                    try:
                        from ai_tutor_agent.utils.db_manager import db_manager, User
                        db_session = db_manager.get_session()
                        try:
                            db_session.query(User).filter_by(user_id=guest_user_id).delete()
                            db_session.commit()
                            print("\n🗑️  Guest cleaned.")
                        except:
                            pass
                        finally:
                            db_session.close()
                    except:
                        pass
                
                print("\n👋 Goodbye!\n")
                break
            
            user_message = types.Content(
                role='user',
                parts=[types.Part(text=query)]
            )
            
            events = runner.run_async(
                user_id=session_id,
                session_id=session.id,
                new_message=user_message
            )
            
            print("\n🤖 Tutor:\n")
            
            all_text_parts = []
            seen_texts = set()
            
            async for event in events:
                if hasattr(event, 'content') and event.content:
                    if hasattr(event.content, 'parts') and event.content.parts:
                        for part in event.content.parts:
                            if hasattr(part, 'text') and part.text:
                                text = str(part.text).strip()
                                text = clean_json_response(text)
                                
                                if text and text not in seen_texts:
                                    seen_texts.add(text)
                                    all_text_parts.append(text)
            
            if all_text_parts:
                full_response = '\n\n'.join(all_text_parts)
                print(full_response)
                
                if "guest_" in full_response.lower():
                    is_guest = True
                    import re
                    match = re.search(r'guest_[a-f0-9]{6}', full_response.lower())
                    if match:
                        guest_user_id = match.group(0)
            else:
                print("(No response)")
            
            print()
            
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!\n")
            break
        except Exception as e:
            if "429" in str(e):
                print("\n⚠️  Rate limit. Waiting 60s...\n")
                await asyncio.sleep(60)
            else:
                print(f"\n❌ Error: {str(e)}\n")


if __name__ == "__main__":
    os.chdir(script_dir)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!\n")
    except Exception as e:
        print(f"\n❌ Fatal: {str(e)}\n")
        sys.exit(1)
