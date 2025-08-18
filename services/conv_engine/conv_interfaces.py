"""
Integration interfaces and contracts between the three layers
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

from .flow_models import ClassificationResult, ConversationIntent, CustomerContext, FlowType



    
class IFlowEngine(ABC):
    """Interface that all specialized flow engines must implement"""
    
    @abstractmethod
    def can_handle_flow(self, flow_type: FlowType) -> bool:
        """Check if this engine can handle the specified flow type"""
        pass
    
    @abstractmethod
    def initialize_flow(self, session_id: str, customer_context: CustomerContext, 
                       flow_context: Dict[str, Any]) -> Dict[str, Any]:
        """Initialize the flow with customer and conversation context"""
        pass
    
    @abstractmethod
    def execute_flow_segment(self, session_id: str, customer_input: str, 
                           segment_context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a segment of the flow and return results"""
        pass
    
    @abstractmethod
    def handle_interruption(self, session_id: str, interruption_type: str) -> Dict[str, Any]:
        """Handle interruptions during flow execution"""
        pass
    
    @abstractmethod
    def finalize_flow(self, session_id: str) -> Dict[str, Any]:
        """Finalize the flow and return outcomes"""
        pass
    
    @abstractmethod
    def get_flow_status(self, session_id: str) -> Dict[str, Any]:
        """Get current status of the flow execution"""
        pass


class IClassificationEngine(ABC):
    """Interface for the classification engine"""
    
    @abstractmethod
    def analyze_conversation(self, customer_input: str, conversation_history: List[Dict[str, Any]], 
                           customer_context: CustomerContext) -> Tuple[List[ConversationIntent], Dict[str, Any]]:
        """Analyze conversation and return intents and signals"""
        pass
    
    @abstractmethod
    def classify_flow_needs(self, intents: List[ConversationIntent], customer_signals: Dict[str, Any], 
                          conversation_context: Dict[str, Any]) -> ClassificationResult:
        """Classify what flow is needed"""
        pass
    
    @abstractmethod
    def evaluate_transition_readiness(self, current_flow: FlowType, target_flow: FlowType, 
                                    conversation_state: Dict[str, Any]) -> Tuple[bool, float, str]:
        """Evaluate if ready for flow transition"""
        pass
    
    @abstractmethod
    def adapt_classification_real_time(self, current_classification: ClassificationResult, 
                                     conversation_events: List[Any], 
                                     performance_feedback: Dict[str, float]) -> ClassificationResult:
        """Adapt classification based on real-time feedback"""
        pass
    
    @abstractmethod
    def learn_from_outcomes(self, session_id: str, classification_sequence: List[ClassificationResult], 
                          final_outcomes: Dict[str, Any]) -> Dict[str, Any]:
        """Learn from conversation outcomes"""
        pass


class IOrchestrationEngine(ABC):
    """Interface for the orchestration engine"""
    
    @abstractmethod
    def register_flow_engine(self, flow_types: List[FlowType], engine: IFlowEngine) -> bool:
        """Register a specialized flow engine"""
        pass
    
    @abstractmethod
    def set_classification_engine(self, classification_engine: IClassificationEngine) -> None:
        """Set the classification engine"""
        pass
    
    @abstractmethod
    def process_customer_input(self, session_id: str, customer_input: str) -> Dict[str, Any]:
        """Main entry point for processing customer input"""
        pass
    
    @abstractmethod
    def get_conversation_status(self, session_id: str) -> Dict[str, Any]:
        """Get current conversation status"""
        pass


