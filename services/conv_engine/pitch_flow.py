"""
PitchAdaptationEngine.py - Specialized pitch flow handling classes
"""

import json
import random
import re
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import logging
from dataclasses import asdict

from .flow_models import (
    CustomerContext, CustomerReadinessLevel, PitchContent, PitchOutcome,
    ConversationState, FlowType, FlowStage
)

from .conv_interfaces import IFlowEngine


class PitchReadinessAssessor:
    """Assesses customer readiness for pitch delivery"""
    
    def __init__(self):
        self.readiness_criteria = self._init_readiness_criteria()
        self.logger = logging.getLogger(__name__)
    
    def evaluate_pitch_timing(
        self, 
        conversation_context: Dict[str, Any], 
        customer_readiness_signals: List[str]
    ) -> Tuple[bool, float, str]:
        """Evaluate if timing is appropriate for pitch delivery"""
        
        # Analyze conversation duration
        start_time = conversation_context.get("start_time", datetime.now())
        conversation_duration = (datetime.now() - start_time).total_seconds() / 60
        
        # Timing factors
        timing_score = 0.0
        timing_reasons = []
        
        # Minimum conversation time (avoid rushing)
        if conversation_duration >= 3:  # At least 3 minutes
            timing_score += 0.3
            timing_reasons.append("Sufficient conversation time established")
        else:
            timing_reasons.append("Conversation too brief for pitch")
        
        # Discovery completion check
        discovery_complete = conversation_context.get("discovery_phase_complete", False)
        if discovery_complete:
            timing_score += 0.4
            timing_reasons.append("Discovery phase completed")
        else:
            timing_reasons.append("Discovery phase incomplete")
        
        # Customer engagement level
        engagement_level = conversation_context.get("engagement_level", 0.5)
        if engagement_level > 0.6:
            timing_score += 0.3
            timing_reasons.append("High customer engagement detected")
        elif engagement_level < 0.3:
            timing_reasons.append("Low customer engagement")
        
        is_ready = timing_score >= 0.6
        reason = "; ".join(timing_reasons)
        
        return is_ready, timing_score, reason
    
    def assess_customer_pitch_receptiveness(
        self, 
        engagement_level: float, 
        conversation_history: List[Dict[str, Any]]
    ) -> CustomerReadinessLevel:
        """Assess customer's receptiveness to receiving a pitch"""
        
        # Analyze recent conversation patterns
        recent_interactions = conversation_history[-5:] if len(conversation_history) >= 5 else conversation_history
        
        # Positive indicators
        positive_signals = 0
        negative_signals = 0
        
        for interaction in recent_interactions:
            content = interaction.get("content", "").lower()
            
            # Positive signals
            positive_keywords = [
                "interested", "tell me more", "sounds good", "that's helpful",
                "how does", "what about", "show me", "benefits", "features"
            ]
            negative_keywords = [
                "not interested", "too expensive", "not now", "busy", "maybe later",
                "not sure", "concerns", "worried", "but", "however"
            ]
            
            for keyword in positive_keywords:
                if keyword in content:
                    positive_signals += 1
            
            for keyword in negative_keywords:
                if keyword in content:
                    negative_signals += 1
        
        # Calculate receptiveness score
        signal_ratio = positive_signals / max(1, positive_signals + negative_signals)
        combined_score = (engagement_level * 0.6) + (signal_ratio * 0.4)
        
        # Determine readiness level
        if combined_score >= 0.8:
            return CustomerReadinessLevel.HIGHLY_ENGAGED
        elif combined_score >= 0.6:
            return CustomerReadinessLevel.READY
        elif combined_score >= 0.4:
            return CustomerReadinessLevel.WARMING_UP
        elif negative_signals > positive_signals * 2:
            return CustomerReadinessLevel.RESISTANT
        else:
            return CustomerReadinessLevel.NOT_READY
    
    def identify_pitch_focus_areas(
        self, 
        customer_needs: List[str], 
        pain_points_discovered: List[str]
    ) -> List[Dict[str, Any]]:
        """Identify key areas to focus on in the pitch"""
        
        focus_areas = []
        
        # Map pain points to solution areas
        pain_point_mapping = {
            "cost": {"area": "ROI and Cost Savings", "priority": 0.9},
            "time": {"area": "Efficiency and Time Savings", "priority": 0.8},
            "complexity": {"area": "Simplification and Ease of Use", "priority": 0.7},
            "scalability": {"area": "Growth and Scalability", "priority": 0.8},
            "integration": {"area": "Seamless Integration", "priority": 0.7},
            "security": {"area": "Security and Compliance", "priority": 0.9},
            "performance": {"area": "Performance and Reliability", "priority": 0.8}
        }
        
        # Analyze pain points
        for pain_point in pain_points_discovered:
            pain_lower = pain_point.lower()
            for key, mapping in pain_point_mapping.items():
                if key in pain_lower:
                    focus_area = {
                        "area": mapping["area"],
                        "priority": mapping["priority"],
                        "pain_point": pain_point,
                        "focus_type": "pain_resolution"
                    }
                    focus_areas.append(focus_area)
        
        # Analyze customer needs
        need_mapping = {
            "growth": {"area": "Growth Enablement", "priority": 0.8},
            "automation": {"area": "Process Automation", "priority": 0.7},
            "analytics": {"area": "Data and Analytics", "priority": 0.6},
            "collaboration": {"area": "Team Collaboration", "priority": 0.6},
            "compliance": {"area": "Regulatory Compliance", "priority": 0.9}
        }
        
        for need in customer_needs:
            need_lower = need.lower()
            for key, mapping in need_mapping.items():
                if key in need_lower:
                    focus_area = {
                        "area": mapping["area"],
                        "priority": mapping["priority"],
                        "customer_need": need,
                        "focus_type": "need_fulfillment"
                    }
                    focus_areas.append(focus_area)
        
        # Sort by priority and return top focus areas
        focus_areas.sort(key=lambda x: x["priority"], reverse=True)
        return focus_areas[:5]  # Top 5 focus areas
    
    def determine_pitch_depth_level(
        self, 
        customer_sophistication: str, 
        technical_background: Optional[str]
    ) -> str:
        """Determine appropriate level of detail for the pitch"""
        
        sophistication_levels = {
            "beginner": 1,
            "intermediate": 2,
            "advanced": 3,
            "expert": 4
        }
        
        technical_levels = {
            "non_technical": 1,
            "basic_technical": 2,
            "technical": 3,
            "highly_technical": 4
        }
        
        soph_score = sophistication_levels.get(customer_sophistication, 2)
        tech_score = technical_levels.get(technical_background or "basic_technical", 2)
        
        avg_score = (soph_score + tech_score) / 2
        
        if avg_score >= 3.5:
            return "detailed_technical"
        elif avg_score >= 2.5:
            return "moderate_detail"
        elif avg_score >= 1.5:
            return "high_level"
        else:
            return "conceptual"
    
    def validate_pitch_prerequisites(
        self, 
        required_information: List[str], 
        conversation_progress: Dict[str, Any]
    ) -> Tuple[bool, List[str]]:
        """Validate that all prerequisites for pitch are met"""
        
        missing_prerequisites = []
        discovered_info = conversation_progress.get("discovered_information", [])
        
        for requirement in required_information:
            if requirement not in discovered_info:
                missing_prerequisites.append(requirement)
        
        # Check for critical prerequisites
        critical_requirements = [
            "customer_role", "company_size", "current_solution", "primary_pain_point"
        ]
        
        missing_critical = [req for req in critical_requirements if req in missing_prerequisites]
        
        # Additional validation checks
        if not conversation_progress.get("rapport_established", False):
            missing_prerequisites.append("rapport_establishment")
        
        if conversation_progress.get("customer_engagement_level", 0) < 0.4:
            missing_prerequisites.append("sufficient_engagement")
        
        is_valid = len(missing_critical) == 0 and len(missing_prerequisites) <= 2
        
        return is_valid, missing_prerequisites
    
    def _init_readiness_criteria(self) -> Dict[str, Dict[str, Any]]:
        """Initialize criteria for assessing pitch readiness"""
        return {
            "timing": {
                "min_conversation_duration": 180,  # 3 minutes
                "max_conversation_duration": 1800,  # 30 minutes
                "optimal_range": (300, 900)  # 5-15 minutes
            },
            "engagement": {
                "min_engagement_level": 0.4,
                "optimal_engagement_level": 0.7
            },
            "discovery": {
                "min_pain_points_discovered": 1,
                "min_needs_identified": 1,
                "required_context_elements": ["role", "company_context"]
            }
        }


