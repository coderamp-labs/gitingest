function getFileName(element) {
    const indentSize = 4;
    let path = '';
    let prevIndentLevel = null;

    while (element) {
        const line = element.textContent;
        const index = line.search(/[a-zA-Z0-9_.-]/);
        const indentLevel = index / indentSize;

        // Stop when we reach or go above the top-level directory
        if (indentLevel <= 1) {
            break;
        }

        // Only include directories that are one level above the previous
        if (prevIndentLevel === null || indentLevel === prevIndentLevel - 1) {
            const fileName = line.substring(index).trim();

            path = fileName + path;
            prevIndentLevel = indentLevel;
        }

        element = element.previousElementSibling;
    }

    return path;
}

function toggleFile(element) {
    const patternInput = document.getElementById('pattern');
    const patternFiles = patternInput.value ? patternInput.value.split(',').map((item) => item.trim()) : [];

    const directoryContainer = document.getElementById('directory-structure-container');
    const treeLineElements = Array.from(directoryContainer.children).filter((child) => child.tagName === 'PRE');

    // Skip the first two tree lines (header and repository name)
    if (treeLineElements[0] === element || treeLineElements[1] === element) {
        return;
    }

    element.classList.toggle('line-through');
    element.classList.toggle('text-gray-500');

    const fileName = getFileName(element);
    const fileIndex = patternFiles.indexOf(fileName);

    if (fileIndex !== -1) {
        patternFiles.splice(fileIndex, 1);
    } else {
        patternFiles.push(fileName);
    }

    patternInput.value = patternFiles.join(', ');
}

// Copy functionality
function copyText(className) {
    let textToCopy;

    if (className === 'directory-structure') {
    // For directory structure, get the hidden input value
        const hiddenInput = document.getElementById('directory-structure-content');

        if (!hiddenInput) {return;}
        textToCopy = hiddenInput.value;
    } else {
    // For other elements, get the textarea value
        const textarea = document.querySelector(`.${ className }`);

        if (!textarea) {return;}
        textToCopy = textarea.value;
    }

    const button = document.querySelector(`button[onclick="copyText('${className}')"]`);

    if (!button) {return;}

    // Copy text
    navigator.clipboard.writeText(textToCopy)
        .then(() => {
            // Store original content
            const originalContent = button.innerHTML;

            // Change button content
            button.innerHTML = 'Copied!';

            // Reset after 1 second
            setTimeout(() => {
                button.innerHTML = originalContent;
            }, 1000);
        })
        .catch((err) => {
            console.error('Failed to copy text:', err);
            const originalContent = button.innerHTML;

            button.innerHTML = 'Failed to copy';
            setTimeout(() => {
                button.innerHTML = originalContent;
            }, 1000);
        });
}

// Helper functions for toggling result blocks
function showLoading() {
    document.getElementById('results-loading').style.display = 'block';
    document.getElementById('results-section').style.display = 'none';
    document.getElementById('results-error').style.display = 'none';
}
function showResults() {
    document.getElementById('results-loading').style.display = 'none';
    document.getElementById('results-section').style.display = 'block';
    document.getElementById('results-error').style.display = 'none';
}
function showError(msg) {
    document.getElementById('results-loading').style.display = 'none';
    document.getElementById('results-section').style.display = 'none';
    const errorDiv = document.getElementById('results-error');

    errorDiv.innerHTML = msg;
    errorDiv.style.display = 'block';
}

// Helper function to collect form data
function collectFormData(form) {
    const json_data = {};
    const inputText = form.querySelector('[name="input_text"]');
    const token = form.querySelector('[name="token"]');
    const hiddenInput = document.getElementById('max_file_size_kb');
    const patternType = document.getElementById('pattern_type');
    const pattern = document.getElementById('pattern');

    if (inputText) {json_data.input_text = inputText.value;}
    if (token) {json_data.token = token.value;}
    if (hiddenInput) {json_data.max_file_size = hiddenInput.value;}
    if (patternType) {json_data.pattern_type = patternType.value;}
    if (pattern) {json_data.pattern = pattern.value;}

    return json_data;
}

// Helper function to manage button loading state
function setButtonLoadingState(submitButton, isLoading) {
    if (!isLoading) {
        submitButton.disabled = false;
        submitButton.innerHTML = submitButton.getAttribute('data-original-content') || 'Submit';
        submitButton.classList.remove('bg-[#ffb14d]');

        return;
    }

    // Store original content if not already stored
    if (!submitButton.getAttribute('data-original-content')) {
        submitButton.setAttribute('data-original-content', submitButton.innerHTML);
    }

    submitButton.disabled = true;
    submitButton.innerHTML = `
        <div class="flex items-center justify-center">
            <svg class="animate-spin h-5 w-5 text-gray-900" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <span class="ml-2">Processing...</span>
        </div>
    `;
    submitButton.classList.add('bg-[#ffb14d]');
}

