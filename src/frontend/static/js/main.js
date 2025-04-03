/**
 * Main page JavaScript for Touch Companion
 */

// DOM elements
const totalCountElement = document.getElementById('total-count');
const hourCountElement = document.getElementById('hour-count');
const stateTextElement = document.getElementById('state-text');
const stateCircleElement = document.querySelector('.state-circle');
const lastUpdateTimeElement = document.getElementById('last-update-time');
const hourCountAnimation = document.getElementById('hour-count-animation');

// State variables
let currentState = '';
let stats = {};
let previousHourCount = 0;

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
    eventSource.addEventListener('touch_event', handleTouchEvent);
    eventSource.addEventListener('error', handleEventError);

    console.log('Connected to event stream');
}

// Handle statistics updates
function handleStatsUpdate(event) {
    try {
        const data = JSON.parse(event.data);
        stats = data;

        // Save previous hour count for animation
        previousHourCount = parseInt(hourCountElement.textContent.replace(/\s+/g, ''), 10) || 0;

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

// Handle touch events
function handleTouchEvent(event) {
    try {
        // Get current hour count
        const currentHourCount = stats.touch_count?.hour || 0;

        // Increment hour count (we assume this is a new touch event)
        stats.touch_count.hour = currentHourCount + 1;
        stats.touch_count.all_time = (stats.touch_count?.all_time || 0) + 1;

        // Update displayed statistics
        updateDisplayedStats();

        // Trigger animation
        animateTouchEvent();

    } catch (error) {
        console.error('Error processing touch event:', error);
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

// Update displayed statistics
function updateDisplayedStats() {
    if (!stats) return;

    // Update total count
    if (stats.touch_count?.all_time !== undefined) {
        totalCountElement.textContent = formatNumberRu(stats.touch_count.all_time);
    }

    // Update hour count with animation if changed
    if (stats.touch_count?.hour !== undefined) {
        const newHourCount = stats.touch_count.hour;
        hourCountElement.textContent = formatNumberRu(newHourCount);

        // Animate if increased
        if (newHourCount > previousHourCount) {
            hourCountAnimation.classList.add('animate-update');
            setTimeout(() => {
                hourCountAnimation.classList.remove('animate-update');
            }, 1000);
        }

        previousHourCount = newHourCount;
    }
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

// Animate when a new touch event occurs
function animateTouchEvent() {
    // Add pulse animation to hour count
    hourCountElement.classList.add('pulse');

    // Remove animation after it completes
    setTimeout(() => {
        hourCountElement.classList.remove('pulse');
    }, 1000);
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