"""
Models package for Voice Bot Project

This package contains database models and data management classes.
"""

from .database import (
    DatabaseManager,
    Base,
    Prospect,
    CallHistory,
    Campaign,
    ProspectSource,
    CallOutcome
)
from .prospect import ProspectManager

__all__ = [
    'DatabaseManager',
    'Base',
    'Prospect', 
    'CallHistory',
    'Campaign',
    'ProspectSource',
    'CallOutcome',
    'ProspectManager'
]

# Package metadata
__version__ = '1.0.0'
__author__ = 'Voice Bot Team'
__description__ = 'Database models and data management for Voice Bot'

# Default database configuration
DEFAULT_DATABASE_CONFIG = {
    'pool_size': 10,
    'max_overflow': 20,
    'pool_timeout': 30,
    'pool_recycle': 3600,
    'echo': False
}

def get_database_manager(database_url: str, **kwargs) -> DatabaseManager:
    """
    Factory function to create a DatabaseManager instance with default configuration.
    
    Args:
        database_url: Database connection URL
        **kwargs: Additional configuration options
    
    Returns:
        DatabaseManager: Configured database manager instance
    """
    config = {**DEFAULT_DATABASE_CONFIG, **kwargs}
    return DatabaseManager(database_url, **config)

def create_all_tables(database_manager: DatabaseManager):
    """
    Create all database tables.
    
    Args:
        database_manager: Database manager instance
    """
    Base.metadata.create_all(bind=database_manager.engine)

def drop_all_tables(database_manager: DatabaseManager):
    """
    Drop all database tables (use with caution!).
    
    Args:
        database_manager: Database manager instance
    """
    Base.metadata.drop_all(bind=database_manager.engine)