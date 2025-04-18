const responseTextDiv = document.getElementById('response-text');
let socket;

function connectWebSocket() {
    // Determine WebSocket protocol based on window location protocol
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.host}/ws/api_response`;

    console.log(`Connecting to WebSocket: ${wsUrl}`);
    socket = new WebSocket(wsUrl);

    socket.onopen = function (event) {
        console.log('WebSocket connection established');
    };

    socket.onmessage = function (event) {
        console.log('Message from server:', event.data);
        try {
            const data = JSON.parse(event.data);
            updateResponse(data);
        } catch (e) {
            console.error('Error parsing message:', e);
        }
    };

    socket.onclose = function (event) {
        console.log('WebSocket connection closed:', event);
        // Attempt to reconnect after a delay
        setTimeout(connectWebSocket, 5000);
    };

    socket.onerror = function (error) {
        console.error('WebSocket Error:', error);
    };
}

function updateResponse(data) {
    if (data.expired === true || !data.text || data.text.trim() === '') {
        // Handle expiration or empty text
        responseTextDiv.classList.add('empty-state');
        responseTextDiv.textContent = 'Ожидание ответа от API...';
        return;
    }

    // Update with new response text
    responseTextDiv.classList.remove('empty-state');

    // Apply a small animation effect - fade out, change text, fade in
    responseTextDiv.classList.add('hidden');

    setTimeout(() => {
        responseTextDiv.textContent = data.text;
        responseTextDiv.classList.remove('hidden');
    }, 300);
}

// Initial connection attempt
connectWebSocket();