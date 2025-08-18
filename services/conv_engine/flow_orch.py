"""
GenericFlowCoordinator.py - Top level orchestration and state management classes
"""

import os
import re
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import logging
from abc import ABC, abstractmethod
from .conv_interfaces import (
    IOrchestrationEngine, IFlowEngine, IClassificationEngine,
    FlowEngineRegistry, EventBus, ConversationEvent, IntegrationBridge,
    PerformanceFeedbackCollector
)
from .flow_models import ClassificationResult, FlowType, FlowStage, CustomerContext, ConversationState, FlowTransition, PerformanceMetrics, ConversationEvent, CustomerReadinessLevel



class FlowStateManager:
    """Manages conversation flow state and history"""
    
    def __init__(self):
        self.active_sessions: Dict[str, ConversationState] = {}
        self.flow_history: Dict[str, List[FlowTransition]] = {}
        self.logger = logging.getLogger(__name__)

    
    
    def initialize_conversation_flow(
        self, 
        call_type: str, 
        customer_context: CustomerContext,
        session_id: Optional[str] = None  # ← ADD THIS

    ) -> str:
        """Initialize a new conversation flow session"""
        
        clean_customer_id = re.sub(r'[^\w\-]', '', customer_context.customer_id)

        if session_id is None:
            session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{customer_context.customer_id}"
        
        # Determine initial flow based on call type
        initial_flow = self._determine_initial_flow(call_type, customer_context)
        
        conversation_state = ConversationState(
            session_id=session_id,
            current_flow=initial_flow,
            current_stage=FlowStage.INITIALIZATION,
            context_data={
                "call_type": call_type,
                "customer_context": customer_context,
                "start_time": datetime.now()
            }
        )
        
        self.active_sessions[session_id] = conversation_state
        self.flow_history[session_id] = []
        
        self.logger.info(f"Initialized session {session_id} with flow {initial_flow}")
        return session_id
    
    def track_current_flow_state(
        self, 
        session_id: str, 
        flow_type: FlowType, 
        stage: FlowStage
    ) -> bool:
        """Track and update current flow state"""
        if session_id not in self.active_sessions:
            self.logger.error(f"Session {session_id} not found")
            return False
        
        session = self.active_sessions[session_id]
        previous_flow = session.current_flow
        previous_stage = session.current_stage
        
        session.current_flow = flow_type
        session.current_stage = stage
        session.last_updated = datetime.now()
        
        # Log state change
        self.logger.info(
            f"Session {session_id}: {previous_flow}.{previous_stage} -> {flow_type}.{stage}"
        )
        
        return True
    
    def maintain_flow_history(
        self, 
        session_id: str, 
        flow_transitions: List[FlowTransition]
    ) -> None:
        """Maintain comprehensive flow transition history"""
        if session_id not in self.flow_history:
            self.flow_history[session_id] = []
        
        self.flow_history[session_id].extend(flow_transitions)
        
        # Update context data with flow history insights
        if session_id in self.active_sessions:
            session = self.active_sessions[session_id]
            session.context_data["flow_transition_count"] = len(self.flow_history[session_id])
            session.context_data["last_transition"] = flow_transitions[-1] if flow_transitions else None
    
    def preserve_cross_flow_context(
        self, 
        session_id: str, 
        context_data: Dict[str, Any]
    ) -> None:
        """Preserve context data across flow transitions"""
        if session_id in self.active_sessions:
            session = self.active_sessions[session_id]
            session.context_data.update(context_data)
            session.last_updated = datetime.now()
    
    def update_flow_progression(
        self, 
        session_id: str, 
        current_stage: FlowStage, 
        next_stage: FlowStage
    ) -> bool:
        """Update progression within current flow"""
        if session_id not in self.active_sessions:
            return False
        
        session = self.active_sessions[session_id]
        
        # Validate progression logic
        if self._validate_stage_progression(current_stage, next_stage):
            session.current_stage = next_stage
            session.last_updated = datetime.now()
            
            # Update momentum based on progression
            session.conversation_momentum = self._calculate_momentum(session)
            return True
        
        return False
    
    def _determine_initial_flow(self, call_type: str, customer_context: CustomerContext) -> FlowType:
        """Determine initial flow based on call type and context"""
        flow_mapping = {
            "cold_call": FlowType.DISCOVERY,
            "demo_request": FlowType.PITCH,
            "inbound_call": FlowType.PITCH,
            "support_inquiry": FlowType.KNOWLEDGE,
            "follow_up": FlowType.RELATIONSHIP
        }
        return flow_mapping.get(call_type, FlowType.DISCOVERY)
    
    def _validate_stage_progression(self, current: FlowStage, next_stage: FlowStage) -> bool:
        """Validate that stage progression is logical"""
        valid_progressions = {
            FlowStage.INITIALIZATION: [FlowStage.ASSESSMENT, FlowStage.EXECUTION],
            FlowStage.ASSESSMENT: [FlowStage.EXECUTION, FlowStage.TRANSITION],
            FlowStage.EXECUTION: [FlowStage.TRANSITION, FlowStage.COMPLETION, FlowStage.RECOVERY],
            FlowStage.TRANSITION: [FlowStage.ASSESSMENT, FlowStage.EXECUTION],
            FlowStage.COMPLETION: [FlowStage.TRANSITION, FlowStage.INITIALIZATION],
            FlowStage.RECOVERY: [FlowStage.ASSESSMENT, FlowStage.EXECUTION, FlowStage.TRANSITION]
        }
        return next_stage in valid_progressions.get(current, [])
    
    def _calculate_momentum(self, session: ConversationState) -> float:
        """Calculate conversation momentum based on progression and timing"""
        time_factor = min(1.0, (datetime.now() - session.last_updated).seconds / 300)  # 5 min max
        transition_factor = min(1.0, len(self.flow_history.get(session.session_id, [])) / 10)
        return max(0.1, 1.0 - time_factor - transition_factor * 0.1)
    
    def get_session_debug_info(self, session_id: str) -> Dict:

        return {
        "session_exists": session_id in self.active_sessions,
        "active_session_count": len(self.active_sessions),
        "active_session_ids": list(self.active_sessions.keys()),
        "target_session_id": session_id
        }

    def cleanup_expired_sessions(self, max_age_minutes: int = 60):
        """Remove sessions older than max_age_minutes"""
        cutoff_time = datetime.now() - timedelta(minutes=max_age_minutes)
        expired_sessions = []
        
        for session_id, session in self.active_sessions.items():
            if session.last_updated < cutoff_time:
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            del self.active_sessions[session_id]
            del self.flow_history[session_id]
            self.logger.info(f"Cleaned up expired session {session_id}")

