/**
 * Login Page JavaScript
 */

document.addEventListener('DOMContentLoaded', function() {
    // Elements
    const loginForm = document.getElementById('login-form');
    const registerForm = document.getElementById('register-form');
    const authTabs = document.querySelectorAll('.auth-tab');
    
    // Tab switching
    authTabs.forEach(tab => {
        tab.addEventListener('click', function() {
            const tabName = this.dataset.tab;
            switchTab(tabName);
        });
    });
    
    function switchTab(tabName) {
        // Update active tab
        authTabs.forEach(tab => {
            tab.classList.toggle('active', tab.dataset.tab === tabName);
        });
        
        // Show/hide forms
        if (tabName === 'login') {
            loginForm.style.display = 'flex';
            registerForm.style.display = 'none';
        } else {
            loginForm.style.display = 'none';
            registerForm.style.display = 'flex';
        }
        
        // Clear messages
        clearMessages();
    }
    
    function clearMessages() {
        document.getElementById('login-message').textContent = '';
        document.getElementById('register-message').textContent = '';
    }
    
    function showMessage(elementId, message, isError = false) {
        const element = document.getElementById(elementId);
        if (element) {
            element.textContent = message;
            element.className = 'form-message ' + (isError ? 'error' : 'success');
        }
    }
    
    // Login form submission
    loginForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const email = document.getElementById('login-email').value.trim();
        const password = document.getElementById('login-password').value;
        const submitBtn = document.getElementById('login-submit');
        
        if (!email || !password) {
            showMessage('login-message', 'Please enter email and password', true);
            return;
        }
        
        // Disable button
        submitBtn.disabled = true;
        submitBtn.classList.add('loading');
        clearMessages();
        
        try {
            const response = await fetch('/api/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password }),
                credentials: 'include'
            });
            
            const data = await response.json();
            
            if (response.ok) {
                // Save token and user info
                localStorage.setItem('access_token', data.access_token);
                localStorage.setItem('user', JSON.stringify(data.user));
                
                // Show success message
                showMessage('login-message', 'Login successful! Redirecting...', false);
                
                // Redirect to dashboard
                setTimeout(() => {
                    window.location.href = '/';
                }, 500);
            } else {
                showMessage('login-message', data.error || 'Login failed', true);
                submitBtn.disabled = false;
                submitBtn.classList.remove('loading');
            }
        } catch (error) {
            console.error('Login error:', error);
            showMessage('login-message', 'Network error. Please try again.', true);
            submitBtn.disabled = false;
            submitBtn.classList.remove('loading');
        }
    });
    
    // Register form submission
    registerForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const name = document.getElementById('register-name').value.trim();
        const email = document.getElementById('register-email').value.trim();
        const password = document.getElementById('register-password').value;
        const submitBtn = document.getElementById('register-submit');
        
        if (!name || !email || !password) {
            showMessage('register-message', 'Please fill in all fields', true);
            return;
        }
        
        // Disable button
        submitBtn.disabled = true;
        submitBtn.classList.add('loading');
        clearMessages();
        
        try {
            const response = await fetch('/api/auth/register', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, email, password })
            });
            
            const data = await response.json();
            
            if (response.ok) {
                // Show success message
                showMessage('register-message', 'Registration successful! Logging you in...', false);
                
                // Auto-login after successful registration
                setTimeout(async () => {
                    const loginResponse = await fetch('/api/auth/login', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ email, password }),
                        credentials: 'include'
                    });
                    
                    const loginData = await loginResponse.json();
                    
                    if (loginResponse.ok) {
                        localStorage.setItem('access_token', loginData.access_token);
                        localStorage.setItem('user', JSON.stringify(loginData.user));
                        window.location.href = '/';
                    } else {
                        // Switch to login tab if auto-login fails
                        switchTab('login');
                        showMessage('login-message', 'Registration successful! Please login.', false);
                    }
                }, 500);
            } else {
                showMessage('register-message', data.error || 'Registration failed', true);
                submitBtn.disabled = false;
                submitBtn.classList.remove('loading');
            }
        } catch (error) {
            console.error('Register error:', error);
            showMessage('register-message', 'Network error. Please try again.', true);
            submitBtn.disabled = false;
            submitBtn.classList.remove('loading');
        }
    });
});
