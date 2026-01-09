// STREAMING TEXT DISPLAY (like Gemini)
async function streamWords(text, container) {
    /**
     * Stream text word-by-word with fade-in animation
     * Similar to Gemini's streaming effect
     */
    const words = text.split(' ');
    
    for (let i = 0; i < words.length; i++) {
        const span = document.createElement('span');
        span.textContent = words[i] + ' ';
        span.style.opacity = '0';
        span.style.animation = 'fadeIn 0.15s ease-in forwards';
        container.appendChild(span);
        
        // Auto-scroll to bottom
        container.scrollTop = container.scrollHeight;
        
        // Small delay between words (30ms = ~33 words/second)
        await new Promise(resolve => setTimeout(resolve, 30));
    }
}

// Export for use in main script
window.streamWords = streamWords;
