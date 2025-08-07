"""
Enhanced Conversation Engine for Inbound Calls

Extends the existing conversation engine to handle inbound call scenarios
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional

class InboundConversationTemplates:
    def __init__(self):
        """Initialize inbound-specific conversation templates"""
        
        self.inbound_templates = {
            'greeting': {
                'first_time_caller': "Thank you for calling {company_name}. This is Sarah, your AI assistant. I don't believe we've spoken before - how can I help you today?",
                'returning_customer': "Thank you for calling {company_name}, {name}. This is Sarah. It's great to hear from you again! How can I help you today?",
                'known_prospect': "Thank you for calling {company_name}, {name}. This is Sarah. I see you've shown interest in our {product} services. How can I help you today?"
            },
            
            'intent_discovery': {
                'open_ended': "I'd love to help you with that. Can you tell me a bit more about what you're looking for?",
                'sales_focused': "That sounds like something we can definitely help with. What specifically are you hoping to accomplish with {product_category}?",
                'support_focused': "I'm sorry to hear you're having an issue. Can you describe what's happening so I can better assist you?",
                'complaint_focused': "I understand your frustration, and I want to make sure we address your concerns properly. Can you tell me what happened?"
            },
            
            'qualification': {
                'budget_discovery': "To make sure I connect you with the right information, what kind of budget range are you working with for this project?",
                'timeline_discovery': "When are you hoping to move forward with this? Do you have a specific timeline in mind?",
                'authority_discovery': "Will you be making this decision yourself, or are there others involved in the decision-making process?",
                'need_discovery': "Help me understand - what's prompting you to look into this now? What challenges are you trying to solve?"
            },
            
            'objection_handling': {
                'price_objection': "I understand price is always a consideration. Let me ask - if price weren't a factor, would this be the right solution for your needs?",
                'timing_objection': "I hear that timing is a concern. What would need to change for the timing to be right?",
                'authority_objection': "That makes sense. Who else would be involved in this decision, and what questions might they have?",
                'need_objection': "I appreciate your honesty. Help me understand what you'd need to see to feel confident this is the right fit."
            },
            
            'transition_phrases': {
                'to_human': "Based on what you've shared, I think it would be valuable for you to speak with one of our specialists. Let me connect you with someone who can give you more detailed information.",
                'to_callback': "I want to make sure you get the best possible service. Would you prefer to schedule a time for one of our specialists to call you back when it's convenient?",
                'to_information': "Let me get some information sent to you right away, and then we can schedule a follow-up call to discuss your specific needs.",
                'to_demo': "It sounds like you'd benefit from seeing this in action. Would you be interested in a brief demonstration?"
            },
            
            'closing': {
                'qualified_lead': "Thank you so much for calling, {name}. {next_step}. Is there anything else I can help you with today?",
                'transfer_pending': "Perfect! I'm connecting you now with {agent_name} who specializes in {specialty}. Thank you for calling {company_name}!",
                'callback_scheduled': "Excellent! We have you scheduled for a callback {callback_time}. You should receive a confirmation shortly. Thank you for calling {company_name}!",
                'not_qualified': "Thank you for your call, {name}. While we might not be the best fit right now, please don't hesitate to reach out if your situation changes. Have a great day!"
            }
        }
        
        # Intent-specific conversation flows
        self.conversation_flows = {
            'sales_inquiry': [
                'greeting',
                'intent_discovery',
                'need_qualification',
                'budget_qualification', 
                'timeline_qualification',
                'authority_qualification',
                'recommendation',
                'next_steps'
            ],
            
            'support_request': [
                'greeting',
                'problem_identification',
                'account_verification',
                'solution_attempt',
                'escalation_or_resolution'
            ],
            
            'complaint': [
                'greeting',
                'empathy_response',
                'issue_documentation',
                'immediate_action',
                'follow_up_commitment'
            ],
            
            'general_inquiry': [
                'greeting',
                'intent_discovery',
                'information_gathering',
                'appropriate_routing'
            ]
        }

class InboundConversationEngine:
    def __init__(self, base_engine):
        """Initialize with reference to base conversation engine"""
        self.base_engine = base_engine
        self.inbound_templates = InboundConversationTemplates()
        self.conversation_flows = self.inbound_templates.conversation_flows
        
        logging.info("Inbound Conversation Engine initialized")
    
    def generate_inbound_greeting(self, prospect_context: Dict, call_context: Dict) -> str:
        """Generate contextual greeting for inbound calls"""
        try:
            prospect = prospect_context['prospect']
            company_name = self._get_company_name(prospect.product_category)
            
            # Determine caller type
            if prospect.source == 'inbound_call' and not prospect.name:
                # First-time unknown caller
                template_key = 'first_time_caller'
                greeting = self.inbound_templates.inbound_templates['greeting'][template_key]
                return greeting.format(company_name=company_name)
            
            elif prospect_context['previous_conversations'] > 0:
                # Returning customer
                template_key = 'returning_customer'
                greeting = self.inbound_templates.inbound_templates['greeting'][template_key]
                return greeting.format(
                    company_name=company_name,
                    name=prospect.name or "there"
                )
            
            else:
                # Known prospect calling for first time
                template_key = 'known_prospect'
                greeting = self.inbound_templates.inbound_templates['greeting'][template_key]
                return greeting.format(
                    company_name=company_name,
                    name=prospect.name or "there",
                    product=prospect.product_interest or "our services"
                )
        
        except Exception as e:
            logging.error(f"Error generating inbound greeting: {str(e)}")
            # Fallback greeting
            return f"Thank you for calling. This is Sarah. How can I help you today?"
    
    def generate_intent_discovery_response(self, customer_input: str, prospect_context: Dict, 
                                         conversation_history: List[Dict]) -> str:
        """Generate response to discover customer intent"""
        try:
            # Analyze what they said to determine intent
            intent = self._analyze_customer_intent(customer_input)
            
            # Generate appropriate follow-up question
            if intent == 'sales_inquiry':
                template_key = 'sales_focused'
                product_category = prospect_context['prospect'].product_category or 'our services'
                response = self.inbound_templates.inbound_templates['intent_discovery'][template_key]
                return response.format(product_category=product_category)
            
            elif intent == 'support_request':
                template_key = 'support_focused'
                return self.inbound_templates.inbound_templates['intent_discovery'][template_key]
            
            elif intent == 'complaint':
                template_key = 'complaint_focused'
                return self.inbound_templates.inbound_templates['intent_discovery'][template_key]
            
            else:
                # General inquiry
                template_key = 'open_ended'
                return self.inbound_templates.inbound_templates['intent_discovery'][template_key]
        
        except Exception as e:
            logging.error(f"Error generating intent discovery response: {str(e)}")
            return "I'd love to help you with that. Can you tell me a bit more about what you're looking for?"
    
    def generate_qualification_question(self, qualification_type: str, prospect_context: Dict, 
                                      conversation_history: List[Dict]) -> str:
        """Generate specific qualification questions"""
        try:
            prospect = prospect_context['prospect']
            
            # Check what we already know to avoid redundant questions
            known_info = self._analyze_known_prospect_info(prospect)
            
            if qualification_type == 'budget' and 'budget' not in known_info:
                return self.inbound_templates.inbound_templates['qualification']['budget_discovery']
            
            elif qualification_type == 'timeline' and 'timeline' not in known_info:
                return self.inbound_templates.inbound_templates['qualification']['timeline_discovery']
            
            elif qualification_type == 'authority' and 'authority' not in known_info:
                return self.inbound_templates.inbound_templates['qualification']['authority_discovery']
            
            elif qualification_type == 'need' and 'need' not in known_info:
                return self.inbound_templates.inbound_templates['qualification']['need_discovery']
            
            else:
                # Skip this qualification if we already have the info
                return self._get_next_qualification_question(prospect_context, conversation_history)
        
        except Exception as e:
            logging.error(f"Error generating qualification question: {str(e)}")
            return "Can you tell me more about your specific needs?"
    
    def handle_objection(self, objection_type: str, customer_input: str, 
                        prospect_context: Dict) -> str:
        """Handle common objections with appropriate responses"""
        try:
            if objection_type == 'price':
                return self.inbound_templates.inbound_templates['objection_handling']['price_objection']
            
            elif objection_type == 'timing':
                return self.inbound_templates.inbound_templates['objection_handling']['timing_objection']
            
            elif objection_type == 'authority':
                return self.inbound_templates.inbound_templates['objection_handling']['authority_objection']
            
            elif objection_type == 'need':
                return self.inbound_templates.inbound_templates['objection_handling']['need_objection']
            
            else:
                # Generic objection handling
                return f"I understand your concern about {customer_input.lower()}. Help me understand what would make this feel like the right fit for you."
        
        except Exception as e:
            logging.error(f"Error handling objection: {str(e)}")
            return "I understand your concern. Can you help me understand what would make this feel right for you?"
    
    def generate_transition_response(self, transition_type: str, prospect_context: Dict,
                                   next_step_details: Dict = None) -> str:
        """Generate transition responses for next steps"""
        try:
            prospect = prospect_context['prospect']
            
            if transition_type == 'transfer':
                agent_name = next_step_details.get('agent_name', 'one of our specialists')
                specialty = next_step_details.get('specialty', 'your specific needs')
                response = self.inbound_templates.inbound_templates['transition_phrases']['to_human']
                return response.format(agent_name=agent_name, specialty=specialty)
            
            elif transition_type == 'callback':
                return self.inbound_templates.inbound_templates['transition_phrases']['to_callback']
            
            elif transition_type == 'information':
                return self.inbound_templates.inbound_templates['transition_phrases']['to_information']
            
            elif transition_type == 'demo':
                return self.inbound_templates.inbound_templates['transition_phrases']['to_demo']
            
            else:
                return "Based on what you've shared, let me connect you with the right next step."
        
        except Exception as e:
            logging.error(f"Error generating transition response: {str(e)}")
            return "Let me help you with the next step."
    
    def generate_inbound_closing(self, closing_type: str, prospect_context: Dict,
                                next_step_details: Dict = None) -> str:
        """Generate appropriate closing for inbound calls"""
        try:
            prospect = prospect_context['prospect']
            prospect_name = prospect.name or "there"
            
            if closing_type == 'qualified':
                next_step = next_step_details.get('next_step', 'Someone will be in touch shortly')
                template = self.inbound_templates.inbound_templates['closing']['qualified_lead']
                return template.format(name=prospect_name, next_step=next_step)
            
            elif closing_type == 'transfer':
                agent_name = next_step_details.get('agent_name', 'our specialist')
                specialty = next_step_details.get('specialty', 'your needs')
                company_name = self._get_company_name(prospect.product_category)
                template = self.inbound_templates.inbound_templates['closing']['transfer_pending']
                return template.format(
                    agent_name=agent_name, 
                    specialty=specialty,
                    company_name=company_name
                )
            
            elif closing_type == 'callback':
                callback_time = next_step_details.get('callback_time', 'soon')
                company_name = self._get_company_name(prospect.product_category)
                template = self.inbound_templates.inbound_templates['closing']['callback_scheduled']
                return template.format(callback_time=callback_time, company_name=company_name)
            
            elif closing_type == 'not_qualified':
                template = self.inbound_templates.inbound_templates['closing']['not_qualified']
                return template.format(name=prospect_name)
            
            else:
                return f"Thank you for calling, {prospect_name}. Have a great day!"
        
        except Exception as e:
            logging.error(f"Error generating inbound closing: {str(e)}")
            return "Thank you for calling. Have a great day!"
    
    def build_inbound_system_prompt(self, prospect_context: Dict, call_context: Dict,
                                   conversation_history: List[Dict]) -> str:
        """Build system prompt for inbound calls"""
        try:
            prospect = prospect_context['prospect']
            intent = call_context.get('inbound_intent', 'general_inquiry')
            company_name = self._get_company_name(prospect.product_category)
            
            base_prompt = f"""You are Sarah, a professional AI assistant for {company_name}. 