class FlowTransitionController:
    """Controls transitions between conversation flows"""
    
    def __init__(self, state_manager: FlowStateManager):
        self.state_manager = state_manager
        self.transition_rules: Dict[FlowType, List[FlowType]] = self._init_transition_rules()
        self.logger = logging.getLogger(__name__)
    
    def detect_flow_transition_triggers(
        self, 
        conversation_input: str, 
        current_flow: FlowType
    ) -> List[Tuple[FlowType, str, float]]:
        """Detect triggers that suggest flow transitions"""
        triggers = []
        
        # Keyword-based trigger detection
        trigger_keywords = {
            FlowType.OBJECTION: ["but", "however", "concern", "worry", "expensive", "not sure","doubt","hesitant","need more info","not interested","not ready","not convinced","need time"],
            FlowType.KNOWLEDGE: ["how", "what", "explain", "tell me about", "details"],
            FlowType.PITCH: ["interested", "show me", "demo", "benefits", "features","explain","solution","tell me more","offer"],
            FlowType.CLOSING: ["price", "cost", "next steps", "when", "timeline", "decision"]
        }
        
        input_lower = conversation_input.lower()
        
        for flow_type, keywords in trigger_keywords.items():
            if flow_type != current_flow:
                keyword_matches = sum(1 for keyword in keywords if keyword in input_lower)
                if keyword_matches > 0:
                    confidence = min(1.0, keyword_matches / len(keywords) * 2)
                    triggers.append((flow_type, f"Keyword triggers: {keyword_matches}", confidence))
        
        return sorted(triggers, key=lambda x: x[2], reverse=True)
    
    def validate_flow_transition_appropriateness(
        self, 
        from_flow: FlowType, 
        to_flow: FlowType, 
        conversation_context: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """Validate if flow transition is appropriate"""
        # Check if transition is allowed
        if to_flow not in self.transition_rules.get(from_flow, []):
            return False, f"Direct transition from {from_flow} to {to_flow} not allowed"
        
        # Check timing constraints
        current_time = datetime.now()
        flow_start_time = conversation_context.get("flow_start_time", current_time)
        min_flow_duration = timedelta(seconds=30)  # Minimum time in a flow
        
        if current_time - flow_start_time < min_flow_duration:
            return False, "Minimum flow duration not met"
        
        # Check context-specific constraints
        if to_flow == FlowType.PITCH:
            customer_readiness = conversation_context.get("customer_readiness", CustomerReadinessLevel.NOT_READY)
            if customer_readiness in [CustomerReadinessLevel.NOT_READY, CustomerReadinessLevel.RESISTANT]:
                return False, "Customer not ready for pitch"
        
        return True, "Transition validated"
    
    def execute_flow_transition(
        self, 
        session_id: str, 
        target_flow: FlowType, 
        transition_reason: str
    ) -> bool:
        """Execute a flow transition"""
        session = self.state_manager.active_sessions.get(session_id)
        if not session:
            return False
        
        current_flow = session.current_flow
        
        # Create transition record
        transition = FlowTransition(
            from_flow=current_flow,
            to_flow=target_flow,
            trigger_reason=transition_reason,
            transition_time=datetime.now()
        )
        
        # Create context bridge
        bridge_context = self.create_transition_bridge(
            session.context_data, 
            {"target_flow": target_flow}
        )
        transition.context_bridge = bridge_context
        
        # Update state
        success = self.state_manager.track_current_flow_state(
            session_id, target_flow, FlowStage.INITIALIZATION
        )
        
        if success:
            # Update flow history
            self.state_manager.maintain_flow_history(session_id, [transition])
            
            # Preserve context
            self.state_manager.preserve_cross_flow_context(
                session_id, bridge_context
            )
            
            self.logger.info(f"Successfully transitioned from {current_flow} to {target_flow}")
        else:
            transition.success = False
            self.logger.error(f"Failed to transition from {current_flow} to {target_flow}")
        
        return success
    
    def create_transition_bridge(
        self, 
        current_flow_context: Dict[str, Any], 
        target_flow_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create context bridge for smooth transitions"""
        bridge = {
            "transition_timestamp": datetime.now(),
            "preserved_context": {},
            "target_flow_prep": {}
        }
        
        # Preserve important context elements
        preserve_keys = [
            "customer_context", "discovered_needs", "pain_points", 
            "engagement_level", "conversation_history"
        ]
        
        for key in preserve_keys:
            if key in current_flow_context:
                bridge["preserved_context"][key] = current_flow_context[key]
        
        # Prepare target flow context
        bridge["target_flow_prep"] = target_flow_context
        
        return bridge
    
    def handle_interrupted_flows(
        self, 
        session_id: str, 
        interruption_type: str
    ) -> bool:
        """Handle interrupted flows and recovery"""
        session = self.state_manager.active_sessions.get(session_id)
        if not session:
            return False
        
        # Save current state for potential recovery
        interruption_context = {
            "interrupted_flow": session.current_flow,
            "interrupted_stage": session.current_stage,
            "interruption_type": interruption_type,
            "interruption_time": datetime.now(),
            "recovery_context": session.context_data.copy()
        }
        
        # Transition to recovery stage
        self.state_manager.track_current_flow_state(
            session_id, session.current_flow, FlowStage.RECOVERY
        )
        
        # Preserve interruption context
        self.state_manager.preserve_cross_flow_context(
            session_id, {"interruption_context": interruption_context}
        )
        
        return True
    
    def _init_transition_rules(self) -> Dict[FlowType, List[FlowType]]:
        """Initialize flow transition rules"""
        return {
            FlowType.DISCOVERY: [FlowType.PITCH, FlowType.KNOWLEDGE, FlowType.OBJECTION],
            FlowType.PITCH: [FlowType.OBJECTION, FlowType.KNOWLEDGE, FlowType.CLOSING],
            FlowType.KNOWLEDGE: [FlowType.PITCH, FlowType.DISCOVERY, FlowType.OBJECTION],
            FlowType.OBJECTION: [FlowType.PITCH, FlowType.KNOWLEDGE, FlowType.DISCOVERY],
            FlowType.CLOSING: [FlowType.OBJECTION, FlowType.KNOWLEDGE, FlowType.RELATIONSHIP],
            FlowType.RELATIONSHIP: [FlowType.DISCOVERY, FlowType.PITCH, FlowType.KNOWLEDGE]
        }


class ConversationOrchestrator(IOrchestrationEngine):
    """Central orchestrator for conversation flows"""
    
    def __init__(self, state_manager: FlowStateManager, transition_controller: FlowTransitionController):
        self.state_manager = state_manager
        self.transition_controller = transition_controller
        self.active_engines: Dict[str, Any] = {}  # Will hold specialized engines
        self.logger = logging.getLogger(__name__)

        # ADDED: Integration components only
        self.classification_engine: Optional[IClassificationEngine] = None
        self.engine_registry = FlowEngineRegistry()
        self.event_bus = EventBus()
        self.integration_bridge = IntegrationBridge()
        self.feedback_collector = PerformanceFeedbackCollector()
        self.active_flows: Dict[str, Dict[str, Any]] = {}

    def register_flow_engine(self, flow_types: List[FlowType], engine: IFlowEngine) -> bool:
        """INTERFACE METHOD: Register specialized flow engines"""
        return self.engine_registry.register_engine(engine.__class__.__name__, engine, flow_types)
    
    def set_classification_engine(self, classification_engine: IClassificationEngine) -> None:
        """INTERFACE METHOD: Connect classification engine"""
        self.classification_engine = classification_engine
        self.logger.info("Classification engine connected")
    
    def process_customer_input(self, session_id: str, customer_input: str) -> Dict[str, Any]:
        """INTERFACE METHOD: Main integration entry point"""

        logging.info(f"FLOW_ORCH->process_customer_input-> Processing customer input for session_id= {session_id},customer_input= {customer_input}")
       
        session_state = self.state_manager.active_sessions.get(session_id)
        debug_info= self.state_manager.get_session_debug_info(session_id)
        logging.info(f"FLOW_ORCH->process_customer_input-> session debug info: {debug_info}")       
        logging.info(f"FLOW_ORCH->process_customer_input-> session_state: {session_state}")
        if not session_state:
            return {"FLOW_ORCH->process_customer_input->error": "Session not found"}
        

        logging.info(f"FLOW_ORCH->process_customer_input-> Processing STEP 1: Classify input")
        # STEP 1: Classify using classification engine
        classification_result = self._classify_input(customer_input, session_id, session_state)

        logging.info(f"FLOW_ORCH->process_customer_input-> Processing STEP 2: Orchestration decision")
        # STEP 2: Make orchestration decision (uses existing methods)
        orchestration_decision = self._make_orchestration_decision(classification_result, session_id, session_state)

        logging.info(f"FLOW_ORCH->process_customer_input-> Processing STEP 3: Execution result")
        # STEP 3: Execute using appropriate engine
        execution_result = self._execute_flow_action(orchestration_decision, customer_input, session_id)
        
        # STEP 4: Collect feedback and update state
        self._collect_feedback(session_id, classification_result, execution_result)
        self._update_state(session_id, classification_result, execution_result)
        
        return {
            "session_id": session_id,
            "classification": self.integration_bridge.classification_to_orchestration(classification_result),
            "orchestration_decision": orchestration_decision,
            "execution_result": execution_result,
            "success": True
        }
    
    def get_conversation_status(self, session_id: str) -> Dict[str, Any]:
        """INTERFACE METHOD: Enhanced status with integration info"""
        session_state = self.state_manager.active_sessions.get(session_id)
        if not session_state:
            return {"error": "Session not found"}
        
        # Get base status (uses existing state_manager)
        base_status = {
            "session_id": session_id,
            "current_flow": session_state.current_flow.value,
            "current_stage": session_state.current_stage.value,
            "engagement_level": session_state.customer_engagement_level,
            "conversation_momentum": session_state.conversation_momentum
        }
        
        # ADDED: Integration status
        if self.classification_engine:
            base_status["classification_engine_connected"] = True
        
        base_status["available_engines"] = [ft.value for ft in self.engine_registry.get_available_flows()]
        
        return base_status
    
    def finalize_conversation(self, session_id: str) -> Dict[str, Any]:
        """INTERFACE METHOD: Finalize and trigger learning"""
        final_outcomes = {}
        
        # Get outcomes from all registered engines
        for flow_type in self.engine_registry.get_available_flows():
            engine = self.engine_registry.get_engine_for_flow(flow_type)
            if engine:
                try:
                    outcome = engine.finalize_flow(session_id)
                    final_outcomes[flow_type.value] = outcome
                except Exception as e:
                    self.logger.error(f"Error finalizing {flow_type.value}: {e}")
        
        # Trigger learning in classification engine
        if self.classification_engine:
            try:
                # Get classification history from events
                conversation_events = self.event_bus.get_events_for_session(session_id)
                classification_sequence = self._extract_classification_sequence(conversation_events)
                
                learning_insights = self.classification_engine.learn_from_outcomes(
                    session_id, classification_sequence, final_outcomes
                )
                final_outcomes["learning_insights"] = learning_insights
            except Exception as e:
                self.logger.error(f"Learning failed: {e}")
        
        # Cleanup
        if session_id in self.active_flows:
            del self.active_flows[session_id]
        
        return {
            "session_id": session_id,
            "finalization_status": "completed",
            "final_outcomes": final_outcomes,
            "success": True
        }
    
    
    
    
    def coordinate_multi_flow_conversation(
        self, 
        session_id: str, 
        active_flows: List[FlowType]
    ) -> Dict[str, Any]:
        """Coordinate conversations with multiple active flows"""
        session = self.state_manager.active_sessions.get(session_id)
        if not session:
            return {"error": "Session not found"}
        
        coordination_result = {
            "primary_flow": session.current_flow,
            "secondary_flows": [f for f in active_flows if f != session.current_flow],
            "coordination_strategy": "sequential",  # or "parallel", "interleaved"
            "flow_priorities": {}
        }
        
        # Assign priorities based on customer context and conversation state
        for flow in active_flows:
            priority = self._calculate_flow_priority(flow, session)
            coordination_result["flow_priorities"][flow.value] = priority
        
        return coordination_result
    
    def prioritize_competing_flow_triggers(
        self, 
        session_id: str, 
        multiple_triggers: List[Tuple[FlowType, str, float]]
    ) -> Optional[FlowType]:
        """Prioritize when multiple flows are triggered simultaneously"""
        if not multiple_triggers:
            return None
        
        session = self.state_manager.active_sessions.get(session_id)
        if not session:
            return None
        
        # Weight triggers by confidence, context relevance, and business priority
        weighted_triggers = []
        
        for flow_type, reason, confidence in multiple_triggers:
            context_weight = self._get_context_relevance_weight(flow_type, session)
            business_weight = self._get_business_priority_weight(flow_type)
            
            total_weight = confidence * 0.4 + context_weight * 0.4 + business_weight * 0.2
            weighted_triggers.append((flow_type, total_weight))
        
        # Return highest weighted flow
        best_flow = max(weighted_triggers, key=lambda x: x[1])
        return best_flow[0] if best_flow[1] > 0.5 else None
    
    def maintain_conversation_momentum(
        self, 
        session_id: str, 
        flow_changes: List[Dict[str, Any]]
    ) -> float:
        """Maintain conversation momentum through flow changes"""
        session = self.state_manager.active_sessions.get(session_id)
        if not session:
            return 0.0
        
        # Calculate momentum factors
        time_factor = self._calculate_time_momentum(session)
        engagement_factor = session.customer_engagement_level
        transition_factor = self._calculate_transition_momentum(flow_changes)
        
        # Calculate overall momentum
        momentum = (time_factor * 0.3 + engagement_factor * 0.5 + transition_factor * 0.2)
        
        # Update session momentum
        session.conversation_momentum = momentum
        
        return momentum
    
    def align_flows_with_call_objective(
        self, 
        session_id: str, 
        call_purpose: str, 
        current_flows: List[FlowType]
    ) -> Dict[str, Any]:
        """Align active flows with overall call objectives"""
        objective_flow_mapping = {
            "sales": [FlowType.DISCOVERY, FlowType.PITCH, FlowType.CLOSING],
            "support": [FlowType.KNOWLEDGE, FlowType.DISCOVERY],
            "relationship": [FlowType.RELATIONSHIP, FlowType.DISCOVERY],
            "demo": [FlowType.PITCH, FlowType.KNOWLEDGE]
        }
        
        target_flows = objective_flow_mapping.get(call_purpose, [FlowType.DISCOVERY])
        
        alignment_result = {
            "call_purpose": call_purpose,
            "target_flows": [f.value for f in target_flows],
            "current_flows": [f.value for f in current_flows],
            "alignment_score": 0.0,
            "recommended_adjustments": []
        }
        
        # Calculate alignment score
        aligned_flows = set(target_flows) & set(current_flows)
        alignment_result["alignment_score"] = len(aligned_flows) / len(target_flows) if target_flows else 0.0
        
        # Generate recommendations
        missing_flows = set(target_flows) - set(current_flows)
        for flow in missing_flows:
            alignment_result["recommended_adjustments"].append(f"Consider activating {flow.value} flow")
        
        return alignment_result
    
    def recover_from_flow_failures(
        self, 
        session_id: str, 
        failed_flow: FlowType, 
        fallback_options: List[FlowType]
    ) -> bool:
        """Recover from flow failures with fallback strategies"""
        session = self.state_manager.active_sessions.get(session_id)
        if not session:
            return False
        
        self.logger.warning(f"Flow failure detected: {failed_flow} in session {session_id}")
        
        # Choose best fallback option
        best_fallback = self._choose_best_fallback(failed_flow, fallback_options, session)
        
        if best_fallback:
            # Execute recovery transition
            success = self.transition_controller.execute_flow_transition(
                session_id, best_fallback, f"Recovery from {failed_flow} failure"
            )
            
            if success:
                # Update context with failure information
                recovery_context = {
                    "failed_flow": failed_flow.value,
                    "failure_time": datetime.now(),
                    "recovery_flow": best_fallback.value,
                    "recovery_strategy": "fallback_transition"
                }
                
                self.state_manager.preserve_cross_flow_context(session_id, recovery_context)
                self.logger.info(f"Successfully recovered with {best_fallback}")
                return True
        
        return False
    
    def _calculate_flow_priority(self, flow: FlowType, session: ConversationState) -> float:
        """Calculate priority score for a flow"""
        base_priorities = {
            FlowType.OBJECTION: 0.9,  # High priority - must address objections
            FlowType.CLOSING: 0.8,    # High priority - business critical
            FlowType.PITCH: 0.7,      # Medium-high priority
            FlowType.DISCOVERY: 0.6,  # Medium priority
            FlowType.KNOWLEDGE: 0.5,  # Medium priority
            FlowType.RELATIONSHIP: 0.4 # Lower priority
        }
        
        base_priority = base_priorities.get(flow, 0.5)
        
        # Adjust based on session context
        context_adjustment = 0.0
        if session.customer_engagement_level > 0.7:
            context_adjustment += 0.1
        if session.conversation_momentum > 0.8:
            context_adjustment += 0.1
        
        return min(1.0, base_priority + context_adjustment)
    
    def _get_context_relevance_weight(self, flow_type: FlowType, session: ConversationState) -> float:
        """Get context relevance weight for flow type"""
        # Implementation would analyze session context for relevance
        return 0.5  # Placeholder
    
    def _get_business_priority_weight(self, flow_type: FlowType) -> float:
        """Get business priority weight for flow type"""
        priorities = {
            FlowType.CLOSING: 1.0,
            FlowType.PITCH: 0.8,
            FlowType.OBJECTION: 0.9,
            FlowType.DISCOVERY: 0.6,
            FlowType.KNOWLEDGE: 0.5,
            FlowType.RELATIONSHIP: 0.4
        }
        return priorities.get(flow_type, 0.5)
    
    def _calculate_time_momentum(self, session: ConversationState) -> float:
        """Calculate momentum based on timing"""
        time_diff = datetime.now() - session.last_updated
        minutes_passed = time_diff.total_seconds() / 60
        return max(0.0, 1.0 - minutes_passed / 30)  # Decay over 30 minutes
    
    def _calculate_transition_momentum(self, flow_changes: List[Dict[str, Any]]) -> float:
        """Calculate momentum based on flow transitions"""
        if not flow_changes:
            return 1.0
        
        recent_changes = len([c for c in flow_changes if 
                            (datetime.now() - c.get("timestamp", datetime.now())).seconds < 300])
        
        return max(0.2, 1.0 - recent_changes * 0.2)  # Penalty for too many changes
    
    def _choose_best_fallback(
        self, 
        failed_flow: FlowType, 
        fallback_options: List[FlowType], 
        session: ConversationState
    ) -> Optional[FlowType]:
        """Choose the best fallback flow option"""
        if not fallback_options:
            return None
        
        scored_options = []
        for option in fallback_options:
            score = self._calculate_flow_priority(option, session)
            scored_options.append((option, score))
        
        return max(scored_options, key=lambda x: x[1])[0] if scored_options else None


    # ADDED: Private integration helper methods
    
    def _setup_integration(self) -> None:
        """Setup integration event handlers"""
        def handle_classification_update(event):
            session_id = event.session_id
            if session_id in self.active_flows:
                self.active_flows[session_id]["last_classification"] = event.data
        
        self.event_bus.subscribe("classification_update", handle_classification_update)
    
    def _classify_input(self, customer_input: str, session_id: str, session_state: ConversationState):
        """Use classification engine to analyze input"""

        logging.info(f"FLOW_ORCH->_classify_input: Classifying input for session_id={session_id},customer_input= {customer_input},session_state={session_state}")
       
        if not self.classification_engine:
            return self._fallback_classification(customer_input, session_state)
        
        if not hasattr(session_state, 'context_data'):
            return self._fallback_classification(customer_input, None)
        
        try:
            conversation_history = self._get_conversation_history(session_id)
            customer_context = session_state.context_data.get("customer_context")
            
            intents, customer_signals = self.classification_engine.analyze_conversation(
                customer_input, conversation_history, customer_context
            )
            
            return self.classification_engine.classify_flow_needs(
                intents, customer_signals, session_state.context_data
            )
        except Exception as e:
            self.logger.error(f"Classification failed: {e}")
            logging.info("FLOW_ORCH->_classify_input: Classification engine failed, using fallback")
            return self._fallback_classification(customer_input, session_state)
    
    def _make_orchestration_decision(self, classification_result, session_id: str, session_state: ConversationState):
        """Make orchestration decision - uses existing orchestration logic"""
        current_flow = session_state.current_flow
        recommended_flow = classification_result.primary_flow
        
        decision = {
            "action": "continue",
            "target_flow": current_flow,
            "reasoning": "",
            "context_updates": classification_result.context_factors
        }
        
        # Check transition using existing transition_controller
        if recommended_flow != current_flow and classification_result.confidence_score > 0.6:
            if self.classification_engine:
                is_ready, _, reason = self.classification_engine.evaluate_transition_readiness(
                    current_flow, recommended_flow, session_state.context_data
                )
                
                if is_ready:
                    # Use existing transition_controller
                    success = self.transition_controller.execute_flow_transition(
                        session_id, recommended_flow, f"Classification: {classification_result.reasoning}"
                    )
                    
                    if success:
                        decision.update({
                            "action": "transition",
                            "target_flow": recommended_flow,
                            "reasoning": f"Transitioned to {recommended_flow.value}"
                        })
        
        return decision
    
    def _execute_flow_action(self, orchestration_decision, customer_input: str, session_id: str):
        """Execute using registered engines"""
        target_flow = orchestration_decision["target_flow"]
        engine = self.engine_registry.get_engine_for_flow(target_flow)
        
        if not engine:
            return {"error": f"No engine for {target_flow.value}"}
        
        session_state=None
        try:
            session_state = self.state_manager.active_sessions[session_id]
            execution_context = self.integration_bridge.orchestration_to_engine(
                {
                    "session_id": session_id,
                    "customer_context": session_state.context_data.get("customer_context"),
                    "conversation_state": session_state,
                    "flow_context": orchestration_decision.get("context_updates", {})
                },
                target_flow.value
            
            )
            if target_flow == FlowType.PITCH:
            # Set template path for pitch flows
                execution_context["template_path"] = "playbook/pitch_flow.json"
                execution_context["business_context"] = {
                "business_name": os.getenv('BUSINESS_NAME','Burger King'),
                "business_type": os.getenv('BUSINESS_TYPE','franchise'),
                "currency": os.getenv('CURRENCY_SYMBOL','₹'),
                "qualification_flow": os.getenv('QUALIFICATION_FLOWS', '').split(',') if os.getenv('QUALIFICATION_FLOWS') else []
            }
            
            action = orchestration_decision["action"]
            
            if action == "transition":
                result = engine.initialize_flow(session_id, execution_context["customer_context"], execution_context)
            elif action == "continue":
                result = engine.execute_flow_segment(session_id, customer_input, execution_context)
            else:
                result = {"error": f"Unknown action: {action}"}
            
            return self.integration_bridge.engine_to_orchestration(result, target_flow.value)
            
        except Exception as e:
            self.logger.error(f"FLOW_ORCH->_execute_flow_action Execution failed: {e}")
            return {"error": str(e)}
    
    def _collect_feedback(self, session_id: str, classification_result, execution_result) -> None:
        """Collect feedback for learning"""
        if "performance_metrics" in execution_result:
            self.feedback_collector.collect_flow_feedback(
                session_id, classification_result.primary_flow, execution_result["performance_metrics"]
            )
    
    def _update_state(self, session_id: str, classification_result, execution_result) -> None:
        """Update conversation state"""
        context_updates = {}
        context_updates.update(classification_result.context_factors)
        context_updates.update(execution_result.get("context_updates", {}))
        
        # Use existing state_manager
        self.state_manager.preserve_cross_flow_context(session_id, context_updates)
    
    def _get_conversation_history(self, session_id: str) -> List[Dict[str, Any]]:
        """Get conversation history from events"""
        conversation_events = self.event_bus.get_events_for_session(session_id)
        return [{"content": event.data.get("content", ""), "speaker": event.data.get("speaker", "")} 
                for event in conversation_events if event.event_type in ["customer_input", "agent_response"]]
    
    def _fallback_classification(self, customer_input: str, session_state: ConversationState):
        """Simple fallback when classification engine unavailable"""
        input_lower = customer_input.lower()
        logging.info("FLOW_ORCH->_fallback_classification: Using fallback classification")
        if any(word in input_lower for word in ["price", "cost"]):
            primary_flow = FlowType.KNOWLEDGE
        elif any(word in input_lower for word in ["but", "concerned"]):
            primary_flow = FlowType.OBJECTION
        elif any(word in input_lower for word in ["interested", "sounds good"]):
            primary_flow = FlowType.PITCH
        else:
            primary_flow = session_state.current_flow
        
      
        return ClassificationResult(
            primary_flow=primary_flow,
            secondary_flows=[],
            confidence_score=0.5,
            reasoning="Fallback classification",
            context_factors={"fallback_used": True},
            recommended_actions=[]
        )
    
    def _extract_classification_sequence(self, conversation_events):
        """Extract classification sequence from conversation events"""
        # Implementation would extract classification results from events
        return []  # Simplified for brevity

class FlowPerformanceAnalyzer:
    """Analyzes and optimizes flow performance"""
    
    def __init__(self):
        self.performance_data: Dict[str, List[PerformanceMetrics]] = {}
        self.optimization_cache: Dict[str, Dict] = {}
        self.logger = logging.getLogger(__name__)
    
    def measure_flow_effectiveness(
        self, 
        session_id: str, 
        flow_type: FlowType, 
        outcome_metrics: Dict[str, float]
    ) -> PerformanceMetrics:
        """Measure effectiveness of a specific flow"""
        metrics = PerformanceMetrics(
            flow_type=flow_type,
            success_rate=outcome_metrics.get("success_rate", 0.0),
            average_duration=outcome_metrics.get("duration", 0.0),
            customer_satisfaction=outcome_metrics.get("satisfaction", 0.0),
            conversion_rate=outcome_metrics.get("conversion_rate", 0.0),
            engagement_score=outcome_metrics.get("engagement", 0.0)
        )
        
        # Store metrics
        if flow_type.value not in self.performance_data:
            self.performance_data[flow_type.value] = []
        self.performance_data[flow_type.value].append(metrics)
        
        return metrics
    
    def optimize_flow_selection(
        self, 
        conversation_context: Dict[str, Any], 
        historical_performance: Dict[str, PerformanceMetrics]
    ) -> FlowType:
        """Optimize flow selection based on historical performance"""
        context_key = self._generate_context_key(conversation_context)
        
        if context_key in self.optimization_cache:
            return self.optimization_cache[context_key]["recommended_flow"]
        
        # Analyze performance by context similarity
        best_flow = FlowType.DISCOVERY  # Default
        best_score = 0.0
        
        for flow_type_str, metrics in historical_performance.items():
            flow_type = FlowType(flow_type_str)
            composite_score = (
                metrics.success_rate * 0.3 +
                metrics.customer_satisfaction * 0.3 +
                metrics.conversion_rate * 0.2 +
                metrics.engagement_score * 0.2
            )
            
            if composite_score > best_score:
                best_score = composite_score
                best_flow = flow_type
        
        # Cache result
        self.optimization_cache[context_key] = {
            "recommended_flow": best_flow,
            "confidence_score": best_score,
            "timestamp": datetime.now()
        }
        
        return best_flow
    
    def analyze_flow_transition_quality(
        self, 
        session_id: str, 
        transition_points: List[FlowTransition]
    ) -> Dict[str, Any]:
        """Analyze quality of flow transitions"""
        if not transition_points:
            return {"quality_score": 0.0, "insights": []}
        
        successful_transitions = [t for t in transition_points if t.success]
        quality_score = len(successful_transitions) / len(transition_points)
        
        insights = []
        
        # Analyze transition patterns
        transition_types = {}
        for transition in transition_points:
            key = f"{transition.from_flow.value}->{transition.to_flow.value}"
            if key not in transition_types:
                transition_types[key] = {"count": 0, "success_rate": 0.0}
            transition_types[key]["count"] += 1
            if transition.success:
                transition_types[key]["success_rate"] += 1
        
        # Generate insights
        for transition_type, data in transition_types.items():
            success_rate = data["success_rate"] / data["count"] if data["count"] > 0 else 0
            if success_rate < 0.7:
                insights.append(f"Low success rate for {transition_type}: {success_rate:.2f}")
        
        return {
            "quality_score": quality_score,
            "successful_transitions": len(successful_transitions),
            "total_transitions": len(transition_points),
            "transition_patterns": transition_types,
            "insights": insights
        }
    
    def generate_flow_performance_insights(
        self, 
        session_data: Dict[str, Any], 
        flow_outcomes: Dict[FlowType, Any]
    ) -> List[str]:
        """Generate actionable insights from flow performance"""
        insights = []
        
        # Analyze overall performance
        total_flows = len(flow_outcomes)
        if total_flows == 0:
            return ["No flow data available for analysis"]
        
        # Success rate analysis
        successful_flows = sum(1 for outcome in flow_outcomes.values() 
                             if outcome.get("success", False))
        success_rate = successful_flows / total_flows
        
        if success_rate < 0.6:
            insights.append("Overall flow success rate is below optimal threshold")
        
        # Flow-specific insights
        for flow_type, outcome in flow_outcomes.items():
            if outcome.get("engagement_score", 0) < 0.5:
                insights.append(f"{flow_type.value} flow shows low engagement")
            
            if outcome.get("duration", 0) > 600:  # 10 minutes
                insights.append(f"{flow_type.value} flow duration exceeds recommended time")
        
        # Customer satisfaction insights
        avg_satisfaction = sum(outcome.get("satisfaction", 0) 
                             for outcome in flow_outcomes.values()) / total_flows
        if avg_satisfaction < 0.7:
            insights.append("Customer satisfaction across flows needs improvement")
        
        return insights
    
    def _generate_context_key(self, context: Dict[str, Any]) -> str:
        """Generate a key for context-based caching"""
        key_elements = [
            context.get("industry", "unknown"),
            context.get("company_size", "unknown"),
            context.get("call_type", "unknown")
        ]
        return "_".join(key_elements)