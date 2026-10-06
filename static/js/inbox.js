(() => {
    'use strict';
    const list = document.querySelector('.conversation-list');
    if (!list) return;
    let socket, retry = 0, timer, loading = false, closed = false;
    async function refresh() {
        if (loading || document.hidden) return;
        loading = true;
        try {
            const response = await fetch('/api/inbox/', {credentials: 'same-origin', cache: 'no-store'});
            if (!response.ok || response.redirected) return;
            const data = await response.json();
            const next = new DOMParser().parseFromString(data.html, 'text/html').querySelector('.conversation-list');
            if (!next) return;
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
        socket.addEventListener('open', () => { retry = 0; refresh(); });
        socket.addEventListener('message', refresh);
        socket.addEventListener('close', event => {
            if (!closed && event.code !== 4403)
                timer = setTimeout(connect, Math.min(30000, 1000 * 2 ** retry++));
        });
    }
    document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(); });
    window.addEventListener('online', () => { refresh(); if (!socket || socket.readyState === WebSocket.CLOSED) connect(); });
    window.addEventListener('pagehide', () => { closed = true; clearTimeout(timer); socket?.close(); });
    window.addEventListener('pageshow', event => { if (event.persisted) { closed = false; connect(); } });
    connect();
    setInterval(refresh, 15000);
})();
