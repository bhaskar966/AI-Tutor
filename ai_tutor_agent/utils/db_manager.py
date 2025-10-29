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

# Singleton instance
db_manager = DBManager()
