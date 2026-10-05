(() => {
    document.querySelectorAll('.avatar-image').forEach(image => {
        const fallback = () => { image.hidden = true; };
        image.addEventListener('error', fallback);
        if (image.complete && !image.naturalWidth) fallback();
    });
})();
