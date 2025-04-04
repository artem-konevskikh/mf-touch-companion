"""
Database module for touch sensor companion device.

This module provides a SQLite database interface for storing and retrieving
touch event data, as well as calculating statistics.
"""

from __future__ import annotations

import datetime
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Dict, Optional, Tuple, Union, Any, Generator

# Type aliases
Timestamp = float
SensorId = int


@dataclass
class TouchEvent:
    """Represents a touch event from a sensor."""

    sensor_id: SensorId
    timestamp: Timestamp
    duration: float


@dataclass
class EmotionalState:
    """Represents an emotional state change event."""

    state: str  # 'sad' or 'glad'
    timestamp: Timestamp


class DatabaseCache:
    """Simple cache for frequently accessed database statistics."""

    def __init__(self, ttl: int = 10) -> None:
        """Initialize the cache with a time-to-live for entries.

        Args:
            ttl: Time to live in seconds for cache entries
        """
        self._cache: Dict[str, Tuple[Any, Timestamp]] = {}
        self._ttl = ttl

    def get(self, key: str) -> Optional[Any]:
        """Get a value from the cache if it exists and is not expired.

        Args:
            key: Cache key

        Returns:
            The cached value or None if not found or expired
        """
        if key in self._cache:
            value, timestamp = self._cache[key]
            if time.time() - timestamp < self._ttl:
                return value
            # Remove expired entry
            del self._cache[key]
        return None

    def set(self, key: str, value: Any) -> None:
        """Set a value in the cache with the current timestamp.

        Args:
            key: Cache key
            value: Value to cache
        """
        self._cache[key] = (value, time.time())

    def invalidate(self, key: str) -> None:
        """Invalidate a specific cache entry.

        Args:
            key: Cache key to invalidate
        """
        if key in self._cache:
            del self._cache[key]

    def invalidate_all(self) -> None:
        """Invalidate all cache entries."""
        self._cache.clear()


