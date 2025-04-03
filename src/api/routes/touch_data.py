"""
Touch Data API Routes for Touch Companion Application

This module provides API endpoints for:
- Retrieving touch event data
- Getting touch event counts
- Filtering touch events by time period and sensor
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Depends

from modules.database import db
from modules.utils import parse_time_period

# Create router
router = APIRouter()

# Configure logging
logger = logging.getLogger("api.touch_data")


@router.get("/events")
async def get_touch_events(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    sensor_id: Optional[int] = Query(None, ge=0, le=11),
    period: str = Query("all_time", regex="^(all_time|today|hour|week|month|year)$"),
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None),
):
    """
    Get touch events with optional filtering.

    Args:
        limit: Maximum number of events to return
        offset: Number of events to skip
        sensor_id: Filter by specific sensor ID
        period: Predefined time period
        start_time: Filter events after this time (ISO format)
        end_time: Filter events before this time (ISO format)

    Returns:
        List of touch events with total count
    """
    try:
        # Parse time period if start_time not provided
        if not start_time and period != "all_time":
            period_start = parse_time_period(period)
            if period_start:
                start_time = period_start.isoformat()

        # Get touch events
        events = await db.get_touch_events(
            limit=limit,
            offset=offset,
            start_time=start_time,
            end_time=end_time,
            sensor_id=sensor_id,
        )

        # Get total count for pagination
        total_count = await db.get_touch_count(
            start_time=start_time, end_time=end_time, sensor_id=sensor_id
        )

        return {
            "events": events,
            "total": total_count,
            "limit": limit,
            "offset": offset,
        }

    except Exception as e:
        logger.error(f"Error retrieving touch events: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/count")
async def get_touch_count(
    sensor_id: Optional[int] = Query(None, ge=0, le=11),
    period: str = Query("all_time", regex="^(all_time|today|hour|week|month|year)$"),
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None),
):
    """
    Get count of touch events with optional filtering.

    Args:
        sensor_id: Filter by specific sensor ID
        period: Predefined time period
        start_time: Filter events after this time (ISO format)
        end_time: Filter events before this time (ISO format)

    Returns:
        Count of touch events
    """
    try:
        # Parse time period if start_time not provided
        if not start_time and period != "all_time":
            period_start = parse_time_period(period)
            if period_start:
                start_time = period_start.isoformat()

        # Get touch count
        count = await db.get_touch_count(
            start_time=start_time, end_time=end_time, sensor_id=sensor_id
        )

        return {
            "count": count,
            "period": period,
            "sensor_id": sensor_id,
            "start_time": start_time,
            "end_time": end_time,
        }

    except Exception as e:
        logger.error(f"Error retrieving touch count: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/duration/average")
async def get_average_touch_duration(
    sensor_id: Optional[int] = Query(None, ge=0, le=11),
    period: str = Query("all_time", regex="^(all_time|today|hour|week|month|year)$"),
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None),
):
    """
    Get average duration of touch events with optional filtering.

    Args:
        sensor_id: Filter by specific sensor ID
        period: Predefined time period
        start_time: Filter events after this time (ISO format)
        end_time: Filter events before this time (ISO format)

    Returns:
        Average duration in milliseconds
    """
    try:
        # Parse time period if start_time not provided
        if not start_time and period != "all_time":
            period_start = parse_time_period(period)
            if period_start:
                start_time = period_start.isoformat()

        # Get average duration
        avg_duration = await db.get_average_touch_duration(
            start_time=start_time, end_time=end_time, sensor_id=sensor_id
        )

        return {
            "average_duration_ms": avg_duration,
            "period": period,
            "sensor_id": sensor_id,
            "start_time": start_time,
            "end_time": end_time,
        }

    except Exception as e:
        logger.error(f"Error retrieving average touch duration: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
