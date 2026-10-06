(() => {
    function init() {
        document.querySelectorAll('.avatar-image:not([data-fallback-ready])').forEach(image => {
            image.dataset.fallbackReady = 'true';
            const fallback = () => { image.hidden = true; };
            image.addEventListener('error', fallback);
            if (image.complete && !image.naturalWidth) fallback();
        });
    }
    init();
    window.addEventListener('pulse:inbox-updated', init);
})();
