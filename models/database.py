import logging
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

# Enhanced database models to support inbound calls
# Add these to your existing models/database.py file

from sqlalchemy import Column, Integer, String, DateTime, JSON, Float, Boolean, Text, Enum as SQLEnum
from datetime import datetime
from enum import Enum

# Enhanced ProspectSource enum to include inbound calls
class ProspectSource(Enum):
    FORM_SUBMISSION = "form_submission"
    COLD_LIST = "cold_list"
    REFERRAL = "referral"
    WEBSITE_VISITOR = "website_visitor"
    INBOUND_CALL = "inbound_call"  # NEW: For people who call us
    CALLBACK_REQUEST = "callback_request"  # NEW: For scheduled callbacks

# Enhanced CallOutcome enum
class CallOutcome(Enum):
    COMPLETED = "completed"
    NO_ANSWER = "no_answer"
    BUSY = "busy"
    FAILED = "failed"
    VOICEMAIL = "voicemail"
    TRANSFERRED = "transferred"  # NEW: For calls transferred to agents
    ABANDONED = "abandoned"     # NEW: For calls that hung up early

# Add new enum for call direction
class CallDirection(Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"

# Add new enum for inbound call intent
class InboundIntent(Enum):
    SALES_INQUIRY = "sales_inquiry"
    SUPPORT_REQUEST = "support_request"
    COMPLAINT = "complaint"
    GENERAL_INQUIRY = "general_inquiry"
    TRANSFER_REQUEST = "transfer_request"
    CALLBACK_FOLLOWUP = "callback_followup"

# Enhanced Prospect model (add these fields to existing Prospect class)
class EnhancedProspectFields:
    """
    Add these fields to your existing Prospect model:
    """
    
    # Inbound call tracking
    first_inbound_call = Column(DateTime)
    total_inbound_calls = Column(Integer, default=0)
    last_inbound_call = Column(DateTime)
    
    # Call preferences and behavior
    preferred_call_time = Column(String(20))  # e.g., "morning", "afternoon", "evening"
    caller_behavior = Column(JSON)  # Track calling patterns
    
    # Lead quality indicators
    inbound_lead_score = Column(Float, default=0)  # Separate score for inbound behavior
    callback_requested = Column(Boolean, default=False)
    callback_scheduled_for = Column(DateTime)
    
    # Communication preferences
    wants_text_updates = Column(Boolean, default=False)
    wants_email_updates = Column(Boolean, default=False)
    
    # Customer service flags
    has_complained = Column(Boolean, default=False)
    satisfaction_score = Column(Float)  # 1-10 scale
    
    # Referral tracking
    referred_by_prospect_id = Column(Integer)  # Foreign key to another prospect
    has_referred_others = Column(Boolean, default=False)

# Enhanced CallHistory model (add these fields to existing CallHistory class)
class EnhancedCallHistoryFields:
    """
    Add these fields to your existing CallHistory model:
    """
    
    # Call direction and intent
    call_direction = Column(SQLEnum(CallDirection), default=CallDirection.OUTBOUND)
    inbound_intent = Column(SQLEnum(InboundIntent))
    
    # Enhanced call metadata
    caller_wait_time = Column(Integer)  # Seconds before call was answered
    transfer_attempted = Column(Boolean, default=False)
    transfer_successful = Column(Boolean, default=False)
    transfer_target = Column(String(50))  # Phone number or agent ID
    
    # Call quality metrics
    audio_quality_score = Column(Float)  # 0-1 score from Twilio
    speech_recognition_accuracy = Column(Float)  # Average confidence
    customer_satisfaction = Column(Integer)  # 1-5 if collected
    
    # Business context
    business_hours_call = Column(Boolean, default=True)
    holiday_call = Column(Boolean, default=False)
    
    # Follow-up tracking
    follow_up_required = Column(Boolean, default=False)
    follow_up_type = Column(String(50))  # 'callback', 'email', 'text', etc.
    follow_up_completed = Column(Boolean, default=False)
    follow_up_completed_at = Column(DateTime)
    
    # Agent handoff
    escalated_to_human = Column(Boolean, default=False)
    escalation_reason = Column(String(200))
    agent_id = Column(String(50))  # If transferred to specific agent
    
    # Conversation analysis
    customer_emotion = Column(String(20))  # 'positive', 'negative', 'neutral', 'frustrated'
    key_topics_mentioned = Column(JSON)  # Array of topics discussed
    objections_raised = Column(JSON)  # Array of objections
    buying_signals = Column(JSON)  # Array of positive signals
    
    # Marketing attribution (for inbound calls)
    marketing_source = Column(String(100))  # Where they heard about us
    marketing_campaign = Column(String(100))  # Specific campaign reference
    
    # Voicemail specific
    voicemail_transcription = Column(Text)
    voicemail_sentiment = Column(String(20))

# New table for Call Queue Management
class CallQueue(Base):
    __tablename__ = 'call_queue'
    
    id = Column(Integer, primary_key=True)
    call_sid = Column(String(50), unique=True, nullable=False)
    prospect_id = Column(Integer, nullable=False)
    
    # Queue metadata
    queue_entry_time = Column(DateTime, default=datetime.utcnow)
    estimated_wait_time = Column(Integer)  # Seconds
    queue_position = Column(Integer)
    priority_level = Column(Integer, default=1)  # 1=normal, 2=high, 3=urgent
    
    # Queue status
    status = Column(String(20), default='waiting')  # waiting, connected, abandoned, transferred
    connected_at = Column(DateTime)
    abandoned_at = Column(DateTime)
    
    # Agent assignment
    assigned_agent_id = Column(String(50))
    assignment_time = Column(DateTime)

# New table for Callback Requests
class CallbackRequest(Base):
    __tablename__ = 'callback_requests'
    
    id = Column(Integer, primary_key=True)
    prospect_id = Column(Integer, nullable=False)
    
    # Request details
    requested_at = Column(DateTime, default=datetime.utcnow)
    requested_time = Column(DateTime)  # When they want to be called back
    reason = Column(String(200))  # Why they want a callback
    priority = Column(String(20), default='normal')  # normal, high, urgent
    
    # Request metadata
    request_source = Column(String(50))  # 'voicemail', 'after_hours', 'transfer_fail', etc.
    notes = Column(Text)
    
    # Fulfillment
    status = Column(String(20), default='pending')  # pending, scheduled, completed, cancelled
    scheduled_at = Column(DateTime)
    completed_at = Column(DateTime)
    assigned_agent = Column(String(50))
    
    # Results
    callback_call_sid = Column(String(50))  # SID of the callback call
    outcome = Column(String(50))  # reached, no_answer, reschedule, etc.

# New table for Business Hours Configuration
class BusinessHours(Base):
    __tablename__ = 'business_hours'
    
    id = Column(Integer, primary_key=True)
    
    # Day configuration (0=Monday, 6=Sunday)
    day_of_week = Column(Integer, nullable=False)  # 0-6
    is_business_day = Column(Boolean, default=True)
    
    # Hours
    open_time = Column(String(5))  # "09:00"
    close_time = Column(String(5))  # "17:00"
    timezone = Column(String(50), default='UTC')
    
    # Special handling
    lunch_break_start = Column(String(5))  # Optional lunch break
    lunch_break_end = Column(String(5))
    
    # Holiday overrides
    is_holiday = Column(Boolean, default=False)
    holiday_name = Column(String(100))
    holiday_date = Column(DateTime)
    
    # Configuration metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

# New table for Agent Availability (if using human agents)
class AgentAvailability(Base):
    __tablename__ = 'agent_availability'
    
    id = Column(Integer, primary_key=True)
    agent_id = Column(String(50), nullable=False)
    agent_name = Column(String(100))
    
    # Availability status
    status = Column(String(20), default='offline')  # online, busy, offline, break
    last_status_change = Column(DateTime, default=datetime.utcnow)
    
    # Capacity
    max_concurrent_calls = Column(Integer, default=1)
    current_call_count = Column(Integer, default=0)
    
    # Skills and routing
    skills = Column(JSON)  # Array of skills like ['sales', 'support', 'billing']
    department = Column(String(50))
    priority_level = Column(Integer, default=1)  # For call routing
    
    # Performance metrics
    calls_handled_today = Column(Integer, default=0)
    avg_call_duration = Column(Float, default=0)
    customer_satisfaction = Column(Float, default=0)
    
    # Schedule
    shift_start = Column(DateTime)
    shift_end = Column(DateTime)
    
    # Contact info
    phone_number = Column(String(20))
    extension = Column(String(10))

# Database migration script
def add_inbound_call_support(db_manager):
    """
    Add inbound call support to existing database
    Run this to migrate your existing database
    """
    try:
        # Create new tables
        Base.metadata.create_all(bind=db_manager.engine)
        
        # Add new columns to existing tables (manual migration)
        session = db_manager.get_session()
        
        # Example of adding columns (adjust based on your DB engine)
        migration_queries = [
            "ALTER TABLE prospects ADD COLUMN first_inbound_call TIMESTAMP",
            "ALTER TABLE prospects ADD COLUMN total_inbound_calls INTEGER DEFAULT 0",
            "ALTER TABLE prospects ADD COLUMN last_inbound_call TIMESTAMP",
            "ALTER TABLE prospects ADD COLUMN preferred_call_time VARCHAR(20)",
            "ALTER TABLE prospects ADD COLUMN caller_behavior JSON",
            "ALTER TABLE prospects ADD COLUMN inbound_lead_score FLOAT DEFAULT 0",
            "ALTER TABLE prospects ADD COLUMN callback_requested BOOLEAN DEFAULT FALSE",
            "ALTER TABLE prospects ADD COLUMN callback_scheduled_for TIMESTAMP",
            "ALTER TABLE prospects ADD COLUMN wants_text_updates BOOLEAN DEFAULT FALSE",
            "ALTER TABLE prospects ADD COLUMN wants_email_updates BOOLEAN DEFAULT FALSE",
            "ALTER TABLE prospects ADD COLUMN has_complained BOOLEAN DEFAULT FALSE",
            "ALTER TABLE prospects ADD COLUMN satisfaction_score FLOAT",
            "ALTER TABLE prospects ADD COLUMN referred_by_prospect_id INTEGER",
            "ALTER TABLE prospects ADD COLUMN has_referred_others BOOLEAN DEFAULT FALSE",
            
            "ALTER TABLE call_history ADD COLUMN call_direction VARCHAR(10) DEFAULT 'outbound'",
            "ALTER TABLE call_history ADD COLUMN inbound_intent VARCHAR(50)",
            "ALTER TABLE call_history ADD COLUMN caller_wait_time INTEGER",
            "ALTER TABLE call_history ADD COLUMN transfer_attempted BOOLEAN DEFAULT FALSE",
            "ALTER TABLE call_history ADD COLUMN transfer_successful BOOLEAN DEFAULT FALSE",
            "ALTER TABLE call_history ADD COLUMN transfer_target VARCHAR(50)",
            "ALTER TABLE call_history ADD COLUMN audio_quality_score FLOAT",
            "ALTER TABLE call_history ADD COLUMN speech_recognition_accuracy FLOAT",
            "ALTER TABLE call_history ADD COLUMN customer_satisfaction INTEGER",
            "ALTER TABLE call_history ADD COLUMN business_hours_call BOOLEAN DEFAULT TRUE",
            "ALTER TABLE call_history ADD COLUMN holiday_call BOOLEAN DEFAULT FALSE",
            "ALTER TABLE call_history ADD COLUMN follow_up_required BOOLEAN DEFAULT FALSE",
            "ALTER TABLE call_history ADD COLUMN follow_up_type VARCHAR(50)",
            "ALTER TABLE call_history ADD COLUMN follow_up_completed BOOLEAN DEFAULT FALSE",
            "ALTER TABLE call_history ADD COLUMN follow_up_completed_at TIMESTAMP",
            "ALTER TABLE call_history ADD COLUMN escalated_to_human BOOLEAN DEFAULT FALSE",
            "ALTER TABLE call_history ADD COLUMN escalation_reason VARCHAR(200)",
            "ALTER TABLE call_history ADD COLUMN agent_id VARCHAR(50)",
            "ALTER TABLE call_history ADD COLUMN customer_emotion VARCHAR(20)",
            "ALTER TABLE call_history ADD COLUMN key_topics_mentioned JSON",
            "ALTER TABLE call_history ADD COLUMN objections_raised JSON",
            "ALTER TABLE call_history ADD COLUMN buying_signals JSON",
            "ALTER TABLE call_history ADD COLUMN marketing_source VARCHAR(100)",
            "ALTER TABLE call_history ADD COLUMN marketing_campaign VARCHAR(100)",
            "ALTER TABLE call_history ADD COLUMN voicemail_transcription TEXT",
            "ALTER TABLE call_history ADD COLUMN voicemail_sentiment VARCHAR(20)"
        ]
        
        # Note: Execute these carefully based on your database engine
        # Some databases might have different syntax
        
        logging.info("Database migration for inbound calls completed")
        
    except Exception as e:
        logging.error(f"Database migration error: {str(e)}")
        raise

# Helper functions for inbound call management
def get_next_available_agent(skills_required=None):
    """Get next available agent for call transfer"""
    # Implementation would query AgentAvailability table
    pass

def update_call_queue_position(call_sid, new_position):
    """Update position in call queue"""
    # Implementation would update CallQueue table
    pass

def schedule_callback(prospect_id, requested_time, reason):
    """Schedule a callback request"""
    # Implementation would create CallbackRequest record
    pass

def get_business_hours_for_date(date):
    """Get business hours configuration for specific date"""
    # Implementation would query BusinessHours table
    pass

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