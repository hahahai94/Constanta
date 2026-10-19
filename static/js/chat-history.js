(function () {
    const button = document.getElementById('load-earlier-btn');
    const container = document.getElementById('messages-container');
    if (!button || !container) return;

    button.addEventListener('click', async function () {
        const url = button.dataset.url;
        if (!url) return;
        button.disabled = true;

        try {
            const response = await fetch(url, {
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
            });
            if (!response.ok) throw new Error('history request failed');
            const data = await response.json();

            const previousHeight = container.scrollHeight;
            const anchor = container.querySelector('[data-message-id]');
            const wrapper = document.createElement('div');
            wrapper.innerHTML = data.html;

            while (wrapper.firstChild) {
                container.insertBefore(wrapper.firstChild, anchor);
            }
            container.scrollTop += container.scrollHeight - previousHeight;

            button.dataset.url = data.earlier_url || '';
            button.disabled = false;
            if (!data.has_earlier) {
                button.parentElement.hidden = true;
            }
        } catch (error) {
            button.disabled = false;
        }
    });
})();