class PitchCustomizer:
    """Customizes pitch content based on customer context"""
    
    def __init__(self):
        self.value_prop_templates = self._init_value_prop_templates()
        self.proof_point_database = self._init_proof_point_database()
        self.logger = logging.getLogger(__name__)

        # ADDED: Conversation flow support
        self.conversation_templates: Dict[str, Dict] = {}
        self.template_cache: Dict[str, Dict] = {}
    
    def customize_value_proposition(
        self, 
        customer_profile: CustomerContext, 
        discovered_needs: List[str], 
        competitive_landscape: List[str]
    ) -> str:
        """Customize value proposition for specific customer"""
        
        # Select base template based on industry
        industry = customer_profile.industry or "general"
        base_template = self.value_prop_templates.get(industry, self.value_prop_templates["general"])
        
        # Customize based on discovered needs
        need_customizations = {
            "cost_reduction": "significantly reduce operational costs while",
            "efficiency": "streamline operations and dramatically improve efficiency while",
            "growth": "accelerate growth and scale operations while",
            "security": "enhance security and compliance while",
            "integration": "seamlessly integrate with existing systems while"
        }
        
        customization_phrases = []
        for need in discovered_needs:
            need_lower = need.lower()
            for key, phrase in need_customizations.items():
                if key in need_lower:
                    customization_phrases.append(phrase)
        
        # Incorporate competitive differentiation
        competitive_elements = self._generate_competitive_elements(competitive_landscape)
        
        # Build customized value proposition
        value_prop = base_template["opening"]
        
        if customization_phrases:
            value_prop += f" Our solution helps you {' and '.join(customization_phrases[:2])} "
        
        value_prop += base_template["core_value"]
        
        if competitive_elements:
            value_prop += f" {competitive_elements} "
        
        value_prop += base_template["closing"]
        
        return value_prop
    
    def select_relevant_proof_points(
        self, 
        customer_industry: Optional[str], 
        use_case_similarity: float, 
        credibility_requirements: List[str]
    ) -> List[Dict[str, Any]]:
        """Select most relevant proof points for the customer"""
        
        industry = customer_industry or "general"
        available_proof_points = self.proof_point_database.get(industry, [])
        
        # Score proof points based on relevance
        scored_proof_points = []
        
        for proof_point in available_proof_points:
            relevance_score = 0.0
            
            # Industry relevance
            if proof_point.get("industry") == industry:
                relevance_score += 0.4
            
            # Use case similarity
            relevance_score += use_case_similarity * 0.3
            
            # Credibility alignment
            for req in credibility_requirements:
                if req in proof_point.get("credibility_types", []):
                    relevance_score += 0.1
            
            # Recency boost
            if proof_point.get("recency_months", 12) <= 6:
                relevance_score += 0.1
            
            scored_proof_points.append((proof_point, relevance_score))
        
        # Sort and return top proof points
        scored_proof_points.sort(key=lambda x: x[1], reverse=True)
        return [pp[0] for pp in scored_proof_points[:5]]
    

    
    def adapt_pitch_structure(
        self, 
        conversation_flow: Dict[str, Any], 
        customer_preferences: Dict[str, Any], 
        time_constraints: Optional[int]
    ) -> Dict[str, Any]:
        """Adapt pitch structure based on context"""
        
        # Base structure
        structure = {
            "introduction": {"duration": 30, "priority": 1},
            "problem_identification": {"duration": 60, "priority": 2},
            "solution_overview": {"duration": 90, "priority": 1},
            "benefits_and_value": {"duration": 120, "priority": 1},
            "proof_points": {"duration": 90, "priority": 2},
            "next_steps": {"duration": 30, "priority": 1}
        }
        
        # Adjust for time constraints
        if time_constraints:
            total_base_duration = sum(section["duration"] for section in structure.values())
            
            if total_base_duration > time_constraints:
                # Prioritize sections and compress
                compression_factor = time_constraints / total_base_duration
                
                for section_name, section in structure.items():
                    if section["priority"] == 1:
                        # Keep priority 1 sections with minimal compression
                        section["duration"] = int(section["duration"] * max(0.8, compression_factor))
                    else:
                        # Compress priority 2 sections more aggressively
                        section["duration"] = int(section["duration"] * compression_factor)
        
        # Adapt based on customer preferences
        pref_detail_level = customer_preferences.get("detail_level", "medium")
        if pref_detail_level == "high":
            structure["solution_overview"]["duration"] *= 1.3
            structure["proof_points"]["duration"] *= 1.5
        elif pref_detail_level == "low":
            structure["solution_overview"]["duration"] *= 0.7
            structure["proof_points"]["duration"] *= 0.5
        
        # Adapt based on conversation flow
        if conversation_flow.get("customer_initiated_questions", 0) > 3:
            # Customer is engaged, allow for more interaction
            structure["interaction_buffer"] = {"duration": 60, "priority": 2}
        
        return structure
    
    def personalize_solution_positioning(
        self, 
        customer_goals: List[str], 
        current_challenges: List[str], 
        success_metrics: List[str]
    ) -> Dict[str, str]:
        """Personalize how the solution is positioned"""
        
        positioning = {
            "goal_alignment": "",
            "challenge_resolution": "",
            "success_measurement": ""
        }
        
        # Align with customer goals
        goal_mappings = {
            "growth": "accelerate your growth trajectory",
            "efficiency": "optimize your operational efficiency",
            "cost": "reduce costs while maintaining quality",
            "innovation": "drive innovation in your organization",
            "competitive": "maintain competitive advantage"
        }
        
        aligned_goals = []
        for goal in customer_goals:
            goal_lower = goal.lower()
            for key, phrase in goal_mappings.items():
                if key in goal_lower:
                    aligned_goals.append(phrase)
        
        if aligned_goals:
            positioning["goal_alignment"] = f"Our solution directly supports your objective to {', '.join(aligned_goals[:2])}"
        
        # Address current challenges
        challenge_solutions = {
            "manual": "automate manual processes",
            "slow": "accelerate operations",
            "expensive": "reduce operational costs",
            "complex": "simplify complex workflows",
            "unreliable": "ensure reliable performance"
        }
        
        solutions = []
        for challenge in current_challenges:
            challenge_lower = challenge.lower()
            for key, solution in challenge_solutions.items():
                if key in challenge_lower:
                    solutions.append(solution)
        
        if solutions:
            positioning["challenge_resolution"] = f"We specifically address your challenges by helping you {', '.join(solutions[:2])}"
        
        # Connect to success metrics
        if success_metrics:
            positioning["success_measurement"] = f"Success will be measured through {', '.join(success_metrics[:3])}, which our solution directly impacts"
        
        return positioning
    
    def adjust_competitive_positioning(
        self, 
        mentioned_competitors: List[str], 
        customer_preferences: Dict[str, Any], 
        differentiation_opportunities: List[str]
    ) -> Dict[str, Any]:
        """Adjust positioning relative to competitors"""
        
        competitive_strategy = {
            "approach": "collaborative",  # collaborative, defensive, or aggressive
            "key_differentiators": [],
            "positioning_statements": []
        }
        
        # Determine approach based on customer preferences
        if customer_preferences.get("comparison_style") == "direct":
            competitive_strategy["approach"] = "direct_comparison"
        elif len(mentioned_competitors) > 0:
            competitive_strategy["approach"] = "differentiation"
        
        # Identify key differentiators
        differentiator_mapping = {
            "ease_of_use": "Superior user experience and ease of implementation",
            "integration": "Seamless integration capabilities",
            "support": "Exceptional customer support and service",
            "innovation": "Cutting-edge technology and continuous innovation",
            "cost": "Better total cost of ownership",
            "security": "Advanced security and compliance features",
            "scalability": "Superior scalability and performance"
        }
        
        for opportunity in differentiation_opportunities:
            opp_lower = opportunity.lower()
            for key, statement in differentiator_mapping.items():
                if key in opp_lower:
                    competitive_strategy["key_differentiators"].append(statement)
        
        # Generate positioning statements
        if mentioned_competitors:
            competitive_strategy["positioning_statements"].append(
                "While other solutions in the market focus on specific features, our comprehensive approach ensures..."
            )
        
        for differentiator in competitive_strategy["key_differentiators"][:3]:
            competitive_strategy["positioning_statements"].append(
                f"What sets us apart is our {differentiator.lower()}"
            )
        
        return competitive_strategy
    
    def _init_value_prop_templates(self) -> Dict[str, Dict[str, str]]:
        """Initialize value proposition templates by industry"""
        return {
            "technology": {
                "opening": "In today's rapidly evolving tech landscape,",
                "core_value": "delivering scalable, secure solutions that accelerate innovation",
                "closing": "enabling you to focus on what matters most - growing your business."
            },
            "healthcare": {
                "opening": "Healthcare organizations face increasing pressure to",
                "core_value": "improve patient outcomes while reducing costs and ensuring compliance",
                "closing": "all while maintaining the highest standards of care."
            },
            "financial": {
                "opening": "Financial institutions require solutions that",
                "core_value": "enhance operational efficiency while meeting strict regulatory requirements",
                "closing": "ensuring both growth and compliance in a competitive market."
            },
            "general": {
                "opening": "Modern businesses need solutions that",
                "core_value": "drive efficiency, reduce costs, and enable sustainable growth",
                "closing": "positioning your organization for long-term success."
            }
        }
    
    def _init_proof_point_database(self) -> Dict[str, List[Dict[str, Any]]]:
        """Initialize proof points database"""
        return {
            "technology": [
                {
                    "type": "case_study",
                    "industry": "technology",
                    "result": "40% reduction in deployment time",
                    "credibility_types": ["performance", "efficiency"],
                    "recency_months": 3
                },
                {
                    "type": "testimonial",
                    "industry": "technology",
                    "result": "Seamless integration with existing infrastructure",
                    "credibility_types": ["integration", "ease_of_use"],
                    "recency_months": 2
                }
            ],
            "general": [
                {
                    "type": "statistic",
                    "industry": "general",
                    "result": "Average ROI of 300% within first year",
                    "credibility_types": ["roi", "financial"],
                    "recency_months": 1
                }
            ]
        }
    
    def _generate_competitive_elements(self, competitive_landscape: List[str]) -> str:
        """Generate competitive differentiation elements"""
        if not competitive_landscape:
            return ""
        
        competitive_phrases = [
            "Unlike other solutions that require extensive customization,",
            "While competitors focus on features, we prioritize outcomes,",
            "In contrast to complex alternatives,"
        ]
        
        # Select appropriate phrase based on competitive context
        return competitive_phrases[0]  # Simplified selection

    # ADDED: New conversation flow methods
    
    def load_conversation_template(self, template_path: str, flow_id: str) -> Dict[str, Any]:
        """Load conversation flow template from JSON file"""
        try:
            if flow_id in self.template_cache:
                return self.template_cache[flow_id]
            
            with open(template_path, 'r', encoding='utf-8') as file:
                template_data = json.load(file)
            
            if "conversation_flow" not in template_data:
                raise ValueError("Invalid template format: missing 'conversation_flow' key")
            
            conversation_flow = template_data["conversation_flow"]
            
            # Validate template structure
            self._validate_template(conversation_flow)
            
            # Cache the template
            self.template_cache[flow_id] = conversation_flow
            self.conversation_templates[flow_id] = conversation_flow
            
            self.logger.info(f"Loaded conversation template: {flow_id}")
            return conversation_flow
            
        except Exception as e:
            self.logger.error(f"Failed to load conversation template: {e}")
            return self._get_fallback_template()
    def build_conversation_flow(self, flow_id: str, customer_context: CustomerContext, 
                              business_context: Dict[str, Any]) -> Dict[str, Any]:
        """Build customized conversation flow for specific customer"""
        
        if flow_id not in self.conversation_templates:
            self.logger.error(f"Template not found: {flow_id}")
            return self._get_fallback_template()
        
        template = self.conversation_templates[flow_id].copy()
        
        # STEP 1: Customize template variables
        customized_template = self._customize_template_variables(
            template, customer_context, business_context
        )
        
        # STEP 2: Select appropriate message variants
        customized_template = self._select_message_variants(
            customized_template, customer_context
        )
        
        # STEP 3: Adapt conversation flow based on context
        customized_template = self._adapt_conversation_structure(
            customized_template, customer_context, business_context
        )
        
        # STEP 4: Add conversation metadata
        customized_template["customization_metadata"] = {
            "customized_for": customer_context.customer_id,
            "customization_time": datetime.now(),
            "business_context": business_context.get("industry", "general"),
            "customer_profile": {
                "industry": customer_context.industry,
                "company_size": customer_context.company_size,
                "technical_background": customer_context.technical_background
            }
        }
        
        return customized_template
    
    def customize_script_variables(self, template: Dict[str, Any], 
                                 customer_context: CustomerContext,
                                 business_context: Dict[str, Any]) -> Dict[str, str]:
        """Generate variable substitutions for conversation template"""
        
        variables = {
            "customer_name": customer_context.customer_id.split('_')[0].title(),  # Extract name
            "business_name": business_context.get("business_name", "Our Business"),
            "currency_symbol": business_context.get("currency", "₹"),
            "customer_location": customer_context.preferences.get("location", "your area")
        }
        
        # Industry-specific customizations
        if customer_context.industry:
            variables.update(self._get_industry_variables(customer_context.industry, business_context))
        
        # Investment range customization
        investment_config = business_context.get("investment_config", {})
        if customer_context.company_size:
            investment_range = self._calculate_investment_range(
                customer_context.company_size, investment_config
            )
            variables.update(investment_range)
        else:
            variables.update({
                "investment_min": "10 lakhs",
                "investment_max": "40 lakhs"
            })
        
        # Location-specific variables
        if "location" in customer_context.preferences:
            variables["location"] = customer_context.preferences["location"]
        else:
            variables["location"] = "your location"
        
        return variables
    
    def generate_step_sequence(self, template: Dict[str, Any], 
                             customer_context: CustomerContext) -> List[Dict[str, Any]]:
        """Generate optimized step sequence based on customer context"""
        
        steps = template.get("steps", [])
        if not steps:
            return []
        
        # STEP 1: Filter steps based on customer context
        relevant_steps = self._filter_relevant_steps(steps, customer_context)
        
        # STEP 2: Reorder steps based on customer profile
        optimized_steps = self._optimize_step_order(relevant_steps, customer_context)
        
        # STEP 3: Add conditional logic
        enhanced_steps = self._add_conditional_logic(optimized_steps, customer_context)
        
        # STEP 4: Add step metadata
        for i, step in enumerate(enhanced_steps):
            step["execution_metadata"] = {
                "sequence_position": i + 1,
                "estimated_duration": self._estimate_step_duration(step),
                "skip_conditions": self._get_skip_conditions(step, customer_context),
                "personalization_level": self._calculate_personalization_level(step, customer_context)
            }
        
        return enhanced_steps
    
    # ADDED: Private helper methods for pitch based conversation JSON flows
    
    def _validate_template(self, template: Dict[str, Any]) -> None:
        """Validate conversation template structure"""
        required_fields = ["flow_id", "flow_name", "steps"]
        
        for field in required_fields:
            if field not in template:
                raise ValueError(f"Template missing required field: {field}")
        
        if not isinstance(template["steps"], list) or len(template["steps"]) == 0:
            raise ValueError("Template must have at least one step")
        
        # Validate each step
        for i, step in enumerate(template["steps"]):
            step_required = ["step_id", "step_number", "message_variants"]
            for field in step_required:
                if field not in step:
                    raise ValueError(f"Step {i} missing required field: {field}")
    
    def _customize_template_variables(self, template: Dict[str, Any], 
                                    customer_context: CustomerContext,
                                    business_context: Dict[str, Any]) -> Dict[str, Any]:
        """Replace template variables with customer-specific values"""
        
        variables = self.customize_script_variables(template, customer_context, business_context)
        
        # Convert template to string, replace variables, convert back
        template_str = json.dumps(template)
        
        for var_name, var_value in variables.items():
            placeholder = "{{" + var_name + "}}"
            template_str = template_str.replace(placeholder, str(var_value))
        
        try:
            customized_template = json.loads(template_str)
            return customized_template
        except json.JSONDecodeError:
            self.logger.error("Failed to parse customized template")
            return template
    
    def _select_message_variants(self, template: Dict[str, Any], 
                               customer_context: CustomerContext) -> Dict[str, Any]:
        """Select appropriate message variants based on customer context"""
        
        for step in template.get("steps", []):
            if "message_variants" in step and len(step["message_variants"]) > 1:
                # Select variant based on customer preferences
                variant_index = self._choose_variant_index(step, customer_context)
                step["selected_message"] = step["message_variants"][variant_index]
                step["selected_variant_index"] = variant_index
            elif "message_variants" in step:
                step["selected_message"] = step["message_variants"][0]
                step["selected_variant_index"] = 0
        
        return template
    
    def _adapt_conversation_structure(self, template: Dict[str, Any],
                                    customer_context: CustomerContext,
                                    business_context: Dict[str, Any]) -> Dict[str, Any]:
        """Adapt conversation structure based on context"""
        
        # Skip steps based on customer context
        if customer_context.technical_background == "non_technical":
            # Skip highly technical questions
            template["steps"] = [step for step in template["steps"] 
                              if not step.get("requires_technical_knowledge", False)]
        
        # Adjust investment discussion based on company size
        if customer_context.company_size == "enterprise":
            for step in template["steps"]:
                if step["step_id"] == "investment_comfort":
                    step["message_variants"] = [msg.replace("comfortable", "aligned with your budget") 
                                              for msg in step["message_variants"]]
        
        # Add industry-specific steps
        industry_steps = self._get_industry_specific_steps(customer_context.industry)
        if industry_steps:
            # Insert after step 3 (investment)
            insertion_point = 3
            for i, industry_step in enumerate(industry_steps):
                template["steps"].insert(insertion_point + i, industry_step)
        
        return template
    
    def _filter_relevant_steps(self, steps: List[Dict[str, Any]], 
                             customer_context: CustomerContext) -> List[Dict[str, Any]]:
        """Filter steps based on customer relevance"""
        
        relevant_steps = []
        
        for step in steps:
            # Always include required steps
            if step.get("required", False):
                relevant_steps.append(step)
                continue
            
            # Include steps based on customer context
            if self._is_step_relevant(step, customer_context):
                relevant_steps.append(step)
        
        return relevant_steps
    
    def _optimize_step_order(self, steps: List[Dict[str, Any]], 
                           customer_context: CustomerContext) -> List[Dict[str, Any]]:
        """Optimize step order based on customer profile"""
        
        # For time-sensitive customers, prioritize key qualification questions
        if customer_context.preferences.get("urgency") == "high":
            # Move investment and timeline questions earlier
            priority_steps = ["investment_comfort", "timeline"]
            
            high_priority = []
            normal_priority = []
            
            for step in steps:
                if step["step_id"] in priority_steps:
                    high_priority.append(step)
                else:
                    normal_priority.append(step)
            
            # Keep greeting first, then high priority, then normal
            if normal_priority and normal_priority[0]["step_id"] == "greeting_consent":
                greeting = normal_priority.pop(0)
                return [greeting] + high_priority + normal_priority
            else:
                return high_priority + normal_priority
        
        # Default order for normal flow
        return sorted(steps, key=lambda x: x.get("step_number", 999))
    
    def _add_conditional_logic(self, steps: List[Dict[str, Any]], 
                             customer_context: CustomerContext) -> List[Dict[str, Any]]:
        """Add conditional logic to steps"""
        
        for step in steps:
            # Add skip conditions based on customer context
            skip_conditions = []
            
            if step["step_id"] == "experience" and customer_context.previous_interactions:
                # Skip if we already know their experience
                for interaction in customer_context.previous_interactions:
                    if "business_experience" in interaction:
                        skip_conditions.append("experience_already_known")
            
            if step["step_id"] == "location" and customer_context.preferences.get("location"):
                # Modify question if we already know location
                step["context_aware"] = True
                step["known_location"] = customer_context.preferences["location"]
            
            step["skip_conditions"] = skip_conditions
        
        return steps
    
    def _choose_variant_index(self, step: Dict[str, Any], 
                            customer_context: CustomerContext) -> int:
        """Choose appropriate message variant index"""
        
        variants = step["message_variants"]
        
        # Choose based on customer communication style
        communication_style = customer_context.preferences.get("communication_style", "professional")
        
        if communication_style == "casual":
            # Prefer variants with emojis and casual language
            for i, variant in enumerate(variants):
                if "👋" in variant or "🍔" in variant:
                    return i
        elif communication_style == "formal":
            # Prefer variants without emojis
            for i, variant in enumerate(variants):
                if "👋" not in variant and "🍔" not in variant:
                    return i
        
        # Default: random selection for variety
        return random.randint(0, len(variants) - 1)
    
    def _get_industry_variables(self, industry: str, business_context: Dict[str, Any]) -> Dict[str, str]:
        """Get industry-specific variable customizations"""
        
        industry_vars = {
            "food_service": {
                "business_type": "restaurant",
                "experience_type": "food service"
            },
            "retail": {
                "business_type": "retail store", 
                "experience_type": "retail"
            },
            "technology": {
                "business_type": "tech business",
                "experience_type": "technology"
            }
        }
        
        return industry_vars.get(industry, {})
    
    def _calculate_investment_range(self, company_size: str, 
                                  investment_config: Dict[str, Any]) -> Dict[str, str]:
        """Calculate appropriate investment range based on company size"""
        
        size_ranges = {
            "startup": {"min": "5 lakhs", "max": "15 lakhs"},
            "small": {"min": "10 lakhs", "max": "25 lakhs"},
            "medium": {"min": "15 lakhs", "max": "40 lakhs"},
            "large": {"min": "25 lakhs", "max": "75 lakhs"},
            "enterprise": {"min": "50 lakhs", "max": "2 crores"}
        }
        
        range_data = size_ranges.get(company_size, size_ranges["medium"])
        
        return {
            "investment_min": range_data["min"],
            "investment_max": range_data["max"]
        }
    
    def _get_industry_specific_steps(self, industry: str) -> List[Dict[str, Any]]:
        """Get additional steps specific to industry"""
        
        if industry == "food_service":
            return [{
                "step_id": "food_safety_compliance",
                "step_number": 3.5,
                "step_name": "Food Safety Compliance",
                "step_type": "qualification",
                "required": False,
                "message_variants": [
                    "Are you familiar with food safety regulations and FSSAI compliance requirements?"
                ],
                "data_collection": {
                    "knows_food_safety": "boolean"
                }
            }]
        
        return []
    
    def _is_step_relevant(self, step: Dict[str, Any], customer_context: CustomerContext) -> bool:
        """Check if step is relevant for customer"""
        
        # Check step relevance conditions
        if "relevance_conditions" in step:
            conditions = step["relevance_conditions"]
            
            if "min_company_size" in conditions:
                size_order = ["startup", "small", "medium", "large", "enterprise"]
                customer_size_idx = size_order.index(customer_context.company_size) if customer_context.company_size in size_order else 2
                min_size_idx = size_order.index(conditions["min_company_size"])
                
                if customer_size_idx < min_size_idx:
                    return False
        
        return True
    
    def _estimate_step_duration(self, step: Dict[str, Any]) -> int:
        """Estimate duration for step in seconds"""
        
        step_durations = {
            "consent_gate": 30,
            "qualification": 45,
            "information_gathering": 40,
            "engagement": 35,
            "transition_to_booking": 25,
            "booking": 60
        }
        
        return step_durations.get(step.get("step_type", ""), 40)
    
    def _get_skip_conditions(self, step: Dict[str, Any], customer_context: CustomerContext) -> List[str]:
        """Get conditions under which step should be skipped"""
        
        conditions = []
        
        # Skip experience question if already known
        if step["step_id"] == "experience":
            if any("business_experience" in str(interaction) for interaction in customer_context.previous_interactions):
                conditions.append("experience_already_known")
        
        # Skip location question if already specified
        if step["step_id"] == "location":
            if customer_context.preferences.get("location"):
                conditions.append("location_already_specified")
        
        return conditions
    
    def _calculate_personalization_level(self, step: Dict[str, Any], customer_context: CustomerContext) -> float:
        """Calculate personalization level for step"""
        
        personalization = 0.5  # Base level
        
        # Increase based on available customer data
        if customer_context.industry:
            personalization += 0.1
        
        if customer_context.company_size:
            personalization += 0.1
        
        if customer_context.previous_interactions:
            personalization += 0.2
        
        if customer_context.preferences:
            personalization += 0.1
        
        return min(1.0, personalization)
    
    def _get_fallback_template(self) -> Dict[str, Any]:
        """Get fallback template when loading fails"""
        
        return {
            "flow_id": "fallback",
            "flow_name": "Basic Qualification",
            "flow_type": "simple_conversation",
            "steps": [
                {
                    "step_id": "greeting",
                    "step_number": 1,
                    "message_variants": ["Hi! Thanks for your interest. Can I ask a few quick questions?"],
                    "data_collection": {"consent": "boolean"}
                },
                {
                    "step_id": "basic_info",
                    "step_number": 2,
                    "message_variants": ["What's your timeline for making a decision?"],
                    "data_collection": {"timeline": "string"}
                }
            ]
        }
    
    # ADDED: Private helper methods for conversation flows
    
    def _validate_template(self, template: Dict[str, Any]) -> None:
        """Validate conversation template structure"""
        required_fields = ["flow_id", "flow_name", "steps"]
        
        for field in required_fields:
            if field not in template:
                raise ValueError(f"Template missing required field: {field}")
        
        if not isinstance(template["steps"], list) or len(template["steps"]) == 0:
            raise ValueError("Template must have at least one step")
        
        # Validate each step
        for i, step in enumerate(template["steps"]):
            step_required = ["step_id", "step_number", "message_variants"]
            for field in step_required:
                if field not in step:
                    raise ValueError(f"Step {i} missing required field: {field}")
    
    def _customize_template_variables(self, template: Dict[str, Any], 
                                    customer_context: CustomerContext,
                                    business_context: Dict[str, Any]) -> Dict[str, Any]:
        """Replace template variables with customer-specific values"""
        
        variables = self.customize_script_variables(template, customer_context, business_context)
        
        # Convert template to string, replace variables, convert back
        template_str = json.dumps(template)
        
        for var_name, var_value in variables.items():
            placeholder = "{{" + var_name + "}}"
            template_str = template_str.replace(placeholder, str(var_value))
        
        try:
            customized_template = json.loads(template_str)
            return customized_template
        except json.JSONDecodeError:
            self.logger.error("Failed to parse customized template")
            return template
