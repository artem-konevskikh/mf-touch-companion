"""
Utility Functions for Touch Companion Application

This module provides utility functions for time period parsing and other data operations.
All formatting is handled by the frontend to maintain clean data separation.
"""

from datetime import datetime, timedelta
from typing import Optional


def parse_time_period(period: str) -> Optional[datetime]:
    """
    Parse a time period string into a datetime representing the start time.

    Args:
        period: Time period string (e.g., "today", "hour", "week")

    Returns:
        Datetime for the start of the specified period
    """
    now = datetime.now()

    if period == "today":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "hour":
        return now - timedelta(hours=1)
    elif period == "minute":
        return now - timedelta(minutes=1)
    elif period == "week":
        # Start of the current week (Monday)
        return (now - timedelta(days=now.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    elif period == "month":
        # Start of the current month
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif period == "year":
        # Start of the current year
        return now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    elif period == "all_time":
        # Return None for all-time (no time filter)
        return None

    # Invalid period
    raise ValueError(f"Invalid time period: {period}")
