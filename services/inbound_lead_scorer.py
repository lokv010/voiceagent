"""
Enhanced Lead Scorer for Inbound Calls

Extends the existing lead scoring system to properly handle inbound call scenarios
"""

import logging
from datetime import datetime
from typing import Dict, List
from services.lead_scorer import UnifiedLeadScorer

class InboundLeadScorer(UnifiedLeadScorer):
    def __init__(self):
        """Initialize inbound-specific lead scoring system"""
        super().__init__()
        
        # Adjust scoring weights for inbound calls
        self.inbound_scoring_weights = {
            'source_score': 0.20,      # Higher weight for inbound (they called us!)
            'engagement_score': 0.25,   # Same as outbound
            'qualification_score': 0.25, # Slightly lower (conversation may be shorter)
            'behavioral_score': 0.20,   # Same as outbound
            'fit_score': 0.10          # Same as outbound
        }
        
        # Inbound-specific keyword dictionaries
        self.inbound_intent_keywords = {
            'high_intent': [
                'ready to buy', 'want to purchase', 'need to order', 'sign up today',
                'get started now', 'when can we begin', 'what\'s the next step',
                'how do we proceed', 'let\'s do this', 'i\'m ready'
            ],
            'medium_intent': [
                'interested in', 'tell me more', 'sounds good', 'looking for',
                'considering', 'exploring options', 'thinking about', 'might need'
            ],
            'low_intent': [
                'just curious', 'maybe later', 'not sure', 'still looking',
                'comparing options', 'early stages', 'just browsing'
            ],
            'urgency_indicators': [
                'urgent', 'asap', 'immediately', 'right away', 'this week',
                'by friday', 'deadline', 'time sensitive', 'emergency'
            ],
            'research_phase': [
                'research', 'information', 'learn more', 'understand',
                'explain', 'how does', 'what is', 'tell me about'
            ]
        }
        
        # Inbound conversation quality indicators
        self.conversation_quality_indicators = {
            'excellent': [
                'detailed questions', 'specific requirements', 'business context',
                'timeline mentioned', 'budget discussed', 'decision process'
            ],
            'good': [
                'multiple questions', 'engaged responses', 'relevant details',
                'follow-up questions', 'clarification requests'
            ],
            'fair': [
                'basic responses', 'short answers', 'some engagement',
                'limited details', 'generic questions'
            ],
            'poor': [
                'one word answers', 'distracted', 'unrelated questions',
                'frequent interruptions', 'impatient responses'
            ]
        }
        
        logging.info("Inbound Lead Scorer initialized")
    
    def calculate_inbound_lead_score(self, prospect_context: Dict, conversation_data: Dict, 
                                   inbound_context: Dict) -> Dict:
        """Calculate lead score specifically for inbound calls"""
        try:
            prospect = prospect_context['prospect']
            
            # Calculate base component scores
            source_score = self._calculate_inbound_source_score(prospect, inbound_context)
            engagement_score = self._calculate_inbound_engagement_score(conversation_data, inbound_context)
            qualification_score = self._calculate_inbound_qualification_score(conversation_data, prospect)
            behavioral_score = self._calculate_inbound_behavioral_score(conversation_data, inbound_context)
            fit_score = self._calculate_fit_score(prospect)  # Use base implementation
            
            # Calculate weighted final score with inbound weights
            final_score = (
                source_score * self.inbound_scoring_weights['source_score'] +
                engagement_score * self.inbound_scoring_weights['engagement_score'] +
                qualification_score * self.inbound_scoring_weights['qualification_score'] +
                behavioral_score * self.inbound_scoring_weights['behavioral_score'] +
                fit_score * self.inbound_scoring_weights['fit_score']
            )
            
            # Apply inbound-specific bonuses
            final_score = self._apply_inbound_bonuses(final_score, prospect_context, 
                                                    conversation_data, inbound_context)
            
            # Ensure score is within bounds
            final_score = max(0, min(final_score, 100))
            
            # Generate scoring breakdown
            component_scores = {
                'source': round(source_score, 1),
                'engagement': round(engagement_score, 1),
                'qualification': round(qualification_score, 1),
                'behavioral': round(behavioral_score, 1),
                'fit': round(fit_score, 1)
            }
            
            # Generate inbound-specific insights
            inbound_insights = self._generate_inbound_insights(
                conversation_data, inbound_context, component_scores
            )
            
            return {
                'final_score': round(final_score, 1),
                'component_scores': component_scores,
                'score_reasoning': self._generate_inbound_score_reasoning(
                    final_score, component_scores, prospect, conversation_data, inbound_context
                ),
                'confidence_level': self._calculate_inbound_confidence_level(conversation_data, inbound_context),
                'inbound_insights': inbound_insights,
                'recommended_action': self._determine_inbound_next_action(final_score, inbound_insights)
            }
            
        except Exception as e:
            logging.error(f"Error calculating inbound lead score: {str(e)}")
            return {
                'final_score': 45,  # Higher base for inbound
                'component_scores': {'source': 40, 'engagement': 0, 'qualification': 0, 'behavioral': 0, 'fit': 50},
                'score_reasoning': f"Error calculating inbound score: {str(e)}",
                'confidence_level': 'low',
                'inbound_insights': {},
                'recommended_action': 'callback_schedule'
            }
    
    def _calculate_inbound_source_score(self, prospect, inbound_context: Dict) -> float:
        """Calculate source score for inbound calls"""
        # Inbound calls get a significant boost since they initiated contact
        base_score = 60  # Much higher than outbound cold calls
        
        # Bonus for repeat callers
        if prospect.total_inbound_calls and prospect.total_inbound_calls > 1:
            base_score += min(prospect.total_inbound_calls * 5, 20)
        
        # Bonus for previous form submission + inbound call
        if prospect.source == 'form_submission' and inbound_context.get('is_follow_up_call'):
            base_score += 15
        
        # Bonus for referrals who call
        if prospect.referred_by_prospect_id:
            base_score += 10
        
        # Time-based scoring
        call_time = inbound_context.get('call_time', datetime.utcnow())
        if self._is_peak_business_hours(call_time):
            base_score += 5  # Calling during peak hours shows urgency
        
        # Marketing attribution bonus
        if inbound_context.get('marketing_source'):
            base_score += 8
        
        return min(base_score, 100)
    
    def _calculate_inbound_engagement_score(self, conversation_data: Dict, inbound_context: Dict) -> float:
        """Calculate engagement score for inbound conversations"""
        customer_responses = conversation_data.get('customer_responses', [])
        
        if not customer_responses:
            return 0
        
        score = 0
        total_responses = len(customer_responses)
        
        # Analyze intent level from responses
        all_responses_text = ' '.join(customer_responses).lower()
        
        # High intent indicators
        high_intent_matches = sum(1 for keyword in self.inbound_intent_keywords['high_intent'] 
                                if keyword in all_responses_text)
        score += high_intent_matches * 25
        
        # Medium intent indicators
        medium_intent_matches = sum(1 for keyword in self.inbound_intent_keywords['medium_intent'] 
                                  if keyword in all_responses_text)
        score += medium_intent_matches * 15
        
        # Urgency indicators
        urgency_matches = sum(1 for keyword in self.inbound_intent_keywords['urgency_indicators'] 
                            if keyword in all_responses_text)
        score += urgency_matches * 20
        
        # Penalize low intent
        low_intent_matches = sum(1 for keyword in self.inbound_intent_keywords['low_intent'] 
                               if keyword in all_responses_text)
        score -= low_intent_matches * 10
        
        # Conversation quality assessment
        quality_score = self._assess_conversation_quality(customer_responses)
        score += quality_score
        
        # Question asking (shows engagement)
        question_count = sum(1 for response in customer_responses if '?' in response)
        score += min(question_count * 8, 20)
        
        # Response depth and detail
        avg_response_length = sum(len(r.split()) for r in customer_responses) / total_responses
        if avg_response_length > 12:
            score += 15  # Detailed responses
        elif avg_response_length > 6:
            score += 10
        elif avg_response_length < 3:
            score -= 10  # Very short responses
        
        # Conversation continuation (they stayed on the line)
        if total_responses > 5:
            score += 15  # Sustained engagement
        elif total_responses > 3:
            score += 10
        
        # Proactive information sharing
        if any('company' in r.lower() or 'business' in r.lower() for r in customer_responses):
            score += 10
        
        return max(0, min(score / max(total_responses, 1), 100))
    
    def _calculate_inbound_qualification_score(self, conversation_data: Dict, prospect) -> float:
        """BANT qualification scoring adjusted for inbound calls"""
        customer_responses = conversation_data.get('customer_responses', [])
        responses_text = ' '.join(customer_responses).lower()
        
        bant_score = 0
        
        # Budget qualification with inbound context
        budget_score = 0
        if any(indicator in responses_text for indicator in self.budget_indicators):
            budget_score = 25
        
        # Bonus for specific budget mentions
        if any(word in responses_text for word in ['thousand', 'million', '$', 'budget of']):
            budget_score += 10
        
        bant_score += min(budget_score, 35)
        
        # Authority qualification
        authority_score = 0
        if any(indicator in responses_text for indicator in self.authority_indicators):
            authority_score = 25
        
        # Inbound callers often have more authority (they initiated the call)
        authority_score += 10  # Inbound bonus
        
        bant_score += min(authority_score, 35)
        
        # Need qualification (higher weight for inbound)
        need_score = 0
        if any(indicator in responses_text for indicator in self.need_indicators):
            need_score = 25
        
        # They called us, so they likely have a need
        need_score += 15  # Inbound need bonus
        
        bant_score += min(need_score, 40)
        
        # Timeline qualification
        timeline_score = 0
        if any(indicator in responses_text for indicator in self.timeline_indicators):
            timeline_score = 25
        
        # Calling often indicates some urgency
        timeline_score += 5  # Mild urgency bonus for calling
        
        bant_score += min(timeline_score, 30)
        
        # Additional inbound qualifiers
        if 'competitor' in responses_text or 'comparing' in responses_text:
            bant_score += 10  # They're shopping around
        
        if 'recommendation' in responses_text or 'referred' in responses_text:
            bant_score += 15  # Came via referral
        
        return min(bant_score, 100)
    
    def _calculate_inbound_behavioral_score(self, conversation_data: Dict, inbound_context: Dict) -> float:
        """Calculate behavioral score for inbound calls"""
        customer_responses = conversation_data.get('customer_responses', [])
        call_duration = conversation_data.get('call_duration', 0)
        
        if not customer_responses:
            # They called but didn't engage - still some points for initiating
            return 20
        
        behavior_score = 0
        
        # Call initiation bonus (they called us!)
        behavior_score += 25
        
        # Call timing analysis
        call_time = inbound_context.get('call_time', datetime.utcnow())
        if self._is_peak_business_hours(call_time):
            behavior_score += 10  # Called during business hours
        elif call_time.hour < 9 or call_time.hour > 17:
            behavior_score += 15  # Called outside hours (shows urgency)
        
        # Call duration scoring (adjusted for inbound)
        if call_duration > 600:  # 10+ minutes
            behavior_score += 30
        elif call_duration > 300:  # 5+ minutes
            behavior_score += 20
        elif call_duration > 180:  # 3+ minutes
            behavior_score += 15
        elif call_duration < 60:  # Less than 1 minute
            behavior_score -= 5  # Hung up quickly
        
        # Response patterns
        total_responses = len(customer_responses)
        if total_responses > 8:
            behavior_score += 20  # Very engaged
        elif total_responses > 5:
            behavior_score += 15
        elif total_responses > 3:
            behavior_score += 10
        
        # Patience indicators (didn't hang up during qualification)
        if total_responses > 3 and call_duration > 180:
            behavior_score += 10
        
        # Interruption patterns
        interruptions = conversation_data.get('interruptions', 0)
        if interruptions == 0:
            behavior_score += 5  # Polite listener
        elif interruptions > 5:
            behavior_score -= 10  # Impatient
        
        # Callback willingness
        if inbound_context.get('callback_requested'):
            behavior_score += 15  # Willing to continue conversation
        
        # Transfer acceptance
        if inbound_context.get('transfer_accepted'):
            behavior_score += 20  # High engagement
        elif inbound_context.get('transfer_declined'):
            behavior_score -= 5   # Wants to handle via AI only
        
        return max(0, min(behavior_score, 100))
    
    def _apply_inbound_bonuses(self, base_score: float, prospect_context: Dict, 
                             conversation_data: Dict, inbound_context: Dict) -> float:
        """Apply additional bonuses specific to inbound calls"""
        bonus_points = 0
        
        # Repeat caller bonus
        prospect = prospect_context['prospect']
        if prospect.total_inbound_calls and prospect.total_inbound_calls > 1:
            bonus_points += 5
        
        # Multiple contact method bonus (called after form submission)
        if prospect.source == 'form_submission':
            bonus_points += 8
        
        # Marketing attribution bonus
        if inbound_context.get('marketing_campaign'):
            bonus_points += 5
        
        # Peak performance bonus (called during peak sales hours)
        call_time = inbound_context.get('call_time', datetime.utcnow())
        if 10 <= call_time.hour <= 16:  # Peak sales hours
            bonus_points += 3
        
        # Quick response bonus (called back quickly after initial contact)
        if prospect.form_submitted_at:
            time_diff = call_time - prospect.form_submitted_at
            if time_diff.total_seconds() < 3600:  # Called within 1 hour
                bonus_points += 10
            elif time_diff.total_seconds() < 86400:  # Called within 24 hours
                bonus_points += 5
        
        # Referral bonus
        if prospect.referred_by_prospect_id:
            bonus_points += 7
        
        return min(base_score + bonus_points, 100)
    
    def _assess_conversation_quality(self, customer_responses: List[str]) -> float:
        """Assess the overall quality of the conversation"""
        if not customer_responses:
            return 0
        
        quality_score = 0
        responses_text = ' '.join(customer_responses).lower()
        
        # Detailed responses indicator
        technical_terms = ['system', 'process', 'integration', 'requirement', 'specification']
        if any(term in responses_text for term in technical_terms):
            quality_score += 15
        
        # Business context sharing
        business_terms = ['company', 'team', 'department', 'organization', 'business']
        if any(term in responses_text for term in business_terms):
            quality_score += 10
        
        # Specific needs articulation
        if 'specifically' in responses_text or 'exactly' in responses_text:
            quality_score += 8
        
        # Future planning indicators
        planning_terms = ['plan', 'planning', 'strategy', 'roadmap', 'future']
        if any(term in responses_text for term in planning_terms):
            quality_score += 10
        
        # Clear communication
        avg_sentence_length = sum(len(r.split()) for r in customer_responses) / len(customer_responses)
        if 8 <= avg_sentence_length <= 20:  # Sweet spot for clear communication
            quality_score += 10
        
        return quality_score
    
    def _generate_inbound_insights(self, conversation_data: Dict, inbound_context: Dict, 
                                 component_scores: Dict) -> Dict:
        """Generate specific insights for inbound calls"""
        insights = {}
        
        customer_responses = conversation_data.get('customer_responses', [])
        responses_text = ' '.join(customer_responses).lower()
        
        # Intent analysis
        if any(keyword in responses_text for keyword in self.inbound_intent_keywords['high_intent']):
            insights['intent_level'] = 'high'
            insights['intent_confidence'] = 0.9
        elif any(keyword in responses_text for keyword in self.inbound_intent_keywords['medium_intent']):
            insights['intent_level'] = 'medium'
            insights['intent_confidence'] = 0.7
        else:
            insights['intent_level'] = 'low'
            insights['intent_confidence'] = 0.5
        
        # Urgency assessment
        if any(keyword in responses_text for keyword in self.inbound_intent_keywords['urgency_indicators']):
            insights['urgency'] = 'high'
        elif 'soon' in responses_text or 'quickly' in responses_text:
            insights['urgency'] = 'medium'
        else:
            insights['urgency'] = 'low'
        
        # Conversation readiness
        if component_scores['engagement'] > 70 and component_scores['qualification'] > 60:
            insights['conversation_readiness'] = 'ready_for_sales'
        elif component_scores['engagement'] > 50:
            insights['conversation_readiness'] = 'needs_nurturing'
        else:
            insights['conversation_readiness'] = 'early_stage'
        
        # Preferred next step
        if 'demo' in responses_text or 'show me' in responses_text:
            insights['preferred_next_step'] = 'demo'
        elif 'call back' in responses_text or 'schedule' in responses_text:
            insights['preferred_next_step'] = 'callback'
        elif 'information' in responses_text or 'send me' in responses_text:
            insights['preferred_next_step'] = 'information'
        else:
            insights['preferred_next_step'] = 'follow_up'
        
        # Communication style preference
        if len(customer_responses) > 5 and conversation_data.get('call_duration', 0) > 300:
            insights['communication_preference'] = 'detailed_discussion'
        elif any(len(r.split()) < 5 for r in customer_responses[-3:]):
            insights['communication_preference'] = 'brief_and_direct'
        else:
            insights['communication_preference'] = 'standard'
        
        return insights
    
    def _determine_inbound_next_action(self, final_score: float, inbound_insights: Dict) -> str:
        """Determine recommended next action for inbound leads"""
        intent_level = inbound_insights.get('intent_level', 'low')
        urgency = inbound_insights.get('urgency', 'low')
        preferred_step = inbound_insights.get('preferred_next_step', 'follow_up')
        
        if final_score >= 85 and intent_level == 'high':
            return 'immediate_transfer'
        elif final_score >= 75 and urgency == 'high':
            return 'priority_callback'
        elif final_score >= 65:
            if preferred_step == 'demo':
                return 'schedule_demo'
            elif preferred_step == 'callback':
                return 'schedule_callback'
            else:
                return 'send_information_and_follow_up'
        elif final_score >= 45:
            return 'nurture_sequence'
        elif final_score >= 25:
            return 'long_term_follow_up'
        else:
            return 'thank_and_close'
    
    def _generate_inbound_score_reasoning(self, final_score: float, component_scores: Dict, 
                                        prospect, conversation_data: Dict, 
                                        inbound_context: Dict) -> str:
        """Generate reasoning specific to inbound calls"""
        reasoning_parts = []
        
        # Overall assessment with inbound context
        if final_score >= 80:
            reasoning_parts.append("Highly qualified inbound lead with strong purchase intent")
        elif final_score >= 60:
            reasoning_parts.append("Well-qualified inbound prospect showing genuine interest")
        elif final_score >= 40:
            reasoning_parts.append("Moderately qualified inbound caller worth pursuing")
        else:
            reasoning_parts.append("Early-stage inbound inquiry requiring nurturing")
        
        # Inbound-specific factors
        if inbound_context.get('is_repeat_caller'):
            reasoning_parts.append("Repeat caller showing persistent interest")
        
        if prospect.source == 'form_submission':
            reasoning_parts.append("Previously submitted form and now called for follow-up")
        
        # Intent and urgency
        customer_responses = conversation_data.get('customer_responses', [])
        if customer_responses:
            responses_text = ' '.join(customer_responses).lower()
            
            if any(keyword in responses_text for keyword in self.inbound_intent_keywords['high_intent']):
                reasoning_parts.append("Expressed high purchase intent")
            
            if any(keyword in responses_text for keyword in self.inbound_intent_keywords['urgency_indicators']):
                reasoning_parts.append("Indicated time sensitivity")
        
        # Engagement quality
        if component_scores['engagement'] > 75:
            reasoning_parts.append("Highly engaged in conversation")
        elif component_scores['engagement'] < 30:
            reasoning_parts.append("Limited engagement during call")
        
        # Call characteristics
        call_duration = conversation_data.get('call_duration', 0)
        if call_duration > 300:
            reasoning_parts.append("Invested significant time in conversation")
        
        return ". ".join(reasoning_parts) + "."
    
    def _calculate_inbound_confidence_level(self, conversation_data: Dict, inbound_context: Dict) -> str:
        """Calculate confidence level for inbound scoring"""
        customer_responses = conversation_data.get('customer_responses', [])
        call_duration = conversation_data.get('call_duration', 0)
        
        # Higher confidence for inbound calls due to self-selection
        base_confidence = 0.3  # Start higher than outbound
        
        if len(customer_responses) >= 5:
            base_confidence += 0.3
        elif len(customer_responses) >= 3:
            base_confidence += 0.2
        
        if call_duration >= 180:
            base_confidence += 0.2
        elif call_duration >= 120:
            base_confidence += 0.1
        
        # Bonus for repeat interactions
        if inbound_context.get('is_repeat_caller'):
            base_confidence += 0.1
        
        # Bonus for marketing attribution
        if inbound_context.get('marketing_source'):
            base_confidence += 0.1
        
        if base_confidence >= 0.8:
            return 'high'
        elif base_confidence >= 0.6:
            return 'medium'
        else:
            return 'low'
    
    def _is_peak_business_hours(self, call_time: datetime) -> bool:
        """Check if call was made during peak business hours"""
        # Define peak hours as 10 AM - 4 PM on weekdays
        if call_time.weekday() >= 5:  # Weekend
            return False
        
        return 10 <= call_time.hour <= 16
    
    def _is_peak_sales_hours(self, call_time: datetime) -> bool:
        """Check if call was made during peak sales hours"""
        # Peak sales typically Tuesday-Thursday, 10 AM - 4 PM
        if call_time.weekday() not in [1, 2, 3]:  # Tue, Wed, Thu
            return False
        
        return 10 <= call_time.hour <= 16