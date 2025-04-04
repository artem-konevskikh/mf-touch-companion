// Format large numbers with Russian abbreviations
function formatNumber(number) {
    if (number >= 1000000) {
        return (number / 1000000).toFixed(1).replace('.0', '') + ' млн';
    } else if (number >= 1000) {
        return (number / 1000).toFixed(1).replace('.0', '') + ' тыс';
    }
    return number.toString();
}

// Format time in seconds to minutes or hours
function formatTime(seconds) {
    if (seconds >= 3600) {
        const hours = Math.floor(seconds / 3600);
        return hours + ' ч';
    } else if (seconds >= 60) {
        const minutes = Math.floor(seconds / 60);
        return minutes + ' мин';
    }
    return Math.floor(seconds) + ' сек';
}

// Format date and time
function formatDateTime(timestamp) {
    const date = new Date(timestamp * 1000);
    return date.toLocaleTimeString('ru-RU', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
}

// Apply update animation to an element
function animateUpdate(elementId) {
    const element = document.getElementById(elementId);
    element.classList.remove('update-animation');
    void element.offsetWidth; // Force reflow to restart animation
    element.classList.add('update-animation');
}

// Update all metrics with new data
function updateMetrics(data) {
    // Primary metrics
    document.getElementById('total-count').textContent = formatNumber(data.total_count);
    document.getElementById('hour-count').textContent = formatNumber(data.hour_count);

    // Secondary metrics
    document.getElementById('today-count').textContent = formatNumber(data.today_count);
    document.getElementById('avg-duration').textContent = data.avg_duration.toFixed(2) + ' сек';

    // Emotional state
    const stateEmoji = document.getElementById('state-emoji');
    stateEmoji.textContent = data.emotional_state_emoji;

    // Remove old classes
    stateEmoji.classList.remove('sad', 'glad');

    // Add new class based on state
    if (data.emotional_state === 'glad') {
        stateEmoji.classList.add('glad');
    } else {
        stateEmoji.classList.add('sad');
    }

    // State times
    document.getElementById('sad-time').textContent = formatTime(data.emotional_state_time.sad);
    document.getElementById('glad-time').textContent = formatTime(data.emotional_state_time.glad);

    // Last update
    document.getElementById('last-update').textContent = 'Последнее обновление: ' + formatDateTime(data.last_update);

    // Animate updates
    animateUpdate('total-count');
    animateUpdate('hour-count');
    animateUpdate('today-count');
}

// Initialize WebSocket connection
let socket = null;

function connectWebSocket() {
    if (socket) {
        socket.close();
    }

    // Determine the correct WebSocket URL based on the current page URL
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/api/ws/statistics`;
    
    socket = new WebSocket(wsUrl);

    socket.onopen = function() {
        console.log('WebSocket connection established');
    };

    socket.onmessage = function(event) {
        const data = JSON.parse(event.data);
        if (data.success) {
            updateMetrics(data.data);
        } else {
            console.error('Error in WebSocket message:', data.error);
        }
    };

    socket.onclose = function() {
        console.log('WebSocket connection closed. Reconnecting in 5 seconds...');
        setTimeout(connectWebSocket, 5000);
    };

    socket.onerror = function(error) {
        console.error('WebSocket error:', error);
        socket.close();
    };
}

// Fallback to SSE if WebSockets are not supported
function connectEventSource() {
    console.log('Falling back to SSE connection');
    let evtSource = new EventSource('/api/events/statistics');

    evtSource.onmessage = function (event) {
        const data = JSON.parse(event.data);
        if (data.success) {
            updateMetrics(data.data);
        } else {
            console.error('Error in SSE:', data.error);
        }
    };

    evtSource.onerror = function () {
        console.error('EventSource failed. Reconnecting in 5 seconds...');
        evtSource.close();
        setTimeout(connectEventSource, 5000);
    };
}
}

// Initial data load
async function loadInitialData() {
    try {
        const response = await fetch('/api/statistics');
        const result = await response.json();

        if (result.success) {
            updateMetrics(result.data);
            // Try to connect using WebSockets first
            if ('WebSocket' in window) {
                connectWebSocket();
            } else {
                // Fall back to SSE if WebSockets are not supported
                connectEventSource();
            }
        } else {
            console.error('Error loading initial data:', result.error);
            setTimeout(loadInitialData, 3000);
        }
    } catch (error) {
        console.error('Failed to load initial data:', error);
        setTimeout(loadInitialData, 3000);
    }
}

// Start the application
document.addEventListener('DOMContentLoaded', loadInitialData);