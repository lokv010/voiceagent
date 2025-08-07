"""
Intelligent Callback Scheduling System

Handles scheduling and managing callback requests from inbound calls
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from models.database import CallbackRequest, Prospect, AgentAvailability, BusinessHours
from utils.helpers import format_phone_number, is_business_hours
import asyncio
from enum import Enum

class CallbackPriority(Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"

class CallbackStatus(Enum):
    PENDING = "pending"
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    RESCHEDULED = "rescheduled"

class CallbackScheduler:
    def __init__(self, voice_bot, db_manager, config):
        """Initialize callback scheduling system"""
        self.voice_bot = voice_bot
        self.db_manager = db_manager
        self.config = config
        
        # Scheduling configuration
        self.scheduling_config = {
            'default_callback_window': 60,  # minutes
            'max_callbacks_per_hour': 12,   # per agent
            'min_callback_gap': 15,         # minutes between callbacks
            'business_hours_only': True,
            'auto_confirm_within': 2,       # hours
            'max_reschedule_attempts': 3
        }
        
        # Time slot preferences
        self.time_preferences = {
            'morning': {'start': 9, 'end': 12},
            'afternoon': {'start': 12, 'end': 17},
            'evening': {'start': 17, 'end': 20},
            'anytime': {'start': 9, 'end': 17}
        }
        
        logging.info("Callback Scheduler initialized")
    
    async def request_callback(self, prospect_id: int, callback_data: Dict) -> Dict:
        """Process a callback request from an inbound call"""
        try:
            session = self.db_manager.get_session()
            
            # Get prospect information
            prospect = session.query(Prospect).filter(Prospect.id == prospect_id).first()
            if not prospect:
                return {'success': False, 'error': 'Prospect not found'}
            
            # Determine callback priority
            priority = self._determine_callback_priority(callback_data, prospect)
            
            # Parse requested time
            requested_time = self._parse_callback_time(
                callback_data.get('requested_time'),
                callback_data.get('time_preference', 'anytime'),
                callback_data.get('timezone', 'UTC')
            )
            
            # Create callback request
            callback_request = CallbackRequest(
                prospect_id=prospect_id,
                requested_time=requested_time,
                reason=callback_data.get('reason', 'Follow-up from inbound call'),
                priority=priority.value,
                request_source=callback_data.get('source', 'inbound_call'),
                notes=callback_data.get('notes', ''),
                status=CallbackStatus.PENDING.value
            )
            
            session.add(callback_request)
            session.commit()
            session.refresh(callback_request)
            
            # Attempt to schedule immediately
            scheduling_result = await self._schedule_callback(callback_request.id, session)
            
            session.close()
            
            # Send confirmation if scheduled
            if scheduling_result['success']:
                await self._send_callback_confirmation(prospect, scheduling_result)
            
            return {
                'success': True,
                'callback_id': callback_request.id,
                'status': scheduling_result.get('status', 'pending'),
                'scheduled_time': scheduling_result.get('scheduled_time'),
                'confirmation_sent': scheduling_result.get('confirmation_sent', False)
            }
            
        except Exception as e:
            logging.error(f"Error requesting callback: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    async def schedule_callback_from_conversation(self, call_sid: str, customer_input: str,
                                                prospect_context: Dict) -> Dict:
        """Schedule callback based on customer conversation input"""
        try:
            # Extract callback information from natural language
            callback_info = self._extract_callback_info_from_speech(customer_input)
            
            # Add context from the current call
            callback_data = {
                'requested_time': callback_info.get('requested_time'),
                'time_preference': callback_info.get('time_preference', 'anytime'),
                'reason': f"Callback requested during call {call_sid}",
                'source': 'inbound_conversation',
                'notes': f"Customer said: '{customer_input[:200]}...'",
                'urgency_level': callback_info.get('urgency_level', 'normal')
            }
            
            # Request the callback
            result = await self.request_callback(
                prospect_context['prospect_id'], 
                callback_data
            )
            
            return result
            
        except Exception as e:
            logging.error(f"Error scheduling callback from conversation: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    async def _schedule_callback(self, callback_request_id: int, session) -> Dict:
        """Attempt to schedule a callback request"""
        try:
            callback_request = session.query(CallbackRequest).filter(
                CallbackRequest.id == callback_request_id
            ).first()
            
            if not callback_request:
                return {'success': False, 'error': 'Callback request not found'}
            
            # Find available time slot
            available_slot = await self._find_available_slot(
                callback_request.requested_time,
                callback_request.priority,
                session
            )
            
            if not available_slot:
                # No immediate availability - add to queue
                return await self._add_to_callback_queue(callback_request, session)
            
            # Schedule the callback
            callback_request.scheduled_at = available_slot['time']
            callback_request.assigned_agent = available_slot.get('agent_id')
            callback_request.status = CallbackStatus.SCHEDULED.value
            
            session.commit()
            
            # Create calendar event or notification
            await self._create_callback_event(callback_request)
            
            return {
                'success': True,
                'status': 'scheduled',
                'scheduled_time': available_slot['time'].isoformat(),
                'agent_id': available_slot.get('agent_id'),
                'confirmation_sent': True
            }
            
        except Exception as e:
            logging.error(f"Error scheduling callback: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    async def _find_available_slot(self, requested_time: datetime, priority: str, 
                                 session) -> Optional[Dict]:
        """Find an available time slot for the callback"""
        try:
            # Start with requested time or next business hour
            start_search = requested_time or self._get_next_business_hour()
            
            # Search window based on priority
            search_window_hours = {
                'urgent': 2,
                'high': 8,
                'normal': 24,
                'low': 72
            }.get(priority, 24)
            
            end_search = start_search + timedelta(hours=search_window_hours)
            
            # Check availability in 15-minute increments
            current_time = start_search
            while current_time <= end_search:
                # Skip non-business hours if configured
                if self.scheduling_config['business_hours_only'] and not is_business_hours(current_time):
                    current_time += timedelta(minutes=15)
                    continue
                
                # Check if slot is available
                if await self._is_slot_available(current_time, session):
                    # Find best agent for this slot
                    agent_id = await self._find_best_agent(current_time, session)
                    
                    return {
                        'time': current_time,
                        'agent_id': agent_id
                    }
                
                current_time += timedelta(minutes=15)
            
            return None
            
        except Exception as e:
            logging.error(f"Error finding available slot: {str(e)}")
            return None
    
    async def _is_slot_available(self, slot_time: datetime, session) -> bool:
        """Check if a time slot is available"""
        try:
            # Check for existing callbacks at this time
            existing_callbacks = session.query(CallbackRequest).filter(
                CallbackRequest.scheduled_at == slot_time,
                CallbackRequest.status.in_(['scheduled', 'confirmed'])
            ).count()
            
            # Check agent capacity
            max_concurrent = self.scheduling_config['max_callbacks_per_hour']
            hour_start = slot_time.replace(minute=0, second=0, microsecond=0)
            hour_end = hour_start + timedelta(hours=1)
            
            callbacks_in_hour = session.query(CallbackRequest).filter(
                CallbackRequest.scheduled_at >= hour_start,
                CallbackRequest.scheduled_at < hour_end,
                CallbackRequest.status.in_(['scheduled', 'confirmed'])
            ).count()
            
            return existing_callbacks == 0 and callbacks_in_hour < max_concurrent
            
        except Exception as e:
            logging.error(f"Error checking slot availability: {str(e)}")
            return False
    
    async def _find_best_agent(self, slot_time: datetime, session) -> Optional[str]:
        """Find the best available agent for a callback slot"""
        try:
            # Simple implementation - can be enhanced with skills routing
            available_agents = session.query(AgentAvailability).filter(
                AgentAvailability.status == 'online',
                AgentAvailability.current_call_count < AgentAvailability.max_concurrent_calls
            ).order_by(
                AgentAvailability.current_call_count,  # Least busy first
                AgentAvailability.customer_satisfaction.desc()  # Best rated first
            ).all()
            
            if available_agents:
                return available_agents[0].agent_id
            
            return None
            
        except Exception as e:
            logging.error(f"Error finding best agent: {str(e)}")
            return None
    
    async def _add_to_callback_queue(self, callback_request, session) -> Dict:
        """Add callback request to queue when no immediate slots available"""
        try:
            callback_request.status = CallbackStatus.PENDING.value
            session.commit()
            
            # Estimate callback time based on queue position
            queue_position = session.query(CallbackRequest).filter(
                CallbackRequest.status == CallbackStatus.PENDING.value,
                CallbackRequest.priority == callback_request.priority,
                CallbackRequest.requested_at <= callback_request.requested_at
            ).count()
            
            # Estimate wait time (rough calculation)
            estimated_wait_hours = queue_position * 0.5  # 30 minutes per callback
            estimated_callback_time = datetime.utcnow() + timedelta(hours=estimated_wait_hours)
            
            return {
                'success': True,
                'status': 'queued',
                'queue_position': queue_position,
                'estimated_callback_time': estimated_callback_time.isoformat(),
                'confirmation_sent': False
            }
            
        except Exception as e:
            logging.error(f"Error adding to callback queue: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _determine_callback_priority(self, callback_data: Dict, prospect: Prospect) -> CallbackPriority:
        """Determine priority level for callback request"""
        try:
            # Check explicit urgency
            urgency_level = callback_data.get('urgency_level', '').lower()
            if urgency_level == 'urgent':
                return CallbackPriority.URGENT
            elif urgency_level == 'high':
                return CallbackPriority.HIGH
            
            # Check prospect qualification score
            if prospect.qualification_score >= 80:
                return CallbackPriority.HIGH
            elif prospect.qualification_score >= 60:
                return CallbackPriority.NORMAL
            
            # Check if they're a repeat caller
            if prospect.total_inbound_calls and prospect.total_inbound_calls > 1:
                return CallbackPriority.HIGH
            
            # Check reason for callback
            reason = callback_data.get('reason', '').lower()
            urgent_reasons = ['complaint', 'urgent', 'emergency', 'asap', 'immediately']
            if any(keyword in reason for keyword in urgent_reasons):
                return CallbackPriority.URGENT
            
            high_priority_reasons = ['purchase', 'buy', 'ready', 'decision', 'proposal']
            if any(keyword in reason for keyword in high_priority_reasons):
                return CallbackPriority.HIGH
            
            return CallbackPriority.NORMAL
            
        except Exception as e:
            logging.error(f"Error determining callback priority: {str(e)}")
            return CallbackPriority.NORMAL
    
    def _parse_callback_time(self, requested_time_str: str, time_preference: str, 
                           timezone: str) -> datetime:
        """Parse callback time from various inputs"""
        try:
            # If specific time provided, try to parse it
            if requested_time_str:
                # Handle common formats
                if 'tomorrow' in requested_time_str.lower():
                    base_date = datetime.utcnow() + timedelta(days=1)
                elif 'next week' in requested_time_str.lower():
                    base_date = datetime.utcnow() + timedelta(days=7)
                elif 'monday' in requested_time_str.lower():
                    base_date = self._get_next_weekday(0)  # Monday
                elif 'tuesday' in requested_time_str.lower():
                    base_date = self._get_next_weekday(1)  # Tuesday
                elif 'wednesday' in requested_time_str.lower():
                    base_date = self._get_next_weekday(2)  # Wednesday
                elif 'thursday' in requested_time_str.lower():
                    base_date = self._get_next_weekday(3)  # Thursday
                elif 'friday' in requested_time_str.lower():
                    base_date = self._get_next_weekday(4)  # Friday
                else:
                    base_date = datetime.utcnow() + timedelta(hours=2)
                
                # Extract time if mentioned
                if 'morning' in requested_time_str.lower():
                    return base_date.replace(hour=10, minute=0, second=0, microsecond=0)
                elif 'afternoon' in requested_time_str.lower():
                    return base_date.replace(hour=14, minute=0, second=0, microsecond=0)
                elif 'evening' in requested_time_str.lower():
                    return base_date.replace(hour=17, minute=0, second=0, microsecond=0)
            
            # Use time preference
            preference_hours = self.time_preferences.get(time_preference, self.time_preferences['anytime'])
            next_slot = self._get_next_business_hour()
            
            # Adjust to preferred time range
            if next_slot.hour < preference_hours['start']:
                next_slot = next_slot.replace(hour=preference_hours['start'], minute=0)
            elif next_slot.hour >= preference_hours['end']:
                # Move to next day
                next_slot = next_slot + timedelta(days=1)
                next_slot = next_slot.replace(hour=preference_hours['start'], minute=0)
            
            return next_slot
            
        except Exception as e:
            logging.error(f"Error parsing callback time: {str(e)}")
            # Default to next business hour
            return self._get_next_business_hour()
    
    def _extract_callback_info_from_speech(self, customer_input: str) -> Dict:
        """Extract callback scheduling info from natural language"""
        input_lower = customer_input.lower()
        callback_info = {}
        
        # Time extraction
        if 'tomorrow' in input_lower:
            callback_info['requested_time'] = 'tomorrow'
        elif 'next week' in input_lower:
            callback_info['requested_time'] = 'next week'
        elif 'monday' in input_lower:
            callback_info['requested_time'] = 'monday'
        elif 'tuesday' in input_lower:
            callback_info['requested_time'] = 'tuesday'
        elif 'wednesday' in input_lower:
            callback_info['requested_time'] = 'wednesday'
        elif 'thursday' in input_lower:
            callback_info['requested_time'] = 'thursday'
        elif 'friday' in input_lower:
            callback_info['requested_time'] = 'friday'
        
        # Time preference
        if 'morning' in input_lower:
            callback_info['time_preference'] = 'morning'
        elif 'afternoon' in input_lower:
            callback_info['time_preference'] = 'afternoon'
        elif 'evening' in input_lower:
            callback_info['time_preference'] = 'evening'
        else:
            callback_info['time_preference'] = 'anytime'
        
        # Urgency level
        if any(word in input_lower for word in ['urgent', 'asap', 'immediately', 'emergency']):
            callback_info['urgency_level'] = 'urgent'
        elif any(word in input_lower for word in ['soon', 'quickly', 'priority']):
            callback_info['urgency_level'] = 'high'
        else:
            callback_info['urgency_level'] = 'normal'
        
        return callback_info
    
    def _get_next_business_hour(self) -> datetime:
        """Get the next available business hour"""
        now = datetime.utcnow()
        
        # If it's currently business hours, return next hour
        if is_business_hours(now):
            return now + timedelta(hours=1)
        
        # Otherwise, find next business day at 9 AM
        next_day = now + timedelta(days=1)
        while next_day.weekday() >= 5:  # Skip weekends
            next_day += timedelta(days=1)
        
        return next_day.replace(hour=9, minute=0, second=0, microsecond=0)
    
    def _get_next_weekday(self, weekday: int) -> datetime:
        """Get next occurrence of specified weekday (0=Monday, 6=Sunday)"""
        today = datetime.utcnow()
        days_ahead = weekday - today.weekday()
        
        if days_ahead <= 0:  # Target day already happened this week
            days_ahead += 7
        
        return today + timedelta(days=days_ahead)
    
    async def _create_callback_event(self, callback_request):
        """Create calendar event or notification for the callback"""
        try:
            # This would integrate with calendar systems (Google Calendar, Outlook, etc.)
            # For now, we'll just log the event creation
            
            logging.info(f"Callback event created: {callback_request.id} at {callback_request.scheduled_at}")
            
            # In a real implementation, you would:
            # 1. Create calendar event for the assigned agent
            # 2. Set up reminder notifications
            # 3. Add to call queue management system
            # 4. Update CRM with scheduled callback
            
        except Exception as e:
            logging.error(f"Error creating callback event: {str(e)}")
    
    async def _send_callback_confirmation(self, prospect, scheduling_result):
        """Send confirmation of scheduled callback"""
        try:
            if not scheduling_result.get('success'):
                return
            
            # This would integrate with SMS/email systems
            # For now, we'll just log the confirmation
            
            scheduled_time = scheduling_result.get('scheduled_time')
            logging.info(f"Callback confirmation sent to {prospect.phone_number} for {scheduled_time}")
            
            # In a real implementation, you would:
            # 1. Send SMS confirmation
            # 2. Send email confirmation
            # 3. Update prospect record with confirmation status
            
        except Exception as e:
            logging.error(f"Error sending callback confirmation: {str(e)}")
    
    # Management and monitoring methods
    
    async def get_pending_callbacks(self, limit: int = 50) -> List[Dict]:
        """Get list of pending callback requests"""
        try:
            session = self.db_manager.get_session()
            
            callbacks = session.query(CallbackRequest).filter(
                CallbackRequest.status == CallbackStatus.PENDING.value
            ).order_by(
                CallbackRequest.priority.desc(),
                CallbackRequest.requested_at
            ).limit(limit).all()
            
            result = []
            for callback in callbacks:
                prospect = session.query(Prospect).filter(
                    Prospect.id == callback.prospect_id
                ).first()
                
                result.append({
                    'callback_id': callback.id,
                    'prospect_id': callback.prospect_id,
                    'prospect_name': prospect.name if prospect else 'Unknown',
                    'prospect_phone': prospect.phone_number if prospect else 'Unknown',
                    'requested_time': callback.requested_time.isoformat() if callback.requested_time else None,
                    'priority': callback.priority,
                    'reason': callback.reason,
                    'requested_at': callback.requested_at.isoformat(),
                    'status': callback.status
                })
            
            session.close()
            return result
            
        except Exception as e:
            logging.error(f"Error getting pending callbacks: {str(e)}")
            return []
    
    async def get_scheduled_callbacks(self, date: datetime = None) -> List[Dict]:
        """Get scheduled callbacks for a specific date"""
        try:
            if not date:
                date = datetime.utcnow().date()
            
            session = self.db_manager.get_session()
            
            start_date = datetime.combine(date, datetime.min.time())
            end_date = start_date + timedelta(days=1)
            
            callbacks = session.query(CallbackRequest).filter(
                CallbackRequest.scheduled_at >= start_date,
                CallbackRequest.scheduled_at < end_date,
                CallbackRequest.status.in_(['scheduled', 'confirmed'])
            ).order_by(CallbackRequest.scheduled_at).all()
            
            result = []
            for callback in callbacks:
                prospect = session.query(Prospect).filter(
                    Prospect.id == callback.prospect_id
                ).first()
                
                result.append({
                    'callback_id': callback.id,
                    'prospect_id': callback.prospect_id,
                    'prospect_name': prospect.name if prospect else 'Unknown',
                    'prospect_phone': prospect.phone_number if prospect else 'Unknown',
                    'scheduled_time': callback.scheduled_at.isoformat(),
                    'assigned_agent': callback.assigned_agent,
                    'priority': callback.priority,
                    'reason': callback.reason,
                    'status': callback.status,
                    'notes': callback.notes
                })
            
            session.close()
            return result
            
        except Exception as e:
            logging.error(f"Error getting scheduled callbacks: {str(e)}")
            return []
    
    async def execute_callback(self, callback_id: int) -> Dict:
        """Execute a scheduled callback"""
        try:
            session = self.db_manager.get_session()
            
            callback_request = session.query(CallbackRequest).filter(
                CallbackRequest.id == callback_id
            ).first()
            
            if not callback_request:
                return {'success': False, 'error': 'Callback not found'}
            
            prospect = session.query(Prospect).filter(
                Prospect.id == callback_request.prospect_id
            ).first()
            
            if not prospect:
                return {'success': False, 'error': 'Prospect not found'}
            
            # Initiate the callback call
            call_result = await self.voice_bot.initiate_call(
                prospect.phone_number, 
                'callback'
            )
            
            if call_result['success']:
                # Update callback status
                callback_request.status = CallbackStatus.COMPLETED.value
                callback_request.completed_at = datetime.utcnow()
                callback_request.callback_call_sid = call_result['call_sid']
                session.commit()
            
            session.close()
            
            return {
                'success': call_result['success'],
                'call_sid': call_result.get('call_sid'),
                'callback_id': callback_id
            }
            
        except Exception as e:
            logging.error(f"Error executing callback: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    async def reschedule_callback(self, callback_id: int, new_time: datetime, 
                                reason: str = '') -> Dict:
        """Reschedule a callback request"""
        try:
            session = self.db_manager.get_session()
            
            callback_request = session.query(CallbackRequest).filter(
                CallbackRequest.id == callback_id
            ).first()
            
            if not callback_request:
                return {'success': False, 'error': 'Callback not found'}
            
            # Check reschedule limit
            reschedule_count = callback_request.notes.count('Rescheduled') if callback_request.notes else 0
            if reschedule_count >= self.scheduling_config['max_reschedule_attempts']:
                return {'success': False, 'error': 'Maximum reschedule attempts reached'}
            
            # Update callback
            callback_request.scheduled_at = new_time
            callback_request.status = CallbackStatus.RESCHEDULED.value
            callback_request.notes = f"{callback_request.notes or ''}\nRescheduled to {new_time}: {reason}"
            
            session.commit()
            session.close()
            
            return {
                'success': True,
                'callback_id': callback_id,
                'new_time': new_time.isoformat(),
                'status': 'rescheduled'
            }
            
        except Exception as e:
            logging.error(f"Error rescheduling callback: {str(e)}")
            return {'success': False, 'error': str(e)}