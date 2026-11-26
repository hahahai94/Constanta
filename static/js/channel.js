(function() {
const root = document.querySelector('[data-channel-id]');
if (!root) return;

const channelId = root.dataset.channelId;
const postsContainer = document.querySelector('.posts-container');

function latestCursor() {
    let max = null;
    document.querySelectorAll('[data-message-id]').forEach(function(el) {
        const c = el.dataset.cursor;
        if (c && (!max || c > max)) max = c;
    });
    return max;
}

function loadMorePosts() {
    const btn = document.getElementById('load-more-btn');
    if (!btn || btn.disabled) return;
    btn.disabled = true;

    const page = btn.dataset.page;
    const url = new URL(window.location.href);
    url.searchParams.set('page', page);

    fetch(url.toString(), { headers: {'X-Requested-With': 'XMLHttpRequest'} })
        .then(r => r.json())
        .then(data => {
            postsContainer.insertAdjacentHTML('beforeend', data.html);
            if (data.has_next) {
                btn.dataset.page = data.page + 1;
                btn.disabled = false;
            } else {
                btn.remove();
            }
        })
        .catch(() => { btn.disabled = false; });
}

document.getElementById('load-more-btn')?.addEventListener('click', loadMorePosts);

const pollState = { cursor: latestCursor(), channelId: channelId };
let isPolling = false;

function doPoll(force) {
    if (!force && (isPolling || document.hidden)) return;
    if (isPolling) return;
    isPolling = true;
    const url = '/api/poll/?' + (pollState.cursor ? 'after=' + encodeURIComponent(pollState.cursor) + '&' : '') + 'channel_id=' + pollState.channelId;
    fetch(url, { headers: {'X-Requested-With': 'XMLHttpRequest'} })
        .then(r => r.ok ? r.json() : null)
        .then(data => {
            if (data && data.count > 0) {
                if (window.appendUniqueMessages) {
                    window.appendUniqueMessages(
                        postsContainer, data.html, 'afterbegin');
                } else {
                    postsContainer.insertAdjacentHTML('afterbegin', data.html);
                }
                window.advanceCursor(pollState, data.cursor);
            }
        })
        .catch(() => {})
        .finally(() => {
            isPolling = false;
        });
}

if (channelId) {
    setInterval(doPoll, 3000);
    document.addEventListener('visibilitychange', function() {
        if (!document.hidden) doPoll();
    });
}

document.querySelectorAll('[data-channel-post-form]').forEach(form => {
    form.addEventListener('submit', function(e) {
        e.preventDefault();
        const formData = new FormData(this);
        fetch(this.action, { method: 'POST', body: formData, headers: { 'X-CSRFToken': formData.get('csrfmiddlewaretoken') } })
            .then(r => r.json())
            .then(data => {
                if (data.status === 'ok') {
                    this.querySelector('textarea').value = '';
                    this.querySelector('[type="file"]').value = '';
                    doPoll(true);
                } else {
                    alert(data.message);
                }
            });
    });
});
})();
