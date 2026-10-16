(function() {
    var heartbeatUrl = window.HEARTBEAT_URL || '/api/heartbeat/';

    // Токен берётся из meta-тега в base.html: раньше он читался только из
    // скрытого поля формы, которого нет на страницах без форм, поэтому
    // heartbeat молча получал 403 (problems.md, П-38).
    function getCSRFToken() {
        var meta = document.querySelector('meta[name="csrf-token"]');
        if (meta && meta.content) return meta.content;
        var el = document.querySelector('[name=csrfmiddlewaretoken]');
        return el ? el.value : '';
    }

    function heartbeat() {
        var token = getCSRFToken();
        if (!token) return;
        fetch(heartbeatUrl, {
            method: 'POST',
            headers: { 'X-CSRFToken': token }
        }).catch(function() {});
    }

    heartbeat();
    setInterval(heartbeat, 60000);
})();
