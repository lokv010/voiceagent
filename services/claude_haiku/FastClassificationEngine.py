from configparser import Error
import http
import os    
import json
import logging
import asyncio
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional, List, Union
from enum import Enum
import time
from pathlib import Path
import aiohttp



# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
class Config:
    ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')
    ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
    CONFIDENCE_THRESHOLD = float(os.getenv('CONFIDENCE_THRESHOLD', '0.7'))
    MAX_RETRIES = int(os.getenv('MAX_RETRIES', '3'))
    TIMEOUT_SECONDS = int(os.getenv('TIMEOUT_SECONDS', '30'))
    TEMPLATE_PATH = os.getenv('TEMPLATE_PATH', 'template/burger_franchise.json')


# Proactive Conversation Flow Classes (Ultra-minimal approach)
class ConversationContext:
    """ONLY 1 function: Package context into Claude prompt"""
    
    def build_claude_context(self, customer_input: str, session_data: dict) -> str:
        """Package context into Claude prompt"""
        conversation_history = session_data.get('conversation_history', [])
        customer_data = session_data.get('customer_data', {})
        current_stage = session_data.get('current_stage', 'GREETING')
        
        history_text = "\n".join([f"{entry['role']}: {entry['message']}" for entry in conversation_history[-6:]])  # Last 6 exchanges
        
        stage_objectives = {
            'GREETING': 'Build rapport, understand their situation and interest in franchise',
            'DISCOVERY': 'Learn budget, authority, needs, timeline for franchise investment',
            'PRESENTATION': 'Show relevant franchise benefits and ROI based on their profile',
            'CLOSING': 'Move toward next steps - application, territory selection, or follow-up meeting'
        }
        
        return f"""You are a professional franchise sales agent following this conversation flow:
1. GREETING: Build rapport, understand their situation
2. DISCOVERY: Learn budget, authority, needs, timeline  
3. PRESENTATION: Show relevant solution benefits
4. CLOSING: Move toward next steps/commitment

CURRENT STAGE: {current_stage}
YOUR OBJECTIVE: {stage_objectives.get(current_stage, 'Guide conversation forward')}

CONVERSATION HISTORY:
{history_text}

GATHERED CUSTOMER DATA:
{json.dumps(customer_data, indent=2)}

CUSTOMER'S LATEST INPUT: "{customer_input}"

INSTRUCTIONS:
- Drive conversation toward completing current stage objective
- Ask proactive questions to gather missing information
- When stage is complete, naturally advance to next stage
- Keep responses concise but engaging
- Use gathered data to personalize your response

VOICE CALL REQUIREMENTS:
- Keep responses to 1-2 short sentences maximum, always ending with a question
- Each sentence should be 8-15 words only
- Use conversational, natural speech patterns
- NO expressions like *nods* or *smiles* 
- NO action descriptions or roleplay formatting
- Speak directly like a real phone conversation

PRODUCT INFORMATION:
- Product: Burger Singh Franchise
- Investment Required: 10-25 Lakh INR
- Expected ROI: 20-30% annually
- Location Requirements: High foot traffic, urban areas 1000-5000 sq ft
- Key Benefits: Brand recognition, proven business model, comprehensive training

Respond as the sales agent would speak directly to the customer."""

