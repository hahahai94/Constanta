(function() {
    const body = document.body;
    const pollUrl = body && body.dataset.notificationsPollUrl;
    const chatListUrl = body && body.dataset.chatListUrl;
    if (!pollUrl || !document.getElementById('notification-badge')) return;

    const activeKey = body.dataset.activeConversationKey || '';
    let cursor = null;
    let polling = false;
    let refreshingChats = false;

    function refreshChatList() {
        const list = document.getElementById('chat-list');
        if (!list || !chatListUrl || refreshingChats) return;
        refreshingChats = true;
        const active = list.querySelector('.chat-item.active');
        const activeId = active ? active.dataset.chatUser : '';
        const url = new URL(chatListUrl, window.location.origin);
        if (activeId) url.searchParams.set('active_user_id', activeId);

        fetch(url.toString(), {headers: {'X-Requested-With': 'XMLHttpRequest'}})
            .then(function(response) { return response.json(); })
            .then(function(data) {
                if (!data.html || list.innerHTML.trim() === data.html.trim()) return;
                const scrollTop = list.scrollTop;
                list.innerHTML = data.html;
                list.scrollTop = scrollTop;
            })
            .catch(function() {})
            .finally(function() { refreshingChats = false; });
    }

    function setBadge(id, count) {
        const badge = document.getElementById(id);
        if (!badge) return;
        badge.textContent = count > 0 ? count : '';
        badge.classList.toggle('d-none', !count);
    }

    function updateBadges(data) {
        setBadge('global-chat-badge', data.unread_messages_count || 0);
        setBadge('notification-badge', data.unread_notifications_count || 0);
    }

    function showToast(event) {
        const container = document.getElementById('notification-toasts');
        if (!container || event.conversation_key === activeKey) return;

        const toast = document.createElement('a');
        toast.className = 'toast notification-toast text-decoration-none';
        toast.href = event.url || '/notifications/';
        toast.setAttribute('role', 'alert');

        const header = document.createElement('div');
        header.className = 'toast-header';
        const title = document.createElement('strong');
        title.className = 'me-auto';
        title.textContent = (event.icon || '🔔') + ' ' + (event.title || 'Уведомление');
        const count = document.createElement('span');
        count.className = 'badge bg-primary rounded-pill';
        count.textContent = event.count || 1;
        const close = document.createElement('button');
        close.type = 'button';
        close.className = 'btn-close ms-2';
        close.setAttribute('data-bs-dismiss', 'toast');
        close.setAttribute('aria-label', 'Закрыть');
        close.addEventListener('click', function(event) {
            event.preventDefault();
        });
        header.append(title, count, close);

        const text = document.createElement('div');
        text.className = 'toast-body';
        text.textContent = event.message || '';

        toast.append(header, text);
        container.appendChild(toast);

        if (window.bootstrap && window.bootstrap.Toast) {
            const instance = new window.bootstrap.Toast(toast, {delay: 5000});
            toast.addEventListener('hidden.bs.toast', function() {
                toast.remove();
            });
            instance.show();
        } else {
            toast.classList.add('show');
            setTimeout(function() { toast.remove(); }, 5000);
        }
    }

    function poll() {
        if (polling || document.hidden) return;
        polling = true;
        const url = new URL(pollUrl, window.location.origin);
        if (cursor) url.searchParams.set('since', cursor);

        fetch(url.toString(), {headers: {'X-Requested-With': 'XMLHttpRequest'}})
            .then(function(response) {
                if (!response.ok) throw new Error('poll failed');
                return response.json();
            })
            .then(function(data) {
                updateBadges(data);
                if (Array.isArray(data.events)) data.events.forEach(showToast);
                if (data.cursor) cursor = data.cursor;
                if (data.events && data.events.length) {
                    document.dispatchEvent(new CustomEvent('constanta:notification'));
                    refreshChatList();
                }
            })
            .catch(function() {})
            .finally(function() { polling = false; });
    }

    setInterval(poll, 4000);
    setInterval(refreshChatList, 5000);
    document.addEventListener('visibilitychange', function() {
        if (!document.hidden) {
            poll();
            refreshChatList();
        }
    });
    poll();
    refreshChatList();
})();
