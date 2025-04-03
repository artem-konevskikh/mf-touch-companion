"""
Database Module for Touch Companion Application

This module handles all database operations including:
- Schema creation and management
- Asynchronous CRUD operations for touch events
- Query functions for statistics calculation
- Data retention policy implementation
"""

import sqlite3
import asyncio
import aiosqlite
import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

# Make sure the data directory exists
Path("data").mkdir(exist_ok=True)

DATABASE_PATH = "data/touch_data.db"
# Max number of days to keep detailed touch data
DATA_RETENTION_DAYS = 30

# SQL queries
CREATE_TABLES = """
-- Table for storing individual touch events
CREATE TABLE IF NOT EXISTS touch_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sensor_id INTEGER NOT NULL,
    timestamp TEXT NOT NULL,
    duration_ms INTEGER NOT NULL,
    state TEXT NOT NULL
);

-- Table for tracking emotional state transitions
CREATE TABLE IF NOT EXISTS emotional_states (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    state TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT,
    duration_sec INTEGER
);

-- Table for caching frequently accessed statistics
CREATE TABLE IF NOT EXISTS statistics_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stat_type TEXT NOT NULL,
    time_period TEXT NOT NULL,
    value REAL NOT NULL,
    calculated_at TEXT NOT NULL,
    ttl_seconds INTEGER NOT NULL
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_touch_events_timestamp ON touch_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_touch_events_sensor_id ON touch_events(sensor_id);
CREATE INDEX IF NOT EXISTS idx_emotional_states_state ON emotional_states(state);
CREATE INDEX IF NOT EXISTS idx_statistics_cache_type_period ON statistics_cache(stat_type, time_period);
"""


