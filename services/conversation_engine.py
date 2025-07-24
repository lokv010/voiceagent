import openai
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Optional
import json

class ConversationTemplates:
    def __init__(self):
        self.templates = {
            'solar_energy': {
                'company_name': 'SolarTech Solutions',
                'opening': "Hi {name}, this is {agent_name} from SolarTech Solutions. You recently showed interest in our solar panel installation. Do you have a few minutes to discuss your energy savings goals?",
                'qualification_questions': [
                    "What's your average monthly electricity bill?",
                    "Do you own your home or rent?",
                    "Are you looking to install panels this year?",
                    "What's your main motivation - savings or environmental impact?"
                ],
                'objection_handling': {
                    'too_expensive': "I understand cost is a concern. Our financing options start at $99/month, which is often less than current electricity bills. Would you like to hear about our $0 down program?",
                    'not_sure': "That's completely normal. Would you like me to schedule a free consultation where we can assess your specific situation and potential savings?"
                },
                'target_audience': 'homeowners',
                'value_props': ['significant energy savings', 'increased home value', 'environmental benefits']
            },
            'insurance': {
                'company_name': 'SecureLife Insurance',
                'opening': "Hi {name}, this is {agent_name} from SecureLife Insurance. You inquired about our {product} coverage. Is this still a good time to discuss your insurance needs?",
                'qualification_questions': [
                    "What type of coverage amount were you considering?",
                    "Are you currently insured elsewhere?",
                    "What's your timeline for making a decision?",
                    "Do you have any health concerns I should know about?"
                ],
                'target_audience': 'individuals and families'
            },
            'software': {
                'company_name': 'TechSolutions Pro',
                'opening': "Hi {name}, this is {agent_name} from TechSolutions Pro. You requested information about our {product} software. Are you available for a quick chat about your business needs?",
                'qualification_questions': [
                    "How many employees would be using the software?",
                    "What's your current solution for this?",
                    "What's your biggest challenge with your current setup?",
                    "When are you looking to implement a new solution?"
                ],
                'target_audience': 'business owners and IT professionals'
            },
            'marketing': {
                'company_name': 'GrowthMax Marketing',
                'opening': "Hi {name}, this is {agent_name} from GrowthMax Marketing. You expressed interest in our marketing services. Do you have a moment to discuss how we can help grow your business?",
                'target_audience': 'business owners and entrepreneurs'
            },
            'finance': {
                'company_name': 'FinanceFirst',
                'opening': "Hi {name}, this is {agent_name} from FinanceFirst. You inquired about our financial services. Is now a good time to discuss your financial goals?",
                'target_audience': 'individuals seeking financial services'
            },
            'general': {
                'company_name': 'ProServices',
                'opening': "Hi {name}, this is {agent_name} from ProServices. You recently showed interest in our services. Do you have a few minutes to discuss how we can help you?",
                'target_audience': 'potential customers'
            }
        }
    
    def get_template(self, product_category: str) -> Dict:
        return self.templates.get(product_category, self.templates['general'])