class PitchDeliveryManager:
    """Manages the actual delivery of pitch content"""
    
    def __init__(self):
        self.delivery_state = {}
        self.engagement_checkpoints = []
        self.logger = logging.getLogger(__name__)


        # ADDED: Conversation flow execution state
        self.conversation_sessions: Dict[str, Dict[str, Any]] = {}
        self.step_execution_history: Dict[str, List[Dict[str, Any]]] = {}
    
    def structure_pitch_for_voice_delivery(
        self, 
        pitch_content: PitchContent, 
        conversation_pacing: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Structure pitch content optimized for voice delivery"""
        
        pacing_speed = conversation_pacing.get("words_per_minute", 150)
        pause_preference = conversation_pacing.get("pause_duration", "medium")
        
        structured_pitch = {
            "segments": [],
            "total_estimated_duration": 0,
            "interaction_points": []
        }
        
        # Break down content into segments
        segments = [
            {
                "name": "opening",
                "content": pitch_content.value_proposition,
                "duration": self._calculate_speaking_duration(pitch_content.value_proposition, pacing_speed),
                "type": "value_proposition"
            },
            {
                "name": "proof_points",
                "content": ". ".join(pitch_content.proof_points[:3]),
                "duration": self._calculate_speaking_duration(". ".join(pitch_content.proof_points[:3]), pacing_speed),
                "type": "credibility"
            },
            {
                "name": "benefits",
                "content": ". ".join(pitch_content.solution_benefits),
                "duration": self._calculate_speaking_duration(". ".join(pitch_content.solution_benefits), pacing_speed),
                "type": "benefits"
            }
        ]
        
        # Add appropriate pauses between segments
        pause_durations = {"short": 2, "medium": 3, "long": 5}
        pause_duration = pause_durations.get(pause_preference, 3)
        
        total_duration = 0
        for i, segment in enumerate(segments):
            segment["pause_after"] = pause_duration
            total_duration += segment["duration"] + pause_duration
            structured_pitch["segments"].append(segment)
        
        structured_pitch["total_estimated_duration"] = total_duration
        
        return structured_pitch
    
    def manage_pitch_segment_progression(
        self, 
        current_segment: str, 
        customer_response: Dict[str, Any], 
        remaining_content: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Manage progression through pitch segments"""
        
        progression_decision = {
            "action": "continue",  # continue, pause, adapt, skip
            "next_segment": None,
            "adaptation_needed": False,
            "reasoning": ""
        }
        
        # Analyze customer response
        engagement_level = customer_response.get("engagement_level", 0.5)
        verbal_feedback = customer_response.get("verbal_feedback", "")
        interruption_type = customer_response.get("interruption_type", None)
        
        # Decision logic based on customer response
        if interruption_type == "question":
            progression_decision["action"] = "pause"
            progression_decision["reasoning"] = "Customer has question - address before continuing"
        
        elif interruption_type == "objection":
            progression_decision["action"] = "adapt"
            progression_decision["adaptation_needed"] = True
            progression_decision["reasoning"] = "Objection raised - need to address concerns"
        
        elif engagement_level < 0.3:
            progression_decision["action"] = "pause"
            progression_decision["reasoning"] = "Low engagement - check understanding"
        
        elif engagement_level > 0.8 and remaining_content:
            progression_decision["action"] = "continue"
            progression_decision["next_segment"] = remaining_content[0]["name"]
            progression_decision["reasoning"] = "High engagement - continue with next segment"
        
        # Positive feedback indicators
        positive_indicators = ["interesting", "good", "helpful", "tell me more"]
        if any(indicator in verbal_feedback.lower() for indicator in positive_indicators):
            progression_decision["action"] = "continue"
            progression_decision["reasoning"] = "Positive feedback received"
        
        return progression_decision
    
    def insert_engagement_checkpoints(
        self, 
        pitch_progression: Dict[str, Any], 
        customer_interaction_opportunities: List[str]
    ) -> List[Dict[str, Any]]:
        """Insert engagement checkpoints throughout pitch"""
        
        checkpoints = []
        segments = pitch_progression.get("segments", [])
        
        # Standard checkpoint templates
        checkpoint_templates = {
            "understanding_check": "Does this align with what you're looking for?",
            "relevance_check": "Is this relevant to your current situation?",
            "engagement_check": "What questions do you have so far?",
            "interest_check": "How does this sound to you?",
            "detail_check": "Would you like me to elaborate on any particular aspect?"
        }
        
        # Insert checkpoints between major segments
        for i, segment in enumerate(segments):
            if segment["duration"] > 60:  # For longer segments
                checkpoint = {
                    "position": f"after_segment_{i}",
                    "type": "understanding_check",
                    "question": checkpoint_templates["understanding_check"],
                    "expected_duration": 10,
                    "trigger_condition": "segment_completion"
                }
                checkpoints.append(checkpoint)
        
        # Add checkpoints based on customer interaction opportunities
        for opportunity in customer_interaction_opportunities:
            if "technical" in opportunity.lower():
                checkpoint = {
                    "position": "contextual",
                    "type": "detail_check",
                    "question": checkpoint_templates["detail_check"],
                    "expected_duration": 15,
                    "trigger_condition": "technical_content"
                }
                checkpoints.append(checkpoint)
        
        return checkpoints
    
    def handle_pitch_interruptions(
        self, 
        interruption_type: str, 
        conversation_context: Dict[str, Any], 
        remaining_pitch_content: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Handle interruptions during pitch delivery"""
        
        interruption_response = {
            "immediate_action": "",
            "content_adjustment": None,
            "resumption_strategy": "",
            "context_preservation": {}
        }
        
        # Preserve current context
        interruption_response["context_preservation"] = {
            "interrupted_at": datetime.now(),
            "current_segment": conversation_context.get("current_segment"),
            "remaining_content": remaining_pitch_content,
            "customer_engagement_level": conversation_context.get("engagement_level", 0.5)
        }
        
        # Handle different interruption types
        if interruption_type == "question":
            interruption_response["immediate_action"] = "acknowledge_and_address"
            interruption_response["resumption_strategy"] = "seamless_continuation"
        
        elif interruption_type == "objection":
            interruption_response["immediate_action"] = "acknowledge_and_transition"
            interruption_response["content_adjustment"] = "address_objection_first"
            interruption_response["resumption_strategy"] = "modified_pitch"
        
        elif interruption_type == "time_constraint":
            interruption_response["immediate_action"] = "acknowledge_and_compress"
            interruption_response["content_adjustment"] = "prioritize_key_points"
            interruption_response["resumption_strategy"] = "abbreviated_version"
        
        elif interruption_type == "distraction":
            interruption_response["immediate_action"] = "pause_and_wait"
            interruption_response["resumption_strategy"] = "gentle_refocus"
        
        return interruption_response
    
    def adapt_pitch_based_on_real_time_feedback(
        self, 
        customer_signals: Dict[str, Any], 
        engagement_indicators: Dict[str, float], 
        pitch_effectiveness: float
    ) -> Dict[str, Any]:
        """Adapt pitch delivery based on real-time customer feedback"""
        
        adaptation = {
            "speed_adjustment": 0,  # -1 to 1 scale (slower to faster)
            "detail_level_adjustment": 0,  # -1 to 1 scale (less to more detail)
            "interaction_frequency_adjustment": 0,  # -1 to 1 scale
            "content_focus_shift": None,
            "delivery_style_change": None
        }
        
        # Analyze engagement indicators
        avg_engagement = sum(engagement_indicators.values()) / len(engagement_indicators) if engagement_indicators else 0.5
        
        # Speed adjustments
        if customer_signals.get("comprehension_signals", 0) < 0.5:
            adaptation["speed_adjustment"] = -0.3  # Slow down
        elif avg_engagement > 0.8:
            adaptation["speed_adjustment"] = 0.2   # Speed up slightly
        
        # Detail level adjustments
        if customer_signals.get("detail_requests", 0) > 2:
            adaptation["detail_level_adjustment"] = 0.4  # More detail
        elif customer_signals.get("summary_requests", 0) > 1:
            adaptation["detail_level_adjustment"] = -0.4  # Less detail
        
        # Interaction frequency adjustments
        if avg_engagement < 0.4:
            adaptation["interaction_frequency_adjustment"] = 0.5  # More interaction
        elif customer_signals.get("interruption_count", 0) > 3:
            adaptation["interaction_frequency_adjustment"] = -0.3  # Less interaction
        
        # Content focus shifts
        if customer_signals.get("cost_concerns", 0) > 1:
            adaptation["content_focus_shift"] = "roi_and_value"
        elif customer_signals.get("technical_interest", 0) > 2:
            adaptation["content_focus_shift"] = "technical_details"
        
        # Delivery style changes
        if pitch_effectiveness < 0.5:
            adaptation["delivery_style_change"] = "more_conversational"
        elif avg_engagement > 0.8:
            adaptation["delivery_style_change"] = "more_detailed"
        
        return adaptation
    
    def _calculate_speaking_duration(self, content: str, words_per_minute: int) -> float:
        """Calculate estimated speaking duration for content"""
        word_count = len(content.split())
        duration_minutes = word_count / words_per_minute
        return duration_minutes * 60  # Return in seconds
    # ADDED: New conversation flow execution methods
    
    def execute_conversation_flow(self, session_id: str, conversation_template: Dict[str, Any],
                                customer_context: CustomerContext) -> Dict[str, Any]:
        """Initialize and start conversation flow execution"""
        
        try:
            # Initialize conversation session
            self.conversation_sessions[session_id] = {
                "template": conversation_template,
                "current_step_index": 0,
                "current_step_id": None,
                "conversation_data": {},
                "step_history": [],
                "start_time": datetime.now(),
                "status": "active",
                "customer_context": customer_context,
                "flow_metadata": conversation_template.get("customization_metadata", {})
            }
            
            self.step_execution_history[session_id] = []
            
            # Execute first step
            first_step_result = self.execute_conversation_step(session_id)
            
            self.logger.info(f"Started conversation flow for session {session_id}")
            
            return {
                "status": "conversation_started",
                "session_id": session_id,
                "flow_id": conversation_template.get("flow_id"),
                "first_step": first_step_result,
                "total_steps": len(conversation_template.get("steps", [])),
                "estimated_duration": self._calculate_total_duration(conversation_template)
            }
            
        except Exception as e:
            self.logger.error(f"Failed to start conversation flow: {e}")
            return {"status": "error", "error": str(e)}
    
    def execute_conversation_step(self, session_id: str, 
                                customer_response: Optional[str] = None) -> Dict[str, Any]:
        """Execute current conversation step"""
        
        if session_id not in self.conversation_sessions:
            return {"error": "Session not found"}
        
        session = self.conversation_sessions[session_id]
        template = session["template"]
        steps = template.get("steps", [])
        
        # Check if conversation is complete
        if session["current_step_index"] >= len(steps):
            return self._finalize_conversation_flow(session_id)
        
        current_step = steps[session["current_step_index"]]
        session["current_step_id"] = current_step["step_id"]
        
        try:
            # Process previous customer response if provided
            if customer_response and session["current_step_index"] > 0:
                previous_step = steps[session["current_step_index"] - 1]
                self._process_customer_response(session_id, previous_step, customer_response)
            
            # Check skip conditions
            if self._should_skip_step(current_step, session):
                return self._skip_to_next_step(session_id)
            
            # Execute current step
            step_result = self._execute_single_step(session_id, current_step)
            
            # Log step execution
            self._log_step_execution(session_id, current_step, step_result)
            
            return step_result
            
        except Exception as e:
            self.logger.error(f"Error executing conversation step: {e}")
            return self._handle_step_error(session_id, current_step, str(e))
    
    def handle_conversation_flow_branching(self, session_id: str, customer_response: str,
                                         current_step: Dict[str, Any]) -> Dict[str, Any]:
        """Handle branching logic based on customer response"""
        
        if session_id not in self.conversation_sessions:
            return {"error": "Session not found"}
        
        session = self.conversation_sessions[session_id]
        response_handlers = current_step.get("response_handlers", {})
        
        # Normalize customer response
        normalized_response = customer_response.lower().strip()
        
        # Check for specific response patterns
        branch_result = self._determine_response_branch(normalized_response, response_handlers)
        
        if branch_result["branch_type"] == "yes":
            return self._handle_yes_response(session_id, branch_result, response_handlers)
        elif branch_result["branch_type"] == "no":
            return self._handle_no_response(session_id, branch_result, response_handlers)
        elif branch_result["branch_type"] == "specific":
            return self._handle_specific_response(session_id, branch_result, response_handlers)
        else:
            return self._handle_unclear_response(session_id, customer_response)
    
    def progress_conversation_flow(self, session_id: str, next_step_id: Optional[str] = None) -> Dict[str, Any]:
        """Progress to next step in conversation flow"""
        
        if session_id not in self.conversation_sessions:
            return {"error": "Session not found"}
        
        session = self.conversation_sessions[session_id]
        
        if next_step_id:
            # Jump to specific step
            step_index = self._find_step_index(session["template"], next_step_id)
            if step_index >= 0:
                session["current_step_index"] = step_index
            else:
                self.logger.warning(f"Step {next_step_id} not found, progressing normally")
                session["current_step_index"] += 1
        else:
            # Progress to next step normally
            session["current_step_index"] += 1
        
        # Execute the next step
        return self.execute_conversation_step(session_id)
    
    def adapt_conversation_flow_real_time(self, session_id: str, 
                                        adaptation_signals: Dict[str, Any]) -> Dict[str, Any]:
        """Adapt conversation flow based on real-time signals"""
        
        if session_id not in self.conversation_sessions:
            return {"error": "Session not found"}
        
        session = self.conversation_sessions[session_id]
        adaptations = {
            "flow_adjustments": [],
            "message_modifications": [],
            "step_reordering": [],
            "personalization_updates": []
        }
        
        # Analyze adaptation signals
        engagement_level = adaptation_signals.get("engagement_level", 0.5)
        comprehension_level = adaptation_signals.get("comprehension_level", 0.5)
        time_pressure = adaptation_signals.get("time_pressure", False)
        
        # Apply adaptations based on signals
        if engagement_level < 0.3:
            adaptations["flow_adjustments"].append("increase_engagement")
            adaptations["message_modifications"].append("add_engaging_elements")
        
        if comprehension_level < 0.4:
            adaptations["flow_adjustments"].append("simplify_language")
            adaptations["message_modifications"].append("reduce_complexity")
        
        if time_pressure:
            adaptations["flow_adjustments"].append("accelerate_pace")
            adaptations["step_reordering"].append("prioritize_key_questions")
        
        # Apply adaptations to current session
        self._apply_flow_adaptations(session_id, adaptations)
        
        return {
            "status": "adaptations_applied",
            "adaptations": adaptations,
            "session_updated": True
        }
    
    def get_conversation_flow_status(self, session_id: str) -> Dict[str, Any]:
        """Get current status of conversation flow execution"""
        
        if session_id not in self.conversation_sessions:
            return {"status": "not_active"}
        
        session = self.conversation_sessions[session_id]
        template = session["template"]
        steps = template.get("steps", [])
        
        current_step_index = session["current_step_index"]
        total_steps = len(steps)
        
        # Calculate progress
        progress_percentage = (current_step_index / total_steps) * 100 if total_steps > 0 else 0
        
        # Calculate estimated time remaining
        remaining_steps = steps[current_step_index:] if current_step_index < total_steps else []
        estimated_time_remaining = sum(
            step.get("execution_metadata", {}).get("estimated_duration", 40) 
            for step in remaining_steps
        )
        
        # Get current step info
        current_step_info = None
        if current_step_index < total_steps:
            current_step = steps[current_step_index]
            current_step_info = {
                "step_id": current_step["step_id"],
                "step_name": current_step["step_name"],
                "step_type": current_step.get("step_type", "unknown"),
                "estimated_duration": current_step.get("execution_metadata", {}).get("estimated_duration", 40)
            }
        
        return {
            "session_id": session_id,
            "status": session["status"],
            "flow_id": template.get("flow_id"),
            "current_step_index": current_step_index,
            "total_steps": total_steps,
            "progress_percentage": progress_percentage,
            "estimated_time_remaining": estimated_time_remaining,
            "current_step": current_step_info,
            "conversation_data": session["conversation_data"],
            "step_history_count": len(session["step_history"]),
            "session_duration": (datetime.now() - session["start_time"]).total_seconds()
        }
    
    # ADDED: Private helper methods for conversation flow execution
    
    def _execute_single_step(self, session_id: str, step: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single conversation step"""
        
        session = self.conversation_sessions[session_id]
        
        # Get the message to deliver
        message = step.get("selected_message") or step["message_variants"][0]
        
        # Add natural variations to avoid sounding scripted
        natural_message = self._add_natural_variations(message, session["customer_context"])
        
        # Prepare step execution result
        step_result = {
            "step_id": step["step_id"],
            "step_name": step["step_name"],
            "step_type": step.get("step_type", "conversation"),
            "message": natural_message,
            "expects_response": True,
            "response_handlers": step.get("response_handlers", {}),
            "data_collection": step.get("data_collection", {}),
            "execution_time": datetime.now(),
            "step_metadata": step.get("execution_metadata", {})
        }
        
        # Handle special step types
        if step.get("step_type") == "booking":
            step_result.update(self._handle_booking_step(session_id, step))
        elif step.get("step_type") == "consent_gate":
            step_result.update(self._handle_consent_step(session_id, step))
        
        # Add follow-up messages if configured
        if "follow_up_message" in step:
            step_result["follow_up"] = step["follow_up_message"]
        
        return step_result
    
    def _process_customer_response(self, session_id: str, step: Dict[str, Any], 
                                 customer_response: str) -> None:
        """Process and store customer response data"""
        
        session = self.conversation_sessions[session_id]
        data_collection = step.get("data_collection", {})
        
        # Extract data based on step configuration
        extracted_data = self._extract_response_data(customer_response, data_collection, step)
        
        # Store in conversation data
        for key, value in extracted_data.items():
            session["conversation_data"][key] = value
        
        # Add to step history
        session["step_history"].append({
            "step_id": step["step_id"],
            "customer_response": customer_response,
            "extracted_data": extracted_data,
            "timestamp": datetime.now()
        })
    
    def _determine_response_branch(self, normalized_response: str, 
                                 response_handlers: Dict[str, Any]) -> Dict[str, Any]:
        """Determine which branch to take based on customer response"""
        
        # Check for yes responses
        yes_responses = response_handlers.get("yes_responses", [])
        if any(yes_word in normalized_response for yes_word in yes_responses):
            return {"branch_type": "yes", "confidence": 0.8}
        
        # Check for no responses
        no_responses = response_handlers.get("no_responses", [])
        if any(no_word in normalized_response for no_word in no_responses):
            return {"branch_type": "no", "confidence": 0.8}
        
        # Check for specific responses (like slot selection)
        for handler_key, handler_value in response_handlers.items():
            if handler_key.endswith("_responses") and handler_key not in ["yes_responses", "no_responses"]:
                if isinstance(handler_value, list):
                    if any(response_option in normalized_response for response_option in handler_value):
                        return {"branch_type": "specific", "handler_key": handler_key, "confidence": 0.9}
        
        return {"branch_type": "unclear", "confidence": 0.3}
    
    def _handle_yes_response(self, session_id: str, branch_result: Dict[str, Any],
                           response_handlers: Dict[str, Any]) -> Dict[str, Any]:
        """Handle yes response from customer"""
        
        yes_action = response_handlers.get("yes_action", {})
        
        response_result = {
            "branch_taken": "yes",
            "confidence": branch_result["confidence"]
        }
        
        if "message" in yes_action:
            response_result["acknowledgment_message"] = yes_action["message"]
        
        if "next_step" in yes_action:
            response_result["next_step_id"] = yes_action["next_step"]
        else:
            response_result["progress_normally"] = True
        
        return response_result
    
    def _handle_no_response(self, session_id: str, branch_result: Dict[str, Any],
                          response_handlers: Dict[str, Any]) -> Dict[str, Any]:
        """Handle no response from customer"""
        
        no_action = response_handlers.get("no_action", {})
        
        response_result = {
            "branch_taken": "no",
            "confidence": branch_result["confidence"]
        }
        
        if "message" in no_action:
            response_result["acknowledgment_message"] = no_action["message"]
        
        if "branch_to" in no_action:
            response_result["next_step_id"] = no_action["branch_to"]
        elif "next_step" in no_action:
            response_result["next_step_id"] = no_action["next_step"]
        else:
            response_result["progress_normally"] = True
        
        # Handle follow-up actions
        if "follow_up" in no_action:
            response_result["follow_up_required"] = True
            response_result["follow_up_action"] = no_action["follow_up"]
        
        return response_result
    
    def _handle_specific_response(self, session_id: str, branch_result: Dict[str, Any],
                                response_handlers: Dict[str, Any]) -> Dict[str, Any]:
        """Handle specific response (like slot selection)"""
        
        handler_key = branch_result["handler_key"]
        action_key = handler_key.replace("_responses", "_action")
        
        specific_action = response_handlers.get(action_key, {})
        
        response_result = {
            "branch_taken": "specific",
            "handler_used": handler_key,
            "confidence": branch_result["confidence"]
        }
        
        if "message" in specific_action:
            response_result["acknowledgment_message"] = specific_action["message"]
        
        if "next_step" in specific_action:
            response_result["next_step_id"] = specific_action["next_step"]
        else:
            response_result["progress_normally"] = True
        
        return response_result
    
    def _handle_unclear_response(self, session_id: str, customer_response: str) -> Dict[str, Any]:
        """Handle unclear or unexpected customer response"""
        
        session = self.conversation_sessions[session_id]
        template = session["template"]
        
        # Get fallback responses
        fallback_responses = template.get("fallback_responses", {})
        unclear_responses = fallback_responses.get("unclear_response", [
            "I didn't quite catch that. Could you clarify?",
            "Sorry, could you rephrase that for me?"
        ])
        
        # Select random fallback response
        fallback_message = random.choice(unclear_responses)
        
        return {
            "branch_taken": "unclear",
            "confidence": 0.3,
            "fallback_message": fallback_message,
            "retry_current_step": True,
            "customer_response": customer_response
        }
    
    def _should_skip_step(self, step: Dict[str, Any], session: Dict[str, Any]) -> bool:
        """Check if step should be skipped based on conditions"""
        
        skip_conditions = step.get("skip_conditions", [])
        if not skip_conditions:
            return False
        
        conversation_data = session["conversation_data"]
        customer_context = session["customer_context"]
        
        for condition in skip_conditions:
            if condition == "experience_already_known":
                if "has_business_experience" in conversation_data:
                    return True
            elif condition == "location_already_specified":
                if "location_details" in conversation_data or customer_context.preferences.get("location"):
                    return True
        
        return False
    
    def _skip_to_next_step(self, session_id: str) -> Dict[str, Any]:
        """Skip current step and move to next"""
        
        session = self.conversation_sessions[session_id]
        skipped_step_id = session["current_step_id"]
        
        # Log the skip
        session["step_history"].append({
            "step_id": skipped_step_id,
            "action": "skipped",
            "reason": "skip_conditions_met",
            "timestamp": datetime.now()
        })
        
        # Progress to next step
        session["current_step_index"] += 1
        
        # Execute next step
        return self.execute_conversation_step(session_id)
    
    def _handle_booking_step(self, session_id: str, step: Dict[str, Any]) -> Dict[str, Any]:
        """Handle special booking step logic"""
        
        # Simulate checking available slots (in real implementation, would call booking API)
        available_slots = [
            {"id": "wed_15", "display": "Wednesday – 3 PM", "datetime": "2024-01-17T15:00:00"},
            {"id": "fri_11", "display": "Friday – 11 AM", "datetime": "2024-01-19T11:00:00"},
            {"id": "sat_17", "display": "Saturday – 5 PM", "datetime": "2024-01-20T17:00:00"}
        ]
        
        return {
            "booking_step": True,
            "available_slots": available_slots,
            "booking_options": step.get("follow_up_message", {}).get("options", [])
        }
    
    def _handle_consent_step(self, session_id: str, step: Dict[str, Any]) -> Dict[str, Any]:
        """Handle consent gate step"""
        
        return {
            "consent_step": True,
            "consent_required": True,
            "consent_message": "This step requires your consent to continue."
        }
    
    def _extract_response_data(self, customer_response: str, data_collection: Dict[str, str], 
                             step: Dict[str, Any]) -> Dict[str, Any]:
        """Extract structured data from customer response"""
        
        extracted = {}
        response_lower = customer_response.lower()
        
        for field_name, field_type in data_collection.items():
            if field_type == "boolean":
                # Extract boolean values
                if any(word in response_lower for word in ["yes", "sure", "okay", "absolutely"]):
                    extracted[field_name] = True
                elif any(word in response_lower for word in ["no", "not", "don't"]):
                    extracted[field_name] = False
            
            elif field_type == "string":
                # Store the full response for string fields
                extracted[field_name] = customer_response.strip()
            
            elif field_type == "number":
                # Extract numbers from response
                numbers = [int(s) for s in customer_response.split() if s.isdigit()]
                if numbers:
                    extracted[field_name] = numbers[0]
            
            elif field_type == "array":
                # Split response into array elements
                extracted[field_name] = [item.strip() for item in customer_response.split(",")]
        
        return extracted
    
    def _add_natural_variations(self, message: str, customer_context: CustomerContext) -> str:
        """Add natural variations to avoid scripted feel"""
        
        # Add natural transitions
        transitions = ["", "So, ", "Now, ", "Let me ask - ", "I'm curious - "]
        if not message.startswith(("Hi", "Hello", "Thanks", "Perfect", "Great")):
            transition = random.choice(transitions)
            message = transition + message
        
        # Adjust formality based on customer context
        communication_style = customer_context.preferences.get("communication_style", "professional")
        
        if communication_style == "casual":
            # Make more casual
            message = message.replace("Would you be comfortable", "Are you okay")
            message = message.replace("Could you clarify", "Can you explain")
        elif communication_style == "formal":
            # Make more formal
            message = message.replace("How's", "How is")
            message = message.replace("Can't", "Cannot")
        
        return message
    
    def _find_step_index(self, template: Dict[str, Any], step_id: str) -> int:
        """Find index of step by step_id"""
        
        steps = template.get("steps", [])
        for i, step in enumerate(steps):
            if step["step_id"] == step_id:
                return i
        return -1
    
    def _apply_flow_adaptations(self, session_id: str, adaptations: Dict[str, Any]) -> None:
        """Apply real-time adaptations to conversation flow"""
        
        session = self.conversation_sessions[session_id]
        
        # Apply message modifications
        for modification in adaptations["message_modifications"]:
            if modification == "add_engaging_elements":
                # Add emojis and engaging language to future steps
                self._enhance_message_engagement(session)
            elif modification == "reduce_complexity":
                # Simplify language in remaining steps
                self._simplify_step_messages(session)
        
        # Apply step reordering
        for reorder_action in adaptations["step_reordering"]:
            if reorder_action == "prioritize_key_questions":
                self._prioritize_key_questions(session)
    
    def _enhance_message_engagement(self, session: Dict[str, Any]) -> None:
        """Add engaging elements to remaining steps"""
        
        current_index = session["current_step_index"]
        steps = session["template"]["steps"]
        
        for i in range(current_index, len(steps)):
            step = steps[i]
            if "selected_message" in step:
                # Add engaging elements
                message = step["selected_message"]
                if "!" not in message:
                    message = message.rstrip(".") + "!"
                step["selected_message"] = message
    
    def _simplify_step_messages(self, session: Dict[str, Any]) -> None:
        """Simplify language in remaining steps"""
        
        current_index = session["current_step_index"]
        steps = session["template"]["steps"]
        
        for i in range(current_index, len(steps)):
            step = steps[i]
            if "selected_message" in step:
                # Simplify language
                message = step["selected_message"]
                message = message.replace("comfortable with", "okay with")
                message = message.replace("Would you be interested", "Do you want")
                step["selected_message"] = message
    
    def _prioritize_key_questions(self, session: Dict[str, Any]) -> None:
        """Reorder remaining steps to prioritize key questions"""
        
        current_index = session["current_step_index"]
        steps = session["template"]["steps"]
        remaining_steps = steps[current_index:]
        
        # Priority order for key steps
        priority_steps = ["investment_comfort", "timeline", "location"]
        
        high_priority = []
        normal_priority = []
        
        for step in remaining_steps:
            if step["step_id"] in priority_steps:
                high_priority.append(step)
            else:
                normal_priority.append(step)
        
        # Reorder steps
        reordered_steps = steps[:current_index] + high_priority + normal_priority
        session["template"]["steps"] = reordered_steps
    
    def _calculate_total_duration(self, template: Dict[str, Any]) -> int:
        """Calculate estimated total duration for conversation flow"""
        
        steps = template.get("steps", [])
        total_duration = 0
        
        for step in steps:
            step_duration = step.get("execution_metadata", {}).get("estimated_duration", 40)
            total_duration += step_duration
        
        return total_duration
    
    def _finalize_conversation_flow(self, session_id: str) -> Dict[str, Any]:
        """Finalize completed conversation flow"""
        
        session = self.conversation_sessions[session_id]
        session["status"] = "completed"
        session["end_time"] = datetime.now()
        
        # Generate completion summary
        conversation_end = session["template"].get("conversation_end", {})
        
        completion_result = {
            "status": "conversation_completed",
            "session_id": session_id,
            "completion_message": conversation_end.get("success_message", "Thank you for your time!"),
            "conversation_data": session["conversation_data"],
            "completion_data": conversation_end.get("completion_data", {}),
            "session_duration": (session["end_time"] - session["start_time"]).total_seconds(),
            "steps_completed": len(session["step_history"]),
            "data_collected": len(session["conversation_data"])
        }
        
        # Log completion
        self.step_execution_history[session_id].append({
            "action": "conversation_completed",
            "timestamp": session["end_time"],
            "summary": completion_result
        })
        
        return completion_result
    
    def _handle_step_error(self, session_id: str, step: Dict[str, Any], error: str) -> Dict[str, Any]:
        """Handle error during step execution"""
        
        self.logger.error(f"Step execution error in session {session_id}: {error}")
        
        return {
            "status": "step_error",
            "step_id": step["step_id"],
            "error": error,
            "fallback_message": "I apologize, there was an issue. Let me try a different approach.",
            "retry_step": True
        }
    
    def _log_step_execution(self, session_id: str, step: Dict[str, Any], result: Dict[str, Any]) -> None:
        """Log step execution for analysis"""
        
        if session_id not in self.step_execution_history:
            self.step_execution_history[session_id] = []
        
        self.step_execution_history[session_id].append({
            "step_id": step["step_id"],
            "step_name": step["step_name"],
            "execution_result": result,
            "timestamp": datetime.now()
        })

class PitchResponseHandler:
    """Handles customer responses during pitch delivery"""
    
    def __init__(self):
        self.response_patterns = self._init_response_patterns()
        self.logger = logging.getLogger(__name__)

        # ADDED: Conversation flow response handling
        self.conversation_response_patterns = self._init_conversation_response_patterns()
        self.response_classification_cache: Dict[str, Dict[str, Any]] = {}
        self.step_response_history: Dict[str, List[Dict[str, Any]]] = {}
    
    def monitor_customer_interest_signals(
        self, 
        conversation_analysis: Dict[str, Any], 
        engagement_metrics: Dict[str, float]
    ) -> Dict[str, float]:
        """Monitor and analyze customer interest signals"""
        
        interest_signals = {
            "verbal_interest": 0.5,
            "question_engagement": 0.5,
            "objection_concerns": 0.5,
            "time_investment": 0.5,
            "future_focus": 0.5
        }
        
        # Analyze verbal content
        verbal_content = conversation_analysis.get("customer_speech", "").lower()
        
        # Positive interest indicators
        positive_phrases = [
            "interesting", "good point", "tell me more", "how does", "what about",
            "sounds good", "that's helpful", "I like", "impressive", "exactly"
        ]
        
        negative_phrases = [
            "not sure", "concerned", "but", "however", "expensive", "complicated",
            "not interested", "maybe later", "we already have"
        ]
        
        positive_count = sum(1 for phrase in positive_phrases if phrase in verbal_content)
        negative_count = sum(1 for phrase in negative_phrases if phrase in verbal_content)
        
        if positive_count + negative_count > 0:
            interest_signals["verbal_interest"] = positive_count / (positive_count + negative_count)
        
        # Question engagement analysis
        question_count = conversation_analysis.get("question_count", 0)
        if question_count > 0:
            interest_signals["question_engagement"] = min(1.0, question_count / 5)  # Normalize to 5 questions
        
        # Objection concern analysis
        objection_count = conversation_analysis.get("objection_count", 0)
        if objection_count > 0:
            # Objections can indicate interest (they're engaged enough to raise concerns)
            interest_signals["objection_concerns"] = max(0.3, 0.8 - (objection_count * 0.2))
        
        # Time investment signals
        conversation_duration = conversation_analysis.get("duration_minutes", 0)
        if conversation_duration > 0:
            interest_signals["time_investment"] = min(1.0, conversation_duration / 20)  # 20 min = max score
        
        # Future-focused language
        future_phrases = ["when", "if we", "next steps", "timeline", "implementation", "how long"]
        future_count = sum(1 for phrase in future_phrases if phrase in verbal_content)
        if future_count > 0:
            interest_signals["future_focus"] = min(1.0, future_count / 3)
        
        return interest_signals
    
    def adjust_pitch_complexity_dynamically(
        self, 
        customer_comprehension: float, 
        feedback_signals: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Dynamically adjust pitch complexity based on customer comprehension"""
        
        complexity_adjustments = {
            "vocabulary_level": "maintain",  # simplify, maintain, elevate
            "technical_depth": "maintain",   # reduce, maintain, increase
            "example_type": "maintain",      # basic, maintain, advanced
            "pace_adjustment": "maintain"    # slow, maintain, accelerate
        }
        
        # Comprehension-based adjustments
        if customer_comprehension < 0.4:
            complexity_adjustments["vocabulary_level"] = "simplify"
            complexity_adjustments["technical_depth"] = "reduce"
            complexity_adjustments["example_type"] = "basic"
            complexity_adjustments["pace_adjustment"] = "slow"
        
        elif customer_comprehension > 0.8:
            complexity_adjustments["vocabulary_level"] = "elevate"
            complexity_adjustments["technical_depth"] = "increase"
            complexity_adjustments["example_type"] = "advanced"
            complexity_adjustments["pace_adjustment"] = "accelerate"
        
        # Feedback signal adjustments
        confusion_signals = feedback_signals.get("confusion_indicators", 0)
        if confusion_signals > 2:
            complexity_adjustments["vocabulary_level"] = "simplify"
            complexity_adjustments["pace_adjustment"] = "slow"
        
        technical_questions = feedback_signals.get("technical_question_count", 0)
        if technical_questions > 2:
            complexity_adjustments["technical_depth"] = "increase"
            complexity_adjustments["example_type"] = "advanced"
        
        return complexity_adjustments
    
    def handle_customer_questions_during_pitch(
        self, 
        questions: List[str], 
        current_pitch_context: Dict[str, Any], 
        remaining_content: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Handle customer questions that arise during pitch"""
        
        question_handling_strategy = {
            "immediate_responses": [],
            "deferred_responses": [],
            "pitch_modifications": [],
            "resumption_point": None
        }
        
        for question in questions:
            question_analysis = self._analyze_question(question, current_pitch_context)
            
            if question_analysis["urgency"] == "immediate":
                response_strategy = {
                    "question": question,
                    "response_type": question_analysis["response_type"],
                    "estimated_duration": question_analysis["response_duration"],
                    "context_relevance": question_analysis["relevance_score"]
                }
                question_handling_strategy["immediate_responses"].append(response_strategy)
            
            elif question_analysis["urgency"] == "deferred":
                deferred_strategy = {
                    "question": question,
                    "defer_reason": question_analysis["defer_reason"],
                    "address_at": question_analysis["optimal_timing"]
                }
                question_handling_strategy["deferred_responses"].append(deferred_strategy)
            
            # Check if question suggests pitch modification needed
            if question_analysis["suggests_modification"]:
                modification = {
                    "type": question_analysis["modification_type"],
                    "reason": f"Customer question: {question}",
                    "adjustment": question_analysis["suggested_adjustment"]
                }
                question_handling_strategy["pitch_modifications"].append(modification)
        
        # Determine resumption point
        if question_handling_strategy["immediate_responses"]:
            total_response_time = sum(r["estimated_duration"] for r in question_handling_strategy["immediate_responses"])
            if total_response_time > 180:  # 3 minutes
                question_handling_strategy["resumption_point"] = "abbreviated_continuation"
            else:
                question_handling_strategy["resumption_point"] = "seamless_continuation"
        
        return question_handling_strategy
    
    def transition_between_pitch_segments(
        self, 
        current_topic: str, 
        customer_engagement: float, 
        next_segment: Dict[str, Any]
    ) -> Dict[str, str]:
        """Manage smooth transitions between pitch segments"""
        
        transition_strategies = {
            "bridge_phrase": "",
            "engagement_check": "",
            "context_connection": "",
            "transition_type": "standard"
        }
        
        # Select bridge phrase based on segment types
        segment_transitions = {
            ("value_proposition", "proof_points"): "Let me share some examples that demonstrate this value",
            ("proof_points", "benefits"): "Now, let's talk about what this means for you specifically",
            ("benefits", "competitive"): "You might be wondering how this compares to other options",
            ("competitive", "next_steps"): "So, where do we go from here?"
        }
        
        transition_key = (current_topic, next_segment.get("type", ""))
        if transition_key in segment_transitions:
            transition_strategies["bridge_phrase"] = segment_transitions[transition_key]
        else:
            transition_strategies["bridge_phrase"] = f"Building on that, let's explore {next_segment.get('name', 'the next aspect')}"
        
        # Engagement-based adjustments
        if customer_engagement < 0.5:
            transition_strategies["engagement_check"] = "How are we doing so far? Any questions before we continue?"
            transition_strategies["transition_type"] = "careful"
        elif customer_engagement > 0.8:
            transition_strategies["transition_type"] = "accelerated"
        
        # Context connection
        if next_segment.get("type") == "benefits":
            transition_strategies["context_connection"] = "Based on what you've told me about your situation"
        elif next_segment.get("type") == "proof_points":
            transition_strategies["context_connection"] = "Similar organizations in your industry have seen"
        
        return transition_strategies
    
    def conclude_pitch_effectively(
        self, 
        customer_response: Dict[str, Any], 
        interest_level: float, 
        appropriate_next_steps: List[str]
    ) -> Dict[str, Any]:
        """Conclude pitch effectively based on customer response"""
        
        conclusion_strategy = {
            "closing_approach": "",
            "summary_points": [],
            "next_step_recommendation": "",
            "urgency_level": "medium",
            "follow_up_timing": "within_week"
        }
        
        # Determine closing approach based on interest level
        if interest_level >= 0.8:
            conclusion_strategy["closing_approach"] = "assumptive"
            conclusion_strategy["urgency_level"] = "high"
            conclusion_strategy["follow_up_timing"] = "immediate"
        elif interest_level >= 0.6:
            conclusion_strategy["closing_approach"] = "consultative"
            conclusion_strategy["urgency_level"] = "medium"
            conclusion_strategy["follow_up_timing"] = "within_days"
        elif interest_level >= 0.4:
            conclusion_strategy["closing_approach"] = "educational"
            conclusion_strategy["urgency_level"] = "low"
            conclusion_strategy["follow_up_timing"] = "within_week"
        else:
            conclusion_strategy["closing_approach"] = "nurture"
            conclusion_strategy["urgency_level"] = "very_low"
            conclusion_strategy["follow_up_timing"] = "longer_term"
        
        # Select summary points based on customer response
        if customer_response.get("key_interests"):
            conclusion_strategy["summary_points"] = customer_response["key_interests"][:3]
        else:
            conclusion_strategy["summary_points"] = [
                "Value proposition alignment",
                "Key benefits for your organization",
                "Competitive advantages"
            ]
        
        # Recommend next step
        if appropriate_next_steps:
            if interest_level >= 0.7:
                conclusion_strategy["next_step_recommendation"] = appropriate_next_steps[0]  # Most aggressive
            else:
                conclusion_strategy["next_step_recommendation"] = appropriate_next_steps[-1]  # Most conservative
        
        return conclusion_strategy
    
    def _analyze_question(self, question: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze customer question to determine handling strategy"""
        
        question_lower = question.lower()
        
        analysis = {
            "urgency": "immediate",
            "response_type": "direct",
            "response_duration": 30,
            "relevance_score": 0.5,
            "suggests_modification": False,
            "modification_type": None,
            "suggested_adjustment": None,
            "defer_reason": None,
            "optimal_timing": None
        }
        
        # Urgency classification
        immediate_keywords = ["what", "how", "explain", "clarify", "understand"]
        deferred_keywords = ["price", "cost", "timeline", "implementation", "contract"]
        
        if any(keyword in question_lower for keyword in immediate_keywords):
            analysis["urgency"] = "immediate"
        elif any(keyword in question_lower for keyword in deferred_keywords):
            analysis["urgency"] = "deferred"
            analysis["defer_reason"] = "Better addressed in detailed discussion"
            analysis["optimal_timing"] = "post_pitch"
        
        # Response type and duration
        if "technical" in question_lower or "how does" in question_lower:
            analysis["response_type"] = "detailed"
            analysis["response_duration"] = 60
        elif "price" in question_lower or "cost" in question_lower:
            analysis["response_type"] = "consultative"
            analysis["response_duration"] = 45
        
        # Modification suggestions
        if "too technical" in question_lower or "simpler" in question_lower:
            analysis["suggests_modification"] = True
            analysis["modification_type"] = "complexity_reduction"
            analysis["suggested_adjustment"] = "reduce_technical_depth"
        
        return analysis
    
    def _init_response_patterns(self) -> Dict[str, List[str]]:
        """Initialize customer response patterns"""
        return {
            "high_interest": [
                "that's exactly what we need",
                "this sounds perfect",
                "when can we start",
                "what are the next steps"
            ],
            "moderate_interest": [
                "interesting",
                "tell me more",
                "how does this work",
                "what about"
            ],
            "low_interest": [
                "not sure if this fits",
                "we already have something",
                "need to think about it",
                "maybe later"
            ],
            "objections": [
                "too expensive",
                "too complicated",
                "not the right time",
                "need approval"
            ]
        }

    # ADDED: New conversation flow response handling methods
    
    def handle_conversation_flow_response(self, session_id: str, customer_response: str,
                                        current_step: Dict[str, Any], 
                                        conversation_context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle customer response in conversation flow context"""
        
        try:
            # Parse and classify the response
            response_analysis = self.parse_step_response(customer_response, current_step)
            
            # Determine next step based on response
            next_step_decision = self.determine_next_step(
                session_id, response_analysis, current_step, conversation_context
            )
            
            # Extract qualification data
            qualification_data = self.extract_qualification_data(
                customer_response, current_step, response_analysis
            )
            
            # Store response history
            self._store_response_history(session_id, customer_response, current_step, response_analysis)
            
            return {
                "response_analysis": response_analysis,
                "next_step_decision": next_step_decision,
                "qualification_data": qualification_data,
                "processing_confidence": response_analysis.get("confidence", 0.5),
                "response_quality": self._assess_response_quality(customer_response, current_step),
                "conversation_momentum": self._calculate_conversation_momentum(session_id)
            }
            
        except Exception as e:
            self.logger.error(f"Error handling conversation flow response: {e}")
            return self._get_fallback_response_handling(customer_response, current_step)
    
    def parse_step_response(self, customer_response: str, current_step: Dict[str, Any]) -> Dict[str, Any]:
        """Parse customer response for conversation step"""
        
        response_key = f"{current_step['step_id']}_{hash(customer_response)}"
        
        # Check cache first
        if response_key in self.response_classification_cache:
            return self.response_classification_cache[response_key]
        
        response_analysis = {
            "original_response": customer_response,
            "normalized_response": customer_response.lower().strip(),
            "response_type": "unknown",
            "confidence": 0.5,
            "extracted_entities": {},
            "sentiment": "neutral",
            "clarity": 0.5,
            "completeness": 0.5
        }
        
        normalized = response_analysis["normalized_response"]
        step_type = current_step.get("step_type", "general")
        
        # STEP 1: Classify response type based on step context
        response_analysis["response_type"] = self._classify_response_type(normalized, step_type, current_step)
        
        # STEP 2: Extract entities (names, numbers, locations, etc.)
        response_analysis["extracted_entities"] = self._extract_response_entities(customer_response)
        
        # STEP 3: Analyze sentiment
        response_analysis["sentiment"] = self._analyze_response_sentiment(normalized)
        
        # STEP 4: Assess response quality
        response_analysis["clarity"] = self._assess_response_clarity(customer_response)
        response_analysis["completeness"] = self._assess_response_completeness(customer_response, current_step)
        
        # STEP 5: Calculate overall confidence
        response_analysis["confidence"] = self._calculate_response_confidence(response_analysis)
        
        # Cache the result
        self.response_classification_cache[response_key] = response_analysis
        
        return response_analysis
    
    def determine_next_step(self, session_id: str, response_analysis: Dict[str, Any],
                          current_step: Dict[str, Any], conversation_context: Dict[str, Any]) -> Dict[str, Any]:
        """Determine next step based on customer response analysis"""
        
        next_step_decision = {
            "action": "continue",  # continue, repeat, branch, skip, end
            "next_step_id": None,
            "reasoning": "",
            "confidence": 0.5,
            "special_handling": None
        }
        
        response_type = response_analysis["response_type"]
        response_handlers = current_step.get("response_handlers", {})
        
        # Handle different response types
        if response_type == "yes":
            yes_action = response_handlers.get("yes_action", {})
            next_step_decision.update({
                "action": "continue",
                "next_step_id": yes_action.get("next_step"),
                "reasoning": "Customer provided positive response",
                "confidence": response_analysis["confidence"]
            })
            
        elif response_type == "no":
            no_action = response_handlers.get("no_action", {})
            next_step_decision.update({
                "action": "branch" if no_action.get("branch_to") else "continue",
                "next_step_id": no_action.get("branch_to") or no_action.get("next_step"),
                "reasoning": "Customer provided negative response",
                "confidence": response_analysis["confidence"],
                "special_handling": "handle_objection" if response_type == "no" else None
            })
            
        elif response_type == "unclear":
            next_step_decision.update({
                "action": "repeat",
                "reasoning": "Customer response unclear, requesting clarification",
                "confidence": 0.3,
                "special_handling": "clarification_needed"
            })
            
        elif response_type == "off_topic":
            next_step_decision.update({
                "action": "redirect",
                "reasoning": "Customer went off-topic, redirecting to current step",
                "confidence": 0.6,
                "special_handling": "redirect_to_topic"
            })
            
        elif response_type == "detailed_answer":
            # Extract information and continue
            next_step_decision.update({
                "action": "continue",
                "reasoning": "Customer provided detailed response",
                "confidence": response_analysis["confidence"],
                "special_handling": "extract_additional_info"
            })
            
        else:
            # Default action based on step configuration
            default_action = response_handlers.get("default_action", {})
            next_step_decision.update({
                "action": "continue",
                "next_step_id": default_action.get("next_step"),
                "reasoning": "Using default progression",
                "confidence": 0.5
            })
        
        # Apply conversation context adjustments
        next_step_decision = self._apply_context_adjustments(
            next_step_decision, conversation_context, session_id
        )
        
        return next_step_decision
    
    def extract_qualification_data(self, customer_response: str, current_step: Dict[str, Any],
                                 response_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Extract qualification data from customer response"""
        
        qualification_data = {}
        data_collection = current_step.get("data_collection", {})
        extracted_entities = response_analysis.get("extracted_entities", {})
        
        # Extract data based on step configuration
        for field_name, field_type in data_collection.items():
            qualification_data[field_name] = self._extract_field_data(
                customer_response, field_name, field_type, extracted_entities
            )
        
        # Add step-specific extraction logic
        step_id = current_step["step_id"]
        
        if step_id == "experience":
            qualification_data.update(self._extract_experience_data(customer_response, extracted_entities))
        elif step_id == "investment_comfort":
            qualification_data.update(self._extract_investment_data(customer_response, extracted_entities))
        elif step_id == "location":
            qualification_data.update(self._extract_location_data(customer_response, extracted_entities))
        elif step_id == "timeline":
            qualification_data.update(self._extract_timeline_data(customer_response, extracted_entities))
        elif step_id == "outlet_count":
            qualification_data.update(self._extract_outlet_data(customer_response, extracted_entities))
        elif step_id == "motivation":
            qualification_data.update(self._extract_motivation_data(customer_response, extracted_entities))
        
        # Add metadata
        qualification_data["_metadata"] = {
            "extraction_confidence": response_analysis["confidence"],
            "extraction_timestamp": datetime.now(),
            "step_id": step_id,
            "response_quality": response_analysis.get("clarity", 0.5)
        }
        
        return qualification_data
    
    def monitor_conversation_flow_engagement(self, session_id: str, 
                                           conversation_history: List[Dict[str, Any]]) -> Dict[str, float]:
        """Monitor engagement throughout conversation flow"""
        
        if session_id not in self.step_response_history:
            return {"overall_engagement": 0.5}
        
        response_history = self.step_response_history[session_id]
        
        if not response_history:
            return {"overall_engagement": 0.5}
        
        engagement_metrics = {
            "response_quality": 0.5,
            "response_speed": 0.5,
            "information_richness": 0.5,
            "cooperation_level": 0.5,
            "overall_engagement": 0.5
        }
        
        # Calculate response quality trend
        quality_scores = [resp.get("response_quality", 0.5) for resp in response_history]
        engagement_metrics["response_quality"] = sum(quality_scores) / len(quality_scores)
        
        # Calculate information richness
        word_counts = [len(resp.get("customer_response", "").split()) for resp in response_history]
        avg_word_count = sum(word_counts) / len(word_counts) if word_counts else 0
        engagement_metrics["information_richness"] = min(1.0, avg_word_count / 10)  # Normalize to 10 words
        
        # Calculate cooperation level (yes vs no responses)
        response_types = [resp.get("response_analysis", {}).get("response_type", "unknown") for resp in response_history]
        positive_responses = sum(1 for rt in response_types if rt in ["yes", "detailed_answer"])
        cooperation_ratio = positive_responses / len(response_types) if response_types else 0.5
        engagement_metrics["cooperation_level"] = cooperation_ratio
        
        # Calculate overall engagement
        engagement_metrics["overall_engagement"] = (
            engagement_metrics["response_quality"] * 0.3 +
            engagement_metrics["information_richness"] * 0.3 +
            engagement_metrics["cooperation_level"] * 0.4
        )
        
        return engagement_metrics
    
    def adapt_conversation_response_handling(self, session_id: str, 
                                           adaptation_signals: Dict[str, Any]) -> Dict[str, Any]:
        """Adapt response handling based on conversation signals"""
        
        adaptations = {
            "response_tolerance": "normal",  # strict, normal, lenient
            "clarification_frequency": "normal",  # rare, normal, frequent
            "extraction_aggressiveness": "normal",  # conservative, normal, aggressive
            "follow_up_intensity": "normal"  # minimal, normal, detailed
        }
        
        engagement_level = adaptation_signals.get("engagement_level", 0.5)
        confusion_signals = adaptation_signals.get("confusion_signals", 0)
        time_pressure = adaptation_signals.get("time_pressure", False)
        
        # Adjust based on engagement
        if engagement_level < 0.3:
            adaptations["response_tolerance"] = "lenient"
            adaptations["clarification_frequency"] = "rare"
            adaptations["follow_up_intensity"] = "minimal"
        elif engagement_level > 0.8:
            adaptations["extraction_aggressiveness"] = "aggressive"
            adaptations["follow_up_intensity"] = "detailed"
        
        # Adjust based on confusion
        if confusion_signals > 2:
            adaptations["clarification_frequency"] = "frequent"
            adaptations["response_tolerance"] = "lenient"
        
        # Adjust based on time pressure
        if time_pressure:
            adaptations["extraction_aggressiveness"] = "aggressive"
            adaptations["clarification_frequency"] = "rare"
        
        return adaptations
    
    # ADDED: Private helper methods for conversation flow response handling
    
    def _init_conversation_response_patterns(self) -> Dict[str, List[str]]:
        """Initialize response patterns for conversation flows"""
        
        return {
            "affirmative": [
                "yes", "yeah", "yep", "sure", "absolutely", "definitely", 
                "of course", "certainly", "ok", "okay", "alright", "fine",
                "sounds good", "that works", "i agree", "go ahead"
            ],
            "negative": [
                "no", "nope", "not really", "don't think so", "i don't",
                "not interested", "not now", "maybe later", "not sure",
                "i can't", "won't work", "not for me"
            ],
            "uncertainty": [
                "maybe", "not sure", "i think", "possibly", "perhaps",
                "might", "could be", "i guess", "kind of", "sort of"
            ],
            "enthusiasm": [
                "excited", "love", "great", "awesome", "perfect", "amazing",
                "fantastic", "wonderful", "excellent", "brilliant"
            ],
            "concern": [
                "worried", "concerned", "nervous", "anxious", "hesitant",
                "unsure", "doubtful", "skeptical", "cautious"
            ],
            "information_request": [
                "tell me more", "explain", "how does", "what about",
                "can you", "details", "specifics", "more info"
            ]
        }
    
    def _classify_response_type(self, normalized_response: str, step_type: str, 
                              current_step: Dict[str, Any]) -> str:
        """Classify the type of customer response"""
        
        patterns = self.conversation_response_patterns
        
        # Check for affirmative responses
        if any(pattern in normalized_response for pattern in patterns["affirmative"]):
            return "yes"
        
        # Check for negative responses
        if any(pattern in normalized_response for pattern in patterns["negative"]):
            return "no"
        
        # Check for uncertainty
        if any(pattern in normalized_response for pattern in patterns["uncertainty"]):
            return "uncertain"
        
        # Check for information requests
        if any(pattern in normalized_response for pattern in patterns["information_request"]):
            return "information_request"
        
        # Step-specific classification
        if step_type == "booking":
            # Look for slot selection
            if re.search(r'\b[1-3]\b', normalized_response) or any(day in normalized_response for day in ["wednesday", "friday", "saturday"]):
                return "slot_selection"
        
        elif step_type == "qualification":
            # Look for detailed answers
            if len(normalized_response.split()) > 5:
                return "detailed_answer"
        
        # Check if response is off-topic
        step_keywords = self._get_step_keywords(current_step)
        if step_keywords and not any(keyword in normalized_response for keyword in step_keywords):
            if len(normalized_response.split()) > 3:  # Only for substantial responses
                return "off_topic"
        
        # Check for unclear/very short responses
        if len(normalized_response.strip()) < 3 or normalized_response in ["ok", "um", "uh", "well"]:
            return "unclear"
        
        return "general"
    
    def _extract_response_entities(self, customer_response: str) -> Dict[str, Any]:
        """Extract entities from customer response"""
        
        entities = {
            "numbers": [],
            "locations": [],
            "time_references": [],
            "business_terms": [],
            "amounts": []
        }
        
        # Extract numbers
        numbers = re.findall(r'\b\d+(?:\.\d+)?\b', customer_response)
        entities["numbers"] = [float(n) if '.' in n else int(n) for n in numbers]
        
        # Extract locations (simplified - would use NER in production)
        location_indicators = ["in", "at", "near", "around", "from"]
        words = customer_response.split()
        for i, word in enumerate(words):
            if word.lower() in location_indicators and i + 1 < len(words):
                entities["locations"].append(words[i + 1])
        
        # Extract time references
        time_patterns = [
            r'\b(?:next|this|last)\s+(?:week|month|year|quarter)\b',
            r'\b\d+\s+(?:days?|weeks?|months?|years?)\b',
            r'\b(?:soon|asap|immediately|quickly|slowly)\b'
        ]
        for pattern in time_patterns:
            matches = re.findall(pattern, customer_response, re.IGNORECASE)
            entities["time_references"].extend(matches)
        
        # Extract business terms
        business_keywords = [
            "franchise", "business", "restaurant", "outlet", "store", "location",
            "investment", "budget", "experience", "management", "operations"
        ]
        entities["business_terms"] = [word for word in customer_response.lower().split() 
                                    if word in business_keywords]
        
        # Extract amounts (money)
        amount_patterns = [
            r'\b(?:₹|rs\.?|rupees?)\s*\d+(?:,\d+)*(?:\.\d+)?\s*(?:lakhs?|crores?)?\b',
            r'\b\d+(?:,\d+)*(?:\.\d+)?\s*(?:lakhs?|crores?|thousands?)\b'
        ]
        for pattern in amount_patterns:
            matches = re.findall(pattern, customer_response, re.IGNORECASE)
            entities["amounts"].extend(matches)
        
        return entities
    
    def _analyze_response_sentiment(self, normalized_response: str) -> str:
        """Analyze sentiment of customer response"""
        
        patterns = self.conversation_response_patterns
        
        # Count positive and negative indicators
        positive_count = sum(1 for pattern in patterns["enthusiasm"] if pattern in normalized_response)
        negative_count = sum(1 for pattern in patterns["concern"] if pattern in normalized_response)
        
        # Add general positive/negative words
        positive_words = ["good", "great", "like", "love", "happy", "pleased", "satisfied"]
        negative_words = ["bad", "don't like", "hate", "disappointed", "unhappy", "dissatisfied"]
        
        positive_count += sum(1 for word in positive_words if word in normalized_response)
        negative_count += sum(1 for word in negative_words if word in normalized_response)
        
        if positive_count > negative_count:
            return "positive"
        elif negative_count > positive_count:
            return "negative"
        else:
            return "neutral"
    
    def _assess_response_clarity(self, customer_response: str) -> float:
        """Assess clarity of customer response"""
        
        clarity_score = 0.5
        
        # Length factor (too short or too long reduces clarity)
        length = len(customer_response.split())
        if 3 <= length <= 20:
            clarity_score += 0.2
        elif length < 3:
            clarity_score -= 0.3
        elif length > 30:
            clarity_score -= 0.1
        
        # Grammar indicators (simplified)
        if customer_response[0].isupper() and customer_response.endswith(('.', '!', '?')):
            clarity_score += 0.1
        
        # Complete sentences
        if re.search(r'\b(?:i|we|my|our)\b', customer_response.lower()):
            clarity_score += 0.1
        
        # Avoid filler words
        filler_words = ["um", "uh", "like", "you know", "basically", "actually"]
        filler_count = sum(1 for filler in filler_words if filler in customer_response.lower())
        clarity_score -= filler_count * 0.05
        
        return max(0.0, min(1.0, clarity_score))
    
    def _assess_response_completeness(self, customer_response: str, current_step: Dict[str, Any]) -> float:
        """Assess completeness of response relative to step requirements"""
        
        data_collection = current_step.get("data_collection", {})
        if not data_collection:
            return 1.0  # No specific data required
        
        completeness_score = 0.0
        
        # Check if response addresses each required data field
        response_lower = customer_response.lower()
        
        for field_name, field_type in data_collection.items():
            if field_type == "boolean":
                # Look for yes/no type responses
                if any(word in response_lower for word in ["yes", "no", "true", "false"]):
                    completeness_score += 1.0 / len(data_collection)
            elif field_type == "string":
                # Any substantial text counts
                if len(customer_response.strip()) > 5:
                    completeness_score += 1.0 / len(data_collection)
            elif field_type == "number":
                # Look for numbers
                if re.search(r'\d+', customer_response):
                    completeness_score += 1.0 / len(data_collection)
        
        return completeness_score
    
    def _calculate_response_confidence(self, response_analysis: Dict[str, Any]) -> float:
        """Calculate overall confidence in response analysis"""
        
        clarity = response_analysis.get("clarity", 0.5)
        completeness = response_analysis.get("completeness", 0.5)
        
        # Response type confidence
        response_type = response_analysis.get("response_type", "unknown")
        type_confidence = {
            "yes": 0.9, "no": 0.9, "detailed_answer": 0.8,
            "slot_selection": 0.9, "general": 0.6, "uncertain": 0.4,
            "unclear": 0.2, "off_topic": 0.3
        }.get(response_type, 0.5)
        
        # Sentiment confidence
        sentiment = response_analysis.get("sentiment", "neutral")
        sentiment_confidence = 0.8 if sentiment != "neutral" else 0.6
        
        # Overall confidence
        confidence = (clarity * 0.3 + completeness * 0.3 + type_confidence * 0.3 + sentiment_confidence * 0.1)
        
        return confidence
    
    def _apply_context_adjustments(self, next_step_decision: Dict[str, Any],
                                 conversation_context: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        """Apply conversation context adjustments to next step decision"""
        
        # Adjust based on conversation momentum
        momentum = conversation_context.get("conversation_momentum", 0.5)
        if momentum < 0.3 and next_step_decision["action"] == "continue":
            next_step_decision["special_handling"] = "rebuild_momentum"
        
        # Adjust based on time constraints
        if conversation_context.get("time_pressure", False):
            if next_step_decision["action"] == "repeat":
                next_step_decision["action"] = "continue"
                next_step_decision["reasoning"] += " (Skip clarification due to time pressure)"
        
        # Adjust based on customer engagement history
        if session_id in self.step_response_history:
            unclear_responses = sum(1 for resp in self.step_response_history[session_id] 
                                  if resp.get("response_analysis", {}).get("response_type") == "unclear")
            if unclear_responses > 2 and next_step_decision["action"] == "repeat":
                next_step_decision["special_handling"] = "simplify_question"
        
        return next_step_decision
    
    def _extract_field_data(self, customer_response: str, field_name: str, field_type: str,
                          extracted_entities: Dict[str, Any]) -> Any:
        """Extract specific field data from customer response"""
        
        response_lower = customer_response.lower()
        
        if field_type == "boolean":
            if any(word in response_lower for word in ["yes", "sure", "okay", "absolutely", "definitely"]):
                return True
            elif any(word in response_lower for word in ["no", "not", "don't", "can't", "won't"]):
                return False
            else:
                return None
        
        elif field_type == "string":
            # Return cleaned response
            return customer_response.strip()
        
        elif field_type == "number":
            numbers = extracted_entities.get("numbers", [])
            return numbers[0] if numbers else None
        
        elif field_type == "array":
            # Split on common delimiters
            delimiters = [",", "and", "&", "+"]
            result = [customer_response.strip()]
            for delimiter in delimiters:
                if delimiter in customer_response:
                    result = [item.strip() for item in customer_response.split(delimiter)]
                    break
            return result
        
        return customer_response.strip()
    
    def _extract_experience_data(self, customer_response: str, entities: Dict[str, Any]) -> Dict[str, Any]:
        """Extract business experience specific data"""
        
        experience_data = {}
        response_lower = customer_response.lower()
        
        # Extract years of experience
        numbers = entities.get("numbers", [])
        if numbers:
            experience_data["experience_years"] = numbers[0]
        
        # Extract type of experience
        business_types = ["restaurant", "food", "retail", "franchise", "business", "store", "cafe"]
        mentioned_types = [btype for btype in business_types if btype in response_lower]
        if mentioned_types:
            experience_data["experience_type"] = mentioned_types[0]
        
        # Extract management level
        management_terms = ["owner", "manager", "director", "ceo", "founder", "partner"]
        mentioned_roles = [role for role in management_terms if role in response_lower]
        if mentioned_roles:
            experience_data["management_level"] = mentioned_roles[0]
        
        return experience_data
    
    def _extract_investment_data(self, customer_response: str, entities: Dict[str, Any]) -> Dict[str, Any]:
        """Extract investment comfort specific data"""
        
        investment_data = {}
        response_lower = customer_response.lower()
        
        # Extract specific amounts mentioned
        amounts = entities.get("amounts", [])
        if amounts:
            investment_data["mentioned_amounts"] = amounts
        
        # Extract budget concerns
        concern_indicators = ["tight", "limited", "small", "conservative", "careful"]
        if any(indicator in response_lower for indicator in concern_indicators):
            investment_data["budget_concerns"] = True
        
        # Extract financing needs
        financing_terms = ["loan", "finance", "financing", "bank", "credit", "payment plan"]
        if any(term in response_lower for term in financing_terms):
            investment_data["needs_financing"] = True
        
        return investment_data
    
    def _extract_location_data(self, customer_response: str, entities: Dict[str, Any]) -> Dict[str, Any]:
        """Extract location specific data"""
        
        location_data = {}
        
        # Extract mentioned locations
        locations = entities.get("locations", [])
        if locations:
            location_data["mentioned_locations"] = locations
        
        # Extract location status
        response_lower = customer_response.lower()
        if any(phrase in response_lower for phrase in ["already have", "own", "identified", "found"]):
            location_data["has_location"] = True
        elif any(phrase in response_lower for phrase in ["need help", "assistance", "suggest", "recommend"]):
            location_data["needs_location_help"] = True
        
        return location_data
    
    def _extract_timeline_data(self, customer_response: str, entities: Dict[str, Any]) -> Dict[str, Any]:
        """Extract timeline specific data"""
        
        timeline_data = {}
        
        # Extract time references
        time_refs = entities.get("time_references", [])
        if time_refs:
            timeline_data["time_references"] = time_refs
        
        # Extract urgency level
        response_lower = customer_response.lower()
        if any(word in response_lower for word in ["asap", "urgent", "quickly", "soon", "immediately"]):
            timeline_data["urgency_level"] = "high"
        elif any(word in response_lower for word in ["no rush", "flexible", "whenever", "eventually"]):
            timeline_data["urgency_level"] = "low"
        else:
            timeline_data["urgency_level"] = "medium"
        
        return timeline_data
    
    def _extract_outlet_data(self, customer_response: str, entities: Dict[str, Any]) -> Dict[str, Any]:
        """Extract outlet count specific data"""
        
        outlet_data = {}
        
        # Extract numbers
        numbers = entities.get("numbers", [])
        if numbers:
            outlet_data["outlet_count"] = numbers[0]
        
        # Extract expansion plans
        response_lower = customer_response.lower()
        if any(word in response_lower for word in ["multiple", "several", "many", "expand", "growth"]):
            outlet_data["expansion_plans"] = True
        elif any(word in response_lower for word in ["one", "single", "start with one"]):
            outlet_data["expansion_plans"] = False
        
        return outlet_data
    
    def _extract_motivation_data(self, customer_response: str, entities: Dict[str, Any]) -> Dict[str, Any]:
        """Extract motivation specific data"""
        
        motivation_data = {}
        
        # Extract key interests
        interests = []
        response_lower = customer_response.lower()
        
        interest_keywords = {
            "financial": ["money", "profit", "income", "financial", "earnings"],
            "independence": ["own", "boss", "independent", "freedom", "control"],
            "growth": ["growth", "expand", "scale", "build", "develop"],
            "passion": ["love", "passion", "enjoy", "excited", "interested"],
            "family": ["family", "legacy", "children", "future", "generations"]
        }
        
        for category, keywords in interest_keywords.items():
            if any(keyword in response_lower for keyword in keywords):
                interests.append(category)
        
        motivation_data["key_interests"] = interests
        motivation_data["motivation_text"] = customer_response.strip()
        
        return motivation_data
    
    def _get_step_keywords(self, current_step: Dict[str, Any]) -> List[str]:
        """Get relevant keywords for current step to detect off-topic responses"""
        
        step_id = current_step["step_id"]
        
        keyword_map = {
            "experience": ["business", "experience", "restaurant", "food", "retail", "management"],
            "investment_comfort": ["investment", "money", "budget", "cost", "comfortable", "afford"],
            "location": ["location", "place", "where", "site", "area", "city"],
            "timeline": ["time", "when", "timeline", "decision", "start", "launch"],
            "outlet_count": ["outlet", "store", "location", "one", "multiple", "how many"],
            "motivation": ["excited", "why", "motivation", "interest", "reason"]
        }
        
        return keyword_map.get(step_id, [])
    
    def _store_response_history(self, session_id: str, customer_response: str,
                              current_step: Dict[str, Any], response_analysis: Dict[str, Any]) -> None:
        """Store response history for analysis"""
        
        if session_id not in self.step_response_history:
            self.step_response_history[session_id] = []
        
        history_entry = {
            "step_id": current_step["step_id"],
            "customer_response": customer_response,
            "response_analysis": response_analysis,
            "response_quality": self._assess_response_quality(customer_response, current_step),
            "timestamp": datetime.now()
        }
        
        self.step_response_history[session_id].append(history_entry)
        
        # Limit history size
        if len(self.step_response_history[session_id]) > 50:
            self.step_response_history[session_id] = self.step_response_history[session_id][-50:]
    
    def _assess_response_quality(self, customer_response: str, current_step: Dict[str, Any]) -> float:
        """Assess overall quality of customer response"""
        
        quality_score = 0.5
        
        # Length appropriateness
        length = len(customer_response.split())
        if 2 <= length <= 25:
            quality_score += 0.2
        elif length == 1:
            quality_score -= 0.2
        elif length > 50:
            quality_score -= 0.1
        
        # Relevance to step
        step_keywords = self._get_step_keywords(current_step)
        if step_keywords:
            relevance = sum(1 for keyword in step_keywords if keyword in customer_response.lower())
            quality_score += min(0.3, relevance * 0.1)
        
        # Information content
        if re.search(r'\b(?:because|since|due to|reason|because of)\b', customer_response.lower()):
            quality_score += 0.1  # Explanatory content
        
        return max(0.0, min(1.0, quality_score))
    
    def _calculate_conversation_momentum(self, session_id: str) -> float:
        """Calculate conversation momentum based on response history"""
        
        if session_id not in self.step_response_history:
            return 0.5
        
        history = self.step_response_history[session_id]
        if not history:
            return 0.5
        
        # Recent response quality
        recent_responses = history[-3:] if len(history) >= 3 else history
        avg_quality = sum(resp["response_quality"] for resp in recent_responses) / len(recent_responses)
        
        # Response consistency
        response_types = [resp["response_analysis"]["response_type"] for resp in recent_responses]
        clear_responses = sum(1 for rt in response_types if rt not in ["unclear", "off_topic"])
        consistency = clear_responses / len(response_types) if response_types else 0.5
        
        # Overall momentum
        momentum = (avg_quality * 0.6 + consistency * 0.4)
        
        return momentum
    
    def _get_fallback_response_handling(self, customer_response: str, current_step: Dict[str, Any]) -> Dict[str, Any]:
        """Get fallback response handling when main processing fails"""
        
        return {
            "response_analysis": {
                "original_response": customer_response,
                "response_type": "unclear",
                "confidence": 0.3,
                "fallback_used": True
            },
            "next_step_decision": {
                "action": "repeat",
                "reasoning": "Processing error, requesting clarification",
                "confidence": 0.3,
                "special_handling": "clarification_needed"
            },
            "qualification_data": {
                "raw_response": customer_response,
                "_metadata": {"fallback_extraction": True}
            },
            "processing_confidence": 0.3,
            "response_quality": 0.3,
            "conversation_momentum": 0.3
        }

class PitchOutcomeAnalyzer:
    """Analyzes pitch outcomes and determines next steps"""
    
    def __init__(self):
        self.outcome_criteria = self._init_outcome_criteria()
        self.logger = logging.getLogger(__name__)
    
    def assess_pitch_effectiveness(
        self, 
        customer_response: Dict[str, Any], 
        engagement_metrics: Dict[str, float], 
        stated_interest: str
    ) -> PitchOutcome:
        """Assess overall effectiveness of the pitch"""
        
        # Calculate interest level
        interest_score = self._calculate_interest_score(customer_response, stated_interest)
        
        # Compile engagement metrics
        compiled_engagement = {
            "average_engagement": sum(engagement_metrics.values()) / len(engagement_metrics) if engagement_metrics else 0.5,
            "peak_engagement": max(engagement_metrics.values()) if engagement_metrics else 0.5,
            "engagement_consistency": self._calculate_engagement_consistency(engagement_metrics)
        }
        
        # Extract customer questions and objections
        questions = customer_response.get("questions_asked", [])
        objections = customer_response.get("objections_raised", [])
        
        # Determine next steps
        next_steps = self._determine_next_steps(interest_score, compiled_engagement, questions, objections)
        
        # Identify follow-up requirements
        follow_up_requirements = self._identify_follow_up_requirements(customer_response, questions)
        
        # Identify success indicators
        success_indicators = self._identify_success_indicators(customer_response, engagement_metrics)
        
        outcome = PitchOutcome(
            interest_level=interest_score,
            engagement_metrics=compiled_engagement,
            customer_questions=questions,
            objections_raised=objections,
            next_steps=next_steps,
            follow_up_requirements=follow_up_requirements,
            success_indicators=success_indicators
        )
        
        return outcome
    
    def identify_follow_up_requirements(
        self, 
        customer_questions: List[str], 
        information_gaps: List[str], 
        next_step_needs: List[str]
    ) -> List[str]:
        """Identify specific follow-up requirements"""
        
        requirements = []
        
        # Question-based requirements
        for question in customer_questions:
            question_lower = question.lower()
            
            if "price" in question_lower or "cost" in question_lower:
                requirements.append("Prepare detailed pricing proposal")
            elif "technical" in question_lower or "integration" in question_lower:
                requirements.append("Technical deep-dive session required")
            elif "timeline" in question_lower or "implementation" in question_lower:
                requirements.append("Implementation timeline and project plan")
            elif "reference" in question_lower or "case study" in question_lower:
                requirements.append("Relevant customer references and case studies")
        
        # Information gap requirements
        for gap in information_gaps:
            gap_requirements = {
                "decision_process": "Understand decision-making process and stakeholders",
                "budget": "Budget qualification and approval process",
                "timeline": "Project timeline and decision timeline",
                "technical_requirements": "Detailed technical requirements gathering",
                "competitive_landscape": "Competitive analysis and positioning"
            }
            
            if gap in gap_requirements:
                requirements.append(gap_requirements[gap])
        
        # Next step requirements
        for need in next_step_needs:
            need_requirements = {
                "demo": "Schedule product demonstration",
                "proposal": "Prepare formal proposal",
                "trial": "Set up trial or pilot program",
                "stakeholder_meeting": "Multi-stakeholder presentation",
                "technical_review": "Technical architecture review"
            }
            
            if need in need_requirements:
                requirements.append(need_requirements[need])
        
        return list(set(requirements))  # Remove duplicates
    
    def capture_pitch_feedback_for_optimization(
        self, 
        customer_response: Dict[str, Any], 
        pitch_variant_used: str, 
        outcome_metrics: Dict[str, float]
    ) -> Dict[str, Any]:
        """Capture feedback for pitch optimization"""
        
        feedback_data = {
            "pitch_variant": pitch_variant_used,
            "outcome_metrics": outcome_metrics,
            "customer_feedback": customer_response,
            "effectiveness_score": outcome_metrics.get("overall_effectiveness", 0.5),
            "optimization_insights": [],
            "variant_performance": {},
            "timestamp": datetime.now()
        }
        
        # Generate optimization insights
        if outcome_metrics.get("engagement_score", 0.5) < 0.5:
            feedback_data["optimization_insights"].append("Consider more interactive elements")
        
        if outcome_metrics.get("comprehension_score", 0.5) < 0.6:
            feedback_data["optimization_insights"].append("Simplify technical explanations")
        
        if outcome_metrics.get("relevance_score", 0.5) < 0.7:
            feedback_data["optimization_insights"].append("Better customer context integration needed")
        
        # Analyze customer verbal feedback
        positive_feedback = customer_response.get("positive_comments", [])
        negative_feedback = customer_response.get("concerns_raised", [])
        
        if len(positive_feedback) > len(negative_feedback):
            feedback_data["optimization_insights"].append("Pitch structure effective - maintain approach")
        else:
            feedback_data["optimization_insights"].append("Review pitch structure and content")
        
        # Variant performance tracking
        feedback_data["variant_performance"] = {
            "structure_effectiveness": outcome_metrics.get("structure_score", 0.5),
            "content_relevance": outcome_metrics.get("relevance_score", 0.5),
            "delivery_quality": outcome_metrics.get("delivery_score", 0.5),
            "customer_resonance": outcome_metrics.get("resonance_score", 0.5)
        }
        
        return feedback_data
    
    def transition_from_pitch_to_next_flow(
        self, 
        pitch_outcome: PitchOutcome, 
        customer_state: Dict[str, Any], 
        conversation_objectives: List[str]
    ) -> Dict[str, Any]:
        """Determine transition from pitch to next conversation flow"""
        
        transition_plan = {
            "next_flow": FlowType.KNOWLEDGE,  # Default
            "transition_reason": "",
            "context_to_preserve": {},
            "flow_priority": 0.5,
            "transition_timing": "immediate"
        }
        
        # Determine next flow based on pitch outcome
        if pitch_outcome.interest_level >= 0.8:
            if pitch_outcome.objections_raised:
                transition_plan["next_flow"] = FlowType.OBJECTION
                transition_plan["transition_reason"] = "High interest but objections need addressing"
            else:
                transition_plan["next_flow"] = FlowType.CLOSING
                transition_plan["transition_reason"] = "High interest - move to closing"
                transition_plan["flow_priority"] = 0.9
        
        elif pitch_outcome.interest_level >= 0.6:
            if pitch_outcome.customer_questions:
                transition_plan["next_flow"] = FlowType.KNOWLEDGE
                transition_plan["transition_reason"] = "Questions indicate need for more information"
            else:
                transition_plan["next_flow"] = FlowType.DISCOVERY
                transition_plan["transition_reason"] = "Moderate interest - deeper discovery needed"
        
        elif pitch_outcome.interest_level >= 0.4:
            transition_plan["next_flow"] = FlowType.DISCOVERY
            transition_plan["transition_reason"] = "Low interest - return to discovery"
            transition_plan["transition_timing"] = "gradual"
        
        else:
            transition_plan["next_flow"] = FlowType.RELATIONSHIP
            transition_plan["transition_reason"] = "Very low interest - focus on relationship building"
            transition_plan["transition_timing"] = "gentle"
        
        # Context to preserve
        transition_plan["context_to_preserve"] = {
            "pitch_outcome": asdict(pitch_outcome),
            "customer_interests_identified": customer_state.get("interests", []),
            "objections_for_follow_up": pitch_outcome.objections_raised,
            "questions_for_follow_up": pitch_outcome.customer_questions,
            "engagement_pattern": pitch_outcome.engagement_metrics
        }
        
        # Align with conversation objectives
        for objective in conversation_objectives:
            if objective == "close_sale" and pitch_outcome.interest_level >= 0.7:
                transition_plan["next_flow"] = FlowType.CLOSING
                transition_plan["flow_priority"] = 0.9
            elif objective == "educate_customer" and pitch_outcome.customer_questions:
                transition_plan["next_flow"] = FlowType.KNOWLEDGE
                transition_plan["flow_priority"] = 0.8
        
        return transition_plan
    
    def handle_unsuccessful_pitch_outcomes(
        self, 
        low_interest: float, 
        objections_raised: List[str], 
        conversation_recovery_options: List[str]
    ) -> Dict[str, Any]:
        """Handle unsuccessful pitch outcomes and recovery strategies"""
        
        recovery_strategy = {
            "primary_approach": "",
            "recovery_actions": [],
            "conversation_pivot": None,
            "relationship_preservation": [],
            "future_opportunity_setup": []
        }
        
        # Determine primary approach based on interest level
        if low_interest < 0.2:
            recovery_strategy["primary_approach"] = "graceful_exit"
            recovery_strategy["relationship_preservation"].append("Thank for time and openness")
            recovery_strategy["future_opportunity_setup"].append("Leave door open for future")
        
        elif low_interest < 0.4:
            recovery_strategy["primary_approach"] = "value_pivot"
            recovery_strategy["recovery_actions"].append("Explore different value angles")
            recovery_strategy["conversation_pivot"] = FlowType.DISCOVERY
        
        # Handle specific objections
        objection_strategies = {
            "price": "Focus on ROI and value demonstration",
            "timing": "Explore future timeline and preparation steps",
            "fit": "Deeper discovery to understand requirements",
            "authority": "Identify true decision makers",
            "need": "Revisit problem identification"
        }
        
        for objection in objections_raised:
            objection_lower = objection.lower()
            for key, strategy in objection_strategies.items():
                if key in objection_lower:
                    recovery_strategy["recovery_actions"].append(strategy)
        
        # Recovery options analysis
        for option in conversation_recovery_options:
            if option == "return_to_discovery":
                recovery_strategy["conversation_pivot"] = FlowType.DISCOVERY
            elif option == "educational_approach":
                recovery_strategy["conversation_pivot"] = FlowType.KNOWLEDGE
            elif option == "relationship_focus":
                recovery_strategy["conversation_pivot"] = FlowType.RELATIONSHIP
        
        # Future opportunity setup
        if low_interest >= 0.3:  # Some potential for future
            recovery_strategy["future_opportunity_setup"].extend([
                "Establish follow-up timeline",
                "Provide relevant resources",
                "Maintain periodic contact"
            ])
        
        return recovery_strategy
    
    def _calculate_interest_score(self, customer_response: Dict[str, Any], stated_interest: str) -> float:
        """Calculate overall customer interest score"""
        
        # Base score from stated interest
        interest_mapping = {
            "very_interested": 0.9,
            "interested": 0.7,
            "somewhat_interested": 0.5,
            "not_very_interested": 0.3,
            "not_interested": 0.1
        }
        
        base_score = interest_mapping.get(stated_interest.lower(), 0.5)
        
        # Adjustments based on behavior
        behavioral_indicators = customer_response.get("behavioral_indicators", {})
        
        # Positive adjustments
        if behavioral_indicators.get("asked_follow_up_questions", False):
            base_score += 0.1
        if behavioral_indicators.get("requested_more_information", False):
            base_score += 0.1
        if behavioral_indicators.get("discussed_timeline", False):
            base_score += 0.15
        if behavioral_indicators.get("mentioned_budget", False):
            base_score += 0.1
        
        # Negative adjustments
        if behavioral_indicators.get("expressed_concerns", False):
            base_score -= 0.1
        if behavioral_indicators.get("short_responses", False):
            base_score -= 0.05
        if behavioral_indicators.get("tried_to_end_call", False):
            base_score -= 0.2
        
        return max(0.0, min(1.0, base_score))
    
    def _calculate_engagement_consistency(self, engagement_metrics: Dict[str, float]) -> float:
        """Calculate consistency of engagement throughout pitch"""
        if not engagement_metrics:
            return 0.5
        
        values = list(engagement_metrics.values())
        if len(values) < 2:
            return 1.0
        
        # Calculate variance
        mean_engagement = sum(values) / len(values)
        variance = sum((x - mean_engagement) ** 2 for x in values) / len(values)
        
        # Convert variance to consistency score (lower variance = higher consistency)
        consistency = max(0.0, 1.0 - variance)
        return consistency
    
    def _determine_next_steps(
        self, 
        interest_score: float, 
        engagement_metrics: Dict[str, float], 
        questions: List[str], 
        objections: List[str]
    ) -> List[str]:
        """Determine appropriate next steps based on pitch outcome"""
        
        next_steps = []
        
        # Interest-based next steps
        if interest_score >= 0.8:
            next_steps.append("Schedule detailed proposal meeting")
            next_steps.append("Arrange stakeholder presentation")
        elif interest_score >= 0.6:
            next_steps.append("Provide additional information")
            next_steps.append("Schedule follow-up demo")
        elif interest_score >= 0.4:
            next_steps.append("Educational follow-up")
            next_steps.append("Nurture relationship")
        else:
            next_steps.append("Long-term relationship building")
        
        # Question-based next steps
        if questions:
            if any("technical" in q.lower() for q in questions):
                next_steps.append("Technical deep-dive session")
            if any("price" in q.lower() for q in questions):
                next_steps.append("Budget and pricing discussion")
        
        # Objection-based next steps
        if objections:
            next_steps.append("Address remaining concerns")
            if len(objections) > 2:
                next_steps.append("Stakeholder alignment meeting")
        
        return next_steps[:3]  # Limit to top 3 next steps
    
    def _identify_follow_up_requirements(
        self, 
        customer_response: Dict[str, Any], 
        questions: List[str]
    ) -> List[str]:
        """Identify specific follow-up requirements"""
        
        requirements = []
        
        # Based on customer response
        if customer_response.get("requested_references"):
            requirements.append("Customer reference contacts")
        
        if customer_response.get("requested_case_studies"):
            requirements.append("Relevant case studies")
        
        if customer_response.get("technical_questions_count", 0) > 2:
            requirements.append("Technical documentation")
        
        # Based on questions asked
        question_requirements = {
            "integration": "Integration documentation",
            "security": "Security compliance information",
            "support": "Support and service details",
            "training": "Training and onboarding information"
        }
        
        for question in questions:
            question_lower = question.lower()
            for keyword, requirement in question_requirements.items():
                if keyword in question_lower and requirement not in requirements:
                    requirements.append(requirement)
        
        return requirements
    
    def _identify_success_indicators(
        self, 
        customer_response: Dict[str, Any], 
        engagement_metrics: Dict[str, float]
    ) -> List[str]:
        """Identify positive indicators from the pitch"""
        
        indicators = []
        
        # Engagement-based indicators
        avg_engagement = sum(engagement_metrics.values()) / len(engagement_metrics) if engagement_metrics else 0.5
        if avg_engagement > 0.7:
            indicators.append("High engagement throughout pitch")
        
        # Response-based indicators
        if customer_response.get("positive_comments"):
            indicators.append("Positive verbal feedback received")
        
        if customer_response.get("questions_asked"):
            indicators.append("Customer actively engaged with questions")
        
        if customer_response.get("discussed_next_steps"):
            indicators.append("Customer interested in next steps")
        
        if customer_response.get("timeline_discussion"):
            indicators.append("Timeline discussion indicates buying interest")
        
        if customer_response.get("stakeholder_mention"):
            indicators.append("Customer mentioned involving other stakeholders")
        
        return indicators
    
    def _init_outcome_criteria(self) -> Dict[str, Dict[str, float]]:
        """Initialize criteria for evaluating pitch outcomes"""
        return {
            "success_thresholds": {
                "interest_level": 0.6,
                "engagement_consistency": 0.5,
                "question_engagement": 0.4
            },
            "warning_thresholds": {
                "interest_level": 0.3,
                "engagement_consistency": 0.3,
                "objection_ratio": 0.5
            }
        }
class PitchAdaptationEngine(IFlowEngine):  # ADDED: Direct interface implementation
    """
    ENHANCED ORIGINAL CLASS - composed of original components + integration
    No wrapper - direct enhancement with interface methods
    """
    
    def __init__(self):
        # ORIGINAL: Composition of specialized components (unchanged)
        self.readiness_assessor = PitchReadinessAssessor()
        self.pitch_customizer = PitchCustomizer()
        self.delivery_manager = PitchDeliveryManager()
        self.response_handler = PitchResponseHandler()
        self.outcome_analyzer = PitchOutcomeAnalyzer()
        
        # ADDED: Integration state management only
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        self.logger = logging.getLogger(__name__)
    
    # ALL ORIGINAL COMPONENT METHODS STAY THE SAME:
    # PitchReadinessAssessor methods, PitchCustomizer methods, etc.
    # are accessed via self.readiness_assessor.method(), etc.
    
    # ADDED: IFlowEngine interface methods only
    
    def can_handle_flow(self, flow_type: FlowType) -> bool:
        """INTERFACE METHOD: Check flow capability"""
        return flow_type == FlowType.PITCH
    
    def initialize_flow(self, session_id: str, customer_context: CustomerContext, 
                       flow_context: Dict[str, Any]) -> Dict[str, Any]:
        """INTERFACE METHOD: Coordinate original components for initialization"""
        
        # Use ORIGINAL components in coordinated way
        conversation_context = {
            "start_time": flow_context.get("conversation_start_time", datetime.now()),
            "engagement_level": flow_context.get("customer_readiness", 0.5),
            "discovery_phase_complete": len(flow_context.get("discovered_needs", [])) > 0,
            "customer_context": customer_context
        }
        
        # ORIGINAL: Use readiness_assessor (no changes to component)
        is_ready, readiness_score, reason = self.readiness_assessor.evaluate_pitch_timing(
            conversation_context, flow_context.get("readiness_signals", [])
        )
        
        if not is_ready:
            return {"status": "not_ready", "reason": reason, "readiness_score": readiness_score}
        
        # ORIGINAL: Use pitch_customizer (no changes to component)
        value_proposition = self.pitch_customizer.customize_value_proposition(
            customer_context, 
            flow_context.get("discovered_needs", []), 
            customer_context.competitive_landscape
        )
        
        proof_points = self.pitch_customizer.select_relevant_proof_points(
            customer_context.industry, 0.8, ["credibility", "relevance"]
        )
        
        # ORIGINAL: Use delivery_manager (no changes to component)
        pitch_content = PitchContent(
            value_proposition=value_proposition,
            proof_points=[pp.get("content", "") for pp in proof_points],
            competitive_positioning=flow_context.get("competitive_positioning", []),
            solution_benefits=flow_context.get("solution_benefits", [])
        )
        
        delivery_plan = self.delivery_manager.structure_pitch_for_voice_delivery(
            pitch_content, flow_context.get("conversation_pacing", {"words_per_minute": 150})
        )
        
        # ADDED: Store session state for integration
        self.active_sessions[session_id] = {
            "pitch_content": pitch_content,
            "delivery_plan": delivery_plan,
            "current_segment": 0,
            "customer_responses": [],
            "start_time": datetime.now()
        }
        
        return {
            "status": "initialized",
            "readiness_score": readiness_score,
            "estimated_duration": delivery_plan.get("total_estimated_duration", 300),
            "value_proposition": value_proposition,
            "next_action": "begin_pitch_delivery"
        }
    
    def execute_flow_segment(self, session_id: str, customer_input: str, 
                           segment_context: Dict[str, Any]) -> Dict[str, Any]:
        """INTERFACE METHOD: Coordinate original components for execution"""
        
        if session_id not in self.active_sessions:
            return {"error": "Session not initialized"}
        
        session_data = self.active_sessions[session_id]
        
        # ORIGINAL: Use response_handler (no changes to component)
        engagement_metrics = self.response_handler.monitor_customer_interest_signals(
            {"customer_speech": customer_input}, 
            session_data.get("engagement_metrics", {})
        )
        
        # ORIGINAL: Use delivery_manager (no changes to component)
        current_segment = session_data["current_segment"]
        segments = session_data["delivery_plan"].get("segments", [])
        
        if current_segment >= len(segments):
            return self._finalize_pitch_delivery(session_id)
        
        segment_info = segments[current_segment]
        
        delivery_result = self.delivery_manager.deliver_knowledge_segment(
            session_data["pitch_content"],
            segment_context.get("delivery_style", "conversational"),
            segment_context
        )
        
        progression_decision = self.delivery_manager.manage_pitch_segment_progression(
            segment_info.get("name", ""), 
            {"customer_response": customer_input}, 
            segments[current_segment + 1:]
        )
        
        # Update session state
        if progression_decision["action"] == "continue":
            session_data["current_segment"] += 1
        
        session_data["engagement_metrics"] = engagement_metrics
        session_data["customer_responses"].append({
            "content": customer_input,
            "timestamp": datetime.now(),
            "engagement": engagement_metrics.get("overall_engagement", 0.5)
        })
        
        return {
            "status": "segment_completed",
            "segment_delivered": segment_info.get("name", f"segment_{current_segment}"),
            "engagement_metrics": engagement_metrics,
            "progression_decision": progression_decision,
            "segments_remaining": len(segments) - current_segment - 1
        }
    
    def handle_interruption(self, session_id: str, interruption_type: str) -> Dict[str, Any]:
        """INTERFACE METHOD: Use original delivery_manager for interruptions"""
        
        if session_id not in self.active_sessions:
            return {"error": "Session not found"}
        
        session_data = self.active_sessions[session_id]
        
        # ORIGINAL: Use delivery_manager (no changes to component)
        remaining_segments = session_data["delivery_plan"].get("segments", [])[session_data["current_segment"]:]
        
        interruption_response = self.delivery_manager.handle_pitch_interruptions(
            interruption_type, {}, remaining_segments
        )
        
        return {
            "status": "interruption_handled",
            "interruption_type": interruption_type,
            "immediate_action": interruption_response["immediate_action"],
            "resumption_strategy": interruption_response["resumption_strategy"]
        }
    
    def finalize_flow(self, session_id: str) -> Dict[str, Any]:
        """INTERFACE METHOD: Use original outcome_analyzer for finalization"""
        
        if session_id not in self.active_sessions:
            return {"error": "Session not found"}
        
        session_data = self.active_sessions[session_id]
        
        # ORIGINAL: Use outcome_analyzer (no changes to component)
        customer_responses = session_data["customer_responses"]
        engagement_metrics = session_data.get("engagement_metrics", {})
        
        stated_interest = "somewhat_interested"  # Would extract from responses
        
        pitch_outcome = self.outcome_analyzer.assess_pitch_effectiveness(
            {"customer_responses": customer_responses}, 
            engagement_metrics, 
            stated_interest
        )
        
        follow_up_requirements = self.outcome_analyzer.identify_follow_up_requirements(
            [r.get("content", "") for r in customer_responses], [], ["next_steps"]
        )
        
        transition_plan = self.outcome_analyzer.transition_from_pitch_to_next_flow(
            pitch_outcome, {}, ["close_deal"]
        )
        
        # Calculate performance metrics
        performance_metrics = {
            "effectiveness_score": pitch_outcome.interest_level,
            "engagement_score": engagement_metrics.get("overall_engagement", 0.5),
            "completion_rate": session_data["current_segment"] / len(session_data["delivery_plan"].get("segments", [1])),
            "duration": (datetime.now() - session_data["start_time"]).total_seconds()
        }
        
        # ADDED: Cleanup session
        final_result = {
            "session_id": session_id,
            "status": "completed",
            "pitch_outcome": {
                "interest_level": pitch_outcome.interest_level,
                "engagement_metrics": pitch_outcome.engagement_metrics,
                "next_steps": pitch_outcome.next_steps,
                "follow_up_requirements": pitch_outcome.follow_up_requirements
            },
            "transition_recommendation": transition_plan,
            "performance_metrics": performance_metrics,
            "effectiveness_score": performance_metrics["effectiveness_score"]
        }
        
        del self.active_sessions[session_id]
        return final_result
    
    def get_flow_status(self, session_id: str) -> Dict[str, Any]:
        """INTERFACE METHOD: Get current status"""
        
        if session_id not in self.active_sessions:
            return {"status": "not_active"}
        
        session_data = self.active_sessions[session_id]
        segments = session_data["delivery_plan"].get("segments", [])
        current_segment = session_data["current_segment"]
        
        return {
            "session_id": session_id,
            "status": "active",
            "current_segment": current_segment,
            "total_segments": len(segments),
            "completion_percentage": (current_segment / len(segments)) * 100 if segments else 0,
            "customer_engagement": session_data.get("engagement_metrics", {}).get("overall_engagement", 0.5),
            "response_count": len(session_data["customer_responses"])
        }
    
    # ADDED: Private helper methods for integration only
    
    def _finalize_pitch_delivery(self, session_id: str) -> Dict[str, Any]:
        """Handle completion of all pitch segments"""
        session_data = self.active_sessions[session_id]
        
        completion_rate = session_data["current_segment"] / len(session_data["delivery_plan"].get("segments", [1]))
        final_engagement = session_data.get("engagement_metrics", {}).get("overall_engagement", 0.5)
        
        if final_engagement > 0.7:
            next_action = "transition_to_closing"
        elif final_engagement > 0.4:
            next_action = "handle_questions_and_objections"
        else:
            next_action = "return_to_discovery"
        
        return {
            "status": "pitch_delivery_completed",
            "completion_rate": completion_rate,
            "final_engagement": final_engagement,
            "next_action": next_action
        }