class FlowEngineRegistry:
    """Registry for managing specialized flow engines"""
    
    def __init__(self):
        self.engines: Dict[FlowType, IFlowEngine] = {}
        self.engine_capabilities: Dict[str, List[FlowType]] = {}
    
    def register_engine(self, engine_name: str, engine: IFlowEngine, flow_types: List[FlowType]) -> bool:
        """Register an engine for specific flow types"""
        try:
            for flow_type in flow_types:
                if engine.can_handle_flow(flow_type):
                    self.engines[flow_type] = engine
                    
            self.engine_capabilities[engine_name] = flow_types
            return True
        except Exception as e:
            print(f"Failed to register engine {engine_name}: {e}")
            return False
    
    def get_engine_for_flow(self, flow_type: FlowType) -> Optional[IFlowEngine]:
        """Get the appropriate engine for a flow type"""
        return self.engines.get(flow_type)
    
    def get_available_flows(self) -> List[FlowType]:
        """Get all available flow types"""
        return list(self.engines.keys())


class ConversationEvent:
    """Event for communication between layers"""
    
    def __init__(self, event_type: str, session_id: str, data: Dict[str, Any]):
        self.event_id = f"{datetime.now().isoformat()}_{session_id}_{event_type}"
        self.event_type = event_type
        self.session_id = session_id
        self.timestamp = datetime.now()
        self.data = data
        self.processed = False


class EventBus:
    """Event bus for inter-component communication"""
    
    def __init__(self):
        self.subscribers: Dict[str, List[callable]] = {}
        self.event_history: List[ConversationEvent] = []
    
    def subscribe(self, event_type: str, handler: callable) -> None:
        """Subscribe to events of a specific type"""
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(handler)
    
    def publish(self, event: ConversationEvent) -> None:
        """Publish an event to all subscribers"""
        self.event_history.append(event)
        
        if event.event_type in self.subscribers:
            for handler in self.subscribers[event.event_type]:
                try:
                    handler(event)
                except Exception as e:
                    print(f"Error in event handler: {e}")
        
        event.processed = True
    
    def get_events_for_session(self, session_id: str) -> List[ConversationEvent]:
        """Get all events for a specific session"""
        return [event for event in self.event_history if event.session_id == session_id]


class IntegrationBridge:
    """Bridge class that handles data transformation between layers"""
    
    @staticmethod
    def classification_to_orchestration(classification_result: ClassificationResult) -> Dict[str, Any]:
        """Transform classification result for orchestration layer"""
        return {
            "primary_flow": classification_result.primary_flow,
            "secondary_flows": classification_result.secondary_flows,
            "confidence": classification_result.confidence_score,
            "reasoning": classification_result.reasoning,
            "context_factors": classification_result.context_factors,
            "recommended_actions": classification_result.recommended_actions
        }
    
    @staticmethod
    def orchestration_to_engine(orchestration_context: Dict[str, Any], 
                              engine_type: str) -> Dict[str, Any]:
        """Transform orchestration context for specific engine"""
        base_context = {
            "session_id": orchestration_context.get("session_id"),
            "customer_context": orchestration_context.get("customer_context"),
            "conversation_state": orchestration_context.get("conversation_state"),
            "flow_context": orchestration_context.get("flow_context", {})
        }
        
        # Engine-specific transformations
        if engine_type == "pitch":
            base_context.update({
                "pitch_focus_areas": orchestration_context.get("focus_areas", []),
                "customer_readiness": orchestration_context.get("readiness_level", 0.5),
                "discovered_needs": orchestration_context.get("customer_needs", []),
                "pain_points": orchestration_context.get("pain_points", [])
            })
        elif engine_type == "knowledge":
            base_context.update({
                "knowledge_gaps": orchestration_context.get("knowledge_gaps", []),
                "customer_questions": orchestration_context.get("questions", []),
                "complexity_level": orchestration_context.get("technical_level", "intermediate")
            })
        
        return base_context
    
    @staticmethod
    def engine_to_orchestration(engine_result: Dict[str, Any], 
                              engine_type: str) -> Dict[str, Any]:
        """Transform engine result back to orchestration format"""
        base_result = {
            "execution_status": engine_result.get("status", "completed"),
            "customer_response": engine_result.get("customer_response", {}),
            "message": engine_result.get("message", ""),
            "next_recommended_action": engine_result.get("next_action"),
            "performance_metrics": engine_result.get("metrics", {}),
            "context_updates": engine_result.get("context_updates", {})
        }
        
        # Engine-specific result handling
        if engine_type == "pitch":
            pitch_outcome = engine_result.get("pitch_outcome")
            if pitch_outcome:
                base_result.update({
                    "interest_level": pitch_outcome.interest_level,
                    "objections_raised": pitch_outcome.objections_raised,
                    "next_steps": pitch_outcome.next_steps,
                    "follow_up_requirements": pitch_outcome.follow_up_requirements
                })
        
        return base_result
    
    @staticmethod
    def outcomes_to_classification_feedback(session_outcomes: Dict[str, Any]) -> Dict[str, float]:
        """Transform session outcomes to classification feedback"""
        return {
            "classification_accuracy": session_outcomes.get("classification_accuracy", 0.5),
            "flow_effectiveness": session_outcomes.get("overall_effectiveness", 0.5),
            "customer_satisfaction": session_outcomes.get("customer_satisfaction", 0.5),
            "objective_achievement": session_outcomes.get("objective_achievement", 0.5),
            "conversation_momentum": session_outcomes.get("final_momentum", 0.5)
        }


