/* Логика личного чата.
 *
 * Раньше этот код лежал инлайновым <script> прямо в index.html — 270 строк,
 * которые не кешировались браузером. Django-тегов внутри нет, поэтому файл
 * статический.
 */
const emojiList = [
    '😀','😃','😄','😁','😆','😅','🤣','😂','🙂','😉','😊','🥰','😍','🤩','😘','😗',
    '😋','😛','😜','😝','🤑','🤗','🤭','🤐','🤨','😐','😑','😶','😏','😒','🙄','😬',
    '😌','😔','😪','🤤','😴','😷','🤒','🤕','🤢','🤮','🤧','🥵','🥶','🥴','😵','🤯',
    '🤠','🥳','🥸','😎','🤓','🧐','😕','😟','🙁','😮','😲','😳','🥺','😢','😭','😱',
    '😤','😡','🤬','👻','💀','☠️','👽','🤖','🎃','🙈','🙉','🙊','💫','💨','💣',
    '👋','🤚','🖐️','✋','🖖','👌','🤌','🤏','✌️','🤞','🤟','🤘','🤙','👈','👉','👆',
    '🖕','👇','☝️','👍','👎','✊','👊','🤛','🤜','👏','🙌','👐','🤲','🤝','🙏',
    '💪','🦵','🦶','👂','🦻','👃','🧠','🦷','👀','👅','👄',
    '❤️','🧡','💛','💚','💙','💜','🖤','🤍','🤎','💔','🔥','⭐','✨','💥','💯','💢',
    '💬','💭','💤','🎉','🎊','🎈','🎁','🎀','🎯','🎲','🎭',
    '💻','📱','📞','📟','📠','🔋','💡','🔦','📖','📕','📗','📘','📙','📚','📰',
    '💰','💴','💵','💶','💷','💸','📧','📨','📩','📥','📦',
    '✅','❌','❓','❔','❕','❗','➕','➖','➗','♠️','♥️','♦️','♣️',
    '🔇','🔈','🔉','🔊','📢','📣','🔔','🎵','🎶','🎼','🎤','🎧','🎷','🎸','🎹','🎺',
    '⚽','⚾','🏀','🏐','🎾','🎳','🏓','🏸','🥊','🥋','🎿','🏂',
    '🏋️','🤼','🤸','🏄','🏊','🤽','🚣','🚵','🚴',
    '☀️','🌞','⭐','🌟','🌙','☁️','⛅','🌈','⚡','💧','❄️','🌊','🔥','🌪️',
    '🍏','🍎','🍐','🍊','🍋','🍌','🍉','🍇','🍓','🍈','🍒','🍑','🥭','🍍',
    '🍅','🍆','🥑','🥦','🥒','🌽','🥕','🍞','🥖','🧀','🥚','🍳','🥓','🍗','🍖',
    '🌭','🍔','🍟','🍕','🌮','🌯','🥗','🍝','🍜','🍲','🍛','🍣','🍱','🍤',
    '🍦','🍰','🎂','🍭','🍬','🍫','🍿','🍩','🍪','☕','🍵','🧃','🥤','🍺','🍻','🥂',
    '🍷','🥃','🍸','🍹','🍾','🥄','🔪',
    '🌍','🌎','🌏','🏔️','🏖️','🏜️','🏝️','🏞️','🏟️','🏛️','🏠','🏡','🏢','🏣',
    '🏥','🏦','🏨','🏩','🏪','🏫','🏬','🏭','🏯','🏰','🗼','🗽','⛪','🕌','🕍',
    '🌁','🌃','🏙️','🌄','🌅','🌆','🌇','🌉','🎠','🎡','🎢',
    '🚂','🚃','🚄','🚅','🚆','🚇','🚈','🚉','🚊','🚌','🚍','🚎','🚐','🚑','🚒',
    '🚓','🚔','🚕','🚖','🚗','🚘','🚙','🚚','🚛','🚜','🚲','🛴','🛹',
    '🚨','🚥','🚦','🛑','🚧','⚓','⛵','🚤','🚢','✈️','🚁','🚀','🛸',
    '🏁','🚩','🎌'
];

// ===== ЭМОДЗИ =====
const emojiPicker = document.getElementById('emoji-picker');
const messageInput = document.getElementById('message-input');

emojiPicker.innerHTML = emojiList.map(e => `<button type="button" class="emoji-btn" data-emoji="${e}">${e}</button>`).join('');

document.getElementById('emoji-btn').addEventListener('click', (e) => {
    e.stopPropagation();
    emojiPicker.classList.toggle('active');
});

