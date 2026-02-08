/**
 * Smart Dorm Finder - AI Chatbot Widget
 * Powered by Google Gemini AI
 */

// Session management
function getSessionId() {
    let sessionId = localStorage.getItem('chatbot_session_id');
    if (!sessionId) {
        sessionId = 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
        localStorage.setItem('chatbot_session_id', sessionId);
    }
    return sessionId;
}

// Toggle chatbot modal
function toggleChatbot() {
    const modal = document.getElementById('chatbotModal');
    const isHidden = modal.classList.contains('scale-0');
    
    if (isHidden) {
        // Open chatbot
        modal.classList.remove('scale-0', 'opacity-0');
        modal.classList.add('scale-100', 'opacity-100');
        document.getElementById('chatInput').focus();
    } else {
        // Close chatbot
        closeChatbot();
    }
}

function closeChatbot() {
    const modal = document.getElementById('chatbotModal');
    modal.classList.add('scale-0', 'opacity-0');
    modal.classList.remove('scale-100', 'opacity-100');
}

// Open chatbot (called from button)
document.getElementById('chatbotTrigger')?.addEventListener('click', toggleChatbot);

// Get CSRF token
function getCSRFToken() {
    const cookieValue = document.cookie
        .split('; ')
        .find(row => row.startsWith('csrftoken='))
        ?.split('=')[1];
    return cookieValue || '';
}

// Add message to chat
function addMessage(role, content, isAnimated = true) {
    const container = document.getElementById('chatMessages');
    const messageDiv = document.createElement('div');
    
    if (isAnimated) {
        messageDiv.className = 'flex gap-2 animate-fade-in';
    } else {
        messageDiv.className = 'flex gap-2';
    }
    
    if (role === 'user') {
        messageDiv.classList.add('justify-end');
    }
    
    // Avatar
    let avatarHTML = '';
    if (role === 'assistant') {
        avatarHTML = `
            <div class="flex-shrink-0">
                <div class="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center">
                    <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"></path>
                    </svg>
                </div>
            </div>
        `;
    }
    
    // Message bubble
    const bubbleClass = role === 'user' 
        ? 'bg-blue-600 text-white' 
        : 'bg-white text-gray-800 shadow-sm';
    
    // Format content (preserve line breaks, handle markdown-like formatting)
    const formattedContent = formatMessageContent(content);
    
    messageDiv.innerHTML = `
        ${role === 'assistant' ? avatarHTML : ''}
        <div class="flex-1 ${bubbleClass} rounded-lg p-3 max-w-[85%]">
            <div class="text-sm prose prose-sm max-w-none">${formattedContent}</div>
        </div>
    `;
    
    container.appendChild(messageDiv);
    scrollToBottom();
}

// Format message content
function formatMessageContent(content) {
    // Escape HTML
    content = content
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
    
    // Convert line breaks
    content = content.replace(/\n/g, '<br>');
    
    // Bold text **text**
    content = content.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    
    // Italic text *text*
    content = content.replace(/\*(.+?)\*/g, '<em>$1</em>');
    
    // Lists - (dash space)
    content = content.replace(/^- (.+)$/gm, '• $1');
    
    return content;
}

// Add typing indicator
function addTypingIndicator() {
    const container = document.getElementById('chatMessages');
    const typingDiv = document.createElement('div');
    typingDiv.id = 'typingIndicator';
    typingDiv.className = 'flex gap-2 animate-fade-in';
    
    typingDiv.innerHTML = `
        <div class="flex-shrink-0">
            <div class="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center">
                <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"></path>
                </svg>
            </div>
        </div>
        <div class="flex-1 bg-white rounded-lg shadow-sm p-3 max-w-[85%]">
            <div class="flex gap-1">
                <div class="w-2 h-2 bg-gray-400 rounded-full typing-dot"></div>
                <div class="w-2 h-2 bg-gray-400 rounded-full typing-dot"></div>
                <div class="w-2 h-2 bg-gray-400 rounded-full typing-dot"></div>
            </div>
        </div>
    `;
    
    container.appendChild(typingDiv);
    scrollToBottom();
    return 'typingIndicator';
}

// Remove typing indicator
function removeTypingIndicator() {
    const indicator = document.getElementById('typingIndicator');
    if (indicator) {
        indicator.remove();
    }
}

// Scroll to bottom of chat
function scrollToBottom() {
    const container = document.getElementById('chatMessages');
    setTimeout(() => {
        container.scrollTop = container.scrollHeight;
    }, 100);
}

