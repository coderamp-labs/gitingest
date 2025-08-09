// AI-powered git form JavaScript

// Show/hide the Personal-Access-Token section when the "Private repository" checkbox is toggled.
function toggleAccessSettings() {
    const container = document.getElementById('accessSettingsContainer');
    const examples = document.getElementById('exampleRepositories');
    const show = document.getElementById('showAccessSettings')?.checked;

    container?.classList.toggle('hidden', !show);
    // Adjust examples margin if needed
    if (examples) {
        examples.classList.toggle('lg:mt-0', show);
    }
}

// Auto-resize textarea
function autoResizeTextarea() {
    const textarea = document.getElementById('user_prompt');
    if (textarea) {
        textarea.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = this.scrollHeight + 'px';
        });
    }
}

// Context size management
const contextSizeMap = {
    1: '32k',
    2: '128k', 
    3: '512k',
    4: '1M'
};

const reverseContextSizeMap = {
    '32k': 1,
    '128k': 2,
    '512k': 3,
    '1M': 4
};

function updateContextSizeDisplay(value) {
    const display = document.getElementById('context_size_display');
    if (display) {
        display.textContent = `${value} tokens`;
    }
}

function setContextSize(value) {
    const input = document.getElementById('context_size_input');
    const slider = document.getElementById('context_size_slider');
    
    if (input) {
        input.value = value;
    }
    
    if (slider && reverseContextSizeMap[value]) {
        slider.value = reverseContextSizeMap[value];
        updateSliderBackground(slider);
    }
    
    updateContextSizeDisplay(value);
}

function updateSliderBackground(slider) {
    const percentage = ((slider.value - slider.min) / (slider.max - slider.min)) * 100;
    slider.style.backgroundSize = `${percentage}% 100%`;
}

function handleContextSizeChange() {
    const slider = document.getElementById('context_size_slider');
    const input = document.getElementById('context_size_input');
    
    if (slider) {
        slider.addEventListener('input', function() {
            const mappedValue = contextSizeMap[this.value];
            if (mappedValue && input) {
                input.value = mappedValue;
                updateContextSizeDisplay(mappedValue);
                updateSliderBackground(this);
            }
        });
        
        // Initialize slider background
        updateSliderBackground(slider);
    }
    
    if (input) {
        input.addEventListener('input', function() {
            const value = this.value.toLowerCase().trim();
            updateContextSizeDisplay(value);
            
            // Update slider if it's a standard value
            if (reverseContextSizeMap[value] && slider) {
                slider.value = reverseContextSizeMap[value];
                updateSliderBackground(slider);
            }
        });
        
        // Validate and format on blur
        input.addEventListener('blur', function() {
            const value = this.value.toLowerCase().trim();
            
            // Try to parse and format the value
            if (value.match(/^\d+k?$/)) {
                // Handle numbers like "128", "32k"
                const numValue = parseInt(value.replace('k', ''));
                if (numValue > 0) {
                    this.value = numValue >= 1000 ? `${Math.round(numValue/1000)}M` : `${numValue}k`;
                }
            } else if (value.match(/^\d*\.?\d+m$/)) {
                // Handle "1M", "1.5M", etc.
                const numValue = parseFloat(value.replace('m', ''));
                if (numValue > 0) {
                    this.value = `${numValue}M`;
                }
            } else if (!value.match(/^\d+(k|m)$/i)) {
                // Invalid format, reset to default
                this.value = '128k';
            }
            
            updateContextSizeDisplay(this.value);
        });
    }
}

// Enhanced form validation
function validateAIForm() {
    const inputText = document.getElementById('input_text')?.value?.trim();
    const contextSize = document.getElementById('context_size')?.value;
    
    if (!inputText) {
        alert('Please enter a repository URL or slug');
        return false;
    }
    
    if (!contextSize) {
        alert('Please select a context size');
        return false;
    }
    
    return true;
}

// Add loading state management
function setLoadingState(isLoading) {
    const submitButton = document.querySelector('button[type="submit"]');
    const form = document.getElementById('ingestForm');
    
    if (isLoading) {
        submitButton.innerHTML = '🤖 AI Analyzing...';
        submitButton.disabled = true;
        submitButton.classList.add('opacity-75', 'cursor-not-allowed');
        form.classList.add('pointer-events-none');
    } else {
        submitButton.innerHTML = '🚀 AI Analyze';
        submitButton.disabled = false;
        submitButton.classList.remove('opacity-75', 'cursor-not-allowed');
        form.classList.remove('pointer-events-none');
    }
}

// The main submit handler is now in utils_ai.js as handleAISubmit

// Success and error handlers are now in utils_ai.js

// Initialize everything when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    toggleAccessSettings();
    autoResizeTextarea();
    handleContextSizeChange();
    
    // Attach the AI submit handler to the form
    const form = document.getElementById('ingestForm');
    if (form) {
        form.onsubmit = function(event) {
            return window.handleAISubmit(event, true);
        };
    }
});

// Make functions available globally for inline handlers
window.toggleAccessSettings = toggleAccessSettings;
window.setContextSize = setContextSize;