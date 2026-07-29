(function() {
    var heartbeatUrl = window.HEARTBEAT_URL || '/api/heartbeat/';
    function getCSRFToken() {
        var el = document.querySelector('[name=csrfmiddlewaretoken]');
        return el ? el.value : '';
    }
    function heartbeat() {
        fetch(heartbeatUrl, {
            method: 'POST',
            headers: { 'X-CSRFToken': getCSRFToken() }
        }).catch(function() {});
    }
    if (heartbeatUrl) {
        heartbeat();
        setInterval(heartbeat, 60000);
    }
})();
