"""Database manager for persistent storage."""
from sqlalchemy import create_engine, Column, String, Text, DateTime, Integer, Engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session as SQLSession
from datetime import datetime
import os

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    user_id = Column(String(100), primary_key=True)
    name = Column(String(200), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class Interaction(Base):
    __tablename__ = 'interactions'
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(100), nullable=False, index=True)
    user_id = Column(String(100), nullable=False, index=True)
    agent_name = Column(String(100))
    query = Column(Text)
    response = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)

class StudentProfile(Base):
    __tablename__ = 'student_profiles'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(100), nullable=False, index=True)
    subject = Column(String(50), nullable=False)  # e.g., 'dsa', 'math'
    level = Column(String(50), default='beginner')  # e.g., 'beginner', 'intermediate'
    details = Column(Text, default='{}')  # JSON string for granular tracking
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class LearningPath(Base):
    __tablename__ = 'learning_paths'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(100), nullable=False, index=True)
    session_id = Column(String(100), nullable=False, unique=True)
    subject = Column(String(50), nullable=False)
    title = Column(String(200), nullable=False)
    syllabus = Column(Text, default='{}')  # JSON string for path-specific syllabus
    created_at = Column(DateTime, default=datetime.utcnow)

class DBManager:
    """Singleton database manager for user and interaction storage."""
    
    _instance = None
    engine: Engine
    Session: sessionmaker[SQLSession]
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DBManager, cls).__new__(cls)
            db_uri = os.getenv("DATABASE_URI", "sqlite:///ai_tutor.db")
            cls._instance.engine = create_engine(db_uri, echo=False)
            Base.metadata.create_all(cls._instance.engine)
            cls._instance.Session = sessionmaker(bind=cls._instance.engine)
            
            # Auto-Migration for 'syllabus' column
            # SQLite doesn't support "IF NOT EXISTS" for ADD COLUMN nicely, so we try/except
            from sqlalchemy import text
            try:
                with cls._instance.engine.connect() as conn:
                    conn.execute(text("ALTER TABLE learning_paths ADD COLUMN syllabus TEXT DEFAULT '{}'"))
            except Exception:
                # Column likely exists
                pass
            
        return cls._instance
    
    def get_session(self) -> SQLSession:
        """Get a new database session."""
        return self.Session()
    
    def create_user(self, user_id: str, name: str) -> dict:
        """Create a new user in the database."""
        session = self.get_session()
        try:
            user = User(user_id=user_id, name=name)
            session.add(user)
            session.commit()
            return {"success": True, "user_id": user_id, "name": name}
        except Exception as e:
            session.rollback()
            return {"success": False, "error": str(e)}
        finally:
            session.close()
    
    def get_user(self, user_id: str) -> dict | None:
        """Get user by user_id."""
        session = self.get_session()
        try:
            user = session.query(User).filter_by(user_id=user_id).first()
            if user:
                return {"user_id": user.user_id, "name": user.name}
            return None
        finally:
            session.close()
    

    def log_interaction(self, session_id: str, user_id: str, agent_name: str, 
                       query: str, response: str) -> bool:
        """Log an interaction to the database."""
        session = self.get_session()
        try:
            interaction = Interaction(
                session_id=session_id,
                user_id=user_id,
                agent_name=agent_name,
                query=query,
                response=response
            )
            session.add(interaction)
            session.commit()
            return True
        except:
            session.rollback()
            return False
        finally:
            session.close()

    def get_chat_history(self, user_id: str, session_id: str = None, limit: int = 20) -> list:
        """Get recent chat history for a user, optionally filtered by session."""
        session = self.get_session()
        try:
            query = session.query(Interaction).filter_by(user_id=user_id)
            if session_id:
                query = query.filter_by(session_id=session_id)
            
            interactions = query.order_by(Interaction.timestamp.desc()).limit(limit).all()
            
            # Return reversed to show chronological order
            return [{
                "id": i.id,
                "agent": i.agent_name,
                "query": i.query,
                "response": i.response if i.response else "Thinking...", # Handle pending
                "timestamp": i.timestamp.isoformat()
            } for i in reversed(interactions)]
        finally:
            session.close()

    def update_student_profile(self, user_id: str, subject: str, level: str, details: str = "{}") -> bool:
        """Update or create a student profile for a subject."""
        session = self.get_session()
        try:
            profile = session.query(StudentProfile).filter_by(
                user_id=user_id, subject=subject
            ).first()
            
            if profile:
                profile.level = level
                profile.details = details
            else:
                profile = StudentProfile(
                    user_id=user_id,
                    subject=subject,
                    level=level,
                    details=details
                )
                session.add(profile)
            
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            print(f"Error updating profile: {e}")
            return False
        finally:
            session.close()

    def get_student_profile(self, user_id: str, subject: str = None) -> list | dict:
        """Get student profile(s). If subject is None, returns all subjects."""
        session = self.get_session()
        try:
            if subject:
                profile = session.query(StudentProfile).filter_by(
                    user_id=user_id, subject=subject
                ).first()
                return {
                    "subject": profile.subject,
                    "level": profile.level,
                    "details": profile.details
                } if profile else None
            else:
                profiles = session.query(StudentProfile).filter_by(user_id=user_id).all()
                return [{
                    "subject": p.subject,
                    "level": p.level,
                    "details": p.details
                } for p in profiles]
        finally:
            session.close()

    def create_learning_path(self, user_id: str, session_id: str, subject: str, title: str) -> bool:
        """Create a new learning path."""
        session = self.get_session()
        try:
            path = LearningPath(
                user_id=user_id,
                session_id=session_id,
                subject=subject.lower(), # Normalize
                title=title
            )
            session.add(path)
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            print(f"Error creating learning path: {e}")
            return False
        finally:
            session.close()

    def update_learning_path_details(self, session_id: str, syllabus: str) -> bool:
        """Update the syllabus for a specific learning path."""
        session = self.get_session()
        try:
            path = session.query(LearningPath).filter_by(session_id=session_id).first()
            if path:
                path.syllabus = syllabus
                session.commit()
                return True
            return False
        except Exception as e:
            session.rollback()
            print(f"Error updating path syllabus: {e}")
            return False
        finally:
            session.close()

    def get_learning_paths(self, user_id: str) -> list:
        """Get all learning paths for a user."""
        session = self.get_session()
        try:
            paths = session.query(LearningPath).filter_by(user_id=user_id).order_by(LearningPath.created_at.desc()).all()
            return [{
                "id": p.id,
                "session_id": p.session_id,
                "subject": p.subject,
                "title": p.title,
                "syllabus": p.syllabus,
                "created_at": p.created_at.isoformat()
            } for p in paths]
        finally:
            session.close()

db_manager = DBManager()