class PerformanceFeedbackCollector:
    """Collects and aggregates performance feedback for learning"""
    
    def __init__(self):
        self.session_feedback: Dict[str, Dict[str, Any]] = {}
        self.aggregated_metrics: Dict[str, float] = {}
    
    def collect_flow_feedback(self, session_id: str, flow_type: FlowType, 
                            flow_outcomes: Dict[str, Any]) -> None:
        """Collect feedback from a specific flow execution"""
        if session_id not in self.session_feedback:
            self.session_feedback[session_id] = {}
        
        self.session_feedback[session_id][f"{flow_type.value}_feedback"] = {
            "timestamp": datetime.now(),
            "outcomes": flow_outcomes,
            "effectiveness": flow_outcomes.get("effectiveness", 0.5)
        }
    
    def collect_session_feedback(self, session_id: str, final_outcomes: Dict[str, Any]) -> None:
        """Collect final session feedback"""
        if session_id not in self.session_feedback:
            self.session_feedback[session_id] = {}
        
        self.session_feedback[session_id]["session_final"] = {
            "timestamp": datetime.now(),
            "final_outcomes": final_outcomes,
            "overall_success": final_outcomes.get("overall_success", 0.5)
        }
    
    def get_feedback_for_learning(self, session_id: str) -> Dict[str, Any]:
        """Get aggregated feedback for learning algorithms"""
        session_data = self.session_feedback.get(session_id, {})
        
        feedback = {
            "flow_performances": {},
            "transition_effectiveness": {},
            "overall_metrics": {}
        }
        
        # Aggregate flow performances
        for key, value in session_data.items():
            if key.endswith("_feedback"):
                flow_name = key.replace("_feedback", "")
                feedback["flow_performances"][flow_name] = value.get("effectiveness", 0.5)
        
        # Overall metrics
        if "session_final" in session_data:
            feedback["overall_metrics"] = session_data["session_final"]["final_outcomes"]
        
        return feedback
    
    def update_aggregated_metrics(self) -> None:
        """Update aggregated metrics across all sessions"""
        all_effectiveness = []
        flow_effectiveness = {}
        
        for session_data in self.session_feedback.values():
            for key, value in session_data.items():
                if key.endswith("_feedback"):
                    flow_name = key.replace("_feedback", "")
                    if flow_name not in flow_effectiveness:
                        flow_effectiveness[flow_name] = []
                    flow_effectiveness[flow_name].append(value.get("effectiveness", 0.5))
                    all_effectiveness.append(value.get("effectiveness", 0.5))
        
        # Update aggregated metrics
        if all_effectiveness:
            self.aggregated_metrics["overall_average"] = sum(all_effectiveness) / len(all_effectiveness)
        
        for flow_name, effectiveness_list in flow_effectiveness.items():
            if effectiveness_list:
                self.aggregated_metrics[f"{flow_name}_average"] = sum(effectiveness_list) / len(effectiveness_list)