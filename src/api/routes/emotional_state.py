"""
Emotional State API Routes for Touch Companion Application

This module provides API endpoints for:
- Getting the current emotional state
- Retrieving state history
- Forcibly changing the emotional state (for testing)
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Path, Body, Depends

from modules.database import db
from modules.utils import parse_time_period

# Get reference to the emotional state engine
from api.app import emotional_state_engine

# Create router
router = APIRouter()

# Configure logging
logger = logging.getLogger("api.emotional_state")




@router.get("/current")
async def get_current_emotional_state():
    """
    Get the current emotional state.

    Returns:
        Current emotional state information
    """
    try:
        # Get state
        state = await emotional_state_engine.get_current_state()
        state_info = emotional_state_engine.get_state_info()

        return {
            "state": state,
            "in_transition": state_info["in_transition"],
            "touch_count": state_info["touch_count"],
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error retrieving current emotional state: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/history")
async def get_emotional_state_history(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None),
):
    """
    Get emotional state transition history.

    Args:
        limit: Maximum number of transitions to return
        offset: Number of transitions to skip
        start_time: Filter transitions after this time (ISO format)
        end_time: Filter transitions before this time (ISO format)

    Returns:
        List of emotional state transitions
    """
    try:
        # This would require additional database methods not yet implemented
        # For now, return a placeholder error
        raise HTTPException(
            status_code=501, detail="State history endpoint not implemented yet"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving emotional state history: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/set/{state}")
async def set_emotional_state(state: str = Path(..., regex="^(sad|glad)$")):
    """
    Forcibly set the emotional state (for testing only).

    This endpoint is primarily for testing purposes to force
    a state transition without waiting for touch events.

    Args:
        state: New emotional state ("sad" or "glad")

    Returns:
        Result of the state change operation
    """
    try:
        # Only allow in development mode for testing
        # In production, this would be guarded by authentication

        from enum import Enum

        EmotionalState = Enum("EmotionalState", "SAD GLAD")

        # Set new state
        new_state = EmotionalState.GLAD if state == "glad" else EmotionalState.SAD
        await emotional_state_engine._change_state(new_state)

        return {
            "success": True,
            "new_state": state,
            "timestamp": datetime.now().isoformat(),
            "message": "Emotional state manually changed",
        }

    except Exception as e:
        logger.error(f"Error setting emotional state: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
