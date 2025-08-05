// AI-enhanced utilities for git ingest

// Copy functionality
function copyText(className) {
    let textToCopy;

    if (className === 'directory-structure') {
        // For directory structure, get the hidden input value
        const hiddenInput = document.getElementById('directory-structure-content');
        if (!hiddenInput) return;
        textToCopy = hiddenInput.value;
    } else {
        // For other elements, get the textarea value
        const textarea = document.querySelector(`.${className}`);
        if (!textarea) return;
        textToCopy = textarea.value;
    }

    const button = document.querySelector(`button[onclick="copyText('${className}')"]`);
    if (!button) return;

    // Copy text
    navigator.clipboard.writeText(textToCopy)
        .then(() => {
            // Store original content
            const originalContent = button.innerHTML;
            
            // Change button content
            button.innerHTML = `
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
                </svg>
                Copied!
            `;
            
            // Reset after 2 seconds
            setTimeout(() => {
                button.innerHTML = originalContent;
            }, 2000);
        })
        .catch((err) => {
            console.error('Failed to copy text:', err);
            const originalContent = button.innerHTML;
            
            button.innerHTML = `
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                </svg>
                Failed
            `;
            setTimeout(() => {
                button.innerHTML = originalContent;
            }, 2000);
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
    
    // Scroll to error
    errorDiv.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// Helper function to collect AI form data
function collectAIFormData(form) {
    const json_data = {};
    const inputText = form.querySelector('[name="input_text"]');
    const contextSize = form.querySelector('[name="context_size"]');
    const userPrompt = form.querySelector('[name="user_prompt"]');
    const token = form.querySelector('[name="token"]');

    if (inputText) json_data.input_text = inputText.value.trim();
    if (contextSize) json_data.context_size = contextSize.value;
    if (userPrompt) json_data.user_prompt = userPrompt.value.trim();
    if (token && token.value.trim()) json_data.token = token.value.trim();

    return json_data;
}

// Helper function to manage AI button loading state
function setAIButtonLoadingState(submitButton, isLoading) {
    if (!isLoading) {
        submitButton.disabled = false;
        submitButton.innerHTML = submitButton.getAttribute('data-original-content') || 'Ingest';
        submitButton.classList.remove('bg-[#ffb14d]', 'opacity-75', 'cursor-not-allowed');
        return;
    }

    // Store original content if not already stored
    if (!submitButton.getAttribute('data-original-content')) {
        submitButton.setAttribute('data-original-content', submitButton.innerHTML);
    }

    submitButton.disabled = true;
    submitButton.innerHTML = `
        <div class="flex items-center justify-center">
            <svg class="animate-spin h-5 w-5 text-gray-900 mr-2" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            Processing...
        </div>
    `;
    submitButton.classList.add('bg-[#ffb14d]', 'opacity-75', 'cursor-not-allowed');
}

// Enhanced success handler for AI results
function handleAISuccessfulResponse(data) {
    // Show results section
    showResults();

    // Store the digest_url for download functionality
    window.currentDigestUrl = data.digest_url;

    // Set plain text content for summary, tree, and content
    document.getElementById('result-summary').value = data.summary || '';
    document.getElementById('directory-structure-content').value = data.tree || '';
    document.getElementById('result-content').value = data.content || '';

    // Update AI-specific information if available
    if (window.updateAIInfo && (data.selected_files || data.context_size)) {
        window.updateAIInfo(data);
    }

    // Populate directory structure (without clickable functionality for AI)
    const dirPre = document.getElementById('directory-structure-pre');
    if (dirPre && data.tree) {
        dirPre.innerHTML = '';
        data.tree.split('\n').forEach((line) => {
            const pre = document.createElement('pre');
            pre.setAttribute('name', 'tree-line');
            pre.className = 'whitespace-pre-wrap';
            pre.textContent = line;
            dirPre.appendChild(pre);
        });
    }

    // Show success notification
    showNotification('🎉 Analysis completed successfully!', 'success');

    // Scroll to results
    document.getElementById('results-section').scrollIntoView({ 
        behavior: 'smooth', 
        block: 'start' 
    });
}

// AI-enhanced submit handler
function handleAISubmit(event, showLoadingSpinner = false) {
    event.preventDefault();
    const form = event.target || document.getElementById('ingestForm');

    if (!form) return;

    // Validate form
    const inputText = form.querySelector('[name="input_text"]').value.trim();
    if (!inputText) {
        showNotification('❌ Please enter a repository URL or slug', 'error');
        return;
    }

    if (showLoadingSpinner) {
        showLoading();
    }

    const submitButton = form.querySelector('button[type="submit"]');
    if (!submitButton) return;

    const json_data = collectAIFormData(form);

    if (showLoadingSpinner) {
        setAIButtonLoadingState(submitButton, true);
    }

    // Log the request for debugging
    console.log('Ingest Request:', json_data);

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
        } catch (parseError) {
            console.error('Failed to parse response:', parseError);
            data = { error: 'Invalid response from server' };
        }
        
        setAIButtonLoadingState(submitButton, false);

        if (!response.ok) {
            // Show all error details if present
            if (Array.isArray(data.detail)) {
                const details = data.detail.map((d) => `<li>${d.msg || JSON.stringify(d)}</li>`).join('');
                showError(`<div class='mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700'><b>Analysis Error(s):</b><ul>${details}</ul></div>`);
                return;
            }
            // Other errors
            const errorMsg = data.error || data.message || 'Analysis failed. Please try again.';
            showError(`<div class='mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700'><strong>❌ Analysis Failed</strong><br>${errorMsg}</div>`);
            showNotification(`❌ Analysis failed: ${errorMsg}`, 'error');
            return;
        }

        // Handle error in data
        if (data.error) {
            showError(`<div class='mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700'><strong>❌ Analysis Error</strong><br>${data.error}</div>`);
            showNotification(`❌ ${data.error}`, 'error');
            return;
        }

        handleAISuccessfulResponse(data);
    })
    .catch((error) => {
        console.error('Network error:', error);
        setAIButtonLoadingState(submitButton, false);
        
        const errorMsg = `Network error: ${error.message || 'Unable to connect to server'}`;
        showError(`<div class='mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700'><strong>❌ Connection Error</strong><br>${errorMsg}</div>`);
        showNotification(`❌ ${errorMsg}`, 'error');
    });
}

