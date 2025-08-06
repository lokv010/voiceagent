import logging
from datetime import datetime
from typing import Dict, List
import re

class UnifiedLeadScorer:
    def __init__(self):
        """Initialize lead scoring system"""
        self.scoring_weights = {
            'source_score': 0.15,      # Warm vs cold lead (0-100)
            'engagement_score': 0.25,   # Response quality and interest (0-100)
            'qualification_score': 0.30, # BANT qualification (0-100)
            'behavioral_score': 0.20,   # Call behavior patterns (0-100)
            'fit_score': 0.10          # Company/profile fit (0-100)
        }
        
        # Keyword dictionaries for scoring
        self.positive_keywords = [
            'interested', 'tell me more', 'sounds good', 'when can', 'how much',
            'what are the options', 'that makes sense', 'i like that', 'perfect',
            'exactly', 'right', 'yes', 'definitely', 'absolutely', 'great',
            'awesome', 'fantastic', 'wonderful', 'amazing', 'excellent'
        ]
        
        self.negative_keywords = [
            'not interested', 'no thanks', 'remove me', 'busy', 'not now',
            'maybe later', 'send me information', 'i need to think', 'no',
            'never', 'stop', 'don\'t', 'can\'t', 'won\'t', 'not really'
        ]
        
        self.question_indicators = [
            'how', 'what', 'when', 'where', 'why', 'can you', 'could you',
            'would you', 'will you', 'do you', 'are you', 'is it', 'does it'
        ]
        
        self.budget_indicators = [
            'budget', 'afford', 'cost', 'price', 'investment', 'expensive',
            'cheap', 'money', 'pay', 'payment', 'financing', 'loan'
        ]
        
        self.authority_indicators = [
            'decision', 'decide', 'team', 'boss', 'manager', 'i can',
            'my company', 'we need', 'approval', 'authorize', 'owner'
        ]
        
        self.need_indicators = [
            'need', 'problem', 'challenge', 'looking for', 'want', 'require',
            'must have', 'essential', 'important', 'critical', 'urgent'
        ]
        
        self.timeline_indicators = [
            'soon', 'this month', 'next quarter', 'asap', 'quickly', 'immediate',
            'right away', 'within', 'by', 'before', 'deadline', 'urgent'
        ]
        
        logging.info("Unified Lead Scorer initialized")
    
    def calculate_comprehensive_score(self, prospect_context: Dict, conversation_data: Dict) -> Dict:
        """Calculate unified lead score across all factors"""
        prospect = prospect_context['prospect']
        
        try:
            # Calculate component scores
            source_score = self._calculate_source_score(prospect)
            engagement_score = self._calculate_engagement_score(conversation_data)
            qualification_score = self._calculate_qualification_score(conversation_data, prospect)
            behavioral_score = self._calculate_behavioral_score(conversation_data)
            fit_score = self._calculate_fit_score(prospect)
            
            # Calculate weighted final score
            final_score = (
                source_score * self.scoring_weights['source_score'] +
                engagement_score * self.scoring_weights['engagement_score'] +
                qualification_score * self.scoring_weights['qualification_score'] +
                behavioral_score * self.scoring_weights['behavioral_score'] +
                fit_score * self.scoring_weights['fit_score']
            )
            
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
            
            return {
                'final_score': round(final_score, 1),
                'component_scores': component_scores,
                'score_reasoning': self._generate_score_reasoning(
                    final_score, component_scores, prospect, conversation_data
                ),
                'confidence_level': self._calculate_confidence_level(conversation_data)
            }
            
        except Exception as e:
            logging.error(f"Error calculating lead score: {str(e)}")
            return {
                'final_score': 0,
                'component_scores': {'source': 0, 'engagement': 0, 'qualification': 0, 'behavioral': 0, 'fit': 0},
                'score_reasoning': f"Error calculating score: {str(e)}",
                'confidence_level': 'low'
            }
    
    def _calculate_source_score(self, prospect) -> float:
        """Score based on lead source and quality"""
        # Base scores by source
        source_scores = {
            'form_submission': 40,    # Warm lead base score
            'cold_list': 10,         # Cold lead base score
            'referral': 60,          # Referral base score
            'website_visitor': 25    # Website visitor base score
        }
        
        base_score = source_scores.get(prospect.source, 10)
        
        # Bonus points for form submission quality
        if prospect.source == 'form_submission' and prospect.form_data:
            form_fields = len(prospect.form_data)
            form_bonus = min(form_fields * 3, 20)  # Up to 20 bonus points
            base_score += form_bonus
            
            # Extra bonus for high-value form fields
            if 'budget' in prospect.form_data:
                base_score += 10
            if 'timeline' in prospect.form_data:
                base_score += 10
            if 'company' in prospect.form_data:
                base_score += 5
        
        # Bonus for multiple contact attempts (shows persistence paid off)
        if prospect.contact_attempts > 1:
            base_score += min(prospect.contact_attempts * 2, 10)
        
        return min(base_score, 100)
    
    def _calculate_engagement_score(self, conversation_data: Dict) -> float:
        """Score based on conversation engagement"""
        customer_responses = conversation_data.get('customer_responses', [])
        
        if not customer_responses:
            return 0
        
        score = 0
        total_responses = len(customer_responses)
        
        for response in customer_responses:
            response_lower = response.lower()
            response_score = 0
            
            # Positive engagement indicators
            positive_matches = sum(1 for keyword in self.positive_keywords if keyword in response_lower)
            response_score += positive_matches * 15
            
            # Question asking (shows interest)
            question_matches = sum(1 for indicator in self.question_indicators if indicator in response_lower)
            response_score += question_matches * 12
            
            # Negative engagement indicators
            negative_matches = sum(1 for keyword in self.negative_keywords if keyword in response_lower)
            response_score -= negative_matches * 20
            
            # Response length (longer responses = more engagement)
            word_count = len(response.split())
            if word_count > 15:
                response_score += 10
            elif word_count > 8:
                response_score += 5
            elif word_count < 3:
                response_score -= 5
            
            # Emotional indicators
            if any(word in response_lower for word in ['excited', 'love', 'hate', 'frustrated']):
                response_score += 8
            
            score += response_score
        
        # Average out by number of responses
        if total_responses > 0:
            score = score / total_responses
        
        # Conversation continuation bonus
        if total_responses > 3:
            score += 10  # Bonus for sustained conversation
        
        return max(0, min(score, 100))
    
    def _calculate_qualification_score(self, conversation_data: Dict, prospect) -> float:
        """BANT (Budget, Authority, Need, Timeline) qualification scoring"""
        customer_responses = conversation_data.get('customer_responses', [])
        responses_text = ' '.join(customer_responses).lower()
        
        bant_score = 0
        
        # Budget qualification (25 points max)
        budget_matches = sum(1 for indicator in self.budget_indicators if indicator in responses_text)
        if budget_matches > 0:
            bant_score += min(budget_matches * 12, 25)
        
        # Authority qualification (25 points max)
        authority_matches = sum(1 for indicator in self.authority_indicators if indicator in responses_text)
        if authority_matches > 0:
            bant_score += min(authority_matches * 12, 25)
        
        # Need qualification (25 points max)
        need_matches = sum(1 for indicator in self.need_indicators if indicator in responses_text)
        if need_matches > 0:
            bant_score += min(need_matches * 12, 25)
        
        # Timeline qualification (25 points max)
        timeline_matches = sum(1 for indicator in self.timeline_indicators if indicator in responses_text)
        if timeline_matches > 0:
            bant_score += min(timeline_matches * 12, 25)
        
        # Bonus for form data (if available)
        if prospect.form_data:
            if 'budget' in prospect.form_data and prospect.form_data['budget']:
                bant_score += 15
            if 'timeline' in prospect.form_data and prospect.form_data['timeline']:
                bant_score += 15
            if 'company_size' in prospect.form_data:
                bant_score += 10
        
        # Specific qualification phrases
        qualification_phrases = [
            'ready to buy', 'ready to move forward', 'let\'s do it',
            'sign me up', 'what\'s the next step', 'how do we proceed'
        ]
        
        for phrase in qualification_phrases:
            if phrase in responses_text:
                bant_score += 20
                break
        
        return min(bant_score, 100)
    
    def _calculate_behavioral_score(self, conversation_data: Dict) -> float:
        """Score based on call behavior patterns"""
        customer_responses = conversation_data.get('customer_responses', [])
        call_duration = conversation_data.get('call_duration', 0)
        
        if not customer_responses:
            return 0
        
        behavior_score = 0
        
        # Call duration scoring (longer calls = higher engagement)
        if call_duration > 300:  # 5+ minutes
            behavior_score += 25
        elif call_duration > 180:  # 3+ minutes
            behavior_score += 15
        elif call_duration > 120:  # 2+ minutes
            behavior_score += 10
        elif call_duration < 60:  # Less than 1 minute
            behavior_score -= 10
        
        # Response consistency
        total_responses = len(customer_responses)
        if total_responses > 5:
            behavior_score += 15  # Sustained conversation
        elif total_responses > 3:
            behavior_score += 10
        elif total_responses < 2:
            behavior_score -= 5
        
        # Response quality patterns
        avg_response_length = sum(len(r.split()) for r in customer_responses) / len(customer_responses)
        if avg_response_length > 10:
            behavior_score += 15  # Detailed responses
        elif avg_response_length > 5:
            behavior_score += 10
        elif avg_response_length < 3:
            behavior_score -= 10  # Very short responses
        
        # Interruption patterns (if available in conversation data)
        interruptions = conversation_data.get('interruptions', 0)
        if interruptions > 3:
            behavior_score -= 15  # Too many interruptions
        elif interruptions == 0:
            behavior_score += 5   # Polite listener
        
        # Enthusiasm indicators
        enthusiasm_words = ['great', 'awesome', 'fantastic', 'perfect', 'excellent']
        enthusiasm_count = sum(1 for response in customer_responses 
                             for word in enthusiasm_words 
                             if word in response.lower())
        behavior_score += min(enthusiasm_count * 5, 15)
        
        return max(0, min(behavior_score, 100))
    
    def _calculate_fit_score(self, prospect) -> float:
        """Score based on company/profile alignment"""
        fit_score = 50  # Base score
        
        # Company size and industry fit
        if prospect.company:
            fit_score += 15  # Has company information
            
            # Industry-specific scoring
            if prospect.industry:
                # Add industry-specific logic here
                high_value_industries = ['technology', 'finance', 'healthcare', 'manufacturing']
                if any(industry in prospect.industry.lower() for industry in high_value_industries):
                    fit_score += 15
        
        # Job title relevance
        if prospect.job_title:
            decision_maker_titles = ['owner', 'ceo', 'president', 'director', 'manager', 'vp']
            if any(title in prospect.job_title.lower() for title in decision_maker_titles):
                fit_score += 20
        
        # Product category alignment
        if prospect.product_category:
            # This could be customized based on your specific products
            fit_score += 10
        
        # Geographic considerations (if available)
        # This would require additional data about prospect location
        
        return min(fit_score, 100)
    
    def _generate_score_reasoning(self, final_score: float, component_scores: Dict, 
                                prospect, conversation_data: Dict) -> str:
        """Generate human-readable scoring explanation"""
        reasoning_parts = []
        
        # Overall assessment
        if final_score >= 80:
            reasoning_parts.append("Highly qualified lead")
        elif final_score >= 60:
            reasoning_parts.append("Well-qualified lead")
        elif final_score >= 40:
            reasoning_parts.append("Moderately qualified lead")
        elif final_score >= 20:
            reasoning_parts.append("Partially qualified lead")
        else:
            reasoning_parts.append("Low qualification score")
        
        # Component breakdown
        highest_component = max(component_scores.items(), key=lambda x: x[1])
        lowest_component = min(component_scores.items(), key=lambda x: x[1])
        
        reasoning_parts.append(f"Strongest area: {highest_component[0]} ({highest_component[1]}/100)")
        
        if lowest_component[1] < 30:
            reasoning_parts.append(f"Needs improvement: {lowest_component[0]} ({lowest_component[1]}/100)")
        
        # Specific insights
        customer_responses = conversation_data.get('customer_responses', [])
        if customer_responses:
            responses_text = ' '.join(customer_responses).lower()
            
            if any(word in responses_text for word in self.positive_keywords):
                reasoning_parts.append("Showed positive interest")
            
            if any(word in responses_text for word in self.budget_indicators):
                reasoning_parts.append("Discussed budget considerations")
            
            if any(word in responses_text for word in self.timeline_indicators):
                reasoning_parts.append("Mentioned timeline requirements")
        
        return ". ".join(reasoning_parts) + "."
    
    def _calculate_confidence_level(self, conversation_data: Dict) -> str:
        """Calculate confidence level in the scoring"""
        customer_responses = conversation_data.get('customer_responses', [])
        call_duration = conversation_data.get('call_duration', 0)
        
        # Base confidence on amount of interaction
        if len(customer_responses) >= 5 and call_duration >= 180:
            return 'high'
        elif len(customer_responses) >= 3 and call_duration >= 120:
            return 'medium'
        else:
            return 'low'