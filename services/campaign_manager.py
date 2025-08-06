import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from sqlalchemy import and_, or_, desc, func
from models.database import Prospect, CallHistory, Campaign, ProspectSource, CallOutcome
import asyncio

class UnifiedCampaignManager:
    def __init__(self, voice_bot, db_manager):
        """Initialize campaign manager"""
        self.voice_bot = voice_bot
        self.db_manager = db_manager
        self.prospect_manager = voice_bot.prospect_manager
        
        logging.info("Unified Campaign Manager initialized")
    
    def create_form_follow_up_campaign(self, hours_back=24, product_filter=None, max_calls=100):
        """Create campaign for form submissions"""
        try:
            session = self.db_manager.get_session()
            
            # Get recent form submissions
            query = session.query(Prospect).filter(
                Prospect.source == ProspectSource.FORM_SUBMISSION.value,
                Prospect.form_submitted_at >= datetime.utcnow() - timedelta(hours=hours_back),
                Prospect.call_status == 'pending',
                Prospect.do_not_call == False
            )
            
            if product_filter:
                query = query.filter(Prospect.product_category == product_filter)
            
            prospects = query.order_by(desc(Prospect.form_submitted_at)).limit(max_calls).all()
            
            # Create campaign record
            campaign = Campaign(
                name=f"Form Follow-up {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}",
                campaign_type='form_follow_up',
                total_prospects=len(prospects),
                campaign_config={
                    'hours_back': hours_back,
                    'product_filter': product_filter,
                    'max_calls': max_calls
                },
                started_at=datetime.utcnow(),
                status='running'
            )
            
            session.add(campaign)
            session.commit()
            
            # Schedule calls with priority
            scheduled_calls = []
            for i, prospect in enumerate(prospects):
                priority = self._calculate_call_priority(prospect)
                delay_minutes = self._calculate_delay_minutes(priority, i)
                
                # In production, this would use Celery
                call_result = asyncio.run(
                    self.voice_bot.initiate_call(prospect.phone_number, 'form_follow_up')
                )
                
                scheduled_calls.append({
                    'prospect_id': prospect.id,
                    'call_result': call_result,
                    'delay_minutes': delay_minutes
                })
            
            logging.info(f"Form follow-up campaign created: {campaign.id} with {len(prospects)} prospects")
            
            return {
                'campaign_id': campaign.id,
                'campaign_type': 'form_follow_up',
                'total_prospects': len(prospects),
                'scheduled_calls': len(scheduled_calls),
                'estimated_completion': self._estimate_completion_time(prospects)
            }
            
        except Exception as e:
            logging.error(f"Error creating form follow-up campaign: {str(e)}")
            session.rollback()
            raise
    
    def create_cold_outreach_campaign(self, prospect_list, product_target, 
                                    call_schedule='business_hours', max_calls=100):
        """Create campaign for cold outreach"""
        try:
            session = self.db_manager.get_session()
            
            # Import prospect list
            prospects = []
            for lead_data in prospect_list[:max_calls]:
                try:
                    prospect = self.prospect_manager.create_prospect_from_cold_list({
                        **lead_data,
                        'target_product': product_target
                    })
                    prospects.append(prospect)
                except Exception as e:
                    logging.error(f"Error creating prospect from cold list: {str(e)}")
                    continue
            
            # Create campaign record
            campaign = Campaign(
                name=f"Cold Outreach {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}",
                campaign_type='cold_outreach',
                total_prospects=len(prospects),
                campaign_config={
                    'product_target': product_target,
                    'call_schedule': call_schedule,
                    'max_calls': max_calls
                },
                started_at=datetime.utcnow(),
                status='running'
            )
            
            session.add(campaign)
            session.commit()
            
            # Schedule calls with proper pacing
            scheduled_calls = []
            for i, prospect in enumerate(prospects):
                # Space out cold calls to avoid spam detection
                delay_minutes = i * 5  # 5-minute intervals
                
                # In production, would use Celery with delay
                call_result = asyncio.run(
                    self.voice_bot.initiate_call(prospect.phone_number, 'cold_outreach')
                )
                
                scheduled_calls.append({
                    'prospect_id': prospect.id,
                    'call_result': call_result,
                    'delay_minutes': delay_minutes
                })
            
            logging.info(f"Cold outreach campaign created: {campaign.id} with {len(prospects)} prospects")
            
            return {
                'campaign_id': campaign.id,
                'campaign_type': 'cold_outreach',
                'total_prospects': len(prospects),
                'scheduled_calls': len(scheduled_calls),
                'call_schedule': call_schedule
            }
            
        except Exception as e:
            logging.error(f"Error creating cold outreach campaign: {str(e)}")
            session.rollback()
            raise
    
    def create_mixed_campaign(self, include_forms=True, include_cold=True, max_calls=100):
        """Create campaign mixing both warm and cold leads"""
        try:
            session = self.db_manager.get_session()
            
            prospects = []
            
            if include_forms:
                # Get warm leads (form submissions)
                warm_prospects = session.query(Prospect).filter(
                    Prospect.source == ProspectSource.FORM_SUBMISSION.value,
                    Prospect.call_status == 'pending',
                    Prospect.do_not_call == False
                ).order_by(desc(Prospect.form_submitted_at)).limit(max_calls // 2).all()
                
                prospects.extend(warm_prospects)
            
            if include_cold:
                # Get cold leads
                cold_prospects = session.query(Prospect).filter(
                    Prospect.source == ProspectSource.COLD_LIST.value,
                    Prospect.call_status == 'pending',
                    Prospect.do_not_call == False
                ).order_by(desc(Prospect.qualification_score)).limit(max_calls // 2).all()
                
                prospects.extend(cold_prospects)
            
            # Sort by priority (warm leads first, then by score)
            prospects.sort(key=lambda p: (
                0 if p.source == ProspectSource.FORM_SUBMISSION.value else 1,
                -p.qualification_score
            ))
            
            # Limit to max_calls
            prospects = prospects[:max_calls]
            
            # Create campaign record
            campaign = Campaign(
                name=f"Mixed Campaign {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}",
                campaign_type='mixed_campaign',
                total_prospects=len(prospects),
                campaign_config={
                    'include_forms': include_forms,
                    'include_cold': include_cold,
                    'max_calls': max_calls
                },
                started_at=datetime.utcnow(),
                status='running'
            )
            
            session.add(campaign)
            session.commit()
            
            # Execute calls with intelligent scheduling
            scheduled_calls = []
            for i, prospect in enumerate(prospects):
                # Warm leads get priority (shorter delay)
                if prospect.source == ProspectSource.FORM_SUBMISSION.value:
                    delay_minutes = i * 2
                    call_type = 'form_follow_up'
                else:
                    delay_minutes = i * 5
                    call_type = 'cold_outreach'
                
                call_result = asyncio.run(
                    self.voice_bot.initiate_call(prospect.phone_number, call_type)
                )
                
                scheduled_calls.append({
                    'prospect_id': prospect.id,
                    'call_result': call_result,
                    'call_type': call_type,
                    'delay_minutes': delay_minutes
                })
            
            warm_count = len([p for p in prospects if p.source == ProspectSource.FORM_SUBMISSION.value])
            cold_count = len(prospects) - warm_count
            
            logging.info(f"Mixed campaign created: {campaign.id} with {warm_count} warm + {cold_count} cold prospects")
            
            return {
                'campaign_id': campaign.id,
                'campaign_type': 'mixed_campaign',
                'total_prospects': len(prospects),
                'warm_leads': warm_count,
                'cold_leads': cold_count,
                'scheduled_calls': len(scheduled_calls)
            }
            
        except Exception as e:
            logging.error(f"Error creating mixed campaign: {str(e)}")
            session.rollback()
            raise
    
    def get_campaign_status(self, campaign_id):
        """Get campaign status and progress"""
        try:
            session = self.db_manager.get_session()
            
            campaign = session.query(Campaign).filter(Campaign.id == campaign_id).first()
            if not campaign:
                return {'error': 'Campaign not found'}
            
            # Get call statistics
            call_stats = session.query(
                func.count(CallHistory.id).label('total_calls'),
                func.count(CallHistory.id).filter(
                    CallHistory.call_outcome == CallOutcome.COMPLETED.value
                ).label('completed_calls'),
                func.count(CallHistory.id).filter(
                    CallHistory.qualification_score >= 70
                ).label('qualified_leads'),
                func.avg(CallHistory.qualification_score).label('avg_score')
            ).filter(
                CallHistory.called_at >= campaign.started_at
            ).first()
            
            # Calculate progress
            progress_percentage = 0
            if campaign.total_prospects > 0:
                progress_percentage = (call_stats.total_calls / campaign.total_prospects) * 100
            
            return {
                'campaign_id': campaign.id,
                'name': campaign.name,
                'type': campaign.campaign_type,
                'status': campaign.status,
                'started_at': campaign.started_at.isoformat(),
                'total_prospects': campaign.total_prospects,
                'progress': {
                    'calls_attempted': call_stats.total_calls,
                    'calls_completed': call_stats.completed_calls,
                    'qualified_leads': call_stats.qualified_leads,
                    'avg_qualification_score': round(call_stats.avg_score or 0, 1),
                    'progress_percentage': round(progress_percentage, 1)
                },
                'config': campaign.campaign_config
            }
            
        except Exception as e:
            logging.error(f"Error getting campaign status: {str(e)}")
            return {'error': str(e)}
    
    def stop_campaign(self, campaign_id):
        """Stop a running campaign"""
        try:
            session = self.db_manager.get_session()
            
            campaign = session.query(Campaign).filter(Campaign.id == campaign_id).first()
            if not campaign:
                return {'error': 'Campaign not found'}
            
            # Update campaign status
            campaign.status = 'stopped'
            campaign.completed_at = datetime.utcnow()
            
            # In production, would cancel pending Celery tasks
            
            session.commit()
            
            logging.info(f"Campaign stopped: {campaign_id}")
            
            return {
                'campaign_id': campaign_id,
                'status': 'stopped',
                'stopped_at': campaign.completed_at.isoformat()
            }
            
        except Exception as e:
            logging.error(f"Error stopping campaign: {str(e)}")
            session.rollback()
            return {'error': str(e)}
    
    def get_analytics_data(self, start_date):
        """Get comprehensive analytics data"""
        try:
            session = self.db_manager.get_session()
            
            # Overall metrics
            total_prospects = session.query(Prospect).filter(
                Prospect.created_at >= start_date
            ).count()
            
            total_calls = session.query(CallHistory).filter(
                CallHistory.called_at >= start_date
            ).count()
            
            completed_calls = session.query(CallHistory).filter(
                CallHistory.called_at >= start_date,
                CallHistory.call_outcome == CallOutcome.COMPLETED.value
            ).count()
            
            qualified_leads = session.query(CallHistory).filter(
                CallHistory.called_at >= start_date,
                CallHistory.qualification_score >= 70
            ).count()
            
            # Performance by source
            source_performance = session.query(
                Prospect.source,
                func.count(Prospect.id).label('total_prospects'),
                func.count(CallHistory.id).label('total_calls'),
                func.avg(CallHistory.qualification_score).label('avg_score'),
                func.count(CallHistory.id).filter(
                    CallHistory.qualification_score >= 70
                ).label('qualified_leads')
            ).outerjoin(CallHistory, Prospect.id == CallHistory.prospect_id).filter(
                Prospect.created_at >= start_date
            ).group_by(Prospect.source).all()
            
            # Daily performance
            daily_performance = session.query(
                func.date(CallHistory.called_at).label('date'),
                func.count(CallHistory.id).label('total_calls'),
                func.count(CallHistory.id).filter(
                    CallHistory.call_outcome == CallOutcome.COMPLETED.value
                ).label('completed_calls'),
                func.count(CallHistory.id).filter(
                    CallHistory.qualification_score >= 70
                ).label('qualified_leads')
            ).filter(
                CallHistory.called_at >= start_date
            ).group_by(func.date(CallHistory.called_at)).order_by('date').all()
            
            # Conversion rates
            conversion_rate = (qualified_leads / completed_calls * 100) if completed_calls > 0 else 0
            connect_rate = (completed_calls / total_calls * 100) if total_calls > 0 else 0
            
            return {
                'summary': {
                    'total_prospects': total_prospects,
                    'total_calls': total_calls,
                    'completed_calls': completed_calls,
                    'qualified_leads': qualified_leads,
                    'conversion_rate': round(conversion_rate, 1),
                    'connect_rate': round(connect_rate, 1)
                },
                'source_performance': [
                    {
                        'source': row.source,
                        'total_prospects': row.total_prospects,
                        'total_calls': row.total_calls or 0,
                        'avg_score': round(row.avg_score or 0, 1),
                        'qualified_leads': row.qualified_leads or 0,
                        'conversion_rate': round((row.qualified_leads or 0) / (row.total_calls or 1) * 100, 1)
                    }
                    for row in source_performance
                ],
                'daily_performance': [
                    {
                        'date': row.date.isoformat(),
                        'total_calls': row.total_calls,
                        'completed_calls': row.completed_calls,
                        'qualified_leads': row.qualified_leads,
                        'conversion_rate': round((row.qualified_leads / row.completed_calls * 100) if row.completed_calls > 0 else 0, 1)
                    }
                    for row in daily_performance
                ]
            }
            
        except Exception as e:
            logging.error(f"Error getting analytics data: {str(e)}")
            return {'error': str(e)}
    
    def _calculate_call_priority(self, prospect):
        """Calculate call priority for scheduling"""
        priority = 'normal'
        
        if prospect.source == ProspectSource.FORM_SUBMISSION.value:
            # Form submissions get higher priority
            priority = 'high'
            
            # Very recent submissions get highest priority
            if prospect.form_submitted_at:
                hours_ago = (datetime.utcnow() - prospect.form_submitted_at).total_seconds() / 3600
                if hours_ago < 2:
                    priority = 'urgent'
            
            # High-value forms get priority boost
            if prospect.form_data:
                if prospect.form_data.get('budget') and prospect.form_data.get('timeline'):
                    priority = 'urgent'
        
        return priority
    
    def _calculate_delay_minutes(self, priority, index):
        """Calculate delay in minutes based on priority and position"""
        base_delays = {
            'urgent': 5,
            'high': 15,
            'normal': 30,
            'low': 60
        }
        
        base_delay = base_delays.get(priority, 30)
        
        # Add staggered delay based on position
        stagger_delay = index * 2
        
        return base_delay + stagger_delay
    
    def _estimate_completion_time(self, prospects):
        """Estimate campaign completion time"""
        total_prospects = len(prospects)
        
        # Assume 5 minutes per call on average + delays
        avg_call_time = 5
        avg_delay = 10
        
        total_minutes = total_prospects * (avg_call_time + avg_delay)
        completion_time = datetime.utcnow() + timedelta(minutes=total_minutes)
        
        return completion_time.isoformat()
    
    # Additional helper methods for API endpoints...
    
    def get_prospects_paginated(self, page, per_page, source_filter, status_filter, search_query):
        """Get paginated prospects with filters"""
        session = self.db_manager.get_session()
        
        query = session.query(Prospect)
        
        if source_filter:
            query = query.filter(Prospect.source == source_filter)
        
        if status_filter:
            query = query.filter(Prospect.call_status == status_filter)
        
        if search_query:
            query = query.filter(
                or_(
                    Prospect.name.ilike(f'%{search_query}%'),
                    Prospect.phone_number.ilike(f'%{search_query}%'),
                    Prospect.email.ilike(f'%{search_query}%'),
                    Prospect.company.ilike(f'%{search_query}%')
                )
            )
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        prospects = query.order_by(desc(Prospect.created_at)).offset(
            (page - 1) * per_page
        ).limit(per_page).all()
        
        return {
            'prospects': [
                {
                    'id': p.id,
                    'name': p.name,
                    'phone_number': p.phone_number,
                    'email': p.email,
                    'company': p.company,
                    'source': p.source,
                    'product_interest': p.product_interest,
                    'qualification_score': p.qualification_score,
                    'call_status': p.call_status,
                    'created_at': p.created_at.isoformat(),
                    'last_contacted': p.last_contacted.isoformat() if p.last_contacted else None
                }
                for p in prospects
            ],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'pages': (total + per_page - 1) // per_page
            }
        }
    
    def get_total_prospects(self):
        """Get total number of prospects"""
        session = self.db_manager.get_session()
        return session.query(Prospect).count()
    
    def get_calls_today(self):
        """Get number of calls made today"""
        session = self.db_manager.get_session()
        today = datetime.utcnow().date()
        return session.query(CallHistory).filter(
            func.date(CallHistory.called_at) == today
        ).count()
    
    def get_qualified_leads_today(self):
        """Get number of qualified leads today"""
        session = self.db_manager.get_session()
        today = datetime.utcnow().date()
        return session.query(CallHistory).filter(
            func.date(CallHistory.called_at) == today,
            CallHistory.qualification_score >= 70
        ).count()
    
    def get_system_uptime(self):
        """Get system uptime (placeholder)"""
        return "24h 15m"  # Would calculate actual uptime in production
    
    # Add these methods to the UnifiedCampaignManager class

    def get_prospect_call_history(self, prospect_id: int):
        """Get call history for a specific prospect"""
        try:
            session = self.db_manager.get_session()
            
            calls = session.query(CallHistory).filter(
                CallHistory.prospect_id == prospect_id
            ).order_by(desc(CallHistory.called_at)).all()
            
            # Serialize call history for JSON response
            call_history = []
            for call in calls:
                call_data = {
                    'id': call.id,
                    'call_sid': call.call_sid,
                    'call_type': call.call_type,
                    'call_duration': call.call_duration,
                    'call_outcome': call.call_outcome,
                    'qualification_score': call.qualification_score,
                    'component_scores': call.component_scores,
                    'conversation_summary': call.conversation_summary,
                    'next_action': call.next_action,
                    'called_at': call.called_at.isoformat() if call.called_at else None,
                    'completed_at': call.completed_at.isoformat() if call.completed_at else None,
                    'recording_url': call.recording_url,
                    'recording_duration': call.recording_duration,
                    'notes': call.notes
                }
                
                # Add conversation log if exists (deserialize it)
                if call.conversation_log:
                    from utils.helpers import deserialize_conversation_log
                    call_data['conversation_log'] = deserialize_conversation_log(call.conversation_log)
                
                call_history.append(call_data)
            
            session.close()
            return call_history
            
        except Exception as e:
            logging.error(f"Error getting prospect call history: {str(e)}")
            return []

    def get_prospect_details(self, prospect_id: int):
        """Get detailed prospect information"""
        try:
            session = self.db_manager.get_session()
            
            prospect = session.query(Prospect).filter(Prospect.id == prospect_id).first()
            
            if not prospect:
                session.close()
                return None
            
            # Get call history
            call_history = self.get_prospect_call_history(prospect_id)
            
            # Serialize prospect data
            prospect_data = {
                'id': prospect.id,
                'phone_number': prospect.phone_number,
                'email': prospect.email,
                'name': prospect.name,
                'source': prospect.source,
                'source_data': prospect.source_data,
                'product_interest': prospect.product_interest,
                'product_category': prospect.product_category,
                'company': prospect.company,
                'job_title': prospect.job_title,
                'industry': prospect.industry,
                'created_at': prospect.created_at.isoformat() if prospect.created_at else None,
                'last_contacted': prospect.last_contacted.isoformat() if prospect.last_contacted else None,
                'contact_attempts': prospect.contact_attempts,
                'qualification_score': prospect.qualification_score,
                'qualification_stage': prospect.qualification_stage,
                'call_status': prospect.call_status,
                'best_call_time': prospect.best_call_time,
                'timezone': prospect.timezone,
                'form_submitted_at': prospect.form_submitted_at.isoformat() if prospect.form_submitted_at else None,
                'form_data': prospect.form_data,
                'do_not_call': prospect.do_not_call,
                'preferred_contact_method': prospect.preferred_contact_method,
                'call_history': call_history
            }
            
            session.close()
            return prospect_data
            
        except Exception as e:
            logging.error(f"Error getting prospect details: {str(e)}")
            return None

    def mark_prospect_do_not_call(self, prospect_id: int):
        """Mark prospect as do not call"""
        try:
            session = self.db_manager.get_session()
            
            prospect = session.query(Prospect).filter(Prospect.id == prospect_id).first()
            
            if not prospect:
                session.close()
                return {'error': 'Prospect not found'}
            
            prospect.do_not_call = True
            prospect.call_status = 'do_not_call'
            session.commit()
            
            result = {
                'success': True,
                'prospect_id': prospect_id,
                'status': 'marked_do_not_call',
                'message': f'Prospect {prospect_id} marked as do not call'
            }
            
            session.close()
            return result
            
        except Exception as e:
            logging.error(f"Error marking prospect do not call: {str(e)}")
            return {'error': str(e)}

    def get_calls_paginated(self, page: int, per_page: int, outcome_filter: str = None, start_date = None):
        """Get paginated call history"""
        try:
            session = self.db_manager.get_session()
            
            query = session.query(CallHistory)
            
            if outcome_filter:
                query = query.filter(CallHistory.call_outcome == outcome_filter)
            
            if start_date:
                query = query.filter(CallHistory.called_at >= start_date)
            
            # Get total count
            total = query.count()
            
            # Apply pagination
            calls = query.order_by(desc(CallHistory.called_at)).offset(
                (page - 1) * per_page
            ).limit(per_page).all()
            
            # Serialize calls
            calls_data = []
            for call in calls:
                # Get prospect name for display
                prospect = session.query(Prospect).filter(Prospect.id == call.prospect_id).first()
                prospect_name = prospect.name if prospect else 'Unknown'
                
                call_data = {
                    'id': call.id,
                    'prospect_id': call.prospect_id,
                    'prospect_name': prospect_name,
                    'call_sid': call.call_sid,
                    'call_type': call.call_type,
                    'call_duration': call.call_duration,
                    'call_outcome': call.call_outcome,
                    'qualification_score': call.qualification_score,
                    'conversation_summary': call.conversation_summary,
                    'next_action': call.next_action,
                    'called_at': call.called_at.isoformat() if call.called_at else None,
                    'completed_at': call.completed_at.isoformat() if call.completed_at else None
                }
                calls_data.append(call_data)
            
            # Calculate pagination info
            from utils.helpers import create_pagination_info
            pagination = create_pagination_info(page, per_page, total)
            
            session.close()
            
            return {
                'calls': calls_data,
                'pagination': pagination
            }
            
        except Exception as e:
            logging.error(f"Error getting paginated calls: {str(e)}")
            return {'calls': [], 'pagination': {}}

    def get_call_details(self, call_sid: str):
        """Get detailed call information"""
        try:
            session = self.db_manager.get_session()
            
            call = session.query(CallHistory).filter(CallHistory.call_sid == call_sid).first()
            
            if not call:
                session.close()
                return None
            
            # Get prospect info
            prospect = session.query(Prospect).filter(Prospect.id == call.prospect_id).first()
            
            call_data = {
                'id': call.id,
                'call_sid': call.call_sid,
                'prospect_id': call.prospect_id,
                'prospect_name': prospect.name if prospect else 'Unknown',
                'prospect_phone': prospect.phone_number if prospect else 'Unknown',
                'call_type': call.call_type,
                'call_duration': call.call_duration,
                'call_outcome': call.call_outcome,
                'qualification_score': call.qualification_score,
                'component_scores': call.component_scores,
                'conversation_summary': call.conversation_summary,
                'next_action': call.next_action,
                'called_at': call.called_at.isoformat() if call.called_at else None,
                'completed_at': call.completed_at.isoformat() if call.completed_at else None,
                'recording_url': call.recording_url,
                'recording_duration': call.recording_duration,
                'notes': call.notes
            }
            
            # Add conversation log if exists
            if call.conversation_log:
                from utils.helpers import deserialize_conversation_log
                call_data['conversation_log'] = deserialize_conversation_log(call.conversation_log)
            
            session.close()
            return call_data
            
        except Exception as e:
            logging.error(f"Error getting call details: {str(e)}")
            return None

    def get_call_recording(self, call_sid: str):
        """Get call recording information"""
        try:
            session = self.db_manager.get_session()
            
            call = session.query(CallHistory).filter(CallHistory.call_sid == call_sid).first()
            
            if not call or not call.recording_url:
                session.close()
                return None
            
            recording_data = {
                'call_sid': call.call_sid,
                'recording_url': call.recording_url,
                'recording_duration': call.recording_duration,
                'recorded_at': call.completed_at.isoformat() if call.completed_at else None
            }
            
            session.close()
            return recording_data
            
        except Exception as e:
            logging.error(f"Error getting call recording: {str(e)}")
            return None