emojiPicker.addEventListener('click', (e) => {
    if (e.target.classList.contains('emoji-btn')) {
        const emoji = e.target.dataset.emoji;
        const start = messageInput.selectionStart;
        const text = messageInput.value;
        messageInput.value = text.substring(0, start) + emoji + text.substring(messageInput.selectionEnd);
        messageInput.focus();
        messageInput.selectionStart = messageInput.selectionEnd = start + emoji.length;
        emojiPicker.classList.remove('active');
    }
});

document.addEventListener('click', (e) => {
    if (!emojiPicker.contains(e.target) && e.target.id !== 'emoji-btn') {
        emojiPicker.classList.remove('active');
    }
});

// ===== ФАЙЛЫ =====
const fileUpload = document.getElementById('file-upload');
const fileTagContainer = document.getElementById('file-tag-container');

fileUpload.addEventListener('change', function() {
    fileTagContainer.innerHTML = '';
    if (this.files.length > 0) {
        const file = this.files[0];
        const sizeKB = (file.size / 1024).toFixed(1);
        const tag = document.createElement('div');
        tag.className = 'file-tag mb-2';
        // Имя файла подставляется через textContent: в шаблонной строке с
        // innerHTML оно исполнялось бы как разметка (problems.md, П-36).
        const nameSpan = document.createElement('span');
        nameSpan.style.margin = '0 5px';
        nameSpan.textContent = file.name;
        const sizeSpan = document.createElement('small');
        sizeSpan.textContent = `(${sizeKB} КБ)`;
        const removeBtn = document.createElement('button');
        removeBtn.type = 'button';
        removeBtn.textContent = '×';
        removeBtn.addEventListener('click', function() {
            tag.remove();
            document.getElementById('file-upload').value = '';
        });
        tag.append('📎 ', nameSpan, ' ', sizeSpan, ' ', removeBtn);
        fileTagContainer.appendChild(tag);
    }
});

// ===== ОТВЕТЫ =====
window.startReply = function(msgId, author, text) {
    document.getElementById('reply-to-id').value = msgId;
    document.getElementById('reply-author').textContent = author + ':';
    document.getElementById('reply-text').textContent = text.length > 60 ? text.substring(0, 60) + '...' : text;
    document.getElementById('reply-panel').classList.add('active');
    messageInput.focus();
};

window.cancelReply = function() {
    document.getElementById('reply-to-id').value = '';
    document.getElementById('reply-panel').classList.remove('active');
    messageInput.focus();
};

window.scrollToMessage = function(msgId) {
    const element = document.querySelector(`[data-message-id="${msgId}"]`);
    if (element) {
        element.scrollIntoView({ behavior: 'smooth', block: 'center' });
        element.style.background = 'rgba(102, 126, 234, 0.2)';
        setTimeout(() => { element.style.background = ''; }, 2000);
    }
};

// Кнопки ответа обрабатываются делегированием, а значения берутся из
// data-атрибутов, а не подставляются в JS-код. Поэтому имя пользователя
// не может влиять на исполняемый сценарий (problems.md, П-2).
document.getElementById('messages-container')?.addEventListener('click', function(e) {
    const btn = e.target.closest('.reply-btn');
    if (!btn) return;
    window.startReply(btn.dataset.replyId, btn.dataset.replyAuthor, btn.dataset.replyText || '');
});

// Удаление своего сообщения (problems.md, П-20): мягкое удаление на сервере,
// из разметки убираем после успешного ответа.
document.getElementById('messages-container')?.addEventListener('click', function(e) {
    const btn = e.target.closest('.delete-btn');
    if (!btn) return;
    if (!confirm('Удалить сообщение?')) return;
    const meta = document.querySelector('meta[name="csrf-token"]');
    fetch('/api/message/' + btn.dataset.deleteId + '/delete/', {
        method: 'POST',
        headers: {'X-CSRFToken': meta ? meta.content : '', 'X-Requested-With': 'XMLHttpRequest'}
    }).then(function(response) {
        if (!response.ok) return;
        const container = btn.closest('[data-message-id]');
        if (container) container.remove();
    }).catch(function() {});
});