You are handling an INBOUND call - the customer called YOU.

INBOUND CALL CONTEXT:
- Customer Name: {prospect.name or 'Unknown caller'}
- Phone: {prospect.phone_number}
- Previous Calls: {prospect_context['previous_conversations']}
- Suspected Intent: {intent}
- Call Source: They called us (inbound)

INBOUND CALL GUIDELINES:
1. LISTEN FIRST: Let them tell you why they're calling
2. BE HELPFUL: They reached out to us, so provide value
3. ASK PERMISSION: "Do you have a few minutes to chat about this?"
4. QUALIFY GENTLY: Understand their needs without being pushy
5. OFFER OPTIONS: Transfer, callback, information, or immediate help
6. RESPECT TIME: They called us, so be efficient but thorough

CONVERSATION GOALS (in order):
1. Understand why they called
2. Determine if we can help them
3. Qualify their needs (BANT)
4. Provide appropriate next steps
5. Ensure customer satisfaction

RESPONSE STYLE:
- Warm and welcoming (they chose to call us!)
- Professional but conversational
- Ask one question at a time
- Acknowledge what they've shared
- Be solution-oriented

CALL FLOW FOR {intent.upper()}:
"""
            
            # Add intent-specific guidelines
            if intent == 'sales_inquiry':
                base_prompt += """
