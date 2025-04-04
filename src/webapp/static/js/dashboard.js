/**
 * Dashboard.js - Touch Companion Dashboard
 * Handles real-time updates of touch sensor data with throttling to limit updates to once per second
 */

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

// Dashboard controller - manages all dashboard functionality
class DashboardController {
    constructor() {
        this.socket = null;
        this.evtSource = null;
        this.lastUpdateTime = 0;
        this.updateInterval = 1000; // Minimum 1 second between updates
        this.reconnectDelay = 5000; // 5 seconds delay for reconnection attempts
        this.initialLoadRetryDelay = 3000; // 3 seconds delay for initial load retries
        this.maxReconnectAttempts = 5; // Maximum number of immediate reconnection attempts
        this.reconnectAttempts = 0; // Current number of reconnection attempts
        this.reconnectBackoffMultiplier = 1.5; // Backoff multiplier for reconnection attempts
        this.pingInterval = 30000; // Send ping every 30 seconds
        this.pingTimeoutId = null; // ID for the ping interval timer
        this.pongTimeoutId = null; // ID for the pong timeout timer
        this.pongTimeout = 10000; // Wait 10 seconds for pong response
    }

    // Initialize the dashboard
    init() {
        this.loadInitialData();
    }

    // Update all metrics with new data
    updateMetrics(data) {
        const now = Date.now();
        
        // Only update if at least 1 second has passed since last update
        if (now - this.lastUpdateTime < this.updateInterval) {
            return;
        }
        
        // Update timestamp
        this.lastUpdateTime = now;
        
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
    connectWebSocket() {
        if (this.socket) {
            this.socket.close();
            // Clear any existing timers
            this.clearPingPongTimers();
        }

        // Determine the correct WebSocket URL based on the current page URL
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/api/ws/statistics`;
        
        this.socket = new WebSocket(wsUrl);

        this.socket.onopen = () => {
            console.log('WebSocket connection established');
            // Reset reconnection attempts on successful connection
            this.reconnectAttempts = 0;
            this.reconnectDelay = 5000; // Reset to initial delay
            
            // Start ping-pong mechanism
            this.startPingPong();
        };

        this.socket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            
            // Check if this is a pong response
            if (data.type === 'pong') {
                console.log('Received pong from server');
                // Clear the pong timeout since we got a response
                if (this.pongTimeoutId) {
                    clearTimeout(this.pongTimeoutId);
                    this.pongTimeoutId = null;
                }
                return;
            }
            
            if (data.success) {
                this.updateMetrics(data.data);
            } else {
                console.error('Error in WebSocket message:', data.error);
            }
        };

        this.socket.onclose = (event) => {
            // Check if the close was clean (normal closure)
            const wasClean = event.wasClean;
            console.log(`WebSocket connection closed ${wasClean ? 'cleanly' : 'unexpectedly'}. Code: ${event.code}`);
            
            // If we've reached max attempts, switch to SSE
            if (this.reconnectAttempts >= this.maxReconnectAttempts) {
                console.log('Maximum WebSocket reconnection attempts reached. Switching to SSE.');
                this.connectEventSource();
                return;
            }
            
            // Increase reconnection attempts
            this.reconnectAttempts++;
            
            // Apply exponential backoff for reconnection delay
            if (!wasClean) {
                this.reconnectDelay = Math.min(30000, this.reconnectDelay * this.reconnectBackoffMultiplier);
            }
            
            console.log(`Reconnecting in ${this.reconnectDelay/1000} seconds... (Attempt ${this.reconnectAttempts})`);
            setTimeout(() => this.connectWebSocket(), this.reconnectDelay);
        };

        this.socket.onerror = (error) => {
            console.error('WebSocket error:', error);
            // Don't close the socket here, let the onclose handler manage reconnection
            // The socket will automatically close after an error
        };
    }

    // Fallback to SSE if WebSockets are not supported
    connectEventSource() {
        console.log('Falling back to SSE connection');
        
        if (this.evtSource) {
            this.evtSource.close();
        }
        
        this.evtSource = new EventSource('/api/events/statistics');

        this.evtSource.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.success) {
                this.updateMetrics(data.data);
            } else {
                console.error('Error in SSE:', data.error);
            }
        };

        this.evtSource.onerror = () => {
            console.error(`EventSource failed. Reconnecting in ${this.reconnectDelay/1000} seconds...`);
            this.evtSource.close();
            
            // Apply exponential backoff for reconnection delay
            this.reconnectDelay = Math.min(30000, this.reconnectDelay * this.reconnectBackoffMultiplier);
            
            setTimeout(() => this.connectEventSource(), this.reconnectDelay);
        };
    }

    // Initial data load
    async loadInitialData() {
        try {
            const response = await fetch('/api/statistics');
            const result = await response.json();

            if (result.success) {
                // For initial load, force update regardless of time
                this.lastUpdateTime = 0;
                this.updateMetrics(result.data);
                
                // Try to connect using WebSockets first
                if ('WebSocket' in window) {
                    this.connectWebSocket();
                } else {
                    // Fall back to SSE if WebSockets are not supported
                    this.connectEventSource();
                }
            } else {
                console.error('Error loading initial data:', result.error);
                setTimeout(() => this.loadInitialData(), this.initialLoadRetryDelay);
            }
        } catch (error) {
            console.error('Failed to load initial data:', error);
            setTimeout(() => this.loadInitialData(), this.initialLoadRetryDelay);
        }
    }

    // Clear ping-pong timers
    clearPingPongTimers() {
        if (this.pingTimeoutId) {
            clearInterval(this.pingTimeoutId);
            this.pingTimeoutId = null;
        }
        if (this.pongTimeoutId) {
            clearTimeout(this.pongTimeoutId);
            this.pongTimeoutId = null;
        }
    }
    
    // Start ping-pong mechanism to detect connection issues
    startPingPong() {
        // Clear any existing timers
        this.clearPingPongTimers();
        
        // Set up ping interval
        this.pingTimeoutId = setInterval(() => {
            if (this.socket && this.socket.readyState === WebSocket.OPEN) {
                // Send ping message
                console.log('Sending ping to server');
                try {
                    this.socket.send(JSON.stringify({ type: 'ping' }));
                    
                    // Set up pong timeout - if we don't get a response in time, consider the connection dead
                    this.pongTimeoutId = setTimeout(() => {
                        console.error('Pong timeout - no response from server');
                        // Connection is probably dead, close it and reconnect
                        this.clearPingPongTimers();
                        if (this.socket) {
                            this.socket.close();
                        }
                    }, this.pongTimeout);
                } catch (error) {
                    console.error('Error sending ping:', error);
                    // If we can't send a ping, the connection is probably dead
                    this.clearPingPongTimers();
                    if (this.socket) {
                        this.socket.close();
                    }
                }
            }
        }, this.pingInterval);
    }
}

// Start the application when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    const dashboard = new DashboardController();
    dashboard.init();
});