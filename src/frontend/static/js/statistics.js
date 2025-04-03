/**
 * Statistics page JavaScript for Touch Companion
 * 
 * This script handles:
 * - Displaying and updating statistics
 * - Connecting to server-sent events for real-time updates
 * - Formatting values with Russian number abbreviations
 * - Visualizing emotional state durations
 */

// DOM elements
const totalCountElement = document.getElementById('total-count');
const todayCountElement = document.getElementById('today-count');
const hourCountElement = document.getElementById('hour-count');
const avgDurationElement = document.getElementById('avg-duration');
const stateTextElement = document.getElementById('state-text');
const stateCircleElement = document.querySelector('.state-circle');
const lastUpdateTimeElement = document.getElementById('last-update-time');
const gladTimeElement = document.getElementById('glad-time');
const sadTimeElement = document.getElementById('sad-time');
const gladBarElement = document.getElementById('glad-bar');
const sadBarElement = document.getElementById('sad-bar');

// State variables
let currentState = '';
let stats = {};

// Event source for server-sent events
let eventSource = null;

// Connect to server events
function connectEventSource() {
    if (eventSource) {
        eventSource.close();
    }

    eventSource = new EventSource('/api/events');

    // Event handlers
    eventSource.addEventListener('statistics_update', handleStatsUpdate);
    eventSource.addEventListener('state_change', handleStateChange);
    eventSource.addEventListener('error', handleEventError);

    console.log('Connected to event stream');
}

// Handle statistics updates
function handleStatsUpdate(event) {
    try {
        const data = JSON.parse(event.data);
        stats = data;

        // Update displayed statistics
        updateDisplayedStats();

        // Update last update time
        lastUpdateTimeElement.textContent = formatTimeHM(new Date());

    } catch (error) {
        console.error('Error processing statistics update:', error);
    }
}

// Handle emotional state changes
function handleStateChange(event) {
    try {
        const data = JSON.parse(event.data);

        // Update state display
        updateStateDisplay(data.state);

    } catch (error) {
        console.error('Error processing state change:', error);
    }
}

// Handle event source errors
function handleEventError(event) {
    console.error('EventSource error:', event);

    // Reconnect after 5 seconds
    setTimeout(() => {
        connectEventSource();
    }, 5000);
}

// Update emotional state display
function updateStateDisplay(state) {
    if (currentState === state) return;

    currentState = state;

    // Update text
    if (state === 'glad') {
        stateTextElement.textContent = 'Радость';
    } else {
        stateTextElement.textContent = 'Грусть';
    }

    // Update circle color
    stateCircleElement.classList.remove('glad', 'sad');
    stateCircleElement.classList.add(state);

    // Update body background subtle color
    if (state === 'glad') {
        document.body.style.backgroundColor = '#fffbeb';
    } else {
        document.body.style.backgroundColor = '#eff6ff';
    }
}

// Update displayed statistics
function updateDisplayedStats() {
    if (!stats) return;

    // Update count statistics
    if (stats.touch_count) {
        // All-time count
        if (stats.touch_count.all_time !== undefined) {
            totalCountElement.textContent = formatNumberRu(stats.touch_count.all_time);
        }

        // Today's count
        if (stats.touch_count.today !== undefined) {
            todayCountElement.textContent = formatNumberRu(stats.touch_count.today);
        }

        // Hour count
        if (stats.touch_count.hour !== undefined) {
            hourCountElement.textContent = formatNumberRu(stats.touch_count.hour);
        }
    }

    // Update average duration
    if (stats.avg_duration !== undefined) {
        // Format with appropriate unit (milliseconds or seconds)
        const value = stats.avg_duration;

        if (value >= 1000) {
            // Show in seconds if >= 1 second
            const seconds = value / 1000;
            avgDurationElement.textContent = `${seconds.toFixed(1).replace('.', ',')} сек`;
        } else {
            // Show in milliseconds
            avgDurationElement.textContent = `${Math.round(value)} мс`;
        }
    }

    // Update emotional state durations
    if (stats.emotional_state && stats.emotional_state.durations) {
        const durations = stats.emotional_state.durations;

        // Get durations in seconds
        const gladSeconds = durations.glad || 0;
        const sadSeconds = durations.sad || 0;
        const totalSeconds = gladSeconds + sadSeconds;

        // Update time displays
        gladTimeElement.textContent = formatTimeRu(gladSeconds);
        sadTimeElement.textContent = formatTimeRu(sadSeconds);

        // Update progress bar
        if (totalSeconds > 0) {
            const gladPercentage = (gladSeconds / totalSeconds) * 100;
            const sadPercentage = (sadSeconds / totalSeconds) * 100;

            gladBarElement.style.width = `${gladPercentage}%`;
            sadBarElement.style.width = `${sadPercentage}%`;
        } else {
            // Default 50/50 if no data
            gladBarElement.style.width = '50%';
            sadBarElement.style.width = '50%';
        }
    }
}

// Initial data load
async function loadInitialData() {
    try {
        // Get all statistics
        const response = await fetch('/api/statistics/all');
        if (!response.ok) {
            throw new Error(`HTTP error ${response.status}`);
        }

        stats = await response.json();

        // Get current emotional state
        const stateResponse = await fetch('/api/emotional-state/current');
        if (!stateResponse.ok) {
            throw new Error(`HTTP error ${stateResponse.status}`);
        }

        const stateData = await stateResponse.json();

        // Update displays
        updateDisplayedStats();
        updateStateDisplay(stateData.state);

        // Update last update time
        lastUpdateTimeElement.textContent = formatTimeHM(new Date());

    } catch (error) {
        console.error('Error loading initial data:', error);

        // Show error in update time
        lastUpdateTimeElement.textContent = 'Ошибка загрузки';
    }
}

// Initialize the page
function initialize() {
    // Load initial data
    loadInitialData().then(() => {
        // Connect to event source after initial data load
        connectEventSource();
    });

    // Set up auto-refresh fallback (in case SSE fails)
    setInterval(() => {
        if (!eventSource || eventSource.readyState === 2) {
            loadInitialData();
            connectEventSource();
        }
    }, 60000); // Every minute
}

// Start when DOM is loaded
document.addEventListener('DOMContentLoaded', initialize);