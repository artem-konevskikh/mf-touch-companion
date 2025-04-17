const statusDiv = document.getElementById('status');
const connectionStatusDiv = document.getElementById('connection-status');

let socket;

function connectWebSocket() {
    // Determine WebSocket protocol based on window location protocol
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.host}/ws/stats`;

    console.log(`Connecting to WebSocket: ${wsUrl}`);
    connectionStatusDiv.textContent = 'Connecting...';
    socket = new WebSocket(wsUrl);

    socket.onopen = function(event) {
        console.log('WebSocket connection established');
        connectionStatusDiv.textContent = 'Connected';
        connectionStatusDiv.style.color = 'green';
    };

    socket.onmessage = function(event) {
        console.log('Message from server:', event.data);
        try {
            const data = JSON.parse(event.data);
            updateStatus(data);
        } catch (e) {
            console.error('Error parsing message:', e);
            statusDiv.textContent = 'Error receiving data.';
        }
    };

    socket.onclose = function(event) {
        console.log('WebSocket connection closed:', event);
        connectionStatusDiv.textContent = 'Disconnected. Retrying in 5 seconds...';
        connectionStatusDiv.style.color = 'red';
        statusDiv.textContent = 'Connection lost.';
        statusDiv.className = ''; // Remove sad/glad class
        // Attempt to reconnect after a delay
        setTimeout(connectWebSocket, 5000);
    };

    socket.onerror = function(error) {
        console.error('WebSocket Error:', error);
        connectionStatusDiv.textContent = 'Connection Error';
        connectionStatusDiv.style.color = 'red';
        statusDiv.textContent = 'Error connecting to server.';
    };
}

function updateStatus(data) {
    const isGlad = data.is_glad;
    const touchCount = data.touch_count_last_hour;
    const threshold = data.touch_threshold;

    statusDiv.innerHTML = `
        Current State: <strong class="${isGlad ? 'glad' : 'sad'}">${isGlad ? 'GLAD' : 'SAD'}</strong><br>
        Touches (last hour): <span id="touch-count">${touchCount}</span> / ${threshold}
    `;

    // Update background/border style based on state
    statusDiv.className = isGlad ? 'glad' : 'sad';
}

// Initial connection attempt
connectWebSocket();