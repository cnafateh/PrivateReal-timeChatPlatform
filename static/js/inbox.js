(() => {
    'use strict';
    const list = document.querySelector('.conversation-list');
    let socket, retry = 0, timer, loading = false, closed = false, lastHtml;
    function heartbeat() {
        if (socket?.readyState === WebSocket.OPEN)
            socket.send('{"type":"heartbeat"}');
    }
    async function syncNotifications() {
        if (!window.PulseBridge || document.hidden) return;
        try {
            const response = await fetch('/api/mobile/unread/', {credentials:'same-origin', cache:'no-store'});
            if (!response.ok || response.redirected) return;
            window.PulseBridge.postMessage(JSON.stringify({type:'notifications', payload: await response.json()}));
        } catch (_) { /* The next WebSocket event or scheduled check retries. */ }
    }
    async function refresh() {
        if (!list || loading || document.hidden) return;
        loading = true;
        try {
            const response = await fetch('/api/inbox/', {credentials: 'same-origin', cache: 'no-store'});
            if (!response.ok || response.redirected) return;
            const data = await response.json();
            if (data.html === lastHtml) return;
            const next = new DOMParser().parseFromString(data.html, 'text/html').querySelector('.conversation-list');
            if (!next) return;
            lastHtml = data.html;
            const current = document.querySelector('.conversation-list');
            const scrollTop = current.scrollTop;
            current.replaceWith(next);
            next.scrollTop = scrollTop;
            document.querySelectorAll('.chat-time').forEach(time => {
                const date = new Date(time.dateTime);
                if (date.toDateString() === new Date().toDateString())
                    time.textContent = date.toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'});
            });
            window.dispatchEvent(new Event('pulse:inbox-updated'));
        } catch (_) { /* Reconnect and periodic refresh recover missed updates. */ }
        finally { loading = false; }
    }
    function connect() {
        if (closed) return;
        const scheme = location.protocol === 'https:' ? 'wss:' : 'ws:';
        socket = new WebSocket(`${scheme}//${location.host}/ws/inbox/`);
        socket.addEventListener('open', () => { retry = 0; heartbeat(); refresh(); syncNotifications(); });
        socket.addEventListener('message', () => { refresh(); syncNotifications(); });
        socket.addEventListener('close', event => {
            if (!closed && event.code !== 4403)
                timer = setTimeout(connect, Math.min(30000, 1000 * 2 ** retry++));
        });
    }
    document.addEventListener('visibilitychange', () => { if (!document.hidden) { refresh(); syncNotifications(); } });
    window.addEventListener('online', () => { refresh(); syncNotifications(); if (!socket || socket.readyState === WebSocket.CLOSED) connect(); });
    window.addEventListener('pagehide', () => { closed = true; clearTimeout(timer); socket?.close(); });
    window.addEventListener('pageshow', event => { if (event.persisted) { closed = false; connect(); } });
    connect();
    setInterval(heartbeat, 25000);
    setInterval(refresh, 15000);
    setInterval(syncNotifications, 15000);
})();