- Understand their specific needs
- Qualify budget, timeline, authority, need
- Present relevant solutions
- Offer demo or consultation
- Schedule next steps
"""
            elif intent == 'support_request':
                base_prompt += """
- Identify the specific issue
- Attempt basic troubleshooting if appropriate
- Escalate to technical team if needed
- Ensure issue resolution path is clear
"""
            elif intent == 'complaint':
                base_prompt += """
- Listen empathetically
- Acknowledge their frustration
- Document the issue clearly
- Offer immediate solutions or escalation
- Commit to follow-up
"""
            
            base_prompt += f"""

TRANSFER CRITERIA:
- Complex technical issues
- Pricing negotiations
- Complaints requiring manager
- Requests for specific person
- When you've gathered basic info and they want human interaction

PREVIOUS CONTEXT:
{self._format_previous_context(prospect_context, conversation_history)}

Remember: They called YOU. Be helpful, professional, and solution-focused."""
            
            return base_prompt
        
        except Exception as e:
            logging.error(f"Error building inbound system prompt: {str(e)}")
            return "You are Sarah, a helpful AI assistant. The customer has called for assistance."
    
    def _analyze_customer_intent(self, customer_input: str) -> str:
        """Analyze customer input to determine their intent"""
        input_lower = customer_input.lower()
        
        # Sales indicators
        sales_keywords = [
            'interested in', 'want to buy', 'pricing', 'cost', 'quote', 'information about',
            'tell me about', 'looking for', 'need', 'considering', 'options'
        ]
        if any(keyword in input_lower for keyword in sales_keywords):
            return 'sales_inquiry'
        
        # Support indicators
        support_keywords = [
            'problem', 'issue', 'not working', 'broken', 'help with', 'technical', 'error',
            'troubleshoot', 'fix', 'support', 'how to'
        ]
        if any(keyword in input_lower for keyword in support_keywords):
            return 'support_request'
        
        # Complaint indicators
        complaint_keywords = [
            'complaint', 'unhappy', 'disappointed', 'frustrated', 'angry', 'terrible',
            'awful', 'worst', 'never again', 'refund', 'cancel'
        ]
        if any(keyword in input_lower for keyword in complaint_keywords):
            return 'complaint'
        
        return 'general_inquiry'
    
    def _analyze_known_prospect_info(self, prospect) -> List[str]:
        """Analyze what we already know about the prospect"""
        known_info = []
        
        if prospect.form_data:
            if prospect.form_data.get('budget'):
                known_info.append('budget')
            if prospect.form_data.get('timeline'):
                known_info.append('timeline')
            if prospect.form_data.get('company'):
                known_info.append('authority')
        
        if prospect.company:
            known_info.append('authority')
        
        if prospect.product_interest:
            known_info.append('need')
        
        return known_info
    
    def _get_next_qualification_question(self, prospect_context: Dict, 
                                       conversation_history: List[Dict]) -> str:
        """Determine next appropriate qualification question"""
        # Simple logic - can be enhanced based on conversation flow
        asked_about = []
        
        for exchange in conversation_history:
            if exchange.get('type') == 'agent':
                message = exchange['message'].lower()
                if 'budget' in message or 'cost' in message:
                    asked_about.append('budget')
                if 'timeline' in message or 'when' in message:
                    asked_about.append('timeline')
                if 'decision' in message or 'team' in message:
                    asked_about.append('authority')
        
        # Ask in priority order
        if 'need' not in asked_about:
            return self.generate_qualification_question('need', prospect_context, conversation_history)
        elif 'timeline' not in asked_about:
            return self.generate_qualification_question('timeline', prospect_context, conversation_history)
        elif 'budget' not in asked_about:
            return self.generate_qualification_question('budget', prospect_context, conversation_history)
        elif 'authority' not in asked_about:
            return self.generate_qualification_question('authority', prospect_context, conversation_history)
        else:
            return "Based on what you've shared, let me connect you with someone who can help you take the next step."
    
    def _format_previous_context(self, prospect_context: Dict, conversation_history: List[Dict]) -> str:
        """Format previous context for system prompt"""
        try:
            prospect = prospect_context['prospect']
            context_parts = []
            
            if prospect.source == 'form_submission':
                context_parts.append(f"Previously submitted form for {prospect.product_interest}")
            
            if prospect_context['previous_conversations'] > 0:
                last_call = prospect_context['call_history'][0] if prospect_context['call_history'] else None
                if last_call:
                    context_parts.append(f"Last call: {last_call.conversation_summary}")
            
            if prospect.company:
                context_parts.append(f"Works at: {prospect.company}")
            
            return ". ".join(context_parts) if context_parts else "No previous context available."
        
        except Exception as e:
            logging.error(f"Error formatting previous context: {str(e)}")
            return "Previous context unavailable."
    
    def _get_company_name(self, product_category: str = None) -> str:
        """Get company name from base engine"""
        try:
            template = self.base_engine.templates.get_template(product_category or 'general')
            return template.get('company_name', 'ProServices')
        except:
            return 'ProServices'