// Send message
async function sendChatMessage(message) {
    const sessionId = getSessionId();
    
    try {
        const response = await fetch('/dormitory/chatbot/message/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken()
            },
            body: JSON.stringify({
                message: message,
                session_id: sessionId
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            return {
                success: true,
                response: data.response,
                isCached: data.is_cached || false
            };
        } else {
            return {
                success: false,
                response: data.response || 'Sorry, I encountered an error.',
                error: data.error
            };
        }
    } catch (error) {
        console.error('Chatbot error:', error);
        return {
            success: false,
            response: 'Network error. Please check your connection and try again.',
            error: error.message
        };
    }
}

// Handle form submission
document.getElementById('chatForm')?.addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const input = document.getElementById('chatInput');
    const sendBtn = document.getElementById('chatSendBtn');
    const message = input.value.trim();
    
    if (!message) return;
    
    // Disable input
    input.disabled = true;
    sendBtn.disabled = true;
    
    // Display user message
    addMessage('user', message);
    input.value = '';
    
    // Show typing indicator
    addTypingIndicator();
    
    try {
        // Send to backend
        const result = await sendChatMessage(message);
        
        // Remove typing indicator
        removeTypingIndicator();
        
        // Display AI response
        if (result.success) {
            addMessage('assistant', result.response);
            
            // Show cached badge if from FAQ
            if (result.isCached) {
                console.log('Response from FAQ cache');
            }
        } else {
            addMessage('assistant', result.response);
        }
    } catch (error) {
        removeTypingIndicator();
        addMessage('assistant', 'Sorry, something went wrong. Please try again.');
        console.error('Chat error:', error);
    } finally {
        // Re-enable input
        input.disabled = false;
        sendBtn.disabled = false;
        input.focus();
    }
});

// Reset conversation
async function resetChatbotConversation() {
    if (!confirm('Start a new conversation? This will clear all messages.')) {
        return;
    }
    
    const sessionId = getSessionId();
    
    try {
        const response = await fetch('/dormitory/chatbot/reset/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken()
            },
            body: JSON.stringify({
                session_id: sessionId
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Clear messages
            const container = document.getElementById('chatMessages');
            const messages = container.querySelectorAll('.flex.gap-2');
            messages.forEach((msg, index) => {
                // Keep only the welcome message (first one)
                if (index > 0) {
                    msg.remove();
                }
            });
            
            // Generate new session ID
            localStorage.removeItem('chatbot_session_id');
            getSessionId();
            
            console.log('Conversation reset successfully');
        } else {
            console.error('Failed to reset conversation');
        }
    } catch (error) {
        console.error('Reset error:', error);
    }
}

// Quick reply buttons (optional feature - can be added to welcome message)
function sendQuickReply(message) {
    document.getElementById('chatInput').value = message;
    document.getElementById('chatForm').dispatchEvent(new Event('submit'));
}

// Initialize chatbot on page load
document.addEventListener('DOMContentLoaded', function() {
    console.log('AI Chatbot initialized');
    
    // Auto-focus on input when modal opens
    const modal = document.getElementById('chatbotModal');
    const observer = new MutationObserver(function(mutations) {
        mutations.forEach(function(mutation) {
            if (modal.classList.contains('scale-100')) {
                document.getElementById('chatInput')?.focus();
            }
        });
    });
    
    observer.observe(modal, {
        attributes: true,
        attributeFilter: ['class']
    });
});

// Keyboard shortcut: Ctrl+K or Cmd+K to open chatbot
document.addEventListener('keydown', function(e) {
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        toggleChatbot();
    }
});

// Close chatbot on Escape key when modal is open
document.addEventListener('keydown', function(e) {
    const modal = document.getElementById('chatbotModal');
    if (e.key === 'Escape' && modal.classList.contains('scale-100')) {
        closeChatbot();
    }
});

// Quick Reply Button Functions
function showAccountButtons() {
    const subButtons = document.getElementById('subButtons');
    subButtons.innerHTML = `
        <button onclick="askQuestion('How do I create an account?')" class="w-full bg-white hover:bg-gray-50 border-2 border-blue-600 text-blue-600 px-3 py-2 rounded-lg text-xs font-medium transition-colors text-left">
            📝 How to create an account
        </button>
        <button onclick="askQuestion('I forgot my password, what should I do?')" class="w-full bg-white hover:bg-gray-50 border-2 border-blue-600 text-blue-600 px-3 py-2 rounded-lg text-xs font-medium transition-colors text-left">
            🔑 Forgot password
        </button>
        <button onclick="askQuestion('How do I report a tenant or landlord?')" class="w-full bg-white hover:bg-gray-50 border-2 border-blue-600 text-blue-600 px-3 py-2 rounded-lg text-xs font-medium transition-colors text-left">
            ⚠️ Report a user
        </button>
        <button onclick="askQuestion('How do I update my profile?')" class="w-full bg-white hover:bg-gray-50 border-2 border-blue-600 text-blue-600 px-3 py-2 rounded-lg text-xs font-medium transition-colors text-left">
            👤 Update profile
        </button>
        <button onclick="hideSubButtons()" class="w-full bg-gray-200 hover:bg-gray-300 text-gray-700 px-3 py-2 rounded-lg text-xs font-medium transition-colors">
            ← Back
        </button>
    `;
    subButtons.classList.remove('hidden');
}

