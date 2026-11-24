(function () {
    const body = document.body;
    if (!body) return;

    const pollUrl = body.dataset.notificationsPollUrl;
    const chatListUrl = body.dataset.chatListUrl;
    const activeConvKey = body.dataset.activeConversationKey || '';
    const notifBadge = document.getElementById('notification-badge');
    const chatBadge = document.getElementById('global-chat-badge');
    const toastContainer = document.getElementById('notification-toasts');
    const chatListEl = document.getElementById('chat-list');

    if (!pollUrl) return;

    let since = new Date().toISOString();
    let polling = false;
    const shownIds = new Set();

    function updateBadge(el, count) {
        if (!el) return;
        const num = Number(count) || 0;
        if (num > 0) {
            el.textContent = num > 99 ? '99+' : String(num);
            el.classList.remove('d-none');
        } else {
            el.textContent = '';
            el.classList.add('d-none');
        }
    }

    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str == null ? '' : String(str);
        return div.innerHTML;
    }

    function isSafeLocalUrl(url) {
        return typeof url === 'string' && url.startsWith('/') && !url.startsWith('//') && !url.startsWith('/\\');
    }

    function showToast(event) {
        if (!toastContainer || !event || shownIds.has(event.id)) return;
        shownIds.add(event.id);
        if (shownIds.size > 200) {
            const first = shownIds.values().next().value;
            shownIds.delete(first);
        }

        const toast = document.createElement('a');
        toast.href = isSafeLocalUrl(event.url) ? event.url : '/notifications/';
        toast.className = 'toast show text-decoration-none text-dark mb-2 shadow';
        toast.setAttribute('role', 'alert');

        const countBadge = event.unread_count > 1
            ? `<span class="badge bg-primary rounded-pill ms-1">${escapeHtml(event.unread_count)}</span>`
            : '';

        toast.innerHTML = `
            <div class="toast-header">
                <strong class="me-auto text-truncate">${escapeHtml(event.icon || '🔔')} ${escapeHtml(event.title || 'Уведомление')}${countBadge}</strong>
                <button type="button" class="btn-close ms-2" aria-label="Закрыть"></button>
            </div>
            <div class="toast-body small text-truncate">${escapeHtml(event.message || '')}</div>
        `;

        const closeBtn = toast.querySelector('.btn-close');
        if (closeBtn) {
            closeBtn.addEventListener('click', function (e) {
                e.preventDefault();
                e.stopPropagation();
                toast.remove();
            });
        }

        toastContainer.appendChild(toast);
        setTimeout(function () {
            if (toast.parentNode) toast.remove();
        }, 6000);
    }

    function refreshChatList() {
        if (!chatListEl || !chatListUrl) return;
        const url = new URL(chatListUrl, window.location.origin);
        const currentParams = new URLSearchParams(window.location.search);
        const activeUserId = currentParams.get('user_id');
        if (activeUserId) {
            url.searchParams.set('user_id', activeUserId);
        }

        fetch(url.toString(), {
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
            credentials: 'same-origin'
        })
            .then(function (r) { return r.ok ? r.json() : null; })
            .then(function (data) {
                if (data && typeof data.html === 'string') {
                    chatListEl.innerHTML = data.html;
                }
            })
            .catch(function () {});
    }

    function pollNotifications() {
        if (polling || document.hidden) return;
        polling = true;

        const url = new URL(pollUrl, window.location.origin);
        if (since) url.searchParams.set('since', since);

        fetch(url.toString(), {
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
            credentials: 'same-origin'
        })
            .then(function (r) { return r.ok ? r.json() : null; })
            .then(function (data) {
                if (!data) return;
                if (data.server_time) since = data.server_time;
                updateBadge(notifBadge, data.unread_notifications_count);
                updateBadge(chatBadge, data.unread_messages_count);

                const events = Array.isArray(data.events) ? data.events : [];
                let hasChatChanges = false;
                events.forEach(function (ev) {
                    if (ev.conversation_key && ev.conversation_key === activeConvKey) {
                        return;
                    }
                    showToast(ev);
                    if (ev.type === 'message' || ev.type === 'mention') {
                        hasChatChanges = true;
                    }
                });
                if (hasChatChanges) {
                    refreshChatList();
                }
            })
            .catch(function () {})
            .finally(function () {
                polling = false;
            });
    }

    setInterval(pollNotifications, 4000);
    document.addEventListener('visibilitychange', function () {
        if (!document.hidden) pollNotifications();
    });
})();
