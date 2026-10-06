(() => {
    'use strict';
    const viewport = window.visualViewport;
    if (!viewport) return;
    function update() {
        if (viewport.scale === 1)
            document.documentElement.style.setProperty('--app-height', `${viewport.height}px`);
        else document.documentElement.style.removeProperty('--app-height');
    }
    viewport.addEventListener('resize', update);
    window.addEventListener('orientationchange', update);
    update();
})();