class Database:
    """Handles all database operations for the touch companion application."""

    def __init__(self):
        """Initialize the database connection."""
        self._lock = asyncio.Lock()
        self._db_initialized = False

    async def initialize(self):
        """Initialize the database schema."""
        async with self._lock:
            if not self._db_initialized:
                async with aiosqlite.connect(DATABASE_PATH) as db:
                    await db.executescript(CREATE_TABLES)
                    await db.commit()
                self._db_initialized = True
                await self._initialize_emotional_state()

    async def _initialize_emotional_state(self):
        """Initialize the emotional state if none exists."""
        async with aiosqlite.connect(DATABASE_PATH) as db:
            # Check if there's any active emotional state
            query = "SELECT id FROM emotional_states WHERE end_time IS NULL"
            cursor = await db.execute(query)
            result = await cursor.fetchone()

            if not result:
                # Insert initial emotional state (starting as neutral/sad)
                now = datetime.datetime.now().isoformat()
                query = "INSERT INTO emotional_states (state, start_time) VALUES (?, ?)"
                await db.execute(query, ("sad", now))
                await db.commit()

    async def add_touch_event(
        self, sensor_id: int, duration_ms: int, state: str
    ) -> int:
        """
        Add a new touch event to the database.

        Args:
            sensor_id: ID of the sensor that detected the touch
            duration_ms: Duration of the touch in milliseconds
            state: Current emotional state at the time of touch

        Returns:
            ID of the newly created touch event
        """
        timestamp = datetime.datetime.now().isoformat()

        async with aiosqlite.connect(DATABASE_PATH) as db:
            cursor = await db.execute(
                "INSERT INTO touch_events (sensor_id, timestamp, duration_ms, state) VALUES (?, ?, ?, ?)",
                (sensor_id, timestamp, duration_ms, state),
            )
            await db.commit()
            return cursor.lastrowid

    async def get_touch_events(
        self,
        limit: int = 100,
        offset: int = 0,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        sensor_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve touch events with optional filtering.

        Args:
            limit: Maximum number of records to return
            offset: Number of records to skip
            start_time: Filter events after this time (ISO format)
            end_time: Filter events before this time (ISO format)
            sensor_id: Filter by specific sensor ID

        Returns:
            List of touch events as dictionaries
        """
        query = "SELECT * FROM touch_events WHERE 1=1"
        params = []

        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time)

        if end_time:
            query += " AND timestamp <= ?"
            params.append(end_time)

        if sensor_id is not None:
            query += " AND sensor_id = ?"
            params.append(sensor_id)

        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        async with aiosqlite.connect(DATABASE_PATH) as db:
            db.row_factory = sqlite3.Row
            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_touch_count(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        sensor_id: Optional[int] = None,
    ) -> int:
        """
        Get the count of touch events with optional filtering.

        Args:
            start_time: Filter events after this time (ISO format)
            end_time: Filter events before this time (ISO format)
            sensor_id: Filter by specific sensor ID

        Returns:
            Count of touch events
        """
        query = "SELECT COUNT(*) as count FROM touch_events WHERE 1=1"
        params = []

        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time)

        if end_time:
            query += " AND timestamp <= ?"
            params.append(end_time)

        if sensor_id is not None:
            query += " AND sensor_id = ?"
            params.append(sensor_id)

        async with aiosqlite.connect(DATABASE_PATH) as db:
            cursor = await db.execute(query, params)
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def get_average_touch_duration(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        sensor_id: Optional[int] = None,
    ) -> float:
        """
        Get the average duration of touch events with optional filtering.

        Args:
            start_time: Filter events after this time (ISO format)
            end_time: Filter events before this time (ISO format)
            sensor_id: Filter by specific sensor ID

        Returns:
            Average duration in milliseconds or 0 if no events
        """
        query = "SELECT AVG(duration_ms) as avg_duration FROM touch_events WHERE 1=1"
        params = []

        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time)

        if end_time:
            query += " AND timestamp <= ?"
            params.append(end_time)

        if sensor_id is not None:
            query += " AND sensor_id = ?"
            params.append(sensor_id)

        async with aiosqlite.connect(DATABASE_PATH) as db:
            cursor = await db.execute(query, params)
            row = await cursor.fetchone()
            return row[0] if row and row[0] is not None else 0

    async def update_emotional_state(self, state: str) -> int:
        """
        Update the emotional state.

        Close any open emotional state and create a new one.

        Args:
            state: New emotional state ("sad" or "glad")

        Returns:
            ID of the new emotional state record
        """
        now = datetime.datetime.now()
        now_iso = now.isoformat()

        async with aiosqlite.connect(DATABASE_PATH) as db:
            # Close any open emotional state
            await db.execute(
                """
                UPDATE emotional_states 
                SET end_time = ?, 
                    duration_sec = ROUND((JULIANDAY(?) - JULIANDAY(start_time)) * 86400)
                WHERE end_time IS NULL
                """,
                (now_iso, now_iso),
            )

            # Create a new emotional state
            cursor = await db.execute(
                "INSERT INTO emotional_states (state, start_time) VALUES (?, ?)",
                (state, now_iso),
            )
            await db.commit()
            return cursor.lastrowid

    async def get_current_emotional_state(self) -> str:
        """
        Get the current emotional state.

        Returns:
            Current emotional state ("sad" or "glad")
        """
        async with aiosqlite.connect(DATABASE_PATH) as db:
            cursor = await db.execute(
                "SELECT state FROM emotional_states WHERE end_time IS NULL"
            )
            row = await cursor.fetchone()
            return row[0] if row else "sad"

    async def get_emotional_state_durations(
        self, start_time: Optional[str] = None, end_time: Optional[str] = None
    ) -> Dict[str, int]:
        """
        Get the total duration for each emotional state within a time period.

        Args:
            start_time: Filter states after this time (ISO format)
            end_time: Filter states before this time (ISO format)

        Returns:
            Dictionary with state names as keys and total seconds as values
        """
        if not end_time:
            end_time = datetime.datetime.now().isoformat()

        # For ongoing state, use current time as the end time for calculation
        query = """
        SELECT 
            state,
            SUM(
                CASE 
                    WHEN end_time IS NULL THEN 
                        ROUND((JULIANDAY(?) - JULIANDAY(start_time)) * 86400)
                    ELSE 
                        duration_sec
                END
            ) as total_duration
        FROM emotional_states
        WHERE 1=1
        """
        params = [end_time]

        if start_time:
            query += " AND (end_time >= ? OR end_time IS NULL) AND start_time <= ?"
            params.extend([start_time, end_time])
        else:
            query += " AND (end_time IS NULL OR start_time <= ?)"
            params.append(end_time)

        query += " GROUP BY state"

        async with aiosqlite.connect(DATABASE_PATH) as db:
            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()

            # Initialize with zeros to ensure both states are present
            durations = {"sad": 0, "glad": 0}

            for row in rows:
                durations[row[0]] = int(row[1]) if row[1] is not None else 0

            return durations

    async def set_statistics_cache(
        self, stat_type: str, time_period: str, value: float, ttl_seconds: int = 300
    ) -> None:
        """
        Cache a statistics value.

        Args:
            stat_type: Type of statistic (e.g., "touch_count", "avg_duration")
            time_period: Period identifier (e.g., "all_time", "today", "hour")
            value: The calculated value to cache
            ttl_seconds: Time to live in seconds (default: 5 minutes)
        """
        calculated_at = datetime.datetime.now().isoformat()

        async with aiosqlite.connect(DATABASE_PATH) as db:
            # Delete any existing cache for this stat_type and time_period
            await db.execute(
                "DELETE FROM statistics_cache WHERE stat_type = ? AND time_period = ?",
                (stat_type, time_period),
            )

            # Insert new cache value
            await db.execute(
                """
                INSERT INTO statistics_cache 
                (stat_type, time_period, value, calculated_at, ttl_seconds) 
                VALUES (?, ?, ?, ?, ?)
                """,
                (stat_type, time_period, value, calculated_at, ttl_seconds),
            )
            await db.commit()

    async def get_statistics_cache(
        self, stat_type: str, time_period: str
    ) -> Optional[float]:
        """
        Retrieve a cached statistics value if it's still valid.

        Args:
            stat_type: Type of statistic
            time_period: Period identifier

        Returns:
            Cached value or None if not found or expired
        """
        now = datetime.datetime.now()

        async with aiosqlite.connect(DATABASE_PATH) as db:
            cursor = await db.execute(
                """
                SELECT value, calculated_at, ttl_seconds 
                FROM statistics_cache 
                WHERE stat_type = ? AND time_period = ?
                """,
                (stat_type, time_period),
            )
            row = await cursor.fetchone()

            if not row:
                return None

            value, calculated_at_str, ttl_seconds = row
            calculated_at = datetime.datetime.fromisoformat(calculated_at_str)

            # Check if cache is still valid
            age_seconds = (now - calculated_at).total_seconds()
            if age_seconds <= ttl_seconds:
                return value

            # Cache expired, delete it
            await db.execute(
                "DELETE FROM statistics_cache WHERE stat_type = ? AND time_period = ?",
                (stat_type, time_period),
            )
            await db.commit()
            return None

    async def clean_old_data(self) -> int:
        """
        Remove old touch data based on retention policy.

        Returns:
            Number of records deleted
        """
        retention_date = (
            datetime.datetime.now() - datetime.timedelta(days=DATA_RETENTION_DAYS)
        ).isoformat()

        async with aiosqlite.connect(DATABASE_PATH) as db:
            cursor = await db.execute(
                "DELETE FROM touch_events WHERE timestamp < ?", (retention_date,)
            )
            await db.commit()
            return cursor.rowcount

    async def optimize_database(self) -> None:
        """Run database optimization tasks."""
        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.execute("VACUUM")
            await db.execute("PRAGMA optimize")
            await db.commit()


# Create a singleton instance
db = Database()
