/**
 * Formats a date string into a more readable format
 * @param {string} dateStr - The date string from the Gmail API
 * @returns {string} - Formatted date string
 */
function formatDate(dateStr) {
    if (!dateStr || dateStr === 'N/A') return 'N/A';
    
    try {
        const date = new Date(dateStr);
        
        // Check if date is valid
        if (isNaN(date.getTime())) return dateStr;
        
        // Format the date in a user-friendly way
        return date.toLocaleString('en-US', {
            weekday: 'short',
            month: 'short',
            day: 'numeric',
            year: 'numeric',
            hour: 'numeric',
            minute: 'numeric',
            hour12: true
        });
    } catch (e) {
        console.error('Error formatting date:', e);
        return dateStr; // Return original string if there's an error
    }
}

document.addEventListener('DOMContentLoaded', () => {
    console.log('Dashboard JS initialized');
    // Initialize email thread modal
    const threadModal = document.getElementById('email_thread_modal');
    const emailItems = document.querySelectorAll('.email-item');
    const closeModalButtons = document.querySelectorAll('.close-modal');
    const paginationButtons = document.querySelectorAll('.pagination-btn');
    const emailActionButtons = document.querySelectorAll('.email-action-btn');
    const refreshButton = document.querySelector('.btn.join-item.btn-sm:first-child');
    
    // Email thread viewing functionality
    emailItems.forEach(item => {
        item.addEventListener('click', (e) => {
            // Don't open thread if clicking on action buttons
            if (e.target.closest('.card-actions')) {
                return;
            }
            
            const emailId = item.getAttribute('data-email-id');
            if (emailId) {
                openEmailThread(emailId);
            }
        });
    });
    
    // Close modal functionality
    if (closeModalButtons) {
        closeModalButtons.forEach(button => {
            button.addEventListener('click', () => {
                if (threadModal) {
                    threadModal.close();
                }
            });
        });
    }
    
    if (threadModal) {
        threadModal.addEventListener('click', (event) => {
            if (event.target === threadModal) {
                threadModal.close();
            }
        });
    }
    
    if (paginationButtons) {
        paginationButtons.forEach(button => {
            button.addEventListener('click', () => {
                const page = button.getAttribute('data-page');
                if (page) {
                    loadEmailPage(parseInt(page));
                }
            });
        });
    }
    
    if (emailActionButtons) {
        emailActionButtons.forEach(button => {
            button.addEventListener('click', (e) => {
                e.stopPropagation(); // Prevent opening the thread
                
                const action = button.getAttribute('data-action');
                const emailId = button.closest('.email-item').getAttribute('data-email-id');
                
                if (action && emailId) {
                    handleEmailAction(action, emailId);
                }
            });
        });
    }
    
    if (refreshButton) {
        refreshButton.addEventListener('click', () => {
            const currentPageBtn = document.querySelector('.btn-group .btn:not(.pagination-btn)');
            let pageNum = 1;
            
            if (currentPageBtn) {
                const pageText = currentPageBtn.textContent;
                const match = pageText.match(/\d+/);
                if (match) {
                    pageNum = parseInt(match[0]);
                }
            }
            
            loadEmailPage(pageNum);
            showNotification('Refreshing emails...', 'info');
        });
    }
});

/**
 @param {string} emailId 
 */
function openEmailThread(emailId) {
    const threadModal = document.getElementById('email_thread_modal');
    const threadContent = document.getElementById('email_thread_content');
    const threadLoading = document.getElementById('email_thread_loading');
    
    if (!threadModal || !threadContent) {
        console.error('Email thread modal elements not found');
        return;
    }
    
    // Show loading indicator
    if (threadLoading) {
        threadLoading.classList.remove('hidden');
    }
    threadContent.innerHTML = '';
    threadModal.showModal();
    
    // Fetch email content via AJAX
    fetch(`/api/email/${emailId}`)
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            // Hide loading indicator
            if (threadLoading) {
                threadLoading.classList.add('hidden');
            }
            
            // Render email content
            renderEmailThread(data, threadContent);
        })
        .catch(error => {
            console.error('Error fetching email:', error);
            threadContent.innerHTML = `
                <div class="alert alert-error shadow-lg">
                    <div>
                        <i class="fas fa-exclamation-circle"></i>
                        <span>Failed to load email content. Please try again.</span>
                    </div>
                </div>
            `;
            
            if (threadLoading) {
                threadLoading.classList.add('hidden');
            }
        });
}

/**
 * Renders email thread content in the modal
 * @param {Object} data - The email data from the API
 * @param {HTMLElement} container - The container to render content into
 */