// Enhanced copy full digest for AI
function copyFullDigest() {
    const directoryStructure = document.getElementById('directory-structure-content').value;
    const filesContent = document.querySelector('.result-text').value;
    const fullDigest = `${directoryStructure}\n\n${filesContent}`;
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
        console.error('Failed to copy text:', err);
        showNotification('❌ Failed to copy to clipboard', 'error');
    });
}

// Enhanced download function
function downloadFullDigest() {
    // Check if we have a digest_url
    if (!window.currentDigestUrl) {
        console.error('No digest_url available for download');
        showNotification('❌ No download URL available', 'error');
        return;
    }

    // Show feedback on the button
    const button = document.querySelector('[onclick="downloadFullDigest()"]');
    const originalText = button.innerHTML;

    button.innerHTML = `
        <svg class="w-4 h-4 mr-2 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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
    
    showNotification('✅ Digest downloaded successfully!', 'success');
}

// Notification system
function showNotification(message, type = 'info') {
    // Remove any existing notifications
    const existingNotifications = document.querySelectorAll('.ai-notification');
    existingNotifications.forEach(n => n.remove());

    // Create notification element
    const notification = document.createElement('div');
    notification.className = `ai-notification fixed top-4 right-4 z-50 p-4 rounded-lg shadow-lg transition-all duration-300 max-w-sm ${
        type === 'success' ? 'bg-green-100 border border-green-300 text-green-800' : 
        type === 'error' ? 'bg-red-100 border border-red-300 text-red-800' :
        'bg-blue-100 border border-blue-300 text-blue-800'
    }`;
    
    notification.innerHTML = `
        <div class="flex items-start space-x-2">
            <div class="flex-1">${message}</div>
            <button onclick="this.parentElement.parentElement.remove()" 
                    class="ml-2 text-gray-500 hover:text-gray-700 text-lg leading-none">×</button>
        </div>
    `;
    
    document.body.appendChild(notification);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (notification.parentElement) {
            notification.remove();
        }
    }, 5000);
}

// Global submit handler for examples
function submitExample(url) {
    const inputText = document.getElementById('input_text');
    if (inputText) {
        inputText.value = url;
        
        // Trigger AI submit
        const form = document.getElementById('ingestForm');
        if (form) {
            handleAISubmit(new Event('submit'), true);
        }
    }
}

// Setup global enter handler for AI form
function setupAIGlobalEnterHandler() {
    document.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' && !event.target.matches('textarea')) {
            const form = document.getElementById('ingestForm');
            if (form) {
                event.preventDefault();
                handleAISubmit(new Event('submit'), true);
            }
        }
    });
}

// Initialize AI-specific functionality
document.addEventListener('DOMContentLoaded', () => {
    setupAIGlobalEnterHandler();
});

// Make functions available globally
window.handleAISubmit = handleAISubmit;
window.handleSubmit = handleAISubmit; // Alias for compatibility
window.copyText = copyText;
window.copyFullDigest = copyFullDigest;
window.downloadFullDigest = downloadFullDigest;
window.showNotification = showNotification;
window.submitExample = submitExample;