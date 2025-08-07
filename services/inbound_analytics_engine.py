"""
Advanced Analytics Engine for Inbound Call Performance

Provides comprehensive analytics, insights, and predictive capabilities
for inbound call optimization and business intelligence
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from models.database import Prospect, CallHistory, CallbackRequest, Campaign
from sqlalchemy import func, and_, or_, desc, case, text
import numpy as np
from collections import defaultdict, Counter
import json

class InboundAnalyticsEngine:
    def __init__(self, db_manager):
        """Initialize analytics engine"""
        self.db_manager = db_manager
        
        # Analytics configuration
        self.config = {
            'trend_analysis_periods': [7, 30, 90],  # days
            'peak_hours_threshold': 0.8,  # 80% of max volume
            'conversion_benchmark': 15.0,  # 15% baseline conversion
            'quality_score_weight': 0.7,
            'volume_score_weight': 0.3
        }
        
        logging.info("Inbound Analytics Engine initialized")
    
    async def generate_comprehensive_report(self, start_date: datetime, end_date: datetime) -> Dict:
        """Generate comprehensive analytics report"""
        try:
            session = self.db_manager.get_session()
            
            # Core metrics
            core_metrics = await self._calculate_core_metrics(session, start_date, end_date)
            
            # Trend analysis
            trend_analysis = await self._analyze_trends(session, start_date, end_date)
            
            # Call pattern analysis
            pattern_analysis = await self._analyze_call_patterns(session, start_date, end_date)
            
            # Lead quality analysis
            quality_analysis = await self._analyze_lead_quality(session, start_date, end_date)
            
            # Performance insights
            performance_insights = await self._generate_performance_insights(session, start_date, end_date)
            
            # Predictive analysis
            predictions = await self._generate_predictions(session, start_date, end_date)
            
            session.close()
            
            return {
                'report_period': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat(),
                    'days': (end_date - start_date).days
                },
                'core_metrics': core_metrics,
                'trends': trend_analysis,
                'patterns': pattern_analysis,
                'quality': quality_analysis,
                'insights': performance_insights,
                'predictions': predictions,
                'generated_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logging.error(f"Error generating comprehensive report: {str(e)}")
            return {'error': str(e)}
    
    async def _calculate_core_metrics(self, session, start_date: datetime, end_date: datetime) -> Dict:
        """Calculate core inbound call metrics"""
        
        # Basic call volume metrics
        total_inbound = session.query(CallHistory).filter(
            CallHistory.call_direction == 'inbound',
            CallHistory.called_at >= start_date,
            CallHistory.called_at <= end_date
        ).count()
        
        completed_calls = session.query(CallHistory).filter(
            CallHistory.call_direction == 'inbound',
            CallHistory.call_outcome == 'completed',
            CallHistory.called_at >= start_date,
            CallHistory.called_at <= end_date
        ).count()
        
        qualified_leads = session.query(CallHistory).filter(
            CallHistory.call_direction == 'inbound',
            CallHistory.qualification_score >= 70,
            CallHistory.called_at >= start_date,
            CallHistory.called_at <= end_date
        ).count()
        
        # Calculate rates
        completion_rate = (completed_calls / total_inbound * 100) if total_inbound > 0 else 0
        conversion_rate = (qualified_leads / completed_calls * 100) if completed_calls > 0 else 0
        
        # Average metrics
        avg_metrics = session.query(
            func.avg(CallHistory.call_duration).label('avg_duration'),
            func.avg(CallHistory.qualification_score).label('avg_score')
        ).filter(
            CallHistory.call_direction == 'inbound',
            CallHistory.called_at >= start_date,
            CallHistory.called_at <= end_date
        ).first()
        
        return {
            'total_inbound_calls': total_inbound,
            'completed_calls': completed_calls,
            'qualified_leads': qualified_leads,
            'completion_rate': round(completion_rate, 2),
            'conversion_rate': round(conversion_rate, 2),
            'avg_call_duration': round(avg_metrics.avg_duration or 0, 1),
            'avg_qualification_score': round(avg_metrics.avg_score or 0, 1)
        }
    
    async def _analyze_trends(self, session, start_date: datetime, end_date: datetime) -> Dict:
        """Analyze call volume and performance trends"""
        
        # Daily call volume trend
        daily_calls = session.query(
            func.date(CallHistory.called_at).label('call_date'),
            func.count(CallHistory.id).label('call_count'),
            func.avg(CallHistory.qualification_score).label('avg_score')
        ).filter(
            CallHistory.call_direction == 'inbound',
            CallHistory.called_at >= start_date,
            CallHistory.called_at <= end_date
        ).group_by(func.date(CallHistory.called_at)).order_by('call_date').all()
        
        # Hourly distribution
        hourly_distribution = session.query(
            func.extract('hour', CallHistory.called_at).label('hour'),
            func.count(CallHistory.id).label('call_count')
        ).filter(
            CallHistory.call_direction == 'inbound',
            CallHistory.called_at >= start_date,
            CallHistory.called_at <= end_date
        ).group_by(func.extract('hour', CallHistory.called_at)).order_by('hour').all()
        
        return {
            'daily_trend': [
                {
                    'date': row.call_date.isoformat(),
                    'calls': row.call_count,
                    'avg_score': round(row.avg_score or 0, 1)
                }
                for row in daily_calls
            ],
            'hourly_distribution': [
                {
                    'hour': int(row.hour),
                    'calls': row.call_count,
                    'percentage': round(row.call_count / sum(r.call_count for r in hourly_distribution) * 100, 1)
                }
                for row in hourly_distribution
            ]
        }
    
    async def _analyze_call_patterns(self, session, start_date: datetime, end_date: datetime) -> Dict:
        """Analyze call patterns and behaviors"""
        
        # Intent distribution
        intent_distribution = session.query(
            CallHistory.inbound_intent,
            func.count(CallHistory.id).label('count')
        ).filter(
            CallHistory.call_direction == 'inbound',
            CallHistory.called_at >= start_date,
            CallHistory.called_at <= end_date,
            CallHistory.inbound_intent.isnot(None)
        ).group_by(CallHistory.inbound_intent).all()
        
        # Call outcome distribution
        outcome_distribution = session.query(
            CallHistory.call_outcome,
            func.count(CallHistory.id).label('count')
        ).filter(
            CallHistory.call_direction == 'inbound',
            CallHistory.called_at >= start_date,
            CallHistory.called_at <= end_date
        ).group_by(CallHistory.call_outcome).all()
        
        return {
            'intent_distribution': [
                {'intent': row.inbound_intent, 'count': row.count}
                for row in intent_distribution
            ],
            'outcome_distribution': [
                {'outcome': row.call_outcome, 'count': row.count}
                for row in outcome_distribution
            ]
        }
    
    async def _analyze_lead_quality(self, session, start_date: datetime, end_date: datetime) -> Dict:
        """Analyze lead quality metrics"""
        
        # Score distribution
        score_ranges = [
            (0, 25, 'Poor'),
            (25, 50, 'Fair'),
            (50, 70, 'Good'),
            (70, 85, 'Very Good'),
            (85, 100, 'Excellent')
        ]
        
        score_distribution = []
        for min_score, max_score, label in score_ranges:
            count = session.query(CallHistory).filter(
                CallHistory.call_direction == 'inbound',
                CallHistory.qualification_score >= min_score,
                CallHistory.qualification_score < max_score,
                CallHistory.called_at >= start_date,
                CallHistory.called_at <= end_date
            ).count()
            
            score_distribution.append({
                'range': f"{min_score}-{max_score}",
                'label': label,
                'count': count
            })
        
        return {
            'score_distribution': score_distribution,
            'quality_trends': 'Placeholder for quality trend analysis'
        }
    
    async def _generate_performance_insights(self, session, start_date: datetime, end_date: datetime) -> Dict:
        """Generate actionable performance insights"""
        
        insights = []
        
        # Peak hours analysis
        hourly_data = session.query(
            func.extract('hour', CallHistory.called_at).label('hour'),
            func.count(CallHistory.id).label('call_count'),
            func.avg(CallHistory.qualification_score).label('avg_score')
        ).filter(
            CallHistory.call_direction == 'inbound',
            CallHistory.called_at >= start_date,
            CallHistory.called_at <= end_date
        ).group_by(func.extract('hour', CallHistory.called_at)).all()
        
        if hourly_data:
            max_calls = max(row.call_count for row in hourly_data)
            peak_hours = [row.hour for row in hourly_data if row.call_count >= max_calls * 0.8]
            
            insights.append({
                'type': 'peak_hours',
                'title': 'Peak Call Hours Identified',
                'description': f"Peak inbound call hours: {', '.join(f'{int(h)}:00' for h in peak_hours)}",
                'recommendation': 'Consider optimizing staffing during these hours',
                'impact': 'high'
            })
        
        return {
            'insights': insights,
            'recommendations': [
                'Optimize agent availability during peak hours',
                'Improve call handling for low-scoring interactions',
                'Implement callback scheduling for after-hours calls'
            ]
        }
    
    async def _generate_predictions(self, session, start_date: datetime, end_date: datetime) -> Dict:
        """Generate predictive insights"""
        
        # Simple trend prediction based on historical data
        # In production, this would use more sophisticated ML models
        
        recent_days = []
        for i in range(7):  # Last 7 days
            day_start = end_date - timedelta(days=i+1)
            day_end = day_start + timedelta(days=1)
            
            day_calls = session.query(CallHistory).filter(
                CallHistory.call_direction == 'inbound',
                CallHistory.called_at >= day_start,
                CallHistory.called_at < day_end
            ).count()
            
            recent_days.append(day_calls)
        
        if recent_days:
            avg_daily_calls = sum(recent_days) / len(recent_days)
            trend = 'increasing' if recent_days[0] > recent_days[-1] else 'decreasing'
            
            return {
                'predicted_daily_volume': round(avg_daily_calls),
                'trend_direction': trend,
                'confidence': 'medium',
                'next_week_estimate': round(avg_daily_calls * 7)
            }
        
        return {
            'predicted_daily_volume': 0,
            'trend_direction': 'stable',
            'confidence': 'low'
        }