class Database:
    """SQLite database interface for the touch sensor companion device."""

    def __init__(self, db_path: Union[str, Path], max_events: int = 1000000) -> None:
        """Initialize the database connection and create tables if needed.

        Args:
            db_path: Path to the SQLite database file
            max_events: Maximum number of events to keep in the database
        """
        self.db_path = Path(db_path)
        self.max_events = max_events
        self.cache = DatabaseCache()
        self.lock = Lock()  # For thread safety

        # Create directory if it doesn't exist
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize database
        self._initialize_database()

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager for database connections.

        Yields:
            A SQLite connection
        """
        with self.lock:
            connection = sqlite3.connect(self.db_path)
            # Enable foreign keys
            connection.execute("PRAGMA foreign_keys = ON")
            # For better performance
            connection.execute("PRAGMA journal_mode = WAL")
            # Return rows as dictionaries
            connection.row_factory = sqlite3.Row

            try:
                yield connection
            finally:
                connection.close()

    def _initialize_database(self) -> None:
        """Initialize the database schema."""
        with self.get_connection() as conn:
            # Create touch_events table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS touch_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sensor_id INTEGER NOT NULL,
                    timestamp REAL NOT NULL,
                    duration REAL NOT NULL,
                    
                    -- Indexes
                    INDEX idx_sensor_timestamp (sensor_id, timestamp)
                )
                """
            )

            # Create emotional_states table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS emotional_states (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    state TEXT NOT NULL CHECK(state IN ('sad', 'glad')),
                    timestamp REAL NOT NULL,
                    
                    -- Index
                    INDEX idx_timestamp (timestamp)
                )
                """
            )

            # Create daily_statistics table for pre-computed statistics
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS daily_statistics (
                    date TEXT PRIMARY KEY,
                    total_touches INTEGER NOT NULL DEFAULT 0,
                    avg_duration REAL NOT NULL DEFAULT 0,
                    sad_time REAL NOT NULL DEFAULT 0,
                    glad_time REAL NOT NULL DEFAULT 0,
                    last_updated REAL NOT NULL
                )
                """
            )

            conn.commit()

    def add_touch_event(self, event: TouchEvent) -> int:
        """Add a touch event to the database.

        Args:
            event: The touch event to add

        Returns:
            The ID of the inserted event
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO touch_events (sensor_id, timestamp, duration) VALUES (?, ?, ?)",
                (event.sensor_id, event.timestamp, event.duration),
            )
            conn.commit()

            # Invalidate relevant caches
            self.cache.invalidate("total_touch_count")
            self.cache.invalidate("touch_count_last_hour")
            self.cache.invalidate("touch_count_today")
            self.cache.invalidate("avg_touch_duration")

            # Clean up old events if needed
            self._cleanup_old_events(conn)

            # lastrowid is documented to return int or None, so we need to handle the None case
            last_row_id = cursor.lastrowid
            if last_row_id is None:
                raise RuntimeError("Failed to get last inserted row ID")

            return last_row_id

    def add_emotional_state(self, state: EmotionalState) -> int:
        """Add an emotional state change to the database.

        Args:
            state: The emotional state to add

        Returns:
            The ID of the inserted state change
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO emotional_states (state, timestamp) VALUES (?, ?)",
                (state.state, state.timestamp),
            )
            conn.commit()

            # Invalidate relevant caches
            self.cache.invalidate("emotional_state_time")

            # lastrowid is documented to return int or None, so we need to handle the None case
            last_row_id = cursor.lastrowid
            if last_row_id is None:
                raise RuntimeError("Failed to get last inserted row ID")
            return last_row_id

    def _cleanup_old_events(self, conn: sqlite3.Connection) -> None:
        """Clean up old events if the maximum number is exceeded.

        Args:
            conn: The database connection
        """
        cursor = conn.cursor()
        # Count total events
        cursor.execute("SELECT COUNT(*) FROM touch_events")
        count = cursor.fetchone()[0]

        if count > self.max_events:
            # Delete oldest events, keeping max_events
            delete_count = count - self.max_events
            cursor.execute(
                "DELETE FROM touch_events WHERE id IN (SELECT id FROM touch_events ORDER BY timestamp ASC LIMIT ?)",
                (delete_count,),
            )
            conn.commit()

    def get_total_touch_count(self) -> int:
        """Get the total number of touch events.

        Returns:
            The total number of touch events
        """
        # Check cache first
        cached = self.cache.get("total_touch_count")
        if cached is not None:
            return cached

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM touch_events")
            result = cursor.fetchone()[0]

            # Cache the result
            self.cache.set("total_touch_count", result)

            return result

    def get_touch_count_last_hour(self) -> int:
        """Get the number of touch events in the last hour.

        Returns:
            The number of touch events in the last hour
        """
        # Check cache first
        cached = self.cache.get("touch_count_last_hour")
        if cached is not None:
            return cached

        one_hour_ago = time.time() - 3600  # 1 hour in seconds

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM touch_events WHERE timestamp >= ?",
                (one_hour_ago,),
            )
            result = cursor.fetchone()[0]

            # Cache the result
            self.cache.set("touch_count_last_hour", result)

            return result

    def get_touch_count_today(self) -> int:
        """Get the number of touch events today (since midnight).

        Returns:
            The number of touch events today
        """
        # Check cache first
        cached = self.cache.get("touch_count_today")
        if cached is not None:
            return cached

        # Get timestamp for today at midnight
        today = datetime.datetime.now().replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        today_timestamp = today.timestamp()

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM touch_events WHERE timestamp >= ?",
                (today_timestamp,),
            )
            result = cursor.fetchone()[0]

            # Cache the result
            self.cache.set("touch_count_today", result)

            return result

    def get_average_touch_duration(self) -> float:
        """Get the average duration of all touch events.

        Returns:
            The average duration in seconds
        """
        # Check cache first
        cached = self.cache.get("avg_touch_duration")
        if cached is not None:
            return cached

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT AVG(duration) FROM touch_events")
            result = cursor.fetchone()[0]

            # Handle NULL result (no events yet)
            if result is None:
                result = 0.0

            # Cache the result
            self.cache.set("avg_touch_duration", result)

            return result

    def get_time_in_emotional_states_today(self) -> Dict[str, float]:
        """Get the time spent in each emotional state today.

        Returns:
            A dictionary with 'sad' and 'glad' keys and time values in seconds
        """
        # Check cache first
        cached = self.cache.get("emotional_state_time")
        if cached is not None:
            return cached

        # Get timestamp for today at midnight
        today = datetime.datetime.now().replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        today_timestamp = today.timestamp()
        current_time = time.time()

        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Get all state changes today, ordered by timestamp
            cursor.execute(
                """
                SELECT state, timestamp FROM emotional_states 
                WHERE timestamp >= ? 
                ORDER BY timestamp ASC
                """,
                (today_timestamp,),
            )
            state_changes = cursor.fetchall()

            # Get the last state before today
            cursor.execute(
                """
                SELECT state FROM emotional_states 
                WHERE timestamp < ? 
                ORDER BY timestamp DESC 
                LIMIT 1
                """,
                (today_timestamp,),
            )
            last_state_before_today = cursor.fetchone()

            # Initialize result
            result = {"sad": 0.0, "glad": 0.0}

            # If no state changes today and no previous state, return zeros
            if not state_changes and not last_state_before_today:
                self.cache.set("emotional_state_time", result)
                return result

            # Set initial state
            current_state = (
                last_state_before_today[0] if last_state_before_today else "sad"
            )
            last_time = today_timestamp

            # Calculate time in each state
            for change in state_changes:
                state, change_time = change["state"], change["timestamp"]

                # Add time in previous state
                result[current_state] += change_time - last_time

                # Update for next iteration
                current_state = state
                last_time = change_time

            # Add time from last change to now
            result[current_state] += current_time - last_time

            # Cache the result
            self.cache.set("emotional_state_time", result)

            return result

    def get_current_emotional_state(self) -> str:
        """Get the current emotional state.

        Returns:
            'glad' or 'sad' based on the most recent state change
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT state FROM emotional_states
                ORDER BY timestamp DESC
                LIMIT 1
                """
            )
            result = cursor.fetchone()

            # Default to 'sad' if no state has been set
            return result[0] if result else "sad"

    def get_touch_frequency(self, time_window: int = 3600) -> float:
        """Get the touch frequency (touches per minute) in the given time window.

        Args:
            time_window: Time window in seconds (default: 1 hour)

        Returns:
            Touch frequency in touches per minute
        """
        window_start = time.time() - time_window

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM touch_events WHERE timestamp >= ?",
                (window_start,),
            )
            count = cursor.fetchone()[0]

            # Calculate touches per minute
            minutes = time_window / 60
            return count / minutes if minutes > 0 else 0