class ClaudeFlowDirector:
    """ONLY 3 functions: Proactive conversation management"""
    
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("API key is required")
        self.api_key = api_key
        self.context_builder = ConversationContext()

        self.response_cache = {
        'GREETING': {
            'default': "Thank you for calling about our burger franchise. What interests you most about this opportunity?",
            'interested': "Great to hear you're interested! Do you have restaurant or business experience?",
            'price_inquiry': "Investment starts at 10 lakhs. What's your budget range for this venture?"
        },
        'DISCOVERY': {
            'budget_10_25': "Perfect! That fits our franchise model. Do you have a specific location in mind?",
            'no_experience': "No problem! We provide comprehensive training. What draws you to the food business?",
            'location_ready': "Excellent! High foot traffic areas work best. What's the square footage?"
        },
        'PRESENTATION': {
            'roi_question': "Our franchisees typically see 20-30% ROI annually. Would you like territory details?",
            'training_concern': "We provide 2 weeks intensive training plus ongoing support. When could you start?",
            'competition_worry': "Our unique recipes and brand recognition set us apart. Ready for next steps?"
        },
        'CLOSING': {
            'next_steps': "I'll send you the franchise disclosure document. Can we schedule a call to discuss territories?",
            'need_time': "Absolutely! I'll follow up next week. Any specific questions I can answer now?",
            'ready_to_proceed': "Wonderful! Let me connect you with our franchise director to begin the application."
        }
    }

  
    

    
    async def get_proactive_response(self, customer_input: str, conversation_context: dict, sales_objective: str = None) -> dict:
        """Single Claude call with structured prompt for proactive response"""
        try:

            # Check for simple patterns first
            fast_response = self._check_simple_patterns(customer_input, conversation_context)
            logger.info(f"Fast response check: {fast_response}")
            if fast_response:
                return fast_response
            
            # Build structured context for Claude
            claude_prompt = self.context_builder.build_claude_context(customer_input, conversation_context)
            
            # Add sales objective if provided
            if sales_objective:
                claude_prompt += f"\n\nSPECIFIC OBJECTIVE: {sales_objective}"
            
            # Get proactive response from Claude
            headers = {
                "Content-Type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01"
            }
            
            payload = {
                "model": "claude-3-haiku-20240307",
                "max_tokens": 800,
                "messages": [{"role": "user", "content": claude_prompt}]
            }
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=Config.TIMEOUT_SECONDS)) as session:

                async with session.post(Config.ANTHROPIC_API_URL, json=payload, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        agent_response = data.get('content', [{}])[0].get('text', '')
                        
                        # Determine next stage based on response
                        current_stage = conversation_context.get('current_stage', 'GREETING')
                        next_stage = self._determine_next_stage(agent_response, current_stage, conversation_context)
                        
                        return {
                            'agent_response': agent_response,
                            'current_stage': next_stage,
                            'conversation_continues': True,
                            'processing_time_ms': 0  # Will be set by caller
                        }
                    else:
                        raise Error(f"API error {response.status}")
                    
        except Exception as e:
            logger.error(f"Proactive response failed: {str(e)}")
            return {
                'agent_response': "I'm here to help you with our franchise opportunities. What interests you most about our burger franchise?",
                'current_stage': 'GREETING',
                'conversation_continues': True,
                'processing_time_ms': 0
            }
    
    def update_conversation_memory(self, customer_response: str, system_response: str) -> dict:
        """Simple append to conversation history"""
        return {
            'role_pair': [
                {'role': 'customer', 'message': customer_response, 'timestamp': time.time()},
                {'role': 'agent', 'message': system_response, 'timestamp': time.time()}
            ]
        }
    
    def determine_call_completion(self, conversation_context: dict) -> bool:
        """Basic completion check"""
        conversation_history = conversation_context.get('conversation_history', [])
        current_stage = conversation_context.get('current_stage', 'GREETING')
        
        # Check if in closing stage and enough exchanges happened
        if current_stage == 'CLOSING' and len(conversation_history) >= 8:
            return True
            
        # Check for explicit completion signals in recent messages
        recent_messages = [entry['message'].lower() for entry in conversation_history[-3:]]
        completion_signals = ['thank you', 'i\'ll think about it', 'not interested', 'call me back', 'send information']
        
        if any(signal in ' '.join(recent_messages) for signal in completion_signals):
            return True
            
        return False
    
    def _determine_next_stage(self, agent_response: str, current_stage: str, context: dict) -> str:
        """Simple stage progression logic"""
        response_lower = agent_response.lower()
        
        # Natural progression keywords
        if current_stage == 'GREETING':
            if any(word in response_lower for word in ['budget', 'investment', 'capital', 'afford']):
                return 'DISCOVERY'
        elif current_stage == 'DISCOVERY':
            if any(word in response_lower for word in ['show you', 'here\'s how', 'benefits', 'roi']):
                return 'PRESENTATION'
        elif current_stage == 'PRESENTATION':
            if any(word in response_lower for word in ['next step', 'move forward', 'application', 'schedule']):
                return 'CLOSING'
        
        return current_stage  # Stay in current stage if no progression indicators
    

    def _check_simple_patterns(self, customer_input: str, conversation_context: dict) -> Optional[dict]:

        """Use cached response lookup instead of hardcoding"""
    
        # Delegate to _get_cached_response for pattern matching
        cached_response = self._get_cached_response(customer_input, conversation_context)
        
        if cached_response:
            current_stage = conversation_context.get('current_stage', 'GREETING')
            next_stage = self._determine_next_stage(cached_response, current_stage, conversation_context)
            
            return {
                'agent_response': cached_response,
                'current_stage': next_stage,
                'conversation_continues': True,
                'processing_time_ms': 5,
                'source': 'pattern_cache'
            }
        
        return None  # No pattern matched, use Claude
    
    def _get_cached_response(self, customer_input: str, context: dict) -> Optional[str]:
        """Check for cached responses based on input patterns"""
        input_lower = customer_input.lower()
        current_stage = context.get('current_stage', 'GREETING')
        stage_cache = self.response_cache.get(current_stage, {})
        
        # Pattern matching for common inputs
        if current_stage == 'GREETING':
            if any(word in input_lower for word in ['interested', 'tell me more', 'yes']):
                return stage_cache.get('interested')
            elif any(word in input_lower for word in ['cost', 'price', 'investment', 'money']):
                return stage_cache.get('price_inquiry')
        
        elif current_stage == 'DISCOVERY':
            if any(word in input_lower for word in ['10', '15', '20', 'lakh', 'budget']):
                return stage_cache.get('budget_10_25')
            elif any(word in input_lower for word in ['no experience', 'never ran', 'first time']):
                return stage_cache.get('no_experience')
        
        # ... more pattern matching ...
        
        return stage_cache.get('default')  # Fallback to default stage response

# Enhanced FastClassificationService for Proactive Flow
class ProactiveConversationService:
    """Coordinates proactive conversation flow"""
    
    def __init__(self, api_key: str):
        self.flow_director = ClaudeFlowDirector(api_key)
        self.session_data = {}
    
    async def handle_customer_interaction(self, customer_input: str, session_id: str = "default") -> dict:
        """Main method: Handle customer input with proactive response"""
        start_time = time.time()
        
        # Initialize or get session data
        if session_id not in self.session_data:
            self.session_data[session_id] = {
                'conversation_history': [],
                'customer_data': {},
                'current_stage': 'GREETING',
                'session_start': time.time()
            }
        
        session_context = self.session_data[session_id]
        
        try:
            # Get proactive response
            result = await self.flow_director.get_proactive_response(
                customer_input, 
                session_context
            )
            
            # Update conversation memory
            memory_update = self.flow_director.update_conversation_memory(
                customer_input, 
                result['agent_response']
            )
            
            # Update session data
            session_context['conversation_history'].extend(memory_update['role_pair'])
            session_context['current_stage'] = result['current_stage']
            
            # Extract and update customer data from conversation
            self._update_customer_data(customer_input, session_context)
            
            # Check if conversation should end
            call_completed = self.flow_director.determine_call_completion(session_context)
            
            processing_time = (time.time() - start_time) * 1000
            
            return {
                'agent_response': result['agent_response'],
                'current_stage': result['current_stage'],
                'conversation_continues': not call_completed,
                'call_completed': call_completed,
                'processing_time_ms': processing_time,
                'conversation_length': len(session_context['conversation_history']),
                'customer_data': session_context['customer_data']
            }
            
        except Exception as e:
            logger.error(f"Conversation handling failed: {str(e)}")
            return {
                'agent_response': "I apologize for the technical issue. Let me help you with our franchise information. What would you like to know?",
                'current_stage': 'GREETING',
                'conversation_continues': True,
                'call_completed': False,
                'processing_time_ms': (time.time() - start_time) * 1000
            }
    
    def _update_customer_data(self, customer_input: str, session_context: dict):
        """Extract and update customer information from input"""
        text_lower = customer_input.lower()
        customer_data = session_context['customer_data']
        
        # Extract investment capacity
        if any(word in text_lower for word in ['investment', 'budget', 'afford']):
            if 'investment_capacity' not in customer_data:
                customer_data['investment_capacity'] = 'unknown'
            if 'budget' not in customer_data:
                customer_data['budget'] = 'unknown'

    def get_session_summary(self, session_id: str) -> dict:
        """Get summary of conversation session"""
        if session_id not in self.session_data:
            return {'error': 'Session not found'}
            
        session = self.session_data[session_id]
        return {
            'session_id': session_id,
            'current_stage': session.get('current_stage'),
            'conversation_length': len(session.get('conversation_history', [])),
            'customer_data': session.get('customer_data', {}),
            'session_duration_minutes': (time.time() - session.get('session_start', time.time())) / 60
        }
                