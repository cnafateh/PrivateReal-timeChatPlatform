(() => {
    'use strict';
    const config = JSON.parse(document.getElementById('chat-config').textContent);
    const $ = id => document.getElementById(id);
    const list = $('chat-messages'), input = $('message-input'), send = $('send-button');
    const records = new Map(), rows = new Map();
    const csrf = document.querySelector('[name=csrfmiddlewaretoken]').value;
    const limit = 5 * 1024 * 1024;
    let socket, retry = 0, reconnectTimer, syncing = false, sending = false, closed = false;
    let selectedFile = null, selectedKind = 'file', previewUrl, pendingId, pendingFingerprint;
    let recorder, recordingStream, recordingTimer, recordingSeconds = 0, typingTimer, readTimer;
    let lastTyping = 0, readThrough = 0;
    function messageId() {
        if (crypto.randomUUID) return crypto.randomUUID();
        const bytes = crypto.getRandomValues(new Uint8Array(16));
        bytes[6] = (bytes[6] & 15) | 64; bytes[8] = (bytes[8] & 63) | 128;
        const hex = [...bytes].map(value => value.toString(16).padStart(2, '0')).join('');
        return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
    }
    function error(message = '') { $('chat-error').textContent = message; $('chat-error').hidden = !message; }
    function node(tag, className, text) {
        const element = document.createElement(tag);
        if (className) element.className = className;
        if (text !== undefined) element.textContent = text;
        return element;
    }
    function nearBottom() { return list.scrollHeight - list.scrollTop - list.clientHeight < 100; }
    function bottom() { list.scrollTop = list.scrollHeight; $('jump-latest').hidden = true; }
    function dateKey(date) { return `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`; }
    function dateLabel(date) {
        const now = new Date(), yesterday = new Date(); yesterday.setDate(now.getDate() - 1);
        if (dateKey(date) === dateKey(now)) return 'Today';
        if (dateKey(date) === dateKey(yesterday)) return 'Yesterday';
        return date.toLocaleDateString([], {day:'numeric', month:'long', year:'numeric'});
    }
    function groupDays() {
        list.querySelectorAll('.date-divider').forEach(el => el.remove());
        let previous;
        [...records.values()].sort((a, b) => a.id - b.id).forEach(data => {
            const date = new Date(data.timestamp), key = dateKey(date);
            if (key !== previous) {
                const divider = node('div', 'date-divider');
                divider.append(node('span', '', dateLabel(date)));
                list.insertBefore(divider, rows.get(data.id));
                previous = key;
            }
        });
    }
    function receipt(row, data) {
        const status = row.querySelector('.message-status');
        if (status) {
            status.textContent = data.is_read ? '✓✓' : '✓';
            status.title = data.is_read ? 'Read' : 'Sent';
            status.setAttribute('aria-label', status.title);
            status.classList.toggle('read', data.is_read);
        }
    }
    function add(data) {
        if (records.has(data.id)) {
            data.is_read = data.is_read || records.get(data.id).is_read;
            records.set(data.id, data); receipt(rows.get(data.id), data); return;
        }
        $('empty-chat')?.remove();
        records.set(data.id, data);
        const own = data.sender_id === config.userId;
        const row = node('article', `message-row ${own ? 'own' : 'other'}`);
        row.dataset.messageId = data.id;
        const bubble = node('div', 'message-bubble');
        if (data.attachment_url) {
            if (data.kind === 'image') {
                const link = node('a'); link.href = data.attachment_url; link.target = '_blank'; link.rel = 'noopener';
                const image = node('img', 'message-photo'); image.src = data.attachment_url;
                image.alt = data.name; image.loading = 'lazy';
                image.addEventListener('load', () => { if ($('jump-latest').hidden && nearBottom()) bottom(); });
                link.append(image); bubble.append(link);
            } else if (data.kind === 'voice') {
                const audio = node('audio'); audio.controls = true; audio.preload = 'metadata'; audio.src = data.attachment_url;
                audio.setAttribute('aria-label', 'Voice message'); bubble.append(audio);
            }
            const download = node('a', 'file-link', data.kind === 'voice' ? 'Voice message' : data.name);
            download.href = `${data.attachment_url}?download=1`;
            download.append(node('small', '', `${Math.max(1, Math.ceil(data.size / 1024))} KB ↓`)); bubble.append(download);
        }
        const text = node('div', 'message-text', data.message); text.dir = 'auto'; bubble.append(text);
        const meta = node('div', 'message-meta'); const stamp = new Date(data.timestamp);
        const time = node('time', '', stamp.toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'}));
        time.dateTime = data.timestamp; time.title = stamp.toLocaleString(); meta.append(time);
        if (own) meta.append(node('span', 'message-status'));
        bubble.append(meta); row.append(bubble); rows.set(data.id, row);
        const next = [...rows.keys()].filter(id => id > data.id).sort((a, b) => a - b)[0];
        list.insertBefore(row, next ? rows.get(next) : null); receipt(row, data);
    }
    function merge(items, forceBottom = false) {
        const wasNear = nearBottom(), oldHeight = list.scrollHeight, oldTop = list.scrollTop;
        const previousMax = Math.max(0, ...records.keys());
        items.forEach(add); groupDays();
        if (forceBottom || wasNear) bottom();
        else if (items.length && items.every(m => m.id < previousMax)) list.scrollTop = oldTop + list.scrollHeight - oldHeight;
        else if (items.some(m => m.id > previousMax)) $('jump-latest').hidden = false;
        scheduleRead();
    }
    async function request(url, options = {}) {
        const response = await fetch(url, {credentials:'same-origin', ...options, headers: {'X-CSRFToken':csrf, ...options.headers}});
        if (response.redirected) throw new Error('Your session expired. Sign in again.');
        let data;
        try { data = await response.json(); } catch (_) { throw new Error('The server could not process the request. Please try again.'); }
        if (!response.ok) throw new Error(data.error || 'Request failed. Please try again.');
        return data;
    }
    function scheduleRead() {
        clearTimeout(readTimer);
        if (document.hidden || !nearBottom() || !records.size) return;
        readTimer = setTimeout(async () => {
            const through = Math.max(...records.keys());
            if (through <= readThrough) return;
            const body = new FormData(); body.set('through', through);
            try { await request(config.readUrl, {method:'POST', body}); readThrough = through; document.querySelector('.chat-row.active .badge')?.remove(); }
            catch (_) { /* Retry on the next focus or synchronization. */ }
        }, 300);
    }
    async function sync() {
        if (syncing || document.hidden) return;
        syncing = true;
        try {
            let cursor = Math.max(0, ...records.keys()), page;
            if (cursor) {
                do {
                    page = await request(`${config.historyUrl}?after=${cursor}`);
                    merge(page.messages);
                    if (page.messages.length) cursor = page.messages.at(-1).id;
                } while (page.has_more);
            }
            page = await request(config.historyUrl);
            merge(page.messages);
        } catch (exc) { error(exc.message); }
        finally { syncing = false; }
    }
    function connect() {
        if (closed) return;
        const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
        socket = new WebSocket(`${protocol}//${location.host}/ws/chat/private/${config.chatId}/`);
        socket.addEventListener('open', () => {
            retry = 0; $('connection-status').textContent = 'Connected'; sync();
        });
        socket.addEventListener('message', event => {
            let data; try { data = JSON.parse(event.data); } catch (_) { return; }
            if (data.type === 'message') merge([data], data.sender_id === config.userId);
            if (data.type === 'typing' && data.sender_id !== config.userId) {
                $('typing-status').textContent = 'Typing…'; clearTimeout(typingTimer);
                typingTimer = setTimeout(() => { $('typing-status').textContent = ''; }, 3000);
            }
            if (data.type === 'read' && data.reader_id !== config.userId) {
                records.forEach(dataRow => {
                    if (dataRow.id <= data.through && dataRow.sender_id === config.userId) {
                        dataRow.is_read = true; receipt(rows.get(dataRow.id), dataRow);
                    }
                });
            }
        });
        socket.addEventListener('close', event => {
            if (closed) return;
            $('connection-status').textContent = event.code === 4403 ? 'Access denied. Sign in again.' : 'Reconnecting…';
            if (event.code !== 4403) reconnectTimer = setTimeout(connect, Math.min(30000, 1000 * 2 ** retry++));
        });
        socket.addEventListener('error', () => { $('connection-status').textContent = 'Connection interrupted'; });
    }
    function clearFile() {
        selectedFile = null; $('file-input').value = ''; $('attachment-preview').hidden = true;
        $('voice-preview').pause(); $('voice-preview').removeAttribute('src'); $('voice-preview').load();
        if (previewUrl) URL.revokeObjectURL(previewUrl); previewUrl = null;
    }
    function chooseFile(file, kind = 'file') {
        if (!file || file.size === 0 || file.size > limit) { error('Choose a non-empty file no larger than 5 MB.'); return; }
        clearFile(); selectedFile = file; selectedKind = kind;
        $('attachment-name').textContent = `${file.name} · ${Math.ceil(file.size / 1024)} KB`;
        $('attachment-preview').hidden = false; $('voice-preview').hidden = kind !== 'voice';
        if (kind === 'voice') { previewUrl = URL.createObjectURL(file); $('voice-preview').src = previewUrl; }
        error();
    }
    function setBusy(value) {
        sending = value;
        [send, input, $('attach-button'), $('voice-button'), $('remove-attachment')].forEach(el => { el.disabled = value; });
    }
    async function submit(event) {
        event.preventDefault();
        if (sending || (recorder && recorder.state === 'recording')) return;
        const text = input.value.trim();
        if (!text && !selectedFile) return;
        const fingerprint = JSON.stringify([text, selectedFile?.name, selectedFile?.size, selectedFile?.lastModified]);
        if (fingerprint !== pendingFingerprint) { pendingId = messageId(); pendingFingerprint = fingerprint; }
        const body = new FormData(); body.set('message', text); body.set('client_id', pendingId);
        if (selectedFile) { body.set('file', selectedFile); body.set('kind', selectedKind); }
        setBusy(true); error();
        try {
            const data = await request(config.sendUrl, {method:'POST', body}); merge([data], true);
            input.value = ''; input.style.height = ''; clearFile(); pendingFingerprint = null;
            try { sessionStorage.removeItem(`pulse-draft-${config.userId}-${config.chatId}`); } catch (_) { /* Storage is optional. */ }
        } catch (exc) { error(`${exc.message} Your message is kept here for retry.`); }
        finally { setBusy(false); input.focus(); }
    }
    async function recordVoice() {
        if (recorder && recorder.state === 'recording') { recorder.stop(); return; }
        if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
            error('Voice recording requires HTTPS (or localhost) and a browser with microphone support.'); return;
        }
        $('voice-button').disabled = true; $('attach-button').disabled = true; send.disabled = true;
        try {
            recordingStream = await navigator.mediaDevices.getUserMedia({audio:true});
            const mimeType = ['audio/webm;codecs=opus', 'audio/ogg;codecs=opus', 'audio/mp4'].find(type => MediaRecorder.isTypeSupported(type));
            if (!mimeType) throw new Error('This browser cannot record a supported audio format.');
            recorder = new MediaRecorder(recordingStream, {mimeType, audioBitsPerSecond:64000});
            const chunks = []; let bytes = 0, failed = false;
            recorder.addEventListener('dataavailable', event => {
                if (event.data.size) { chunks.push(event.data); bytes += event.data.size; }
                if (bytes >= limit - 65536 && recorder.state === 'recording') recorder.stop();
            });
            recorder.addEventListener('error', () => { failed = true; error('Recording failed. Please try again.'); recorder.stop(); });
            recorder.addEventListener('stop', () => {
                clearInterval(recordingTimer); recordingStream.getTracks().forEach(track => track.stop());
                $('voice-button').classList.remove('recording'); $('voice-button').setAttribute('aria-label', 'Record voice message');
                $('voice-button').title = 'Record voice message'; $('record-status').textContent = 'Listen to your recording, then press Send.';
                $('attach-button').disabled = false; send.disabled = false;
                if (!failed && !closed) {
                    const extension = mimeType.includes('mp4') ? 'm4a' : mimeType.includes('ogg') ? 'ogg' : 'webm';
                    chooseFile(new File(chunks, `voice-${Date.now()}.${extension}`, {type:mimeType}), 'voice');
                }
            });
            recorder.start(250); recordingSeconds = 0; error();
            $('voice-button').classList.add('recording'); $('voice-button').setAttribute('aria-label', 'Stop recording');
            $('voice-button').title = 'Stop recording'; $('record-status').textContent = 'Recording… press the microphone to stop.';
            $('attach-button').disabled = true; send.disabled = true;
            recordingTimer = setInterval(() => {
                recordingSeconds++; $('record-status').textContent = `Recording ${Math.floor(recordingSeconds / 60)}:${String(recordingSeconds % 60).padStart(2, '0')} · Click microphone to stop`;
                if (recordingSeconds >= 300 && recorder.state === 'recording') recorder.stop();
            }, 1000);
        } catch (exc) {
            recordingStream?.getTracks().forEach(track => track.stop());
            $('attach-button').disabled = false; send.disabled = false;
            error(exc.name === 'NotAllowedError' ? 'Microphone permission was denied. Allow access in your browser and try again.' : exc.message);
        } finally { $('voice-button').disabled = false; }
    }
    $('composer').addEventListener('submit', submit);
    input.addEventListener('keydown', event => {
        if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); $('composer').requestSubmit(); }
    });
    input.addEventListener('input', () => {
        input.style.height = 'auto'; input.style.height = `${Math.min(input.scrollHeight, 140)}px`;
        try { sessionStorage.setItem(`pulse-draft-${config.userId}-${config.chatId}`, input.value); } catch (_) { /* Storage is optional. */ }
        if (socket?.readyState === WebSocket.OPEN && Date.now() - lastTyping > 2000) {
            socket.send(JSON.stringify({type:'typing'})); lastTyping = Date.now();
        }
    });
    $('attach-button').addEventListener('click', () => $('file-input').click());
    $('file-input').addEventListener('change', event => chooseFile(event.target.files[0]));
    $('remove-attachment').addEventListener('click', clearFile);
    $('voice-button').addEventListener('click', recordVoice);
    $('jump-latest').addEventListener('click', () => { bottom(); scheduleRead(); });
    list.addEventListener('scroll', () => { if (nearBottom()) $('jump-latest').hidden = true; scheduleRead(); });
    $('load-older').hidden = !config.hasMore;
    $('load-older').addEventListener('click', async () => {
        $('load-older').disabled = true;
        try {
            const page = await request(`${config.historyUrl}?before=${Math.min(...records.keys())}`);
            const height = list.scrollHeight, top = list.scrollTop;
            page.messages.forEach(add); groupDays(); list.scrollTop = top + list.scrollHeight - height;
            $('load-older').hidden = !page.has_more;
        } catch (exc) { error(exc.message); }
        finally { $('load-older').disabled = false; }
    });
    document.addEventListener('visibilitychange', () => { if (!document.hidden) { groupDays(); sync(); scheduleRead(); } });
    window.addEventListener('online', () => { clearTimeout(reconnectTimer); if (!socket || socket.readyState === WebSocket.CLOSED) connect(); sync(); });
    window.addEventListener('beforeunload', event => {
        if (selectedFile || sending || recorder?.state === 'recording') { event.preventDefault(); event.returnValue = ''; }
    });
    window.addEventListener('pagehide', () => {
        closed = true; clearTimeout(reconnectTimer); clearInterval(recordingTimer); socket?.close();
        recordingStream?.getTracks().forEach(track => track.stop());
    });
    window.addEventListener('pageshow', event => { if (event.persisted) { closed = false; connect(); } });
    try { input.value = sessionStorage.getItem(`pulse-draft-${config.userId}-${config.chatId}`) || ''; } catch (_) { /* Storage is optional. */ }
    merge(config.initial, true); connect();
    setInterval(sync, 15000);
    setInterval(groupDays, 60000);
})();
