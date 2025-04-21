const totalCountDiv = document.getElementById('total-count');
const todayCountDiv = document.getElementById('today-count');
const hourCountDiv = document.getElementById('hour-count');

let socket;

function connectWebSocket() {
    // Determine WebSocket protocol based on window location protocol
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.host}/ws/stats`;

    console.log(`Connecting to WebSocket: ${wsUrl}`);
    socket = new WebSocket(wsUrl);

    socket.onopen = function (event) {
        console.log('WebSocket connection established');
    };

    socket.onmessage = function (event) {
        console.log('Message from server:', event.data);
        try {
            const data = JSON.parse(event.data);
            updateStatus(data);
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

function formatLargeNumber(number) {
    if (number < 10000) return number.toString();
    
    if (number < 1000000) {
        const thousands = number / 1000;
        return `${Math.floor(thousands * 10) / 10} тыс`;
    }
    
    const millions = number / 1000000;
    return `${Math.floor(millions * 10) / 10} млн`;
}

function updateStatus(data) {
    const touchCount = data.touch_count_last_hour;
    const totalTouches = data.total_touches;
    const todayTouches = data.today_touches;

    if (typeof totalTouches !== 'undefined') {
        totalCountDiv.textContent = formatLargeNumber(totalTouches);
    } else {
        totalCountDiv.textContent = '0';
    }
    if (typeof touchCount !== 'undefined') {
        hourCountDiv.textContent = formatLargeNumber(touchCount);
    } else {
        hourCountDiv.textContent = '0';
    }
    if (typeof todayTouches !== 'undefined') {
        todayCountDiv.textContent = formatLargeNumber(todayTouches);
    } else {
        todayCountDiv.textContent = '0';
    }
}

connectWebSocket();