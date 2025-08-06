from sqlalchemy import create_engine, Column, Integer, String, DateTime, JSON, Float, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.orm import scoped_session, sessionmaker
from datetime import datetime
from enum import Enum
import json

Base = declarative_base()

class ProspectSource(Enum):
    FORM_SUBMISSION = "form_submission"
    COLD_LIST = "cold_list"
    REFERRAL = "referral"
    WEBSITE_VISITOR = "website_visitor"

class CallOutcome(Enum):
    COMPLETED = "completed"
    NO_ANSWER = "no_answer"
    BUSY = "busy"
    FAILED = "failed"
    VOICEMAIL = "voicemail"

class Prospect(Base):
    __tablename__ = 'prospects'
    
    id = Column(Integer, primary_key=True)
    phone_number = Column(String(15), unique=True, nullable=False)
    email = Column(String(100))
    name = Column(String(100))
    
    # Source tracking
    source = Column(String(20), nullable=False)
    source_data = Column(JSON)
    
    # Product interest
    product_interest = Column(String(100))
    product_category = Column(String(50))
    
    # Company data (for cold leads)
    company = Column(String(100))
    job_title = Column(String(100))
    industry = Column(String(50))
    
    # Engagement tracking
    created_at = Column(DateTime, default=datetime.utcnow)
    last_contacted = Column(DateTime)
    contact_attempts = Column(Integer, default=0)
    
    # Qualification data
    qualification_score = Column(Float, default=0)
    qualification_stage = Column(String(20), default='unqualified')
    
    # Call management
    call_status = Column(String(20), default='pending')
    best_call_time = Column(String(10))
    timezone = Column(String(20), default='UTC')
    
    # Form-specific data
    form_submitted_at = Column(DateTime)
    form_data = Column(JSON)
    
    # Preferences
    do_not_call = Column(Boolean, default=False)
    preferred_contact_method = Column(String(20), default='phone')

class CallHistory(Base):
    __tablename__ = 'call_history'
    
    id = Column(Integer, primary_key=True)
    prospect_id = Column(Integer, nullable=False)
    call_sid = Column(String(50), unique=True)
    
    # Call metadata
    call_type = Column(String(20))
    call_duration = Column(Integer)
    call_outcome = Column(String(20))
    
    # Conversation data
    conversation_log = Column(JSON)
    conversation_summary = Column(Text)
    qualification_score = Column(Float)
    component_scores = Column(JSON)
    
    # Actions and follow-up
    next_action = Column(String(50))
    callback_scheduled = Column(DateTime)
    notes = Column(Text)
    
    # Timing
    called_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    
    # Recording
    recording_url = Column(String(500))
    recording_duration = Column(Integer)

class Campaign(Base):
    __tablename__ = 'campaigns'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    campaign_type = Column(String(20))  # form_follow_up, cold_outreach, mixed
    
    # Campaign settings
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    
    # Statistics
    total_prospects = Column(Integer, default=0)
    calls_attempted = Column(Integer, default=0)
    calls_completed = Column(Integer, default=0)
    qualified_leads = Column(Integer, default=0)
    
    # Configuration
    campaign_config = Column(JSON)
    status = Column(String(20), default='created')

# Add this method to the DatabaseManager class



class DatabaseManager:
    def __init__(self, database_url, **kwargs):
        self.database_url = database_url
        
        # Create engine with connection pooling
        engine_options = {
            'pool_size': 10,
            'max_overflow': 20,
            'pool_timeout': 30,
            'pool_recycle': 3600,
            'echo': False,
            **kwargs
        }
        
        self.engine = create_engine(database_url, **engine_options)
        
        # Create session factory
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        
        # Create scoped session for thread safety
        self.ScopedSession = scoped_session(self.SessionLocal)
        
        # Create tables
        Base.metadata.create_all(bind=self.engine)
    
    def get_session(self):
        """Get a new database session"""
        return self.SessionLocal()
    
    def get_scoped_session(self):
        """Get scoped session (thread-safe)"""
        return self.ScopedSession()
    
    def close_session(self):
        """Close scoped session"""
        self.ScopedSession.remove()