function showReservationButtons() {
    const subButtons = document.getElementById('subButtons');
    subButtons.innerHTML = `
        <button onclick="askQuestion('How do I make a reservation?')" class="w-full bg-white hover:bg-gray-50 border-2 border-blue-600 text-blue-600 px-3 py-2 rounded-lg text-xs font-medium transition-colors text-left">
            📅 How to reserve a dorm
        </button>
        <button onclick="askQuestion('Can I cancel my reservation?')" class="w-full bg-white hover:bg-gray-50 border-2 border-blue-600 text-blue-600 px-3 py-2 rounded-lg text-xs font-medium transition-colors text-left">
            ❌ Cancel reservation
        </button>
        <button onclick="askQuestion('How do I view my reservations?')" class="w-full bg-white hover:bg-gray-50 border-2 border-blue-600 text-blue-600 px-3 py-2 rounded-lg text-xs font-medium transition-colors text-left">
            📋 View my reservations
        </button>
        <button onclick="askQuestion('What is the refund policy?')" class="w-full bg-white hover:bg-gray-50 border-2 border-blue-600 text-blue-600 px-3 py-2 rounded-lg text-xs font-medium transition-colors text-left">
            💰 Refund policy
        </button>
        <button onclick="hideSubButtons()" class="w-full bg-gray-200 hover:bg-gray-300 text-gray-700 px-3 py-2 rounded-lg text-xs font-medium transition-colors">
            ← Back
        </button>
    `;
    subButtons.classList.remove('hidden');
}

function showPaymentButtons() {
    const subButtons = document.getElementById('subButtons');
    subButtons.innerHTML = `
        <button onclick="askQuestion('What payment methods are accepted?')" class="w-full bg-white hover:bg-gray-50 border-2 border-blue-600 text-blue-600 px-3 py-2 rounded-lg text-xs font-medium transition-colors text-left">
            💳 Payment methods
        </button>
        <button onclick="askQuestion('How are payments processed?')" class="w-full bg-white hover:bg-gray-50 border-2 border-blue-600 text-blue-600 px-3 py-2 rounded-lg text-xs font-medium transition-colors text-left">
            🔄 Payment process
        </button>
        <button onclick="askQuestion('Can I view my transaction history?')" class="w-full bg-white hover:bg-gray-50 border-2 border-blue-600 text-blue-600 px-3 py-2 rounded-lg text-xs font-medium transition-colors text-left">
            📊 Transaction history
        </button>
        <button onclick="askQuestion('Is my payment secure?')" class="w-full bg-white hover:bg-gray-50 border-2 border-blue-600 text-blue-600 px-3 py-2 rounded-lg text-xs font-medium transition-colors text-left">
            🔒 Payment security
        </button>
        <button onclick="hideSubButtons()" class="w-full bg-gray-200 hover:bg-gray-300 text-gray-700 px-3 py-2 rounded-lg text-xs font-medium transition-colors">
            ← Back
        </button>
    `;
    subButtons.classList.remove('hidden');
}

function showDormButtons() {
    const subButtons = document.getElementById('subButtons');
    subButtons.innerHTML = `
        <button onclick="askQuestion('How do I search for dorms?')" class="w-full bg-white hover:bg-gray-50 border-2 border-blue-600 text-blue-600 px-3 py-2 rounded-lg text-xs font-medium transition-colors text-left">
            🔍 Search for dorms
        </button>
        <button onclick="askQuestion('What dorms are available?')" class="w-full bg-white hover:bg-gray-50 border-2 border-blue-600 text-blue-600 px-3 py-2 rounded-lg text-xs font-medium transition-colors text-left">
            🏠 Available dorms
        </button>
        <button onclick="askQuestion('What are the different accommodation types?')" class="w-full bg-white hover:bg-gray-50 border-2 border-blue-600 text-blue-600 px-3 py-2 rounded-lg text-xs font-medium transition-colors text-left">
            🏘️ Accommodation types
        </button>
        <button onclick="askQuestion('How do I schedule a dorm visit?')" class="w-full bg-white hover:bg-gray-50 border-2 border-blue-600 text-blue-600 px-3 py-2 rounded-lg text-xs font-medium transition-colors text-left">
            📍 Schedule a visit
        </button>
        <button onclick="hideSubButtons()" class="w-full bg-gray-200 hover:bg-gray-300 text-gray-700 px-3 py-2 rounded-lg text-xs font-medium transition-colors">
            ← Back
        </button>
    `;
    subButtons.classList.remove('hidden');
}

function hideSubButtons() {
    const subButtons = document.getElementById('subButtons');
    subButtons.classList.add('hidden');
    subButtons.innerHTML = '';
}

function askQuestion(question) {
    // Hide sub-buttons
    hideSubButtons();
    
    // Set input value and submit
    document.getElementById('chatInput').value = question;
    document.getElementById('chatForm').dispatchEvent(new Event('submit'));
}