function renderEmailThread(data, container) {
    // Format the email content
    let html = `
        <div class="email-thread">
            <div class="email-header">
                <h2 class="text-xl font-bold">${data.subject}</h2>
                <div class="email-meta">
                    <p><strong>From:</strong> ${data.from}</p>
                    <p><strong>To:</strong> ${data.to}</p>
                    <p><strong>Date:</strong> ${formatDate(data.date)}</p>
                </div>
            </div>
            <div class="divider"></div>
            <div class="email-body prose">
                <div id="email-content">${data.body}</div>
            </div>
        </div>
    `;
    
    // If there are attachments, add them
    if (data.attachments && data.attachments.length > 0) {
        html += `
            <div class="email-attachments mt-4">
                <h3 class="text-lg font-semibold">Attachments</h3>
                <div class="flex flex-wrap gap-2 mt-2">
        `;
        
        data.attachments.forEach(attachment => {
            html += `
                <div class="attachment-item p-2 border rounded flex items-center gap-2">
                    <i class="fas fa-paperclip"></i>
                    <span>${attachment.filename}</span>
                    <a href="/api/attachment/${attachment.id}" class="btn btn-xs btn-ghost">
                        <i class="fas fa-download"></i>
                    </a>
                </div>
            `;
        });
        
        html += `
                </div>
            </div>
        `;
    }
    
    // Add reply form
    html += `
        <div class="email-reply mt-6">
            <h3 class="text-lg font-semibold">Reply</h3>
            <div class="form-control mt-2">
                <textarea class="textarea textarea-bordered h-24" placeholder="Write your reply here..."></textarea>
                <div class="flex justify-end mt-2">
                    <button class="btn btn-primary" onclick="sendReply('${data.id}')">Send Reply</button>
                </div>
            </div>
        </div>
    `;
    
    container.innerHTML = html;
}

/**
 * Loads a specific page of emails
 * @param {number} page - The page number to load
 */
function loadEmailPage(page) {
    const emailContainer = document.querySelector('.grid.gap-4');
    const paginationControls = document.querySelector('.flex.justify-center.mt-6');
    
    if (!emailContainer) {
        console.error('Email container not found');
        return;
    }
    
    // Show loading state
    emailContainer.innerHTML = `
        <div class="loading-emails flex justify-center items-center py-8">
            <span class="loading loading-spinner loading-lg"></span>
            <span class="ml-2">Loading emails...</span>
        </div>
    `;
    
    // Fetch emails for the requested page
    fetch(`/api/emails?page=${page}`)
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            // Render emails
            renderEmails(data.emails, emailContainer);
            
            // Update pagination if provided
            if (data.pagination && paginationControls) {
                updatePagination(data.pagination, paginationControls);
            }
        })
        .catch(error => {
            console.error('Error loading emails:', error);
            emailContainer.innerHTML = `
                <div class="alert alert-error shadow-lg">
                    <div>
                        <i class="fas fa-exclamation-circle"></i>
                        <span>Failed to load emails. Please try again.</span>
                    </div>
                </div>
            `;
        });
}

/**
 * Renders a list of emails in the container
 * @param {Array} emails - The list of email objects
 * @param {HTMLElement} container - The container to render emails into
 */
function renderEmails(emails, container) {
    if (!emails || emails.length === 0) {
        container.innerHTML = `
            <div class="alert alert-info shadow-lg">
                <div>
                    <i class="fas fa-info-circle"></i>
                    <span>No emails found or unable to fetch emails.</span>
                </div>
            </div>
        `;
        return;
    }
    
    let html = '';
    
    emails.forEach(email => {
        html += `
            <div class="card email-item hover:bg-base-200 cursor-pointer shadow-sm border border-base-200" data-email-id="${email.id}">
                <div class="card-body p-4">
                    <div class="flex justify-between items-start">
                        <h3 class="card-title text-lg">${email.subject}</h3>
                        <span class="badge badge-ghost">${formatDate(email.date)}</span>
                    </div>
                    <p class="email-meta"><strong>From:</strong> ${email.from}</p>
                    <p class="mt-2 text-base-content/80">${email.snippet}...</p>
                    <div class="card-actions justify-end mt-2">
                        <button class="btn btn-ghost btn-sm email-action-btn" data-action="reply" data-email-id="${email.id}">
                            <i class="fas fa-reply"></i> Reply
                        </button>
                        <button class="btn btn-ghost btn-sm email-action-btn" data-action="archive" data-email-id="${email.id}">
                            <i class="fas fa-archive"></i> Archive
                        </button>
                        <button class="btn btn-ghost btn-sm email-action-btn" data-action="delete" data-email-id="${email.id}">
                            <i class="fas fa-trash"></i> Delete
                        </button>
                    </div>
                </div>
            </div>
        `;
    });
    
    container.innerHTML = html;
    
    // Reattach event listeners to new elements
    attachEmailEventListeners();
}

/**
 * Updates the pagination controls
 * @param {Object} pagination - Pagination data
 * @param {HTMLElement} container - The pagination container
 */
function updatePagination(pagination, container) {
    const { current_page, total_pages } = pagination;
    
    let html = `
        <div class="btn-group">
            <button class="btn btn-sm pagination-btn" data-page="${Math.max(1, current_page - 1)}" ${current_page <= 1 ? 'disabled' : ''}>
                «
            </button>
    `;
    
    // Simple pagination with current page indicator
    html += `<button class="btn btn-sm">Page ${current_page} of ${total_pages}</button>`;
    
    html += `
            <button class="btn btn-sm pagination-btn" data-page="${Math.min(total_pages, current_page + 1)}" ${current_page >= total_pages ? 'disabled' : ''}>
                »
            </button>
        </div>
    `;
    
    container.innerHTML = html;
    
    // Reattach event listeners to pagination buttons
    const paginationButtons = container.querySelectorAll('.pagination-btn');
    paginationButtons.forEach(button => {
        button.addEventListener('click', () => {
            const page = button.getAttribute('data-page');
            if (page) {
                loadEmailPage(parseInt(page));
            }
        });
    });
}

