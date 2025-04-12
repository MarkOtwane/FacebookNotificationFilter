/**
 * Facebook Notification Filter - Main JavaScript
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Auto-dismiss flash messages after 5 seconds
    const flashMessages = document.querySelectorAll('.alert:not(.alert-permanent)');
    flashMessages.forEach(function(flash) {
        setTimeout(function() {
            const bsAlert = new bootstrap.Alert(flash);
            bsAlert.close();
        }, 5000);
    });
    
    // Add confirm dialog to dangerous actions
    const dangerButtons = document.querySelectorAll('.btn-danger[data-confirm]');
    dangerButtons.forEach(function(button) {
        button.addEventListener('click', function(e) {
            if (!confirm(this.dataset.confirm || 'Are you sure?')) {
                e.preventDefault();
                return false;
            }
        });
    });
    
    // Toggle importance for notifications
    const importanceToggles = document.querySelectorAll('.toggle-importance');
    importanceToggles.forEach(function(toggle) {
        toggle.addEventListener('click', function(e) {
            e.preventDefault();
            
            const notificationId = this.dataset.id;
            const currentImportance = this.dataset.importance;
            const newImportance = currentImportance === 'important' ? 'normal' : 'important';
            
            // We would normally use fetch to update the importance via AJAX
            // For demonstration, just reload the page
            window.location.reload();
        });
    });
    
    // Form validation for rule creation
    const ruleForm = document.querySelector('form[action*="rules"]');
    if (ruleForm) {
        ruleForm.addEventListener('submit', function(e) {
            const ruleType = document.getElementById('rule_type');
            const importance = document.getElementById('importance');
            
            if (!ruleType.value) {
                e.preventDefault();
                alert('Please select a notification type.');
                ruleType.focus();
                return false;
            }
            
            if (!importance.value) {
                e.preventDefault();
                alert('Please select an importance level.');
                importance.focus();
                return false;
            }
        });
    }
    
    // Notification refresh button loading state
    const refreshButton = document.querySelector('button[type="submit"][form="refresh-form"]');
    if (refreshButton) {
        refreshButton.addEventListener('click', function() {
            this.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Refreshing...';
            this.disabled = true;
        });
    }
});