class UnifiedConversationEngine:
    def __init__(self, openai_api_key: str):
        """Initialize conversation engine"""
        self.client = openai.OpenAI(api_key=openai_api_key)
        self.templates = ConversationTemplates()
        
        # Conversation state management
        self.conversation_states = {}
        
        logging.info("Unified Conversation Engine initialized")
    
    def determine_conversation_strategy(self, prospect_context: Dict) -> str:
        """Determine conversation approach based on prospect data"""
        prospect = prospect_context['prospect']
        is_warm_lead = prospect_context['is_warm_lead']
        previous_conversations = prospect_context['previous_conversations']
        
        if is_warm_lead and previous_conversations == 0:
            return 'form_follow_up'
        elif is_warm_lead and previous_conversations > 0:
            return 'warm_follow_up'
        elif not is_warm_lead and previous_conversations == 0:
            return 'cold_outreach'
        else:
            return 'cold_follow_up'
    
    def generate_opening_message(self, prospect_context: Dict) -> str:
        """Generate context-aware opening message"""
        prospect = prospect_context['prospect']
        strategy = self.determine_conversation_strategy(prospect_context)
        
        if strategy == 'form_follow_up':
            return self._get_form_follow_up_opening(prospect)
        elif strategy == 'warm_follow_up':
            return self._get_warm_follow_up_opening(prospect, prospect_context)
        elif strategy == 'cold_outreach':
            return self._get_cold_outreach_opening(prospect)
        else:  # cold_follow_up
            return self._get_cold_follow_up_opening(prospect, prospect_context)
    
    def _get_form_follow_up_opening(self, prospect) -> str:
        """Personalized opening for form submissions"""
        template = self.templates.get_template(prospect.product_category)
        
        # Calculate time since form submission
        time_ref = "recently"
        if prospect.form_submitted_at:
            time_diff = datetime.utcnow() - prospect.form_submitted_at
            hours_ago = int(time_diff.total_seconds() / 3600)
            
            if hours_ago < 2:
                time_ref = "just submitted"
            elif hours_ago < 24:
                time_ref = f"{hours_ago} hours ago"
            else:
                time_ref = f"{int(time_diff.days)} days ago"
        
        # Extract specific form interests
        form_interests = ""
        if prospect.form_data:
            if 'budget' in prospect.form_data:
                form_interests += f" with a budget of {prospect.form_data['budget']}"
            if 'timeline' in prospect.form_data:
                form_interests += f" looking to move forward {prospect.form_data['timeline']}"
        
        return template['opening'].format(
            name=prospect.name or "there",
            agent_name="Sarah",
            product=prospect.product_interest or "our services"
        ) + f" I see you {time_ref} requested information{form_interests}."
    
    def _get_cold_outreach_opening(self, prospect) -> str:
        """Professional opening for cold leads"""
        template = self.templates.get_template(prospect.product_category)
        
        company_intro = ""
        if prospect.company:
            company_intro = f"I noticed you work at {prospect.company}. "
        
        opening = template['opening'].format(
            name=prospect.name or "there",
            agent_name="Sarah",
            product=prospect.product_interest or "our services"
        )
        
        return f"{opening} {company_intro}I'm reaching out because we help {template.get('target_audience', 'businesses')} with {prospect.product_interest or 'their challenges'}."
    
    def _get_warm_follow_up_opening(self, prospect, prospect_context) -> str:
        """Opening for returning warm leads"""
        last_call = prospect_context['call_history'][0] if prospect_context['call_history'] else None
        
        if last_call and last_call.next_action == 'callback_scheduled':
            return f"Hi {prospect.name}, this is Sarah calling back as promised. Do you have a few minutes to continue our conversation about {prospect.product_interest}?"
        else:
            return f"Hi {prospect.name}, this is Sarah from {self._get_company_name(prospect.product_category)}. I'm following up on our previous conversation. Is this a good time to chat?"
    
    def _get_cold_follow_up_opening(self, prospect, prospect_context) -> str:
        """Opening for cold lead follow-up"""
        return f"Hi {prospect.name}, this is Sarah from {self._get_company_name(prospect.product_category)}. I spoke with you previously about {prospect.product_interest}. Do you have a moment for a quick follow-up?"
    
    def generate_adaptive_response(self, customer_input: str, prospect_context: Dict, 
                                 conversation_history: List[Dict]) -> str:
        """Generate responses that adapt based on all available context"""
        prospect = prospect_context['prospect']
        strategy = self.determine_conversation_strategy(prospect_context)
        
        # Build comprehensive context for AI
        system_prompt = self._build_system_prompt(prospect, strategy, conversation_history)
        
        # Prepare conversation history for context
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add recent conversation history (last 6 exchanges)
        for exchange in conversation_history[-6:]:
            if exchange.get('type') == 'agent':
                messages.append({"role": "assistant", "content": exchange['message']})
            elif exchange.get('type') == 'customer':
                messages.append({"role": "user", "content": exchange['message']})
        
        # Add current customer input
        messages.append({"role": "user", "content": f"Customer just said: {customer_input}"})
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=messages,
                max_tokens=200,
                temperature=0.7,
                presence_penalty=0.1,
                frequency_penalty=0.1
            )
            
            ai_response = response.choices[0].message.content.strip()
            
            # Post-process response
            ai_response = self._post_process_response(ai_response, prospect, customer_input)
            
            return ai_response
            
        except Exception as e:
            logging.error(f"Error generating AI response: {str(e)}")
            # Fallback response
            return f"I understand, {prospect.name}. Let me help you with that. Could you tell me more about what you're looking for?"
    
    def _build_system_prompt(self, prospect, strategy: str, conversation_history: List[Dict]) -> str:
        """Build context-aware system prompt"""
        template = self.templates.get_template(prospect.product_category)
        
        base_prompt = f"""You are Sarah, a professional sales representative for {template['company_name']}.

PROSPECT CONTEXT:
- Name: {prospect.name or 'Customer'}
- Source: {prospect.source}
- Product Interest: {prospect.product_interest or 'general services'}
- Company: {prospect.company or 'Not specified'}
- Current Qualification Score: {prospect.qualification_score}/100
- Previous Conversations: {len(conversation_history)}
- Call Strategy: {strategy}

CONVERSATION GOALS:
1. Qualify their interest level and specific needs
2. Understand their timeline and budget constraints
3. Identify decision-making process and authority
4. Schedule appropriate next steps (demo, consultation, or follow-up)

CONVERSATION GUIDELINES:
- Be natural, friendly, and professional
- Ask ONE focused question at a time
- Listen actively and adapt based on their responses
- If they show strong interest, move toward scheduling next steps
- If they're not interested, politely accept and end the call
- Keep responses under 40 words when possible
- Use their name occasionally but not excessively

HANDLING OBJECTIONS:
- Price concerns: Focus on value and ROI, mention financing options
- Time concerns: Respect their time, offer to call back
- Authority concerns: Ask about decision-making process
- Need concerns: Dig deeper into their specific challenges

CALL ENDING CONDITIONS:
- If they say "not interested", "remove me", "stop calling" -> End politely
- If conversation reaches natural conclusion -> Summarize next steps
- If they're qualified -> Schedule demo/consultation
- If they need time -> Schedule follow-up call
"""

        # Add strategy-specific context
        if strategy == 'form_follow_up':
            base_prompt += f"""
STRATEGY NOTES:
- This is a WARM LEAD who submitted a form
- Form data: {prospect.form_data}
- They've already shown interest, so focus on qualification
- Reference their specific form responses when relevant
"""
        elif strategy == 'cold_outreach':
            base_prompt += """
STRATEGY NOTES:
- This is a COLD LEAD with no previous engagement
- Be respectful of their time and ask permission to continue
- Establish relevance and value quickly
- Expect more resistance and objections
- Focus on building rapport first
"""
        
        return base_prompt
    
    def _post_process_response(self, response: str, prospect, customer_input: str) -> str:
        """Post-process AI response for quality and compliance"""
        # Ensure response isn't too long
        if len(response) > 300:
            sentences = response.split('. ')
            response = '. '.join(sentences[:2]) + '.'
        
        # Add name if not present and appropriate
        if prospect.name and prospect.name.lower() not in response.lower():
            # Add name at beginning if response is a question
            if response.endswith('?') and len(response) < 100:
                response = f"{prospect.name}, {response.lower()}"
        
        # Ensure polite endings for negative responses
        negative_indicators = ['not interested', 'busy', 'no thanks', 'remove me']
        if any(indicator in customer_input.lower() for indicator in negative_indicators):
            if 'thank you' not in response.lower():
                response += " Thank you for your time."
        
        return response
    
    def _get_company_name(self, product_category: str) -> str:
        """Get company name for product category"""
        template = self.templates.get_template(product_category)
        return template['company_name']
    
    def should_end_call(self, customer_input: str, conversation_turn: int, strategy: str) -> bool:
        """Determine if call should end"""
        # Hard stop phrases
        end_phrases = [
            'not interested', 'remove me', 'stop calling', 'don\'t call',
            'take me off', 'not a good time', 'busy right now', 'goodbye', 'bye'
        ]
        
        customer_lower = customer_input.lower()
        
        # Check for explicit end requests
        if any(phrase in customer_lower for phrase in end_phrases):
            return True
        
        # End after maximum turns
        max_turns = 12 if strategy in ['form_follow_up', 'warm_follow_up'] else 8
        if conversation_turn >= max_turns:
            return True
        
        # End if customer is unresponsive (very short responses repeatedly)
        if len(customer_input.strip()) < 3:
            return True
        
        return False