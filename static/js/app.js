(function() {
    // ===== CSRF =====
    // Токен берётся из meta-тега в base.html: раньше он читался только из
    // скрытого поля формы, которого нет на страницах без форм, поэтому
    // heartbeat молча получал 403 (problems.md, П-38).
    function getCSRFToken() {
        var meta = document.querySelector('meta[name="csrf-token"]');
        if (meta && meta.content) return meta.content;
        var el = document.querySelector('[name=csrfmiddlewaretoken]');
        return el ? el.value : '';
    }

    // ===== Онлайн-статус =====
    function heartbeat() {
        var token = getCSRFToken();
        if (!token) return;
        var url = window.HEARTBEAT_URL || '/api/heartbeat/';
        fetch(url, {
            method: 'POST',
            headers: { 'X-CSRFToken': token }
        }).catch(function() {});
    }

    heartbeat();
    setInterval(heartbeat, 60000);

    // ===== Просмотр изображения в полный экран =====
    var viewer = document.getElementById('image-viewer');
    var viewerImg = document.getElementById('image-viewer-img');
    var viewerDownload = document.getElementById('image-viewer-download');

    function openImageViewer(src, download, name) {
        if (!viewer || !src) return;
        viewerImg.src = src;
        viewerImg.alt = name || '';
        viewerDownload.href = download || src;
        viewerDownload.setAttribute('download', name || '');
        viewer.hidden = false;
        document.body.style.overflow = 'hidden';
    }

    function closeImageViewer() {
        if (!viewer || viewer.hidden) return;
        viewer.hidden = true;
        viewerImg.src = '';
        document.body.style.overflow = '';
    }

    // Делегирование: изображения появляются и после отправки, и после опроса.
    document.addEventListener('click', function(event) {
        var trigger = event.target.closest('[data-image-viewer]');
        if (trigger) {
            event.preventDefault();
            openImageViewer(
                trigger.dataset.imageViewer,
                trigger.dataset.imageDownload,
                trigger.dataset.imageName
            );
            return;
        }
        if (event.target === viewer || event.target.id === 'image-viewer-close') {
            closeImageViewer();
        }
    });

    document.addEventListener('keydown', function(event) {
        if (event.key === 'Escape') closeImageViewer();
    });
})();
