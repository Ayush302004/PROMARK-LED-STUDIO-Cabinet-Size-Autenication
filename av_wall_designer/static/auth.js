
const AUTH = {
    token: null,
    user: null,
    
    init() {
        console.log('AUTH: Initializing...');
        
        // Load token from localStorage
        this.token = localStorage.getItem('access_token');
        const userJson = localStorage.getItem('user');
        if (userJson) {
            try {
                this.user = JSON.parse(userJson);
                console.log('AUTH: User loaded from localStorage:', this.user);
            } catch (e) {
                console.error('AUTH: Failed to parse user JSON:', e);
                this.user = null;
            }
        }
        
        console.log('AUTH: Token exists:', !!this.token);
        console.log('AUTH: User exists:', !!this.user);
        
        // Check authentication - redirect to login if not authenticated
        if (!this.isAuthenticated()) {
            console.log('AUTH: Not authenticated, redirecting to login');
            window.location.href = '/login';
            return;
        }
        
        console.log('AUTH: User authenticated, setting up UI');
        
        // Setup UI
        this.updateUI();
        this.setupEventListeners();
        
        // Verify token is still valid
        this.verifyToken();
    },
    
    setupEventListeners() {
        // Logout button
        const logoutBtn = document.getElementById('logout-btn');
        if (logoutBtn) {
            logoutBtn.addEventListener('click', () => this.logout());
        }
        
        // User menu button
        const userMenuBtn = document.getElementById('user-menu-btn');
        if (userMenuBtn) {
            userMenuBtn.addEventListener('click', () => this.toggleUserMenu());
        }
        
        // Click outside to close user menu
        document.addEventListener('click', (e) => {
            const userMenu = document.getElementById('user-menu');
            const userMenuBtn = document.getElementById('user-menu-btn');
            if (userMenu && !userMenu.contains(e.target) && e.target !== userMenuBtn) {
                userMenu.style.display = 'none';
            }
        });
    },
    
    updateUI() {
        const authSection = document.getElementById('auth-section');
        if (!authSection) {
            console.error('AUTH: auth-section not found!');
            return;
        }
        
        console.log('AUTH: Updating UI for user:', this.user);
        
        // User is logged in - show user menu
        authSection.innerHTML = `
            <div class="user-menu-container">
                <button class="quiet" id="user-menu-btn" title="${this.user.email}">
                    ${this.user.name || this.user.email}
                    ${this.user.role === 'admin' ? ' 👑' : ''}
                </button>
                <div class="user-menu" id="user-menu" style="display: none;">
                    <div class="user-info">
                        <strong>${this.user.name}</strong>
                        <small>${this.user.email}</small>
                        ${this.user.role === 'admin' ? '<span class="badge">Admin</span>' : ''}
                    </div>
                    <button id="logout-btn" class="menu-item">Logout</button>
                </div>
            </div>
        `;
        
        console.log('AUTH: UI updated, re-attaching event listeners');
        
        // Re-attach event listeners
        const logoutBtn = document.getElementById('logout-btn');
        if (logoutBtn) {
            logoutBtn.addEventListener('click', () => this.logout());
            console.log('AUTH: Logout button listener attached');
        } else {
            console.error('AUTH: logout-btn not found after UI update');
        }
        
        const userMenuBtn = document.getElementById('user-menu-btn');
        if (userMenuBtn) {
            userMenuBtn.addEventListener('click', () => this.toggleUserMenu());
            console.log('AUTH: User menu button listener attached');
        } else {
            console.error('AUTH: user-menu-btn not found after UI update');
        }
    },
    
    toggleUserMenu() {
        const userMenu = document.getElementById('user-menu');
        if (userMenu) {
            userMenu.style.display = userMenu.style.display === 'none' ? 'block' : 'none';
        }
    },
    
    logout() {
        // Call logout API
        if (this.token) {
            fetch('/api/auth/logout', {
                method: 'POST',
                headers: this.getAuthHeaders(),
                credentials: 'include'
            }).catch(error => {
                console.error('Logout error:', error);
            });
        }
        
        // Clear local data
        this.token = null;
        this.user = null;
        localStorage.removeItem('access_token');
        localStorage.removeItem('user');
        
        // Redirect to login page
        window.location.href = '/login';
    },
    
    async verifyToken() {
        try {
            const response = await fetch('/api/auth/me', {
                headers: this.getAuthHeaders()
            });
            
            if (!response.ok) {
                // Token invalid, try refresh
                const refreshed = await this.refreshToken();
                if (!refreshed) {
                    // Refresh failed, redirect to login
                    this.redirectToLogin();
                }
            }
        } catch (error) {
            console.error('Token verification error:', error);
            this.redirectToLogin();
        }
    },
    
    async refreshToken() {
        try {
            const response = await fetch('/api/auth/refresh', {
                method: 'POST',
                credentials: 'include'
            });
            
            if (response.ok) {
                const data = await response.json();
                this.token = data.access_token;
                this.user = data.user;
                
                localStorage.setItem('access_token', this.token);
                localStorage.setItem('user', JSON.stringify(this.user));
                
                this.updateUI();
                return true;
            } else {
                return false;
            }
        } catch (error) {
            console.error('Refresh token error:', error);
            return false;
        }
    },
    
    redirectToLogin() {
        this.token = null;
        this.user = null;
        localStorage.removeItem('access_token');
        localStorage.removeItem('user');
        window.location.href = '/login';
    },
    
    getAuthHeaders() {
        return {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${this.token}`,
        };
    },
    
    isAuthenticated() {
        return !!(this.token && this.user);
    },
    
    isAdmin() {
        return this.user?.role === 'admin';
    }
};

// Initialize auth when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        console.log('DOM loaded, initializing AUTH...');
        AUTH.init();
    });
} else {
    console.log('DOM already loaded, initializing AUTH...');
    AUTH.init();
}

// Export for use in other scripts
window.AUTH = AUTH;

// Also try updating UI after a short delay to ensure DOM is fully ready
setTimeout(() => {
    if (AUTH.isAuthenticated() && document.getElementById('auth-section')) {
        console.log('Delayed UI update check...');
        AUTH.updateUI();
    }
}, 100);
