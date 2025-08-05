function waitForStars() {
    return new Promise((resolve) => {
        const check = () => {
            const stars = document.getElementById('github-stars');

            if (stars && stars.textContent !== '0') {resolve();}
            else {setTimeout(check, 10);}
        };

        check();
    });
}

document.addEventListener('DOMContentLoaded', () => {
    const urlInput = document.getElementById('input_text');
    const form = document.getElementById('ingestForm');
    const controlsRow = document.getElementById('controlsRow');

    // Debug logging
    console.log('Git.js loaded');
    console.log('URL Input:', urlInput ? urlInput.value : 'not found');
    console.log('Form:', form ? 'found' : 'not found');
    console.log('Controls Row:', controlsRow ? 'found' : 'not found');
    
    if (controlsRow) {
        console.log('Controls Row visibility:', window.getComputedStyle(controlsRow).display);
        console.log('Controls Row classes:', controlsRow.className);
        // Force show controls for debugging
        controlsRow.style.display = 'grid';
        controlsRow.style.visibility = 'visible';
        controlsRow.style.opacity = '1';
        console.log('Forced controls to be visible');
    }

    if (urlInput && urlInput.value.trim() && form) {
        // Auto-submit immediately
        waitForStars().then(() => {
            const submitEvent = new SubmitEvent('submit', {
                cancelable: true,
                bubbles: true
            });

            Object.defineProperty(submitEvent, 'target', {
                value: form,
                enumerable: true
            });
            // Use AI submit handler if available, otherwise fall back to regular submit
            if (window.handleAISubmit) {
                window.handleAISubmit(submitEvent, true);
            } else if (window.handleSubmit) {
                window.handleSubmit(submitEvent, true);
            }
        });
    }
});
