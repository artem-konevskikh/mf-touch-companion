const responseTextDiv = document.getElementById('response-text');
const responseContainer = responseTextDiv.parentElement; // Get the parent container
let socket;

// --- Font Size Adjustment --- //
const MAX_FONT_SIZE = 42; // Initial font size from CSS
const MIN_FONT_SIZE = 14; // Minimum comfortable font size
const PADDING_ADJUSTMENT = 5; // Small buffer to prevent edge cases

function adjustFontSize(element, container) {
    let fontSize = MAX_FONT_SIZE;
    element.style.fontSize = `${fontSize}px`; // Start with max size

    // Check for overflow and decrease font size until it fits or hits min size
    // Use scrollHeight vs clientHeight for vertical fit
    // Use scrollWidth vs clientWidth for horizontal fit (though less likely needed here)
    while (
        (element.scrollHeight > container.clientHeight - PADDING_ADJUSTMENT ||
         element.scrollWidth > container.clientWidth - PADDING_ADJUSTMENT) &&
        fontSize > MIN_FONT_SIZE
    ) {
        fontSize--;
        element.style.fontSize = `${fontSize}px`;
    }
}

// --- WebSocket Logic --- //
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
        responseTextDiv.innerHTML = '...'; // Use innerHTML for consistency
        responseTextDiv.style.fontSize = ''; // Reset font size
        return;
    }

    // Update with new response text
    responseTextDiv.classList.remove('empty-state');

    // Apply a small animation effect - fade out, change text, fade in
    responseTextDiv.classList.add('hidden');

    setTimeout(() => {
        // Replace newline characters with <br> tags and update using innerHTML
        const formattedText = data.text.replace(/\n/g, '<br>');
        responseTextDiv.innerHTML = formattedText;

        // Adjust font size after text is rendered
        adjustFontSize(responseTextDiv, responseContainer);

        responseTextDiv.classList.remove('hidden');
    }, 300); // Ensure this timeout matches or exceeds CSS transition time
}

// Initial connection attempt
connectWebSocket();

// Optional: Adjust font size on window resize
window.addEventListener('resize', () => {
    // Only adjust if not in the empty state
    if (!responseTextDiv.classList.contains('empty-state')) {
        adjustFontSize(responseTextDiv, responseContainer);
    }
});