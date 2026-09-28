(() => {
    const preferred = window.matchMedia('(prefers-color-scheme: dark)');
    let stored;
    try { stored = localStorage.getItem('pulse-theme'); } catch (_) { /* Storage is optional. */ }
    function apply(theme) {
        document.documentElement.dataset.theme = theme;
        document.querySelector('meta[name="theme-color"]').content = theme === 'dark' ? '#080b14' : '#f3f5fa';
        const button = document.getElementById('theme-toggle');
        if (button) button.setAttribute('aria-label', `Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`);
    }
    apply(stored === 'dark' || stored === 'light' ? stored : preferred.matches ? 'dark' : 'light');
    preferred.addEventListener('change', event => { if (!stored) apply(event.matches ? 'dark' : 'light'); });
    document.addEventListener('DOMContentLoaded', () => {
        apply(document.documentElement.dataset.theme);
        document.getElementById('theme-toggle').addEventListener('click', () => {
            stored = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
            apply(stored);
            try { localStorage.setItem('pulse-theme', stored); } catch (_) { /* Keep the session preference. */ }
        });
        document.querySelectorAll('.chat-time').forEach(el => {
            const date = new Date(el.dateTime), today = new Date();
            el.textContent = date.toDateString() === today.toDateString()
                ? date.toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'})
                : date.toLocaleDateString([], {month:'short', day:'numeric', ...(date.getFullYear() !== today.getFullYear() ? {year:'numeric'} : {})});
        });
    });
})();