/**
 * Handles email actions (reply, archive, delete)
 * @param {string} action - The action to perform
 * @param {string} emailId - The ID of the email
 */
function handleEmailAction(action, emailId) {
    // Show confirmation for destructive actions
    if (action === 'delete' && !confirm('Are you sure you want to delete this email?')) {
        return;
    }
    
    // Send action to server
    fetch(`/api/email/${emailId}/${action}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        return response.json();
    })
    .then(data => {
        // Handle success based on action
        if (action === 'delete' || action === 'archive') {
            // Remove email from list if deleted or archived
            const emailElement = document.querySelector(`.email-item[data-email-id="${emailId}"]`);
            if (emailElement) {
                emailElement.remove();
            }
            
            // Show success message
            showNotification(`Email ${action === 'delete' ? 'deleted' : 'archived'} successfully`, 'success');
        } else if (action === 'reply') {
            // Open compose modal with reply details
            openComposeModal(data.replyData);
        }
    })
    .catch(error => {
        console.error(`Error performing ${action}:`, error);
        showNotification(`Failed to ${action} email. Please try again.`, 'error');
    });
}

/**
 * Sends a reply to an email
 * @param {string} emailId - The ID of the email being replied to
 */
function sendReply(emailId) {
    const replyText = document.querySelector('.email-reply textarea').value.trim();
    
    if (!replyText) {
        showNotification('Please enter a reply message', 'warning');
        return;
    }
    
    // Send reply to server
    fetch(`/api/email/${emailId}/reply`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ message: replyText })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        return response.json();
    })
    .then(data => {
        showNotification('Reply sent successfully', 'success');
        
        // Close the modal
        const threadModal = document.getElementById('email_thread_modal');
        if (threadModal) {
            threadModal.close();
        }
    })
    .catch(error => {
        console.error('Error sending reply:', error);
        showNotification('Failed to send reply. Please try again.', 'error');
    });
}

/**
 * Shows a notification message
 * @param {string} message - The message to display
 * @param {string} type - The type of notification (success, error, warning, info)
 */
function showNotification(message, type = 'info') {
    // Create notification element if it doesn't exist
    let notificationContainer = document.getElementById('notification_container');
    
    if (!notificationContainer) {
        notificationContainer = document.createElement('div');
        notificationContainer.id = 'notification_container';
        notificationContainer.className = 'toast toast-end';
        document.body.appendChild(notificationContainer);
    }
    
    // Create notification
    const notification = document.createElement('div');
    notification.className = `alert alert-${type}`;
    
    // Set icon based on type
    let icon = 'info-circle';
    if (type === 'success') icon = 'check-circle';
    if (type === 'error') icon = 'exclamation-circle';
    if (type === 'warning') icon = 'exclamation-triangle';
    
    notification.innerHTML = `
        <div>
            <i class="fas fa-${icon}"></i>
            <span>${message}</span>
        </div>
    `;
    
    // Add to container
    notificationContainer.appendChild(notification);
    
    // Remove after 3 seconds
    setTimeout(() => {
        notification.classList.add('fade-out');
        setTimeout(() => {
            notification.remove();
        }, 300);
    }, 3000);
}

/**
 * Attaches event listeners to email items
 */
function attachEmailEventListeners() {
    // Email thread viewing
    const emailItems = document.querySelectorAll('.email-item');
    emailItems.forEach(item => {
        item.addEventListener('click', (e) => {
            // Don't open thread if clicking on action buttons
            if (e.target.closest('.card-actions')) {
                return;
            }
            
            const emailId = item.getAttribute('data-email-id');
            if (emailId) {
                openEmailThread(emailId);
            }
        });
    });
    
    // Email action buttons
    const emailActionButtons = document.querySelectorAll('.email-action-btn');
    emailActionButtons.forEach(button => {
        button.addEventListener('click', (e) => {
            e.stopPropagation(); // Prevent opening the thread
            
            const action = button.getAttribute('data-action');
            const emailId = button.getAttribute('data-email-id');
            
            if (action && emailId) {
                handleEmailAction(action, emailId);
            }
        });
    });
}

/**
 * Opens the compose modal with optional reply data
 * @param {Object} replyData - Optional data for replying to an email
 */
function openComposeModal(replyData = null) {
    const composeModal = document.getElementById('compose_modal');
    
    if (!composeModal) {
        console.error('Compose modal not found');
        return;
    }
    
    // If replying, pre-fill the form
    if (replyData) {
        const toField = composeModal.querySelector('input[type="email"]');
        const subjectField = composeModal.querySelector('input[type="text"]');
        
        if (toField) toField.value = replyData.to || '';
        if (subjectField) subjectField.value = replyData.subject || '';
    }
    
    composeModal.showModal();
}