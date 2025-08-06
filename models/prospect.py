from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy import and_, or_, desc
from datetime import datetime, timedelta
from models.database import Prospect, CallHistory, Campaign, ProspectSource
import logging

class ProspectManager:
    def __init__(self, db_manager):
        self.db_manager = db_manager
        # Use scoped session for thread safety
        self.Session = scoped_session(sessionmaker(bind=db_manager.engine))
    
    def get_session(self):
        """Get a new session"""
        return self.Session()
    
    def create_prospect_from_form(self, form_data):
        """Create prospect from form submission with proper session management"""
        session = self.get_session()
        try:
            # Check if prospect already exists
            existing_prospect = session.query(Prospect).filter(
                Prospect.phone_number == form_data.get('phone')
            ).first()
            
            if existing_prospect:
                # Update existing prospect
                existing_prospect.form_data = form_data
                existing_prospect.form_submitted_at = datetime.utcnow()
                existing_prospect.product_interest = form_data.get('product')
                existing_prospect.product_category = self.categorize_product(form_data.get('product'))
                existing_prospect.qualification_score = max(existing_prospect.qualification_score, 25)
                session.commit()
                
                # Refresh to ensure it's attached to session
                session.refresh(existing_prospect)
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
                qualification_score=25,
                call_status='pending'
            )
            
            session.add(prospect)
            session.commit()
            session.refresh(prospect)  # Ensure object is fresh and attached
            
            logging.info(f"Created prospect from form: {prospect.id}")
            return prospect
            
        except Exception as e:
            logging.error(f"Error creating prospect from form: {str(e)}")
            session.rollback()
            raise
        finally:
            session.close()
    
    def get_prospect_context(self, phone_number):
        """Get prospect context with proper session management"""
        session = self.get_session()
        try:
            prospect = session.query(Prospect).filter(
                Prospect.phone_number == phone_number
            ).first()
            
            if not prospect:
                return None
            
            # Get call history with explicit join to avoid lazy loading
            call_history = session.query(CallHistory).filter(
                CallHistory.prospect_id == prospect.id
            ).order_by(desc(CallHistory.called_at)).all()
            
            # Create a detached copy of prospect data to avoid session issues
            prospect_data = {
                'id': prospect.id,
                'phone_number': prospect.phone_number,
                'name': prospect.name,
                'email': prospect.email,
                'source': prospect.source,
                'source_data': prospect.source_data,
                'product_interest': prospect.product_interest,
                'product_category': prospect.product_category,
                'company': prospect.company,
                'job_title': prospect.job_title,
                'industry': prospect.industry,
                'qualification_score': prospect.qualification_score,
                'qualification_stage': prospect.qualification_stage,
                'call_status': prospect.call_status,
                'form_submitted_at': prospect.form_submitted_at,
                'form_data': prospect.form_data,
                'created_at': prospect.created_at,
                'last_contacted': prospect.last_contacted,
                'contact_attempts': prospect.contact_attempts,
                'do_not_call': prospect.do_not_call
            }
            
            # Create context with detached data
            context = {
                'prospect': type('ProspectData', (), prospect_data)(),  # Create object from dict
                'prospect_id': prospect.id,  # Keep ID for updates
                'call_history': call_history,
                'is_warm_lead': prospect.source == ProspectSource.FORM_SUBMISSION.value,
                'previous_conversations': len(call_history),
                'last_call_outcome': call_history[0].call_outcome if call_history else None,
                'last_call_score': call_history[0].qualification_score if call_history else None
            }
            
            return context
            
        except Exception as e:
            logging.error(f"Error getting prospect context: {str(e)}")
            return None
        finally:
            session.close()
    
    def update_prospect_score(self, prospect_id, new_score, component_scores=None):
        """Update prospect qualification score with proper session management"""
        session = self.get_session()
        try:
            prospect = session.query(Prospect).filter(
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
                
                session.commit()
                logging.info(f"Updated prospect {prospect_id} score to {new_score}")
                
        except Exception as e:
            logging.error(f"Error updating prospect score: {str(e)}")
            session.rollback()
        finally:
            session.close()
    
    def increment_contact_attempts(self, prospect_id):
        """Increment contact attempts counter"""
        session = self.get_session()
        try:
            prospect = session.query(Prospect).filter(
                Prospect.id == prospect_id
            ).first()
            
            if prospect:
                prospect.contact_attempts += 1
                session.commit()
                
        except Exception as e:
            logging.error(f"Error incrementing contact attempts: {str(e)}")
            session.rollback()
        finally:
            session.close()
    
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