"""
Statistics API Routes for Touch Companion Application

This module provides API endpoints for:
- Getting all statistics at once
- Accessing individual statistic values
- Retrieving cached statistics
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional

from fastapi import APIRouter, HTTPException, Query, Depends

from modules.database import db
from modules.statistics import StatisticsEngine
from modules.utils import parse_time_period

# Create router
router = APIRouter()

# Configure logging
logger = logging.getLogger("api.statistics")

# Get reference to the statistics engine
from api.app import statistics_engine


@router.get("/all")
async def get_all_statistics():
    """
    Get all statistics at once.

    Returns:
        Complete set of statistics including:
        - Touch counts for different time periods
        - Average touch duration
        - Emotional state information
    """
    try:
        # This uses the cache internally where possible
        stats = await statistics_engine.get_all_statistics()
        return stats

    except Exception as e:
        logger.error(f"Error retrieving all statistics: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/touch-count")
async def get_touch_count_statistics(
    period: Optional[str] = Query(
        "all", regex="^(all|all_time|today|hour|week|month|year)$"
    ),
):
    """
    Get touch count statistics for different time periods.

    Args:
        period: Time period to fetch, or "all" for all periods

    Returns:
        Touch count statistics
    """
    try:
        if period == "all":
            stats = await statistics_engine.get_all_statistics()
            return stats["touch_count"]
        else:
            # Parse time period
            if period != "all_time":
                period_start = parse_time_period(period)
                if period_start:
                    start_time = period_start.isoformat()
                else:
                    start_time = None
            else:
                start_time = None

            # Get touch count for specific period
            count = await db.get_touch_count(start_time=start_time)

            return {period: count}

    except Exception as e:
        logger.error(f"Error retrieving touch count statistics: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/average-duration")
async def get_average_duration_statistics(
    period: str = Query("all_time", regex="^(all_time|today|hour|week|month|year)$"),
):
    """
    Get average touch duration statistics.

    Args:
        period: Time period to fetch

    Returns:
        Average duration in milliseconds
    """
    try:
        # Try to get from cache first
        cached_value = await db.get_statistics_cache("avg_duration", period)
        if cached_value is not None:
            return {
                "average_duration_ms": cached_value,
                "period": period,
                "cached": True,
            }

        # Parse time period
        if period != "all_time":
            period_start = parse_time_period(period)
            if period_start:
                start_time = period_start.isoformat()
            else:
                start_time = None
        else:
            start_time = None

        # Calculate average duration
        avg_duration = await db.get_average_touch_duration(start_time=start_time)

        # Cache the result
        if period in statistics_engine.cache_ttl:
            ttl = statistics_engine.cache_ttl[period]
            await db.set_statistics_cache("avg_duration", period, avg_duration, ttl)

        return {"average_duration_ms": avg_duration, "period": period, "cached": False}

    except Exception as e:
        logger.error(f"Error retrieving average duration statistics: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/emotional-state/durations")
async def get_emotional_state_durations(
    period: str = Query("today", regex="^(today|week|month|year|all_time)$"),
):
    """
    Get the duration spent in each emotional state.

    Args:
        period: Time period to fetch

    Returns:
        Time spent in each emotional state
    """
    try:
        # Parse time period
        if period != "all_time":
            period_start = parse_time_period(period)
            if period_start:
                start_time = period_start.isoformat()
            else:
                start_time = None
        else:
            start_time = None

        # Get state durations
        durations = await db.get_emotional_state_durations(start_time=start_time)

        return {
            "durations": durations,
            "period": period,
            "start_time": start_time,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error retrieving emotional state durations: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
