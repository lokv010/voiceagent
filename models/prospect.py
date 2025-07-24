from sqlalchemy.orm import sessionmaker
from sqlalchemy import and_, or_, desc
from datetime import datetime, timedelta
from models.database import Prospect, CallHistory, Campaign, ProspectSource
import logging

class ProspectManager:
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.session = db_manager.get_session()
    
    def create_prospect_from_form(self, form_data):
        """Create prospect from form submission"""
        try:
            # Check if prospect already exists
            existing_prospect = self.session.query(Prospect).filter(
                Prospect.phone_number == form_data.get('phone')
            ).first()
            
            if existing_prospect:
                # Update existing prospect with new form data
                existing_prospect.form_data = form_data
                existing_prospect.form_submitted_at = datetime.utcnow()
                existing_prospect.product_interest = form_data.get('product')
                existing_prospect.product_category = self.categorize_product(form_data.get('product'))
                existing_prospect.qualification_score = max(existing_prospect.qualification_score, 25)
                self.session.commit()
                return existing_prospect
            
            # Create new prospect
            prospect = Prospect(
                phone_number=form_data.get('phone'),
                email=form_data.get('email'),
                name=form_data.get('name'),
                source=ProspectSource.FORM_SUBMISSION.value,
                source_data=form_data,
                product_interest=form_data.get('product'),
                product_category=self.categorize_product(form_data.get('product')),
                form_submitted_at=datetime.utcnow(),
                form_data=form_data,
                qualification_score=25,  # Warm lead base score
                call_status='pending'
            )
            
            self.session.add(prospect)
            self.session.commit()
            
            logging.info(f"Created prospect from form: {prospect.id}")
            return prospect
            
        except Exception as e:
            logging.error(f"Error creating prospect from form: {str(e)}")
            self.session.rollback()
            raise
    
    def create_prospect_from_cold_list(self, lead_data):
        """Create prospect from cold lead list"""
        try:
            prospect = Prospect(
                phone_number=lead_data.get('phone'),
                name=lead_data.get('name'),
                email=lead_data.get('email'),
                company=lead_data.get('company'),
                job_title=lead_data.get('job_title'),
                industry=lead_data.get('industry'),
                source=ProspectSource.COLD_LIST.value,
                source_data=lead_data,
                product_interest=lead_data.get('target_product'),
                product_category=self.categorize_product(lead_data.get('target_product')),
                qualification_score=0,  # Cold lead base score
                call_status='pending'
            )
            
            self.session.add(prospect)
            self.session.commit()
            
            logging.info(f"Created cold prospect: {prospect.id}")
            return prospect
            
        except Exception as e:
            logging.error(f"Error creating cold prospect: {str(e)}")
            self.session.rollback()
            raise
    
    def get_prospect_context(self, phone_number):
        """Get comprehensive prospect context"""
        try:
            prospect = self.session.query(Prospect).filter(
                Prospect.phone_number == phone_number
            ).first()
            
            if not prospect:
                return None
            
            # Get call history
            call_history = self.session.query(CallHistory).filter(
                CallHistory.prospect_id == prospect.id
            ).order_by(desc(CallHistory.called_at)).all()
            
            return {
                'prospect': prospect,
                'call_history': call_history,
                'is_warm_lead': prospect.source == ProspectSource.FORM_SUBMISSION.value,
                'previous_conversations': len(call_history),
                'last_call_outcome': call_history[0].call_outcome if call_history else None,
                'last_call_score': call_history[0].qualification_score if call_history else None
            }
            
        except Exception as e:
            logging.error(f"Error getting prospect context: {str(e)}")
            return None
    
    def get_prospects_by_criteria(self, source=None, created_after=None, 
                                 product_filter=None, call_status=None, limit=None):
        """Get prospects by various criteria"""
        try:
            query = self.session.query(Prospect)
            
            if source:
                query = query.filter(Prospect.source == source)
            
            if created_after:
                query = query.filter(Prospect.created_at >= created_after)
            
            if product_filter:
                query = query.filter(Prospect.product_category == product_filter)
            
            if call_status:
                query = query.filter(Prospect.call_status == call_status)
            
            # Exclude do not call
            query = query.filter(Prospect.do_not_call == False)
            
            # Order by priority (warm leads first, then by score)
            query = query.order_by(
                Prospect.source,
                desc(Prospect.qualification_score),
                Prospect.created_at
            )
            
            if limit:
                query = query.limit(limit)
            
            return query.all()
            
        except Exception as e:
            logging.error(f"Error getting prospects by criteria: {str(e)}")
            return []
    
    def update_prospect_score(self, prospect_id, new_score, component_scores=None):
        """Update prospect qualification score"""
        try:
            prospect = self.session.query(Prospect).filter(
                Prospect.id == prospect_id
            ).first()
            
            if prospect:
                prospect.qualification_score = new_score
                prospect.last_contacted = datetime.utcnow()
                
                # Update qualification stage
                if new_score >= 80:
                    prospect.qualification_stage = 'highly_qualified'
                elif new_score >= 60:
                    prospect.qualification_stage = 'qualified'
                elif new_score >= 40:
                    prospect.qualification_stage = 'partially_qualified'
                else:
                    prospect.qualification_stage = 'unqualified'
                
                self.session.commit()
                logging.info(f"Updated prospect {prospect_id} score to {new_score}")
                
        except Exception as e:
            logging.error(f"Error updating prospect score: {str(e)}")
            self.session.rollback()
    
    def categorize_product(self, product_name):
        """Categorize product into standard categories"""
        if not product_name:
            return 'general'
        
        product_lower = product_name.lower()
        
        if any(word in product_lower for word in ['solar', 'panel', 'energy', 'renewable']):
            return 'solar_energy'
        elif any(word in product_lower for word in ['insurance', 'coverage', 'policy']):
            return 'insurance'
        elif any(word in product_lower for word in ['software', 'app', 'platform', 'tool']):
            return 'software'
        elif any(word in product_lower for word in ['marketing', 'advertising', 'seo']):
            return 'marketing'
        elif any(word in product_lower for word in ['finance', 'loan', 'credit', 'investment']):
            return 'finance'
        else:
            return 'general'
    
    def mark_do_not_call(self, phone_number):
        """Mark prospect as do not call"""
        try:
            prospect = self.session.query(Prospect).filter(
                Prospect.phone_number == phone_number
            ).first()
            
            if prospect:
                prospect.do_not_call = True
                prospect.call_status = 'do_not_call'
                self.session.commit()
                logging.info(f"Marked {phone_number} as do not call")
                
        except Exception as e:
            logging.error(f"Error marking do not call: {str(e)}")
            self.session.rollback()