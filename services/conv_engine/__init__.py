"""
Conversation Engine Package

Handles import order to prevent circular dependencies
"""

# Import base models first
from .flow_models import *

# Import interfaces (but avoid importing implementations that depend on interfaces)
from .conv_interfaces import (
    IFlowEngine, IClassificationEngine, IOrchestrationEngine,
    FlowEngineRegistry, EventBus, ConversationEvent, IntegrationBridge,
    PerformanceFeedbackCollector,FlowType
)

try:
    from .flow_classfier import (
        ConversationAnalyzer, FlowTypeClassifier, ContextualClassifier,
        AdaptiveClassifier, ConversationIntent, ClassificationResult,
        FlowClassificationEngine
    )
except ImportError as e:
    print(f"Warning: Could not import flow_classfier components: {e}")

try:
    from .pitch_flow import PitchAdaptationEngine
except ImportError as e:
    print(f"Warning: Could not import pitch_flow components: {e}")

try:
    from .flow_orch import (
        FlowStateManager, FlowTransitionController, ConversationOrchestrator,
        FlowPerformanceAnalyzer
    )
except ImportError as e:
    print(f"Warning: Could not import flow_orch components: {e}")

# Ensure FlowType is available at package level
try:
    from .flow_models import FlowType
except ImportError:
    pass
