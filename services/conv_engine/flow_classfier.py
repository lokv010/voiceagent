"""
FlowClassificationEngine.py - Classification and analysis classes for conversation flows
"""

from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import re
import logging
from dataclasses import dataclass
from .flow_models import (
    FlowType, CustomerContext, ConversationState, CustomerReadinessLevel,
    ConversationEvent, ConversationIntent, ClassificationResult  # ← Import from here
)
from .conv_interfaces import IClassificationEngine




class ConversationAnalyzer:
    """Analyzes conversation content for intent and flow classification"""
    
    def __init__(self):
        self.intent_patterns = self._init_intent_patterns()
        self.emotion_patterns = self._init_emotion_patterns()
        self.urgency_indicators = self._init_urgency_indicators()
        self.logger = logging.getLogger(__name__)
    
    def analyze_conversation_intent(
        self, 
        conversation_text: str, 
        conversation_history: List[Dict[str, Any]]
    ) -> List[ConversationIntent]:
        """Analyze conversation to detect intents"""
        
        intents = []
        text_lower = conversation_text.lower()
        
        # Detect multiple intents in the conversation
        for intent_type, patterns in self.intent_patterns.items():
            confidence = self._calculate_intent_confidence(text_lower, patterns)
            
            if confidence > 0.3:  # Threshold for intent detection
                context_clues = self._extract_context_clues(text_lower, patterns)
                suggested_flow = self._map_intent_to_flow(intent_type)
                urgency = self._determine_urgency(text_lower, intent_type)
                emotional_tone = self._analyze_emotional_tone(text_lower)
                
                intent = ConversationIntent(
                    intent_type=intent_type,
                    confidence=confidence,
                    context_clues=context_clues,
                    suggested_flow=suggested_flow,
                    urgency=urgency,
                    emotional_tone=emotional_tone
                )
                intents.append(intent)
        
        # Sort by confidence and return top intents
        intents.sort(key=lambda x: x.confidence, reverse=True)
        return intents[:5]  # Top 5 intents
    
    def extract_customer_signals(
        self, 
        conversation_text: str
    ) -> Dict[str, Any]:
        """Extract various customer signals from conversation"""
        
        signals = {
            "buying_signals": [],
            "objection_signals": [],
            "engagement_signals": [],
            "information_requests": [],
            "emotional_state": "neutral",
            "urgency_level": "medium",
            "decision_readiness": 0.5
        }
        
        text_lower = conversation_text.lower()
        
        # Buying signals
        buying_indicators = [
            "when can we start", "what's the price", "how much does it cost",
            "what are the next steps", "who do I need to talk to", "timeline",
            "implementation", "contract", "agreement", "trial", "pilot","purchase","ready to buy","looking to buy","buying process"
        ]
        
        for indicator in buying_indicators:
            if indicator in text_lower:
                signals["buying_signals"].append(indicator)
        
        # Objection signals
        objection_indicators = [
            "too expensive", "not sure", "need to think", "already have",
            "not the right time", "budget", "concerns", "worried", "but","however","issue","not ready","problem","concern"
        ]
        
        for indicator in objection_indicators:
            if indicator in text_lower:
                signals["objection_signals"].append(indicator)
        
        # Engagement signals
        engagement_indicators = [
            "interesting", "tell me more", "how does", "what about",
            "can you explain", "show me", "sounds good", "that's helpful","demo","references"
        ]
        
        for indicator in engagement_indicators:
            if indicator in text_lower:
                signals["engagement_signals"].append(indicator)
        
        # Information requests
        info_requests = [
            "how does it work", "what features", "technical details",
            "specifications", "documentation", "case studies", "references","benifits","features","product details"
        ]
        
        for request in info_requests:
            if request in text_lower:
                signals["information_requests"].append(request)
        
        # Calculate decision readiness
        buying_score = len(signals["buying_signals"]) * 0.3
        engagement_score = len(signals["engagement_signals"]) * 0.2
        objection_penalty = len(signals["objection_signals"]) * 0.1
        
        signals["decision_readiness"] = max(0.0, min(1.0, 
            0.5 + buying_score + engagement_score - objection_penalty))
        
        # Determine emotional state
        signals["emotional_state"] = self._analyze_emotional_tone(text_lower)
        
        # Determine urgency level
        urgency_keywords = {
            "high": ["urgent", "asap", "immediately", "right away", "quickly"],
            "medium": ["soon", "this week", "next week", "timeline"],
            "low": ["eventually", "someday", "maybe", "thinking about"]
        }
        
        for level, keywords in urgency_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                signals["urgency_level"] = level
                break
        
        return signals
    
    def analyze_conversation_flow_patterns(
        self, 
        conversation_history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze patterns in conversation flow"""
        
        if not conversation_history:
            return {"pattern_type": "new_conversation", "confidence": 1.0}
        
        patterns = {
            "pattern_type": "unknown",
            "conversation_stage": "early",
            "topic_progression": [],
            "customer_engagement_trend": "stable",
            "flow_transitions": [],
            "conversation_momentum": 0.5,
            "optimal_next_actions": []
        }
        
        # Analyze conversation stage
        total_exchanges = len(conversation_history)
        if total_exchanges < 5:
            patterns["conversation_stage"] = "early"
        elif total_exchanges < 15:
            patterns["conversation_stage"] = "middle"
        else:
            patterns["conversation_stage"] = "advanced"
        
        # Track topic progression
        topics_discussed = []
        for exchange in conversation_history:
            content = exchange.get("content", "").lower()
            if "price" in content or "cost" in content:
                topics_discussed.append("pricing")
            elif "technical" in content or "how does" in content:
                topics_discussed.append("technical")
            elif "benefit" in content or "value" in content:
                topics_discussed.append("benefits")
            elif "timeline" in content or "implementation" in content:
                topics_discussed.append("timeline")
        
        patterns["topic_progression"] = list(set(topics_discussed))
        
        # Analyze engagement trend
        if len(conversation_history) >= 3:
            recent_engagement = self._calculate_recent_engagement(conversation_history[-3:])
            earlier_engagement = self._calculate_recent_engagement(conversation_history[:-3])
            
            if recent_engagement > earlier_engagement * 1.2:
                patterns["customer_engagement_trend"] = "increasing"
            elif recent_engagement < earlier_engagement * 0.8:
                patterns["customer_engagement_trend"] = "decreasing"
            else:
                patterns["customer_engagement_trend"] = "stable"
        
        # Calculate conversation momentum
        patterns["conversation_momentum"] = self._calculate_conversation_momentum(conversation_history)
        
        # Determine optimal next actions
        patterns["optimal_next_actions"] = self._suggest_next_actions(patterns)
        
        return patterns
    
    def detect_conversation_context_changes(
        self, 
        current_input: str, 
        previous_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Detect significant changes in conversation context"""
        
        changes = {
            "context_shift_detected": False,
            "shift_type": None,
            "confidence": 0.0,
            "new_context_elements": [],
            "preserved_elements": [],
            "recommended_adaptations": []
        }
        
        current_lower = current_input.lower()
        
        # Detect topic shifts
        topic_shift_indicators = [
            "actually", "by the way", "speaking of", "one more thing",
            "before we continue", "i should mention", "let me ask about"
        ]
        
        for indicator in topic_shift_indicators:
            if indicator in current_lower:
                changes["context_shift_detected"] = True
                changes["shift_type"] = "topic_shift"
                changes["confidence"] = 0.7
                break
        
        # Detect priority changes
        priority_change_indicators = [
            "more important", "actually need", "main concern", "biggest issue",
            "first priority", "critical", "essential"
        ]
        
        for indicator in priority_change_indicators:
            if indicator in current_lower:
                changes["context_shift_detected"] = True
                changes["shift_type"] = "priority_change"
                changes["confidence"] = 0.8
                break
        
        # Detect stakeholder changes
        stakeholder_indicators = [
            "my boss", "the team", "we need to", "they want", "management",
            "decision maker", "approval", "board"
        ]
        
        for indicator in stakeholder_indicators:
            if indicator in current_lower:
                changes["new_context_elements"].append("additional_stakeholders")
                changes["recommended_adaptations"].append("adjust_for_multiple_stakeholders")
        
        # Detect timeline changes
        timeline_indicators = [
            "urgent", "asap", "right away", "no rush", "take our time",
            "by next week", "end of month", "quarter"
        ]
        
        for indicator in timeline_indicators:
            if indicator in current_lower:
                changes["new_context_elements"].append("timeline_specification")
                changes["recommended_adaptations"].append("adjust_pitch_timing")
        
        return changes
    
    def _init_intent_patterns(self) -> Dict[str, List[str]]:
        """Initialize intent detection patterns"""
        return {
            "information_seeking": [
                "how does", "what is", "can you explain", "tell me about",
                "what are the features", "how much", "what's included"
            ],
            "problem_solving": [
                "we have a problem", "struggling with", "need help", "challenge",
                "issue", "difficulty", "pain point"
            ],
            "comparison_shopping": [
                "compared to", "versus", "alternative", "competition",
                "other options", "what makes you different"
            ],
            "buying_intent": [
                "ready to buy", "want to purchase", "next steps",
                "how do we proceed", "contract", "agreement", "pricing"
            ],
            "objection_raising": [
                "concerned about", "worried", "not sure", "but",
                "however", "problem is", "issue with"
            ],
            "relationship_building": [
                "nice to meet", "tell me about yourself", "your company",
                "how long", "experience", "background"
            ]
        }
    
    def _init_emotion_patterns(self) -> Dict[str, List[str]]:
        """Initialize emotional tone patterns"""
        return {
            "positive": [
                "great", "excellent", "perfect", "love", "amazing",
                "fantastic", "wonderful", "impressive", "exactly"
            ],
            "negative": [
                "terrible", "awful", "hate", "disappointed", "frustrated",
                "annoyed", "upset", "angry", "ridiculous"
            ],
            "neutral": [
                "okay", "fine", "alright", "understand", "see",
                "got it", "makes sense", "clear"
            ],
            "frustrated": [
                "why", "complicated", "confusing", "difficult",
                "taking too long", "waste of time", "not working"
            ]
        }
    
    def _init_urgency_indicators(self) -> Dict[str, List[str]]:
        """Initialize urgency level indicators"""
        return {
            "high": [
                "urgent", "asap", "immediately", "right away", "emergency",
                "critical", "deadline", "must have"
            ],
            "medium": [
                "soon", "this week", "next week", "quickly",
                "timeline", "schedule", "planning"
            ],
            "low": [
                "eventually", "someday", "thinking about", "considering",
                "maybe", "possibly", "down the road"
            ]
        }
    
    def _calculate_intent_confidence(self, text: str, patterns: List[str]) -> float:
        """Calculate confidence score for intent detection"""
        matches = sum(1 for pattern in patterns if pattern in text)
        total_patterns = len(patterns)
        
        if total_patterns == 0:
            return 0.0
        
        base_confidence = matches / total_patterns
        
        # Boost confidence for exact matches
        exact_matches = sum(1 for pattern in patterns if pattern == text.strip())
        if exact_matches > 0:
            base_confidence += 0.3
        
        return min(1.0, base_confidence)
    
    def _extract_context_clues(self, text: str, patterns: List[str]) -> List[str]:
        """Extract context clues that matched the patterns"""
        clues = []
        for pattern in patterns:
            if pattern in text:
                # Extract surrounding context
                pattern_index = text.find(pattern)
                start = max(0, pattern_index - 20)
                end = min(len(text), pattern_index + len(pattern) + 20)
                context = text[start:end].strip()
                clues.append(context)
        
        return clues[:3]  # Limit to top 3 clues
    
    def _map_intent_to_flow(self, intent_type: str) -> FlowType:
        """Map detected intent to appropriate flow type"""
        intent_flow_mapping = {
            "information_seeking": FlowType.KNOWLEDGE,
            "problem_solving": FlowType.DISCOVERY,
            "comparison_shopping": FlowType.PITCH,
            "buying_intent": FlowType.CLOSING,
            "objection_raising": FlowType.OBJECTION,
            "relationship_building": FlowType.RELATIONSHIP
        }
        
        return intent_flow_mapping.get(intent_type, FlowType.DISCOVERY)
    
    def _determine_urgency(self, text: str, intent_type: str) -> str:
        """Determine urgency level based on text and intent"""
        for urgency_level, indicators in self.urgency_indicators.items():
            if any(indicator in text for indicator in indicators):
                return urgency_level
        
        # Default urgency based on intent type
        intent_urgency_defaults = {
            "buying_intent": "high",
            "problem_solving": "medium",
            "objection_raising": "high",
            "information_seeking": "low"
        }
        
        return intent_urgency_defaults.get(intent_type, "medium")
    
    def _analyze_emotional_tone(self, text: str) -> str:
        """Analyze emotional tone of the text"""
        emotion_scores = {}
        
        for emotion, patterns in self.emotion_patterns.items():
            score = sum(1 for pattern in patterns if pattern in text)
            emotion_scores[emotion] = score
        
        if not emotion_scores or all(score == 0 for score in emotion_scores.values()):
            return "neutral"
        
        return max(emotion_scores, key=emotion_scores.get)
    
    def _calculate_recent_engagement(self, recent_history: List[Dict[str, Any]]) -> float:
        """Calculate engagement level from recent conversation history"""
        if not recent_history:
            return 0.5
        
        engagement_indicators = 0
        total_exchanges = len(recent_history)
        
        for exchange in recent_history:
            content = exchange.get("content", "").lower()
            
            # Count engagement indicators
            positive_indicators = [
                "interesting", "good", "yes", "tell me more", "how",
                "what", "explain", "show me"
            ]
            
            for indicator in positive_indicators:
                if indicator in content:
                    engagement_indicators += 1
                    break  # Count once per exchange
        
        return min(1.0, engagement_indicators / total_exchanges)
    
    def _calculate_conversation_momentum(self, conversation_history: List[Dict[str, Any]]) -> float:
        """Calculate overall conversation momentum"""
        if not conversation_history:
            return 0.5
        
        # Factors affecting momentum
        total_exchanges = len(conversation_history)
        recent_activity = min(1.0, total_exchanges / 10)  # Normalize to 10 exchanges
        
        # Analyze response patterns
        customer_responses = [ex for ex in conversation_history if ex.get("speaker") == "customer"]
        if customer_responses:
            avg_response_length = sum(len(ex.get("content", "")) for ex in customer_responses) / len(customer_responses)
            length_factor = min(1.0, avg_response_length / 50)  # Normalize to 50 characters
        else:
            length_factor = 0.3
        
        # Time factor (recent activity boosts momentum)
        if conversation_history:
            last_exchange_time = conversation_history[-1].get("timestamp", datetime.now())
            time_diff = datetime.now() - last_exchange_time
            time_factor = max(0.2, 1.0 - (time_diff.total_seconds() / 300))  # 5-minute decay
        else:
            time_factor = 1.0
        
        momentum = (recent_activity * 0.4 + length_factor * 0.3 + time_factor * 0.3)
        return momentum
    
    def _suggest_next_actions(self, patterns: Dict[str, Any]) -> List[str]:
        """Suggest optimal next actions based on conversation patterns"""
        actions = []
        
        stage = patterns.get("conversation_stage", "early")
        engagement_trend = patterns.get("customer_engagement_trend", "stable")
        momentum = patterns.get("conversation_momentum", 0.5)
        
        if stage == "early":
            if engagement_trend == "increasing":
                actions.append("Continue discovery with deeper questions")
            else:
                actions.append("Build rapport and establish credibility")
        
        elif stage == "middle":
            if momentum > 0.7:
                actions.append("Transition to pitch or demonstration")
            elif engagement_trend == "decreasing":
                actions.append("Re-engage with relevant questions")
        
        elif stage == "advanced":
            if momentum > 0.6:
                actions.append("Move toward closing")
            else:
                actions.append("Address remaining concerns")
        
        return actions


class FlowTypeClassifier:
    """Classifies conversation flow types based on analysis"""
    
    def __init__(self):
        self.classification_weights = self._init_classification_weights()
        self.flow_requirements = self._init_flow_requirements()
        self.logger = logging.getLogger(__name__)
    
    def classify_primary_flow(
        self, 
        conversation_intents: List[ConversationIntent], 
        customer_signals: Dict[str, Any], 
        conversation_context: Dict[str, Any]
    ) -> ClassificationResult:
        """Classify the primary conversation flow needed"""
        
        # Score each possible flow type
        flow_scores = {}
        for flow_type in FlowType:
            score = self._calculate_flow_score(
                flow_type, conversation_intents, customer_signals, conversation_context
            )
            flow_scores[flow_type] = score
        
        # Find primary and secondary flows
        sorted_flows = sorted(flow_scores.items(), key=lambda x: x[1], reverse=True)
        primary_flow = sorted_flows[0][0]
        primary_score = sorted_flows[0][1]
        
        secondary_flows = [flow for flow, score in sorted_flows[1:4] if score > 0.3]
        
        # Generate reasoning
        reasoning = self._generate_classification_reasoning(
            primary_flow, primary_score, conversation_intents, customer_signals
        )
        
        # Context factors that influenced the decision
        context_factors = self._extract_context_factors(
            conversation_intents, customer_signals, conversation_context
        )
        
        # Recommended actions
        recommended_actions = self._generate_recommended_actions(
            primary_flow, secondary_flows, context_factors
        )
        
        result = ClassificationResult(
            primary_flow=primary_flow,
            secondary_flows=secondary_flows,
            confidence_score=primary_score,
            reasoning=reasoning,
            context_factors=context_factors,
            recommended_actions=recommended_actions
        )
        
        return result
    
    def evaluate_flow_transition_readiness(
        self, 
        current_flow: FlowType, 
        target_flow: FlowType, 
        conversation_state: Dict[str, Any]
    ) -> Tuple[bool, float, str]:
        """Evaluate readiness to transition between flows"""
        
        # Check if transition is logically valid
        valid_transitions = self._get_valid_transitions(current_flow)
        if target_flow not in valid_transitions:
            return False, 0.0, f"Invalid transition from {current_flow} to {target_flow}"
        
        # Check flow requirements
        requirements = self.flow_requirements.get(target_flow, {})
        readiness_score = 0.0
        missing_requirements = []
        
        for requirement, weight in requirements.items():
            if self._check_requirement_met(requirement, conversation_state):
                readiness_score += weight
            else:
                missing_requirements.append(requirement)
        
        # Calculate overall readiness
        total_weight = sum(requirements.values()) if requirements else 1.0
        readiness_percentage = readiness_score / total_weight if total_weight > 0 else 0.0
        
        is_ready = readiness_percentage >= 0.7  # 70% threshold
        
        if is_ready:
            reason = f"Ready for transition: {readiness_percentage:.1%} requirements met"
        else:
            reason = f"Not ready: Missing {', '.join(missing_requirements)}"
        
        return is_ready, readiness_percentage, reason
    
    def determine_flow_priority_stack(
        self, 
        multiple_flows: List[FlowType], 
        business_context: Dict[str, Any]
    ) -> List[Tuple[FlowType, float]]:
        """Determine priority order for multiple active flows"""
        
        business_priorities = business_context.get("priorities", {})
        conversation_urgency = business_context.get("urgency", "medium")
        customer_type = business_context.get("customer_type", "standard")
        
        flow_priorities = []
        
        for flow in multiple_flows:
            priority_score = self._calculate_flow_priority(
                flow, business_priorities, conversation_urgency, customer_type
            )
            flow_priorities.append((flow, priority_score))
        
        # Sort by priority score
        flow_priorities.sort(key=lambda x: x[1], reverse=True)
        
        return flow_priorities
    
    def _init_classification_weights(self) -> Dict[str, Dict[str, float]]:
        """Initialize weights for flow classification"""
        return {
            "intent_weight": 0.4,
            "signal_weight": 0.3,
            "context_weight": 0.2,
            "timing_weight": 0.1
        }
    
    def _init_flow_requirements(self) -> Dict[FlowType, Dict[str, float]]:
        """Initialize requirements for each flow type"""
        return {
            FlowType.PITCH: {
                "customer_context_known": 0.3,
                "pain_points_identified": 0.3,
                "rapport_established": 0.2,
                "customer_engaged": 0.2
            },
            FlowType.CLOSING: {
                "pitch_delivered": 0.4,
                "interest_demonstrated": 0.3,
                "objections_addressed": 0.2,
                "decision_authority_confirmed": 0.1
            },
            FlowType.OBJECTION: {
                "objection_identified": 0.5,
                "context_understood": 0.3,
                "relationship_intact": 0.2
            },
            FlowType.KNOWLEDGE: {
                "question_identified": 0.4,
                "customer_engaged": 0.3,
                "context_relevant": 0.3
            },
            FlowType.DISCOVERY: {
                "rapport_established": 0.3,
                "customer_responsive": 0.4,
                "time_available": 0.3
            },
            FlowType.RELATIONSHIP: {
                "customer_available": 0.3,
                "conversation_appropriate": 0.4,
                "business_context": 0.3
            }
        }
    
    def _calculate_flow_score(
        self, 
        flow_type: FlowType, 
        intents: List[ConversationIntent], 
        signals: Dict[str, Any], 
        context: Dict[str, Any]
    ) -> float:
        """Calculate score for a specific flow type"""
        
        score = 0.0
        weights = self.classification_weights
        
        # Intent-based scoring
        intent_score = 0.0
        for intent in intents:
            if intent.suggested_flow == flow_type:
                intent_score += intent.confidence
        intent_score = min(1.0, intent_score)  # Normalize
        score += intent_score * weights["intent_weight"]
        
        # Signal-based scoring
        signal_score = self._calculate_signal_score(flow_type, signals)
        score += signal_score * weights["signal_weight"]
        
        # Context-based scoring
        context_score = self._calculate_context_score(flow_type, context)
        score += context_score * weights["context_weight"]
        
        # Timing-based scoring
        timing_score = self._calculate_timing_score(flow_type, context)
        score += timing_score * weights["timing_weight"]
        
        return min(1.0, score)
    
    def _calculate_signal_score(self, flow_type: FlowType, signals: Dict[str, Any]) -> float:
        """Calculate score based on customer signals"""
        
        signal_mappings = {
            FlowType.PITCH: {
                "engagement_signals": 0.4,
                "information_requests": 0.3,
                "buying_signals": 0.3
            },
            FlowType.CLOSING: {
                "buying_signals": 0.6,
                "decision_readiness": 0.4
            },
            FlowType.OBJECTION: {
                "objection_signals": 0.8,
                "emotional_state": 0.2
            },
            FlowType.KNOWLEDGE: {
                "information_requests": 0.6,
                "engagement_signals": 0.4
            },
            FlowType.DISCOVERY: {
                "engagement_signals": 0.5,
                "decision_readiness": 0.3,
                "emotional_state": 0.2
            }
        }
        
        mapping = signal_mappings.get(flow_type, {})
        score = 0.0
        
        for signal_type, weight in mapping.items():
            if signal_type in signals:
                if isinstance(signals[signal_type], list):
                    signal_value = min(1.0, len(signals[signal_type]) / 3)  # Normalize to 3 items
                elif isinstance(signals[signal_type], float):
                    signal_value = signals[signal_type]
                else:
                    signal_value = 0.5  # Default for non-numeric values
                
                score += signal_value * weight
        
        return score
    
    def _calculate_context_score(self, flow_type: FlowType, context: Dict[str, Any]) -> float:
        """Calculate score based on conversation context"""
        
        score = 0.0
        
        # Flow-specific context considerations
        if flow_type == FlowType.PITCH:
            if context.get("discovery_complete", False):
                score += 0.4
            if context.get("customer_engaged", False):
                score += 0.3
            if context.get("pain_points_identified", 0) > 0:
                score += 0.3
        
        elif flow_type == FlowType.CLOSING:
            if context.get("pitch_delivered", False):
                score += 0.5
            if context.get("interest_level", 0) > 0.6:
                score += 0.3
            if context.get("objections_addressed", 0) > 0:
                score += 0.2
        
        elif flow_type == FlowType.OBJECTION:
            if context.get("objections_raised", 0) > 0:
                score += 0.6
            if context.get("customer_frustrated", False):
                score += 0.4
        
        return min(1.0, score)
    
    def _calculate_timing_score(self, flow_type: FlowType, context: Dict[str, Any]) -> float:
        """Calculate score based on conversation timing"""
        
        conversation_duration = context.get("duration_minutes", 0)
        conversation_stage = context.get("stage", "early")
        
        # Timing preferences for different flows
        timing_preferences = {
            FlowType.DISCOVERY: {"early": 1.0, "middle": 0.5, "advanced": 0.2},
            FlowType.PITCH: {"early": 0.3, "middle": 1.0, "advanced": 0.7},
            FlowType.CLOSING: {"early": 0.1, "middle": 0.5, "advanced": 1.0},
            FlowType.OBJECTION: {"early": 0.8, "middle": 1.0, "advanced": 0.9},
            FlowType.KNOWLEDGE: {"early": 0.7, "middle": 1.0, "advanced": 0.8},
            FlowType.RELATIONSHIP: {"early": 1.0, "middle": 0.6, "advanced": 0.8}
        }
        
        preferences = timing_preferences.get(flow_type, {"early": 0.5, "middle": 0.5, "advanced": 0.5})
        return preferences.get(conversation_stage, 0.5)
    
    def _get_valid_transitions(self, current_flow: FlowType) -> List[FlowType]:
        """Get valid transition targets from current flow"""
        
        transition_map = {
            FlowType.DISCOVERY: [FlowType.PITCH, FlowType.KNOWLEDGE, FlowType.OBJECTION, FlowType.RELATIONSHIP],
            FlowType.PITCH: [FlowType.OBJECTION, FlowType.KNOWLEDGE, FlowType.CLOSING, FlowType.DISCOVERY],
            FlowType.KNOWLEDGE: [FlowType.PITCH, FlowType.DISCOVERY, FlowType.CLOSING, FlowType.OBJECTION],
            FlowType.OBJECTION: [FlowType.PITCH, FlowType.KNOWLEDGE, FlowType.DISCOVERY, FlowType.CLOSING],
            FlowType.CLOSING: [FlowType.OBJECTION, FlowType.KNOWLEDGE, FlowType.RELATIONSHIP],
            FlowType.RELATIONSHIP: [FlowType.DISCOVERY, FlowType.PITCH, FlowType.KNOWLEDGE]
        }
        
        return transition_map.get(current_flow, list(FlowType))
    
    def _check_requirement_met(self, requirement: str, conversation_state: Dict[str, Any]) -> bool:
        """Check if a specific requirement is met"""
        
        requirement_checkers = {
            "customer_context_known": lambda s: s.get("customer_context_complete", False),
            "pain_points_identified": lambda s: len(s.get("pain_points", [])) > 0,
            "rapport_established": lambda s: s.get("rapport_score", 0) > 0.5,
            "customer_engaged": lambda s: s.get("engagement_level", 0) > 0.5,
            "pitch_delivered": lambda s: s.get("pitch_completed", False),
            "interest_demonstrated": lambda s: s.get("interest_level", 0) > 0.4,
            "objections_addressed": lambda s: s.get("objections_resolved", 0) > 0,
            "objection_identified": lambda s: len(s.get("current_objections", [])) > 0,
            "question_identified": lambda s: len(s.get("current_questions", [])) > 0,
            "customer_responsive": lambda s: s.get("response_rate", 0) > 0.3,
            "time_available": lambda s: s.get("time_remaining", 0) > 300  # 5 minutes
        }
        
        checker = requirement_checkers.get(requirement)
        return checker(conversation_state) if checker else False
    
    def _calculate_flow_priority(
        self, 
        flow: FlowType, 
        business_priorities: Dict[str, Any], 
        urgency: str, 
        customer_type: str
    ) -> float:
        """Calculate priority score for a flow"""
        
        base_priorities = {
            FlowType.OBJECTION: 0.9,  # Always high priority
            FlowType.CLOSING: 0.8,
            FlowType.PITCH: 0.7,
            FlowType.DISCOVERY: 0.6,
            FlowType.KNOWLEDGE: 0.5,
            FlowType.RELATIONSHIP: 0.4
        }
        
        priority = base_priorities.get(flow, 0.5)
        
        # Adjust for business priorities
        if flow.value in business_priorities:
            priority += business_priorities[flow.value] * 0.2
        
        # Adjust for urgency
        urgency_multipliers = {"high": 1.2, "medium": 1.0, "low": 0.8}
        priority *= urgency_multipliers.get(urgency, 1.0)
        
        # Adjust for customer type
        if customer_type == "enterprise" and flow == FlowType.CLOSING:
            priority *= 1.1
        elif customer_type == "small_business" and flow == FlowType.RELATIONSHIP:
            priority *= 1.1
        
        return min(1.0, priority)
    
    def _generate_classification_reasoning(
        self, 
        primary_flow: FlowType, 
        confidence: float, 
        intents: List[ConversationIntent], 
        signals: Dict[str, Any]
    ) -> str:
        """Generate human-readable reasoning for classification"""
        
        reasons = []
        
        # Intent-based reasons
        matching_intents = [i for i in intents if i.suggested_flow == primary_flow]
        if matching_intents:
            top_intent = matching_intents[0]
            reasons.append(f"Customer intent '{top_intent.intent_type}' detected with {top_intent.confidence:.1%} confidence")
        
        # Signal-based reasons
        if primary_flow == FlowType.CLOSING and signals.get("buying_signals"):
            reasons.append(f"Strong buying signals detected: {len(signals['buying_signals'])} indicators")
        
        if primary_flow == FlowType.OBJECTION and signals.get("objection_signals"):
            reasons.append(f"Objection signals present: {len(signals['objection_signals'])} concerns raised")
        
        if primary_flow == FlowType.KNOWLEDGE and signals.get("information_requests"):
            reasons.append(f"Information requests identified: {len(signals['information_requests'])} topics")
        
        # Confidence-based qualifier
        confidence_qualifier = ""
        if confidence >= 0.8:
            confidence_qualifier = "High confidence"
        elif confidence >= 0.6:
            confidence_qualifier = "Moderate confidence"
        else:
            confidence_qualifier = "Low confidence"
        
        reasoning = f"{confidence_qualifier} classification for {primary_flow.value} flow. " + "; ".join(reasons)
        return reasoning
    
    def _extract_context_factors(
        self, 
        intents: List[ConversationIntent], 
        signals: Dict[str, Any], 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract key context factors that influenced classification"""
        
        factors = {
            "primary_intents": [i.intent_type for i in intents[:3]],
            "emotional_tone": signals.get("emotional_state", "neutral"),
            "urgency_level": signals.get("urgency_level", "medium"),
            "engagement_level": context.get("engagement_level", 0.5),
            "conversation_stage": context.get("stage", "early"),
            "decision_readiness": signals.get("decision_readiness", 0.5)
        }
        
        # Add specific signal counts
        for signal_type in ["buying_signals", "objection_signals", "engagement_signals", "information_requests"]:
            if signal_type in signals:
                factors[f"{signal_type}_count"] = len(signals[signal_type]) if isinstance(signals[signal_type], list) else signals[signal_type]
        
        return factors
    
    def _generate_recommended_actions(
        self, 
        primary_flow: FlowType, 
        secondary_flows: List[FlowType], 
        context_factors: Dict[str, Any]
    ) -> List[str]:
        """Generate recommended actions based on classification"""
        
        actions = []
        
        # Primary flow actions
        flow_actions = {
            FlowType.PITCH: ["Prepare customer-specific value proposition", "Gather relevant proof points"],
            FlowType.CLOSING: ["Identify decision criteria", "Present clear next steps"],
            FlowType.OBJECTION: ["Listen actively to concerns", "Prepare objection responses"],
            FlowType.KNOWLEDGE: ["Gather specific questions", "Prepare detailed explanations"],
            FlowType.DISCOVERY: ["Prepare discovery questions", "Focus on pain point identification"],
            FlowType.RELATIONSHIP: ["Build rapport", "Establish credibility"]
        }
        
        actions.extend(flow_actions.get(primary_flow, []))
        
        # Context-specific actions
        if context_factors.get("urgency_level") == "high":
            actions.append("Prioritize time-sensitive elements")
        
        if context_factors.get("emotional_tone") == "frustrated":
            actions.append("Address emotional concerns first")
        
        if context_factors.get("engagement_level", 0) < 0.5:
            actions.append("Focus on re-engagement techniques")
        
        # Secondary flow preparations
        if secondary_flows:
            actions.append(f"Prepare for potential transition to {secondary_flows[0].value}")
        
        return actions[:5]  # Limit to top 5 actions


class ContextualClassifier:
    """Refines classification based on business and customer context"""
    
    def __init__(self):
        self.context_weights = self._init_context_weights()
        self.business_rules = self._init_business_rules()
        self.logger = logging.getLogger(__name__)
    
    def refine_classification_with_context(
        self, 
        initial_classification: ClassificationResult, 
        customer_context: CustomerContext, 
        business_context: Dict[str, Any]
    ) -> ClassificationResult:
        """Refine classification using customer and business context"""
        
        refined_classification = ClassificationResult(
            primary_flow=initial_classification.primary_flow,
            secondary_flows=initial_classification.secondary_flows.copy(),
            confidence_score=initial_classification.confidence_score,
            reasoning=initial_classification.reasoning,
            context_factors=initial_classification.context_factors.copy(),
            recommended_actions=initial_classification.recommended_actions.copy()
        )
        
        # Apply customer context refinements
        customer_adjustments = self._apply_customer_context(
            refined_classification, customer_context
        )
        
        # Apply business context refinements
        business_adjustments = self._apply_business_context(
            refined_classification, business_context
        )
        
        # Combine and apply adjustments
        total_adjustments = self._combine_adjustments(customer_adjustments, business_adjustments)
        self._apply_adjustments(refined_classification, total_adjustments)
        
        # Update reasoning
        refined_classification.reasoning += self._generate_context_reasoning(
            customer_adjustments, business_adjustments
        )
        
        return refined_classification
    
    def apply_customer_profile_rules(
        self, 
        classification: ClassificationResult, 
        customer_profile: CustomerContext
    ) -> Dict[str, Any]:
        """Apply customer profile-specific rules"""
        
        adjustments = {
            "flow_adjustments": {},
            "priority_changes": {},
            "additional_considerations": []
        }
        
        # Industry-specific adjustments
        industry = customer_profile.industry
        if industry:
            industry_rules = self.business_rules.get("industry", {}).get(industry, {})
            
            for rule_type, rule_value in industry_rules.items():
                if rule_type == "preferred_flows":
                    for flow_name, bonus in rule_value.items():
                        flow_type = FlowType(flow_name)
                        adjustments["flow_adjustments"][flow_type] = bonus
                
                elif rule_type == "avoid_flows":
                    for flow_name in rule_value:
                        flow_type = FlowType(flow_name)
                        adjustments["flow_adjustments"][flow_type] = -0.3
        
        # Company size adjustments
        company_size = customer_profile.company_size
        if company_size:
            size_rules = self.business_rules.get("company_size", {}).get(company_size, {})
            
            if company_size in ["enterprise", "large"]:
                # Enterprise customers often need more formal approaches
                adjustments["flow_adjustments"][FlowType.PITCH] = 0.1
                adjustments["flow_adjustments"][FlowType.KNOWLEDGE] = 0.1
                adjustments["additional_considerations"].append("formal_presentation_style")
            
            elif company_size in ["startup", "small"]:
                # Small companies often appreciate direct, efficient approaches
                adjustments["flow_adjustments"][FlowType.CLOSING] = 0.1
                adjustments["flow_adjustments"][FlowType.RELATIONSHIP] = 0.1
                adjustments["additional_considerations"].append("efficient_direct_style")
        
        # Technical background adjustments
        tech_background = customer_profile.technical_background
        if tech_background in ["technical", "highly_technical"]:
            adjustments["flow_adjustments"][FlowType.KNOWLEDGE] = 0.15
            adjustments["additional_considerations"].append("technical_depth_welcomed")
        elif tech_background == "non_technical":
            adjustments["flow_adjustments"][FlowType.KNOWLEDGE] = -0.1
            adjustments["additional_considerations"].append("simplify_technical_content")
        
        # Previous interaction history
        if customer_profile.previous_interactions:
            interaction_count = len(customer_profile.previous_interactions)
            if interaction_count > 3:
                # Established relationship - can be more direct
                adjustments["flow_adjustments"][FlowType.CLOSING] = 0.1
                adjustments["flow_adjustments"][FlowType.RELATIONSHIP] = -0.1
            elif interaction_count == 0:
                # New relationship - build rapport first
                adjustments["flow_adjustments"][FlowType.RELATIONSHIP] = 0.2
                adjustments["flow_adjustments"][FlowType.CLOSING] = -0.2
        
        return adjustments
    
    def incorporate_business_objectives(
        self, 
        classification: ClassificationResult, 
        business_objectives: Dict[str, Any]
    ) -> ClassificationResult:
        """Incorporate business objectives into classification"""
        
        # Create a copy to modify
        updated_classification = ClassificationResult(
            primary_flow=classification.primary_flow,
            secondary_flows=classification.secondary_flows.copy(),
            confidence_score=classification.confidence_score,
            reasoning=classification.reasoning,
            context_factors=classification.context_factors.copy(),
            recommended_actions=classification.recommended_actions.copy()
        )
        
        # Apply objective-based adjustments
        primary_objective = business_objectives.get("primary_objective", "relationship_building")
        
        objective_flow_preferences = {
            "revenue_generation": {
                FlowType.CLOSING: 0.2,
                FlowType.PITCH: 0.1,
                FlowType.OBJECTION: 0.1
            },
            "relationship_building": {
                FlowType.RELATIONSHIP: 0.2,
                FlowType.DISCOVERY: 0.1,
                FlowType.KNOWLEDGE: 0.1
            },
            "product_education": {
                FlowType.KNOWLEDGE: 0.2,
                FlowType.PITCH: 0.1,
                FlowType.DISCOVERY: 0.1
            },
            "market_research": {
                FlowType.DISCOVERY: 0.2,
                FlowType.KNOWLEDGE: 0.1,
                FlowType.RELATIONSHIP: 0.1
            }
        }
        
        preferences = objective_flow_preferences.get(primary_objective, {})
        
        # Adjust flow scores (conceptually - in practice would need to recalculate)
        objective_bonus = preferences.get(updated_classification.primary_flow, 0)
        updated_classification.confidence_score = min(1.0, updated_classification.confidence_score + objective_bonus)
        
        # Add objective-specific actions
        objective_actions = {
            "revenue_generation": ["Focus on value proposition", "Identify budget and timeline"],
            "relationship_building": ["Build trust and rapport", "Understand long-term needs"],
            "product_education": ["Provide detailed explanations", "Offer educational resources"],
            "market_research": ["Ask strategic questions", "Gather competitive intelligence"]
        }
        
        if primary_objective in objective_actions:
            updated_classification.recommended_actions.extend(objective_actions[primary_objective])
        
        # Update reasoning
        updated_classification.reasoning += f" Aligned with business objective: {primary_objective}."
        
        return updated_classification
    
    def _init_context_weights(self) -> Dict[str, float]:
        """Initialize weights for different context factors"""
        return {
            "industry_weight": 0.3,
            "company_size_weight": 0.2,
            "technical_background_weight": 0.2,
            "relationship_history_weight": 0.15,
            "business_objective_weight": 0.15
        }
    
    def _init_business_rules(self) -> Dict[str, Dict[str, Any]]:
        """Initialize business rules for context-based adjustments"""
        return {
            "industry": {
                "healthcare": {
                    "preferred_flows": {"knowledge": 0.2, "objection": 0.1},
                    "considerations": ["compliance_focus", "detailed_documentation"]
                },
                "technology": {
                    "preferred_flows": {"pitch": 0.1, "knowledge": 0.2},
                    "considerations": ["technical_depth", "innovation_focus"]
                },
                "financial": {
                    "preferred_flows": {"objection": 0.2, "knowledge": 0.1},
                    "considerations": ["risk_management", "regulatory_compliance"]
                }
            },
            "company_size": {
                "enterprise": {
                    "preferred_flows": {"knowledge": 0.1, "pitch": 0.1},
                    "considerations": ["formal_process", "multiple_stakeholders"]
                },
                "startup": {
                    "preferred_flows": {"closing": 0.1, "pitch": 0.1},
                    "considerations": ["speed_focus", "cost_conscious"]
                }
            }
        }
    
    def _apply_customer_context(
        self, 
        classification: ClassificationResult, 
        customer_context: CustomerContext
    ) -> Dict[str, Any]:
        """Apply customer context-based adjustments"""
        
        return self.apply_customer_profile_rules(classification, customer_context)
    
    def _apply_business_context(
        self, 
        classification: ClassificationResult, 
        business_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply business context-based adjustments"""
        
        adjustments = {
            "flow_adjustments": {},
            "priority_changes": {},
            "additional_considerations": []
        }
        
        # Call objectives and priorities
        call_objective = business_context.get("call_objective", "discovery")
        business_priority = business_context.get("business_priority", "medium")
        
        # Objective-based adjustments
        if call_objective == "demo":
            adjustments["flow_adjustments"][FlowType.PITCH] = 0.3
            adjustments["flow_adjustments"][FlowType.KNOWLEDGE] = 0.2
        elif call_objective == "closing":
            adjustments["flow_adjustments"][FlowType.CLOSING] = 0.4
            adjustments["flow_adjustments"][FlowType.OBJECTION] = 0.2
        elif call_objective == "discovery":
            adjustments["flow_adjustments"][FlowType.DISCOVERY] = 0.3
            adjustments["flow_adjustments"][FlowType.RELATIONSHIP] = 0.1
        
        # Priority-based adjustments
        if business_priority == "high":
            adjustments["flow_adjustments"][FlowType.CLOSING] = 0.1
            adjustments["additional_considerations"].append("accelerated_timeline")
        
        return adjustments
    
    def _combine_adjustments(
        self, 
        customer_adjustments: Dict[str, Any], 
        business_adjustments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Combine customer and business adjustments"""
        
        combined = {
            "flow_adjustments": {},
            "priority_changes": {},
            "additional_considerations": []
        }
        
        # Combine flow adjustments
        all_flows = set(customer_adjustments.get("flow_adjustments", {}).keys()) | \
                   set(business_adjustments.get("flow_adjustments", {}).keys())
        
        for flow in all_flows:
            customer_adj = customer_adjustments.get("flow_adjustments", {}).get(flow, 0)
            business_adj = business_adjustments.get("flow_adjustments", {}).get(flow, 0)
            combined["flow_adjustments"][flow] = customer_adj + business_adj
        
        # Combine considerations
        combined["additional_considerations"].extend(
            customer_adjustments.get("additional_considerations", [])
        )
        combined["additional_considerations"].extend(
            business_adjustments.get("additional_considerations", [])
        )
        
        return combined
    
    def _apply_adjustments(
        self, 
        classification: ClassificationResult, 
        adjustments: Dict[str, Any]
    ) -> None:
        """Apply adjustments to classification (in-place modification)"""
        
        # Apply flow adjustments to confidence score
        primary_flow_adjustment = adjustments.get("flow_adjustments", {}).get(
            classification.primary_flow, 0
        )
        classification.confidence_score = min(1.0, max(0.0, 
            classification.confidence_score + primary_flow_adjustment
        ))
        
        # Add additional considerations to context factors
        additional_considerations = adjustments.get("additional_considerations", [])
        if additional_considerations:
            classification.context_factors["additional_considerations"] = additional_considerations
        
        # Update recommended actions based on considerations
        for consideration in additional_considerations:
            if consideration == "technical_depth_welcomed":
                classification.recommended_actions.append("Prepare technical deep-dive content")
            elif consideration == "formal_presentation_style":
                classification.recommended_actions.append("Use formal presentation approach")
            elif consideration == "efficient_direct_style":
                classification.recommended_actions.append("Maintain efficient, direct communication")
    
    def _generate_context_reasoning(
        self, 
        customer_adjustments: Dict[str, Any], 
        business_adjustments: Dict[str, Any]
    ) -> str:
        """Generate reasoning text for context-based adjustments"""
        
        reasoning_parts = []
        
        # Customer context reasoning
        customer_considerations = customer_adjustments.get("additional_considerations", [])
        if customer_considerations:
            reasoning_parts.append(f"Customer context: {', '.join(customer_considerations)}")
        
        # Business context reasoning
        business_considerations = business_adjustments.get("additional_considerations", [])
        if business_considerations:
            reasoning_parts.append(f"Business context: {', '.join(business_considerations)}")
        
        if reasoning_parts:
            return f" Context refinements: {'; '.join(reasoning_parts)}."
        else:
            return ""


class AdaptiveClassifier:
    """Provides real-time adjustments to classification based on conversation evolution"""
    
    def __init__(self):
        self.adaptation_history = {}
        self.learning_weights = self._init_learning_weights()
        self.logger = logging.getLogger(__name__)
    
    def adapt_classification_real_time(
        self, 
        current_classification: ClassificationResult, 
        conversation_events: List[ConversationEvent], 
        performance_feedback: Dict[str, float]
    ) -> ClassificationResult:
        """Adapt classification in real-time based on conversation evolution"""
        
        adapted_classification = ClassificationResult(
            primary_flow=current_classification.primary_flow,
            secondary_flows=current_classification.secondary_flows.copy(),
            confidence_score=current_classification.confidence_score,
            reasoning=current_classification.reasoning,
            context_factors=current_classification.context_factors.copy(),
            recommended_actions=current_classification.recommended_actions.copy()
        )
        
        # Analyze recent events for adaptation signals
        adaptation_signals = self._analyze_conversation_events(conversation_events)
        
        # Apply performance-based learning
        performance_adjustments = self._calculate_performance_adjustments(performance_feedback)
        
        # Combine signals and adjustments
        total_adaptation = self._combine_adaptations(adaptation_signals, performance_adjustments)
        
        # Apply adaptations
        self._apply_real_time_adaptations(adapted_classification, total_adaptation)
        
        # Update adaptation history
        self._update_adaptation_history(current_classification, total_adaptation)
        
        return adapted_classification
    
    def learn_from_conversation_outcomes(
        self, 
        session_id: str, 
        classification_sequence: List[ClassificationResult], 
        final_outcomes: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Learn from conversation outcomes to improve future classifications"""
        
        learning_insights = {
            "successful_patterns": [],
            "failed_patterns": [],
            "optimization_suggestions": [],
            "confidence_calibration": {}
        }
        
        # Analyze outcome success
        success_metrics = final_outcomes.get("success_metrics", {})
        overall_success = success_metrics.get("overall_success", 0.5)
        
        # Pattern analysis
        if overall_success > 0.7:
            # Successful conversation - learn from patterns
            successful_flow_sequence = [c.primary_flow for c in classification_sequence]
            learning_insights["successful_patterns"].append({
                "flow_sequence": successful_flow_sequence,
                "success_score": overall_success,
                "key_factors": self._extract_success_factors(classification_sequence, final_outcomes)
            })
        
        elif overall_success < 0.4:
            # Failed conversation - learn what to avoid
            failed_flow_sequence = [c.primary_flow for c in classification_sequence]
            learning_insights["failed_patterns"].append({
                "flow_sequence": failed_flow_sequence,
                "failure_score": overall_success,
                "failure_factors": self._extract_failure_factors(classification_sequence, final_outcomes)
            })
        
        # Confidence calibration
        for classification in classification_sequence:
            predicted_confidence = classification.confidence_score
            actual_effectiveness = success_metrics.get(f"{classification.primary_flow.value}_effectiveness", 0.5)
            
            calibration_error = abs(predicted_confidence - actual_effectiveness)
            learning_insights["confidence_calibration"][classification.primary_flow.value] = {
                "predicted": predicted_confidence,
                "actual": actual_effectiveness,
                "error": calibration_error
            }
        
        # Generate optimization suggestions
        learning_insights["optimization_suggestions"] = self._generate_optimization_suggestions(
            classification_sequence, final_outcomes
        )
        
        return learning_insights
    
    def optimize_classification_parameters(
        self, 
        historical_performance: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Optimize classification parameters based on historical performance"""
        
        optimization_results = {
            "parameter_updates": {},
            "threshold_adjustments": {},
            "weight_modifications": {},
            "new_patterns_detected": []
        }
        
        # Analyze classification accuracy over time
        accuracy_trends = historical_performance.get("accuracy_trends", {})
        
        for flow_type, accuracy_data in accuracy_trends.items():
            current_accuracy = accuracy_data.get("current_accuracy", 0.5)
            target_accuracy = 0.8  # Target 80% accuracy
            
            if current_accuracy < target_accuracy:
                # Adjust thresholds for this flow type
                adjustment_factor = (target_accuracy - current_accuracy) * 0.1
                optimization_results["threshold_adjustments"][flow_type] = adjustment_factor
        
        # Analyze weight effectiveness
        weight_performance = historical_performance.get("weight_performance", {})
        
        for weight_category, performance in weight_performance.items():
            if performance.get("effectiveness", 0.5) < 0.6:
                # Suggest weight modification
                optimization_results["weight_modifications"][weight_category] = "decrease_by_10_percent"
            elif performance.get("effectiveness", 0.5) > 0.9:
                optimization_results["weight_modifications"][weight_category] = "increase_by_5_percent"
        
        # Detect new patterns
        pattern_analysis = historical_performance.get("pattern_analysis", {})
        emerging_patterns = pattern_analysis.get("emerging_patterns", [])
        
        for pattern in emerging_patterns:
            if pattern.get("frequency", 0) > 10 and pattern.get("success_rate", 0) > 0.7:
                optimization_results["new_patterns_detected"].append(pattern)
        
        return optimization_results
    
    def _init_learning_weights(self) -> Dict[str, float]:
        """Initialize weights for adaptive learning"""
        return {
            "recent_performance_weight": 0.4,
            "historical_pattern_weight": 0.3,
            "conversation_momentum_weight": 0.2,
            "outcome_feedback_weight": 0.1
        }
    
    def _analyze_conversation_events(self, events: List[ConversationEvent]) -> Dict[str, Any]:
        """Analyze conversation events for adaptation signals"""
        
        signals = {
            "momentum_change": 0.0,
            "engagement_shift": 0.0,
            "topic_drift": False,
            "urgency_change": 0.0,
            "sentiment_shift": 0.0
        }
        
        if len(events) < 2:
            return signals
        
        # Analyze recent vs earlier events
        recent_events = events[-3:] if len(events) >= 3 else events
        earlier_events = events[:-3] if len(events) > 3 else []
        
        # Calculate momentum change
        recent_momentum = self._calculate_event_momentum(recent_events)
        earlier_momentum = self._calculate_event_momentum(earlier_events) if earlier_events else recent_momentum
        
        signals["momentum_change"] = recent_momentum - earlier_momentum
        
        # Analyze engagement shift
        recent_engagement = self._calculate_event_engagement(recent_events)
        earlier_engagement = self._calculate_event_engagement(earlier_events) if earlier_events else recent_engagement
        
        signals["engagement_shift"] = recent_engagement - earlier_engagement
        
        # Detect topic drift
        signals["topic_drift"] = self._detect_topic_drift(events)
        
        return signals
    
    def _calculate_performance_adjustments(self, performance_feedback: Dict[str, float]) -> Dict[str, float]:
        """Calculate adjustments based on performance feedback"""
        
        adjustments = {}
        
        # Performance thresholds
        excellent_threshold = 0.8
        poor_threshold = 0.4
        
        for metric, value in performance_feedback.items():
            if value > excellent_threshold:
                # Excellent performance - slight confidence boost
                adjustments[f"{metric}_adjustment"] = 0.05
            elif value < poor_threshold:
                # Poor performance - confidence reduction
                adjustments[f"{metric}_adjustment"] = -0.1
            else:
                # Acceptable performance - no adjustment
                adjustments[f"{metric}_adjustment"] = 0.0
        
        return adjustments
    
    def _combine_adaptations(
        self, 
        adaptation_signals: Dict[str, Any], 
        performance_adjustments: Dict[str, float]
    ) -> Dict[str, Any]:
        """Combine adaptation signals and performance adjustments"""
        
        combined = {
            "confidence_adjustment": 0.0,
            "flow_preference_changes": {},
            "urgency_adjustment": 0.0,
            "engagement_response": None
        }
        
        # Combine momentum and engagement signals
        momentum_change = adaptation_signals.get("momentum_change", 0.0)
        engagement_shift = adaptation_signals.get("engagement_shift", 0.0)
        
        # Calculate overall confidence adjustment
        confidence_adjustment = (momentum_change * 0.3 + engagement_shift * 0.4)
        
        # Add performance-based adjustments
        performance_avg = sum(performance_adjustments.values()) / len(performance_adjustments) if performance_adjustments else 0.0
        confidence_adjustment += performance_avg * 0.3
        
        combined["confidence_adjustment"] = max(-0.3, min(0.3, confidence_adjustment))
        
        # Determine engagement response
        if engagement_shift < -0.2:
            combined["engagement_response"] = "increase_interaction"
        elif engagement_shift > 0.2:
            combined["engagement_response"] = "maintain_pace"
        
        return combined
    
    def _apply_real_time_adaptations(
        self, 
        classification: ClassificationResult, 
        adaptations: Dict[str, Any]
    ) -> None:
        """Apply real-time adaptations to classification"""
        
        # Adjust confidence score
        confidence_adjustment = adaptations.get("confidence_adjustment", 0.0)
        classification.confidence_score = max(0.0, min(1.0, 
            classification.confidence_score + confidence_adjustment
        ))
        
        # Add adaptive reasoning
        if abs(confidence_adjustment) > 0.05:
            direction = "increased" if confidence_adjustment > 0 else "decreased"
            classification.reasoning += f" Real-time adaptation: confidence {direction} by {abs(confidence_adjustment):.2f}."
        
        # Add engagement-based actions
        engagement_response = adaptations.get("engagement_response")
        if engagement_response == "increase_interaction":
            classification.recommended_actions.append("Increase customer interaction and engagement")
        elif engagement_response == "maintain_pace":
            classification.recommended_actions.append("Maintain current conversation pace")
        
        # Update context factors with adaptation info
        classification.context_factors["real_time_adaptations"] = adaptations
    
    def _update_adaptation_history(
        self, 
        original_classification: ClassificationResult, 
        adaptations: Dict[str, Any]
    ) -> None:
        """Update adaptation history for learning"""
        
        history_entry = {
            "timestamp": datetime.now(),
            "original_flow": original_classification.primary_flow.value,
            "original_confidence": original_classification.confidence_score,
            "adaptations_applied": adaptations,
            "adaptation_magnitude": abs(adaptations.get("confidence_adjustment", 0.0))
        }
        
        session_key = "current_session"  # In practice, would use actual session ID
        if session_key not in self.adaptation_history:
            self.adaptation_history[session_key] = []
        
        self.adaptation_history[session_key].append(history_entry)
        
        # Limit history size
        if len(self.adaptation_history[session_key]) > 50:
            self.adaptation_history[session_key] = self.adaptation_history[session_key][-50:]
    
    def _calculate_event_momentum(self, events: List[ConversationEvent]) -> float:
        """Calculate momentum from conversation events"""
        if not events:
            return 0.5
        
        # Simple momentum calculation based on event frequency and recency
        recent_weight = 1.0
        momentum = 0.0
        
        for event in reversed(events):
            # Weight recent events more heavily
            momentum += recent_weight
            recent_weight *= 0.8  # Decay factor
        
        # Normalize
        max_possible_momentum = sum(1.0 * (0.8 ** i) for i in range(len(events)))
        return momentum / max_possible_momentum if max_possible_momentum > 0 else 0.5
    
    def _calculate_event_engagement(self, events: List[ConversationEvent]) -> float:
        """Calculate engagement level from conversation events"""
        if not events:
            return 0.5
        
        engagement_score = 0.0
        engagement_events = 0
        
        for event in events:
            event_data = event.data
            
            # Look for engagement indicators in event data
            if event_data.get("customer_question", False):
                engagement_score += 0.3
                engagement_events += 1
            
            if event_data.get("positive_response", False):
                engagement_score += 0.2
                engagement_events += 1
            
            if event_data.get("detailed_response", False):
                engagement_score += 0.1
                engagement_events += 1
        
        return engagement_score / max(1, engagement_events)
    
    def _detect_topic_drift(self, events: List[ConversationEvent]) -> bool:
        """Detect if conversation has drifted from main topic"""
        if len(events) < 4:
            return False
        
        # Simple topic drift detection based on event types
        recent_events = events[-2:]
        earlier_events = events[-4:-2]
        
        recent_types = [event.event_type for event in recent_events]
        earlier_types = [event.event_type for event in earlier_events]
        
        # If event types are completely different, consider it a drift
        common_types = set(recent_types) & set(earlier_types)
        return len(common_types) == 0
    
    def _extract_success_factors(
        self, 
        classification_sequence: List[ClassificationResult], 
        outcomes: Dict[str, Any]
    ) -> List[str]:
        """Extract factors that contributed to successful outcomes"""
        
        factors = []
        
        # Analyze flow sequence
        flows = [c.primary_flow for c in classification_sequence]
        if FlowType.DISCOVERY in flows and FlowType.PITCH in flows:
            factors.append("proper_discovery_before_pitch")
        
        # Analyze confidence levels
        avg_confidence = sum(c.confidence_score for c in classification_sequence) / len(classification_sequence)
        if avg_confidence > 0.7:
            factors.append("high_classification_confidence")
        
        # Analyze outcome metrics
        if outcomes.get("customer_satisfaction", 0) > 0.8:
            factors.append("high_customer_satisfaction")
        
        return factors
    
    def _extract_failure_factors(
        self, 
        classification_sequence: List[ClassificationResult], 
        outcomes: Dict[str, Any]
    ) -> List[str]:
        """Extract factors that contributed to failed outcomes"""
        
        factors = []
        
        # Analyze premature flow transitions
        if len(classification_sequence) > 5:
            factors.append("too_many_flow_transitions")
        
        # Analyze low confidence
        low_confidence_count = sum(1 for c in classification_sequence if c.confidence_score < 0.5)
        if low_confidence_count > len(classification_sequence) / 2:
            factors.append("consistently_low_confidence")
        
        # Analyze outcome metrics
        if outcomes.get("engagement_score", 0) < 0.4:
            factors.append("low_customer_engagement")
        
        return factors
    
    def _generate_optimization_suggestions(
        self, 
        classification_sequence: List[ClassificationResult], 
        outcomes: Dict[str, Any]
    ) -> List[str]:
        """Generate suggestions for optimization"""
        
        suggestions = []
        
        # Flow sequence analysis
        flows = [c.primary_flow for c in classification_sequence]
        if flows.count(FlowType.OBJECTION) > 2:
            suggestions.append("Improve objection prevention in earlier flows")
        
        if FlowType.CLOSING not in flows and outcomes.get("buying_intent", 0) > 0.6:
            suggestions.append("Consider earlier transition to closing flow")
        
        # Confidence analysis
        confidence_variance = self._calculate_confidence_variance(classification_sequence)
        if confidence_variance > 0.3:
            suggestions.append("Improve confidence stability across classifications")
        
        return suggestions
    
    def _calculate_confidence_variance(self, classifications: List[ClassificationResult]) -> float:
        """Calculate variance in confidence scores"""
        if len(classifications) < 2:
            return 0.0
        
        confidences = [c.confidence_score for c in classifications]
        mean_confidence = sum(confidences) / len(confidences)
        variance = sum((c - mean_confidence) ** 2 for c in confidences) / len(confidences)
        
        return variance
    
class FlowClassificationEngine(IClassificationEngine):  # ADDED: Direct interface implementation
    """
    ENHANCED ORIGINAL CLASS - composed of original components + integration
    No wrapper - direct enhancement with interface methods
    """
    
    def __init__(self):
        # ORIGINAL: Composition of specialized components (unchanged)
        self.conversation_analyzer = ConversationAnalyzer()
        self.flow_classifier = FlowTypeClassifier()
        self.contextual_classifier = ContextualClassifier()
        self.adaptive_classifier = AdaptiveClassifier()
        
        # ADDED: Integration state management only
        self.classification_history: Dict[str, List[ClassificationResult]] = {}
        self.performance_feedback: Dict[str, List[Dict[str, float]]] = {}
        self.logger = logging.getLogger(__name__)
    
    # ALL ORIGINAL COMPONENT METHODS STAY THE SAME:
    # ConversationAnalyzer methods, FlowTypeClassifier methods, etc.
    # are accessed via self.conversation_analyzer.method(), etc.
    
    # ADDED: IClassificationEngine interface methods only
    
    def analyze_conversation(self, customer_input: str, conversation_history: List[Dict[str, Any]], 
                           customer_context: CustomerContext) -> Tuple[List[ConversationIntent], Dict[str, Any]]:
        """INTERFACE METHOD: Coordinate original components for analysis"""
        
        try:
            # ORIGINAL: Use conversation_analyzer (no changes to component)
            conversation_intents = self.conversation_analyzer.analyze_conversation_intent(
                customer_input, conversation_history
            )
            
            customer_signals = self.conversation_analyzer.extract_customer_signals(customer_input)
            
            flow_patterns = self.conversation_analyzer.analyze_conversation_flow_patterns(conversation_history)
            
            context_changes = self.conversation_analyzer.detect_conversation_context_changes(
                customer_input, self._get_previous_context(conversation_history)
            )
            
            # ADDED: Combine results for integration
            combined_signals = {
                **customer_signals,
                "flow_patterns": flow_patterns,
                "context_changes": context_changes,
                "analysis_timestamp": datetime.now()
            }
            
            return conversation_intents, combined_signals
            
        except Exception as e:
            self.logger.error(f"Analysis error: {e}")
            return self._fallback_analysis(customer_input)
    
    def classify_flow_needs(self, intents: List[ConversationIntent], customer_signals: Dict[str, Any], 
                          conversation_context: Dict[str, Any]) -> ClassificationResult:
        """INTERFACE METHOD: Coordinate original components for classification"""
        
        try:
            # ORIGINAL: Use flow_classifier (no changes to component)
            primary_classification = self.flow_classifier.classify_primary_flow(
                intents, customer_signals, conversation_context
            )
            
            # ORIGINAL: Use contextual_classifier (no changes to component)
            customer_context = conversation_context.get("customer_context")
            business_context = conversation_context.get("business_context", {})
            
            if customer_context:
                refined_classification = self.contextual_classifier.refine_classification_with_context(
                    primary_classification, customer_context, business_context
                )
            else:
                refined_classification = primary_classification
            
            # ORIGINAL: Use contextual_classifier for business objectives
            business_objectives = business_context.get("objectives", {})
            if business_objectives:
                final_classification = self.contextual_classifier.incorporate_business_objectives(
                    refined_classification, business_objectives
                )
            else:
                final_classification = refined_classification
            
            # ADDED: Integration metadata only
            final_classification.context_factors.update({
                "classification_timestamp": datetime.now(),
                "intent_count": len(intents),
                "signal_strength": self._calculate_signal_strength(customer_signals)
            })
            
            return final_classification
            
        except Exception as e:
            self.logger.error(f"Classification error: {e}")
            return self._fallback_classification()
    
    def evaluate_transition_readiness(self, current_flow: FlowType, target_flow: FlowType, 
                                    conversation_state: Dict[str, Any]) -> Tuple[bool, float, str]:
        """INTERFACE METHOD: Use original flow_classifier for transition evaluation"""
        
        try:
            # ORIGINAL: Use flow_classifier (no changes to component)
            is_ready, readiness_score, reason = self.flow_classifier.evaluate_flow_transition_readiness(
                current_flow, target_flow, conversation_state
            )
            
            # ADDED: Additional integration checks only
            if is_ready:
                momentum = conversation_state.get("conversation_momentum", 0.5)
                engagement = conversation_state.get("customer_engagement_level", 0.5)
                
                if momentum < 0.3:
                    is_ready = False
                    reason += " (Low momentum)"
                    readiness_score *= 0.7
                
                if engagement < 0.4 and target_flow in [FlowType.PITCH, FlowType.CLOSING]:
                    is_ready = False
                    reason += " (Low engagement)"
                    readiness_score *= 0.6
            
            return is_ready, readiness_score, reason
            
        except Exception as e:
            self.logger.error(f"Transition evaluation error: {e}")
            return False, 0.0, f"Evaluation error: {str(e)}"
    
    def adapt_classification_real_time(self, current_classification: ClassificationResult, 
                                     conversation_events: List[Any], 
                                     performance_feedback: Dict[str, float]) -> ClassificationResult:
        """INTERFACE METHOD: Use original adaptive_classifier for real-time adaptation"""
        
        try:
            # ORIGINAL: Use adaptive_classifier (no changes to component)
            adapted_classification = self.adaptive_classifier.adapt_classification_real_time(
                current_classification, conversation_events, performance_feedback
            )
            
            # ADDED: Integration metadata only
            adapted_classification.context_factors.update({
                "adaptation_timestamp": datetime.now(),
                "event_count": len(conversation_events),
                "adaptation_confidence": self._calculate_adaptation_confidence(performance_feedback)
            })
            
            return adapted_classification
            
        except Exception as e:
            self.logger.error(f"Adaptation error: {e}")
            current_classification.context_factors["adaptation_error"] = str(e)
            return current_classification
    
    def learn_from_outcomes(self, session_id: str, classification_sequence: List[ClassificationResult], 
                          final_outcomes: Dict[str, Any]) -> Dict[str, Any]:
        """INTERFACE METHOD: Use original adaptive_classifier for learning"""
        
        try:
            # ADDED: Store history for integration
            self.classification_history[session_id] = classification_sequence
            
            # ORIGINAL: Use adaptive_classifier (no changes to component)
            learning_insights = self.adaptive_classifier.learn_from_conversation_outcomes(
                session_id, classification_sequence, final_outcomes
            )
            
            # ADDED: Integration feedback processing
            performance_data = self._extract_performance_feedback(classification_sequence, final_outcomes)
            if session_id not in self.performance_feedback:
                self.performance_feedback[session_id] = []
            self.performance_feedback[session_id].append(performance_data)
            
            # ORIGINAL: Use adaptive_classifier for optimization
            historical_performance = self._aggregate_historical_performance()
            optimization_results = self.adaptive_classifier.optimize_classification_parameters(
                historical_performance
            )
            
            # ADDED: Combine results for integration
            return {
                **learning_insights,
                "optimization_results": optimization_results,
                "performance_data": performance_data,
                "learning_timestamp": datetime.now()
            }
            
        except Exception as e:
            self.logger.error(f"Learning error: {e}")
            return {"error": str(e)}
    
    # ADDED: Integration helper methods only
    
    def get_classification_confidence_metrics(self, session_id: str) -> Dict[str, float]:
        """Get confidence metrics for orchestrator"""
        if session_id in self.classification_history:
            classifications = self.classification_history[session_id]
            if classifications:
                confidences = [c.confidence_score for c in classifications]
                return {
                    "average_confidence": sum(confidences) / len(confidences),
                    "min_confidence": min(confidences),
                    "max_confidence": max(confidences),
                    "classification_count": len(classifications)
                }
        return {"average_confidence": 0.5, "classification_count": 0}
    
    def validate_business_alignment(self, classification_result: ClassificationResult, 
                                  business_objectives: Dict[str, Any]) -> Dict[str, Any]:
        """Validate business alignment for orchestrator"""
        try:
            # ORIGINAL: Use contextual_classifier (no changes)
            aligned_classification = self.contextual_classifier.incorporate_business_objectives(
                classification_result, business_objectives
            )
            
            confidence_change = aligned_classification.confidence_score - classification_result.confidence_score
            alignment_score = max(0.0, min(1.0, 0.5 + confidence_change))
            
            return {
                "alignment_score": alignment_score,
                "confidence_adjustment": confidence_change,
                "business_aligned": alignment_score > 0.6
            }
        except Exception as e:
            return {"error": str(e), "alignment_score": 0.5}
    
    # ADDED: Private helper methods for integration only
    
    def _get_previous_context(self, conversation_history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract previous context for original analyzer"""
        if not conversation_history:
            return {}
        
        recent_exchanges = conversation_history[-3:] if len(conversation_history) >= 3 else conversation_history
        return {
            "recent_topics": self._extract_topics(recent_exchanges),
            "engagement_trend": "stable",
            "conversation_momentum": 0.5
        }
    
    def _extract_topics(self, exchanges: List[Dict[str, Any]]) -> List[str]:
        """Extract topics from exchanges"""
        topics = []
        for exchange in exchanges:
            content = exchange.get("content", "").lower()
            if "price" in content or "cost" in content:
                topics.append("pricing")
            elif "technical" in content:
                topics.append("technical")
            elif "benefit" in content:
                topics.append("benefits")
        return topics
    
    def _calculate_signal_strength(self, customer_signals: Dict[str, Any]) -> float:
        """Calculate signal strength for integration metadata"""
        signal_weights = {
            "buying_signals": 0.4,
            "engagement_signals": 0.3,
            "objection_signals": 0.2,
            "information_requests": 0.1
        }
        
        total_strength = 0.0
        for signal_type, weight in signal_weights.items():
            if signal_type in customer_signals:
                signal_value = customer_signals[signal_type]
                if isinstance(signal_value, list):
                    strength = min(1.0, len(signal_value) / 3)
                elif isinstance(signal_value, float):
                    strength = signal_value
                else:
                    strength = 0.5
                total_strength += strength * weight
        
        return total_strength
    
    def _calculate_adaptation_confidence(self, performance_feedback: Dict[str, float]) -> float:
        """Calculate adaptation confidence for integration"""
        if not performance_feedback:
            return 0.5
        
        avg_performance = sum(performance_feedback.values()) / len(performance_feedback)
        return min(1.0, max(0.2, avg_performance))
    
    def _extract_performance_feedback(self, classifications: List[ClassificationResult], 
                                    outcomes: Dict[str, Any]) -> Dict[str, float]:
        """Extract performance feedback for learning"""
        if not classifications:
            return {}
        
        avg_confidence = sum(c.confidence_score for c in classifications) / len(classifications)
        
        return {
            "classification_confidence": avg_confidence,
            "outcome_success": outcomes.get("overall_success", 0.5),
            "customer_satisfaction": outcomes.get("customer_satisfaction", 0.5),
            "classification_accuracy": min(avg_confidence, outcomes.get("overall_success", 0.5))
        }
    
    def _aggregate_historical_performance(self) -> Dict[str, Any]:
        """Aggregate historical performance for original adaptive_classifier"""
        if not self.performance_feedback:
            return {}
        
        all_feedback = []
        for session_feedback_list in self.performance_feedback.values():
            all_feedback.extend(session_feedback_list)
        
        if not all_feedback:
            return {}
        
        # Simplified aggregation for original adaptive_classifier
        return {
            "accuracy_trends": {},
            "weight_performance": {},
            "pattern_analysis": {"emerging_patterns": []}
        }
    
    def _fallback_analysis(self, customer_input: str) -> Tuple[List[ConversationIntent], Dict[str, Any]]:
        """Fallback analysis when original components fail"""
        from flow_classfier import ConversationIntent
        
        fallback_intent = ConversationIntent(
            intent_type="general",
            confidence=0.3,
            context_clues=[customer_input[:50]],
            suggested_flow=FlowType.DISCOVERY,
            urgency="medium",
            emotional_tone="neutral"
        )
        return [fallback_intent], {"fallback_used": True}
    
    def _fallback_classification(self) -> ClassificationResult:
        """Fallback classification when original components fail"""
        from flow_classfier import ClassificationResult
        
        return ClassificationResult(
            primary_flow=FlowType.DISCOVERY,
            secondary_flows=[],
            confidence_score=0.3,
            reasoning="Fallback classification",
            context_factors={"fallback_used": True},
            recommended_actions=[]
        )