// Helper function to handle successful response
function handleSuccessfulResponse(data) {
    // Show results section
    showResults();

    // Store the digest_url for download functionality
    window.currentDigestUrl = data.digest_url;

    // Set plain text content for summary, tree, and content
    document.getElementById('result-summary').value = data.summary || '';
    document.getElementById('directory-structure-content').value = data.tree || '';
    document.getElementById('result-content').value = data.content || '';

    // Populate directory structure lines as clickable <pre> elements
    const dirPre = document.getElementById('directory-structure-pre');

    if (dirPre && data.tree) {
        dirPre.innerHTML = '';
        data.tree.split('\n').forEach((line) => {
            const pre = document.createElement('pre');

            pre.setAttribute('name', 'tree-line');
            pre.className = 'cursor-pointer hover:line-through hover:text-gray-500';
            pre.textContent = line;
            pre.onclick = function () { toggleFile(this); };
            dirPre.appendChild(pre);
        });
    }

    // Scroll to results
    document.getElementById('results-section').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function handleSubmit(event, showLoadingSpinner = false) {
    event.preventDefault();
    const form = event.target || document.getElementById('ingestForm');

    if (!form) {return;}

    // Ensure hidden input is updated before collecting form data
    const slider = document.getElementById('file_size');
    const hiddenInput = document.getElementById('max_file_size_kb');

    if (slider && hiddenInput) {
        hiddenInput.value = logSliderToSize(slider.value);
    }

    if (showLoadingSpinner) {
        showLoading();
    }

    const submitButton = form.querySelector('button[type="submit"]');

    if (!submitButton) {return;}

    const json_data = collectFormData(form);

    if (showLoadingSpinner) {
        setButtonLoadingState(submitButton, true);
    }

    // Submit the form to /api/ingest as JSON
    fetch('/api/ingest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(json_data)
    })
        .then(async (response) => {
            let data;

            try {
                data = await response.json();
            } catch {
                data = {};
            }
            setButtonLoadingState(submitButton, false);

            if (!response.ok) {
                // Show all error details if present
                if (Array.isArray(data.detail)) {
                    const details = data.detail.map((d) => `<li>${d.msg || JSON.stringify(d)}</li>`).join('');

                    showError(`<div class='mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700'><b>Error(s):</b><ul>${details}</ul></div>`);

                    return;
                }
                // Other errors
                showError(`<div class='mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700'>${data.error || JSON.stringify(data) || 'An error occurred.'}</div>`);

                return;
            }

            // Handle error in data
            if (data.error) {
                showError(`<div class='mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700'>${data.error}</div>`);

                return;
            }

            handleSuccessfulResponse(data);
        })
        .catch((error) => {
            setButtonLoadingState(submitButton, false);
            showError(`<div class='mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700'>${error}</div>`);
        });
}

function copyFullDigest() {
    const directoryStructure = document.getElementById('directory-structure-content').value;
    const filesContent = document.querySelector('.result-text').value;
    const fullDigest = `${directoryStructure}\n\nFiles Content:\n\n${filesContent}`;
    const button = document.querySelector('[onclick="copyFullDigest()"]');
    const originalText = button.innerHTML;

    navigator.clipboard.writeText(fullDigest).then(() => {
        button.innerHTML = `
            <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
            </svg>
            Copied!
        `;

        setTimeout(() => {
            button.innerHTML = originalText;
        }, 2000);
    })
        .catch((err) => {
            console.error('Failed to copy text: ', err);
        });
}

function downloadFullDigest() {
    // Check if we have a digest_url
    if (!window.currentDigestUrl) {
        console.error('No digest_url available for download');

        return;
    }

    // Show feedback on the button
    const button = document.querySelector('[onclick="downloadFullDigest()"]');
    const originalText = button.innerHTML;

    button.innerHTML = `
        <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
        </svg>
        Downloading...
    `;

    // Create a download link using the digest_url
    const a = document.createElement('a');

    a.href = window.currentDigestUrl;
    a.download = 'digest.txt';
    document.body.appendChild(a);
    a.click();

    // Clean up
    document.body.removeChild(a);

    // Update button to show success
    button.innerHTML = `
        <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
        </svg>
        Downloaded!
    `;

    setTimeout(() => {
        button.innerHTML = originalText;
    }, 2000);
}

// Add the logSliderToSize helper function
function logSliderToSize(position) {
    const maxPosition = 500;
    const maxValue = Math.log(102400); // 100 MB

    const value = Math.exp(maxValue * (position / maxPosition)**1.5);

    return Math.round(value);
}

// Move slider initialization to a separate function
function initializeSlider() {
    const slider = document.getElementById('file_size');
    const sizeValue = document.getElementById('size_value');
    const hiddenInput = document.getElementById('max_file_size_kb');

    if (!slider || !sizeValue || !hiddenInput) {return;}

    function updateSlider() {
        const value = logSliderToSize(slider.value);

        sizeValue.textContent = formatSize(value);
        slider.style.backgroundSize = `${(slider.value / slider.max) * 100}% 100%`;
        hiddenInput.value = value; // Set hidden input to KB value
    }

    // Update on slider change
    slider.addEventListener('input', updateSlider);

    // Initialize slider position
    updateSlider();
}

// Add helper function for formatting size
function formatSize(sizeInKB) {
    if (sizeInKB >= 1024) {
        return `${ Math.round(sizeInKB / 1024) }MB`;
    }

    return `${ Math.round(sizeInKB) }kB`;
}

// Add this new function
function setupGlobalEnterHandler() {
    document.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' && !event.target.matches('textarea')) {
            const form = document.getElementById('ingestForm');

            if (form) {
                handleSubmit(new Event('submit'), true);
            }
        }
    });
}

// Add to the DOMContentLoaded event listener
document.addEventListener('DOMContentLoaded', () => {
    initializeSlider();
    setupGlobalEnterHandler();
});


// Make sure these are available globally
window.handleSubmit = handleSubmit;
window.toggleFile = toggleFile;
window.copyText = copyText;
window.copyFullDigest = copyFullDigest;
window.downloadFullDigest = downloadFullDigest;
