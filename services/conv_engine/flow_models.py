"""
Data models and type definitions for the conversation orchestration system.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
import uuid


class FlowType(Enum):
    """Types of conversation flows"""
    PITCH = "pitch"
    KNOWLEDGE = "knowledge"
    OBJECTION = "objection"
    DISCOVERY = "discovery"
    CLOSING = "closing"
    RELATIONSHIP = "relationship"


class FlowStage(Enum):
    """Stages within a conversation flow"""
    INITIALIZATION = "initialization"
    ASSESSMENT = "assessment"
    EXECUTION = "execution"
    TRANSITION = "transition"
    COMPLETION = "completion"
    RECOVERY = "recovery"


class CustomerReadinessLevel(Enum):
    """Customer readiness levels for different flows"""
    NOT_READY = "not_ready"
    WARMING_UP = "warming_up"
    READY = "ready"
    HIGHLY_ENGAGED = "highly_engaged"
    RESISTANT = "resistant"


class ConversationMode(Enum):
    """Conversation interaction modes"""
    VOICE = "voice"
    TEXT = "text"
    VIDEO = "video"
    HYBRID = "hybrid"


@dataclass
class CustomerContext:
    """Customer information and context"""
    customer_id: str
    industry: Optional[str] = None
    company_size: Optional[str] = None
    technical_background: Optional[str] = None
    previous_interactions: List[Dict] = field(default_factory=list)
    pain_points: List[str] = field(default_factory=list)
    goals: List[str] = field(default_factory=list)
    preferences: Dict[str, Any] = field(default_factory=dict)
    competitive_landscape: List[str] = field(default_factory=list)


@dataclass
class ConversationState:
    """Current state of the conversation"""
    session_id: str
    current_flow: FlowType
    current_stage: FlowStage
    flow_history: List[Dict] = field(default_factory=list)
    context_data: Dict[str, Any] = field(default_factory=dict)
    customer_engagement_level: float = 0.5  # 0-1 scale
    conversation_momentum: float = 0.5  # 0-1 scale
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class FlowTransition:
    """Information about flow transitions"""
    from_flow: FlowType
    to_flow: FlowType
    trigger_reason: str
    transition_time: datetime
    context_bridge: Dict[str, Any] = field(default_factory=dict)
    success: bool = True


@dataclass
class PerformanceMetrics:
    """Performance metrics for flows"""
    flow_type: FlowType
    success_rate: float
    average_duration: float
    customer_satisfaction: float
    conversion_rate: float
    engagement_score: float
    optimization_suggestions: List[str] = field(default_factory=list)


@dataclass
class PitchContent:
    """Content for pitch delivery"""
    value_proposition: str
    proof_points: List[str]= field(default_factory=list)
    competitive_positioning: str= ""
    solution_benefits: List[str]= field(default_factory=list)
    success_stories: List[Dict]= field(default_factory=list)
    technical_details: Optional[Dict] = None
    customization_level: str = "medium"


@dataclass
class PitchOutcome:
    """Results of pitch delivery"""
    interest_level: float  # 0-1 scale
    engagement_metrics: Dict[str, float]= field(default_factory=dict)
    customer_questions: List[str]= field(default_factory=list)
    objections_raised: List[str]= field(default_factory=list)
    next_steps: List[str] = field(default_factory=list)
    follow_up_requirements: List[str]= field(default_factory=list)
    success_indicators: List[str]= field(default_factory=list)
@dataclass
class ConversationIntent:
    """Represents detected conversation intent"""
    intent_type: str
    confidence: float
    context_clues: List[str] = field(default_factory=list)
    suggested_flow: FlowType = FlowType.DISCOVERY
    urgency: str = "medium"
    emotional_tone: str = "neutral"

@dataclass
class ClassificationResult:
    """Result of flow classification analysis"""
    primary_flow: FlowType
    secondary_flows: List[FlowType] = field(default_factory=list)
    confidence_score: float = 0.5
    reasoning: str = ""
    context_factors: Dict[str, Any] = field(default_factory=dict)
    recommended_actions: List[str] = field(default_factory=list)


class ConversationEvent:
    """Base class for conversation events"""
    def __init__(self, event_type: str, timestamp: datetime = None):
        self.event_id = str(uuid.uuid4())
        self.event_type = event_type
        self.timestamp = timestamp or datetime.now()
        self.data: Dict[str, Any] = {}