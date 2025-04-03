"""
Statistics Engine for Touch Companion Application

This module:
- Calculates real-time touch statistics
- Implements caching for frequent queries
- Provides aggregation functions for different time periods
- Calculates average duration statistics
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Set, Callable

# Import database module
from modules.database import db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("data/statistics.log"), logging.StreamHandler()],
)
logger = logging.getLogger("statistics")


class StatisticsEngine:
    """Calculates and caches statistics about touch events."""

    def __init__(self):
        """Initialize the statistics engine."""
        self.stats_changed_callbacks: Set[Callable] = set()
        self.update_interval = 10  # seconds
        self.update_task = None
        self.running = False

        # Cache TTL values (in seconds) for different time periods
        self.cache_ttl = {
            "all_time": 3600,  # 1 hour for all-time stats (changes slowly)
            "today": 300,  # 5 minutes for today's stats
            "hour": 60,  # 1 minute for hourly stats
            "minute": 10,  # 10 seconds for minute stats
        }

    async def start(self) -> None:
        """Start the statistics update loop."""
        if self.running:
            return

        self.running = True
        self.update_task = asyncio.create_task(self._update_loop())
        logger.info("Statistics engine started")

    async def stop(self) -> None:
        """Stop the statistics update loop."""
        self.running = False
        if self.update_task:
            self.update_task.cancel()
            try:
                await self.update_task
            except asyncio.CancelledError:
                pass
        logger.info("Statistics engine stopped")

    def register_stats_changed_callback(self, callback: Callable) -> None:
        """
        Register a callback to be called when statistics are updated.

        Args:
            callback: Function to call with updated statistics
        """
        self.stats_changed_callbacks.add(callback)

    def unregister_stats_changed_callback(self, callback: Callable) -> None:
        """Remove a previously registered callback."""
        if callback in self.stats_changed_callbacks:
            self.stats_changed_callbacks.remove(callback)

    async def _update_loop(self) -> None:
        """Background task to periodically update statistics."""
        while self.running:
            try:
                # Update all statistics
                stats = await self.get_all_statistics()

                # Notify callbacks
                for callback in self.stats_changed_callbacks:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(stats)
                        else:
                            callback(stats)
                    except Exception as e:
                        logger.error(f"Error in stats changed callback: {str(e)}")

                # Sleep until next update
                await asyncio.sleep(self.update_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in statistics update loop: {str(e)}")
                await asyncio.sleep(5)  # Short sleep before retry on error

    async def get_all_statistics(self) -> Dict[str, Any]:
        """
        Get a complete set of statistics.

        Returns:
            Dictionary with all statistics values
        """
        # Get current timestamp for time-based calculations
        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        hour_ago = (now - timedelta(hours=1)).isoformat()

        # Get statistics (using cache where possible)
        all_time_count = await self._get_cached_or_calculate(
            "touch_count", "all_time", lambda: db.get_touch_count()
        )

        today_count = await self._get_cached_or_calculate(
            "touch_count", "today", lambda: db.get_touch_count(start_time=today_start)
        )

        hour_count = await self._get_cached_or_calculate(
            "touch_count", "hour", lambda: db.get_touch_count(start_time=hour_ago)
        )

        avg_duration = await self._get_cached_or_calculate(
            "avg_duration", "all_time", lambda: db.get_average_touch_duration()
        )

        # Get emotional state durations for today
        state_durations = await db.get_emotional_state_durations(start_time=today_start)

        # Get current emotional state
        current_state = await db.get_current_emotional_state()

        # Compile all statistics
        return {
            "touch_count": {
                "all_time": int(all_time_count),
                "today": int(today_count),
                "hour": int(hour_count),
            },
            "avg_duration": round(float(avg_duration), 2),
            "emotional_state": {"current": current_state, "durations": state_durations},
            "timestamp": now.isoformat(),
        }

    async def _get_cached_or_calculate(
        self, stat_type: str, time_period: str, calculator: Callable
    ) -> Any:
        """
        Get a statistic from cache or calculate it if not cached.

        Args:
            stat_type: Type of statistic
            time_period: Time period for the statistic
            calculator: Async function to calculate the value if not cached

        Returns:
            The statistic value
        """
        # Try to get from cache first
        cached_value = await db.get_statistics_cache(stat_type, time_period)
        if cached_value is not None:
            return cached_value

        # Not in cache, calculate it
        try:
            value = await calculator()

            # Store in cache
            ttl = self.cache_ttl.get(time_period, 300)  # Default 5 minutes
            await db.set_statistics_cache(stat_type, time_period, value, ttl)

            return value
        except Exception as e:
            logger.error(
                f"Error calculating statistic {stat_type}/{time_period}: {str(e)}"
            )
            return 0  # Default value on error

    async def invalidate_cache(
        self, stat_type: Optional[str] = None, time_period: Optional[str] = None
    ) -> None:
        """
        Invalidate cache entries to force recalculation.

        Args:
            stat_type: Type of statistic to invalidate, or None for all
            time_period: Time period to invalidate, or None for all
        """
        # Not directly implemented in the database module,
        # but could be added if needed for manual cache invalidation
        pass
