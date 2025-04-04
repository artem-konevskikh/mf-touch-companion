"""
Pydantic models for the web application.
"""

from typing import Dict, Optional, Any

from pydantic import BaseModel


class TouchStatistics(BaseModel):
    """Statistics about touch events."""

    total_count: int
    hour_count: int
    today_count: int
    avg_duration: float
    emotional_state: str
    emotional_state_emoji: str
    emotional_state_time: Dict[str, float]
    last_update: float


class ApiResponse(BaseModel):
    """Standard API response format."""

    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