// ===== ОТПРАВКА =====
document.getElementById('chat-form')?.addEventListener('submit', function(e) {
    e.preventDefault();
    const formData = new FormData(this);
    const textContent = messageInput.value.trim();
    const hasFile = fileUpload.files.length > 0;

    if (!textContent && !hasFile) {
        messageInput.placeholder = '⚠️ Введите текст или прикрепите файл';
        setTimeout(() => messageInput.placeholder = 'Написать сообщение...', 2000);
        return;
    }

    formData.set('content', textContent);

    const container = document.getElementById('messages-container');
    const empty = container.querySelector('.h-100.text-muted');
    if (empty) empty.remove();

    // показываем "отправляется..." сразу
    const sendingDiv = document.createElement('div');
    sendingDiv.className = 'd-flex justify-content-end mb-3';
    const bubble = document.createElement('div');
    bubble.className = 'message-bubble message-own sending';
    bubble.textContent = textContent || '📎 Файл';
    sendingDiv.appendChild(bubble);
    container.appendChild(sendingDiv);
    container.scrollTop = container.scrollHeight;

    const btn = document.getElementById('send-btn');
    btn.disabled = true;
    btn.innerHTML = '<i class="bi bi-hourglass-split"></i>';

    fetch(this.action, { method: 'POST', body: formData })
    .then(r => r.json())
    .then(d => {
        sendingDiv.remove();
        if (d.status === 'ok' && d.html) {
            if (window.appendUniqueMessages) {
                window.appendUniqueMessages(container, d.html);
            } else {
                container.insertAdjacentHTML('beforeend', d.html);
            }
            if (window.pollState) window.advanceCursor(pollState, d.cursor);
            scrollToBottom();
            updateChatPreview(d.peer_id, d.preview);
            messageInput.value = '';
            fileUpload.value = '';
            fileTagContainer.innerHTML = '';
            cancelReply();
        } else {
            alert('Ошибка: ' + (d.message || d.error || 'Неизвестная'));
        }
    })
    .catch(err => {
        sendingDiv.remove();
        console.error('Error:', err);
        alert('Ошибка соединения');
    })
    .finally(() => {
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-send-fill"></i>';
    });
});

// ===== ПРОКРУТКА К ПОСЛЕДНЕМУ СООБЩЕНИЮ =====
// Переписка отдаётся целиком, поэтому к последнему сообщению нужно вернуться
// и после загрузки страницы, и после того, как догрузятся картинки: без этого
// высота контейнера меняется уже после прокрутки.
window.scrollToBottom = function() {
    const container = document.getElementById('messages-container');
    if (container) container.scrollTop = container.scrollHeight;
};

window.updateChatPreview = function(peerId, preview) {
    if (!peerId || !preview) return;
    const item = document.querySelector('.chat-item[data-chat-user="' + peerId + '"]');
    if (!item) return;
    const target = item.querySelector('.chat-preview');
    if (target) target.textContent = preview;
};

document.querySelectorAll('#messages-container img').forEach(function(image) {
    if (!image.complete) image.addEventListener('load', window.scrollToBottom, {once: true});
});
window.addEventListener('load', window.scrollToBottom);

// ===== ПОЛЛЕР (вызывается и по таймеру, и после отправки) =====
window.latestCursor = function() {
    let max = null;
    document.querySelectorAll('[data-message-id]').forEach(function(el) {
        const c = el.dataset.cursor;
        if (c && (!max || c > max)) max = c;
    });
    return max;
};

window.doPoll = function() {
    if (!window.pollState || !pollState.param) return;
    const url = '/api/poll/?' + (pollState.cursor ? 'after=' + encodeURIComponent(pollState.cursor) + '&' : '') + pollState.param;
    fetch(url, { headers: {'X-Requested-With': 'XMLHttpRequest'} })
        .then(r => r.json())
        .then(data => {
            if (data.count > 0) {
                const container = document.getElementById('messages-container');
                const wasAtBottom = container.scrollHeight - container.scrollTop <= container.clientHeight + 50;
                const inserted = window.appendUniqueMessages
                    ? window.appendUniqueMessages(container, data.html)
                    : (container.insertAdjacentHTML('beforeend', data.html), true);
                window.advanceCursor(pollState, data.cursor);
                if (inserted && wasAtBottom) window.scrollToBottom();
                // под ником в списке чатов тоже должно быть актуальное превью
                window.updateChatPreview(data.peer_id, data.preview);
            }
        })
        .catch(() => {});
};

// ===== АВТООБНОВЛЕНИЕ (JSON API) =====
if (!window.pollState) {
    window.pollState = { cursor: window.latestCursor(), url: new URL(window.location.href) };

    const userId = pollState.url.searchParams.get('user_id');
    const groupId = pollState.url.searchParams.get('group_id');
    if (userId) pollState.param = 'user_id=' + userId;
    else if (groupId) pollState.param = 'group_id=' + groupId;

    window.autoRefreshInterval = setInterval(window.doPoll, 2000);
    window.doPoll();
}

// Прокрутка к последнему сообщению
window.scrollToBottom();
