(function() {
    // Вставляет только сообщения, которых ещё нет в DOM. Поллер и ответ на
    // отправку могут принести одно и то же сообщение — раньше из-за этого
    // появлялись дубликаты.
    window.appendUniqueMessages = function(container, html, position) {
        if (!container || !html) return false;
        const template = document.createElement('template');
        template.innerHTML = html.trim();
        const fragment = document.createDocumentFragment();
        let inserted = false;

        Array.from(template.content.children).forEach(function(node) {
            const messageId = node.dataset ? node.dataset.messageId : '';
            if (messageId && container.querySelector(
                    '[data-message-id="' + messageId + '"]')) {
                return;
            }
            fragment.appendChild(node);
            inserted = true;
        });

        if (!inserted) return false;
        if (position === 'afterbegin') {
            container.prepend(fragment);
        } else {
            container.appendChild(fragment);
        }
        return true;
    };

    window.advanceCursor = function(state, cursor) {
        if (!state || !cursor) return;
        if (!state.cursor || cursor > state.cursor) {
            state.cursor = cursor;
        }
    };
})();
