/**
 * Admin Dashboard Module
 * Shows all users, their projects, and statistics
 */

const AdminDashboard = {
    async init() {
        console.log('AdminDashboard: Initializing...');
        
        // Wait for AUTH to be ready
        if (!window.AUTH) {
            console.log('AdminDashboard: AUTH not ready, waiting...');
            return;
        }
        
        console.log('AdminDashboard: AUTH ready, checking role...');
        console.log('AdminDashboard: User:', window.AUTH.user);
        console.log('AdminDashboard: Is Admin:', window.AUTH.isAdmin());
        
        const adminBtn = document.getElementById('admin-dashboard-btn');
        
        // Check if user is admin
        if (!window.AUTH.isAdmin()) {
            console.log('AdminDashboard: User is NOT admin, hiding button');
            if (adminBtn) {
                adminBtn.style.cssText = 'display: none !important;';
                adminBtn.remove(); // Completely remove from DOM for non-admins
            }
            return;
        }
        
        console.log('AdminDashboard: User IS admin, showing button');
        
        // Show admin dashboard button in sidebar for admins only
        if (adminBtn) {
            adminBtn.style.cssText = 'display: flex !important;';
            console.log('AdminDashboard: Button displayed');
        } else {
            console.error('AdminDashboard: Button not found in DOM');
        }
        
        // Setup event listeners
        this.setupEventListeners();
    },
    
    setupEventListeners() {
        const adminBtn = document.getElementById('admin-dashboard-btn');
        if (adminBtn) {
            adminBtn.addEventListener('click', () => this.loadDashboard());
        }
        
        // Refresh button
        const refreshBtn = document.getElementById('admin-refresh-btn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.loadDashboard());
        }
    },
    
    async loadDashboard() {
        const container = document.getElementById('admin-dashboard-content');
        if (!container) return;
        
        container.innerHTML = '<div class="loading-spinner">Loading admin dashboard...</div>';
        
        try {
            // Fetch dashboard data
            const [stats, usersData, projectsData] = await Promise.all([
                this.fetchStats(),
                this.fetchUsers(),
                this.fetchAllProjects()
            ]);
            
            // Render dashboard
            this.renderDashboard(stats, usersData.users, projectsData.projects);
        } catch (error) {
            console.error('Failed to load admin dashboard:', error);
            container.innerHTML = `<div class="error-message">Failed to load dashboard: ${error.message}</div>`;
        }
    },
    
    async fetchStats() {
        if (!window.AUTH || !window.AUTH.getAuthHeaders) {
            throw new Error('AUTH not initialized');
        }
        
        const response = await fetch('/api/admin/dashboard', {
            headers: window.AUTH.getAuthHeaders()
        });
        
        if (!response.ok) {
            const error = await response.text();
            throw new Error(`Failed to fetch stats: ${response.status} - ${error}`);
        }
        
        return await response.json();
    },
    
    async fetchUsers() {
        if (!window.AUTH || !window.AUTH.getAuthHeaders) {
            throw new Error('AUTH not initialized');
        }
        
        const response = await fetch('/api/admin/users?limit=100', {
            headers: window.AUTH.getAuthHeaders()
        });
        
        if (!response.ok) {
            const error = await response.text();
            throw new Error(`Failed to fetch users: ${response.status} - ${error}`);
        }
        
        return await response.json();
    },
    
    async fetchAllProjects() {
        if (!window.AUTH || !window.AUTH.getAuthHeaders) {
            throw new Error('AUTH not initialized');
        }
        
        const response = await fetch('/api/admin/projects?limit=100', {
            headers: window.AUTH.getAuthHeaders()
        });
        
        if (!response.ok) {
            const error = await response.text();
            throw new Error(`Failed to fetch projects: ${response.status} - ${error}`);
        }
        
        return await response.json();
    },
    
    renderDashboard(stats, users, projects) {
        const container = document.getElementById('admin-dashboard-content');
        if (!container) return;
        
        // Group projects by user
        const projectsByUser = {};
        projects.forEach(project => {
            const userId = project.user_id;
            if (!projectsByUser[userId]) {
                projectsByUser[userId] = [];
            }
            projectsByUser[userId].push(project);
        });
        
        const html = `
            <div class="admin-dashboard">
                <div class="admin-header">
                    <div>
                        <h2>Admin Dashboard</h2>
                        <p class="hint">Overview of all users and their projects</p>
                    </div>
                    <button class="quiet" id="admin-refresh-btn">↻ Refresh</button>
                </div>
                
                <div class="admin-stats">
                    <div class="stat-card">
                        <span class="stat-label">Total Users</span>
                        <span class="stat-value">${stats.stats.total_users}</span>
                    </div>
                    <div class="stat-card">
                        <span class="stat-label">Total Projects</span>
                        <span class="stat-value">${stats.stats.total_projects}</span>
                    </div>
                    <div class="stat-card">
                        <span class="stat-label">Avg Projects/User</span>
                        <span class="stat-value">${(stats.stats.total_projects / stats.stats.total_users || 0).toFixed(1)}</span>
                    </div>
                </div>
                
                <div class="admin-users-section">
                    <h3>Users & Their Projects</h3>
                    ${this.renderUsersList(users, projectsByUser)}
                </div>
            </div>
        `;
        
        container.innerHTML = html;
        
        // Re-attach event listeners
        this.setupEventListeners();
        this.setupUserAccordions();
    },
    
    renderUsersList(users, projectsByUser) {
        return `
            <div class="users-list">
                ${users.map(user => this.renderUserCard(user, projectsByUser[user.id] || [])).join('')}
            </div>
        `;
    },
    
    renderUserCard(user, userProjects) {
        const roleClass = user.role === 'admin' ? 'role-admin' : 'role-user';
        
        return `
            <div class="user-card" data-user-id="${user.id}">
                <div class="user-header">
                    <div class="user-info">
                        <div class="user-name">
                            ${this.escapeHtml(user.name)}
                            ${user.role === 'admin' ? '<span class="badge-admin">👑 Admin</span>' : ''}
                        </div>
                        <div class="user-email">${this.escapeHtml(user.email)}</div>
                        <div class="user-meta">
                            <span>Joined: ${this.formatDate(user.created_at)}</span>
                            <span>•</span>
                            <span>${userProjects.length} project${userProjects.length !== 1 ? 's' : ''}</span>
                        </div>
                    </div>
                    <button class="toggle-projects" data-user-id="${user.id}">
                        ${userProjects.length > 0 ? '▼ Show Projects' : '○ No Projects'}
                    </button>
                </div>
                <div class="user-projects" id="projects-${user.id}" style="display: none;">
                    ${userProjects.length > 0 ? this.renderProjectsList(userProjects) : '<p class="no-projects">No projects yet</p>'}
                </div>
            </div>
        `;
    },
    
    renderProjectsList(projects) {
        return `
            <div class="projects-list">
                ${projects.map(project => this.renderProjectItem(project)).join('')}
            </div>
        `;
    },
    
    renderProjectItem(project) {
        const payload = project.payload || {};
        const product = payload.product || {};
        
        return `
            <div class="project-item clickable-project" data-project-id="${project.id}" data-user-id="${project.user_id}">
                <div class="project-header">
                    <strong>${this.escapeHtml(project.name)}</strong>
                    <small>${this.formatDate(project.created_at)}</small>
                </div>
                <div class="project-details">
                    <div class="project-info-grid">
                        <div class="info-item">
                            <span class="info-label">Cabinet Model:</span>
                            <span class="info-value">${this.escapeHtml(product.name || 'N/A')}</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">Environment:</span>
                            <span class="info-value">${this.escapeHtml(payload.environment || 'N/A')}</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">Screen Size:</span>
                            <span class="info-value">${payload.screen_width || 'N/A'} × ${payload.screen_height || 'N/A'} ${payload.unit || 'ft'}</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">Installation:</span>
                            <span class="info-value">${this.escapeHtml(payload.installation || 'N/A')}</span>
                        </div>
                    </div>
                    ${payload.quotation ? `
                        <div class="quotation-info">
                            <strong>Quotation Details:</strong>
                            <div class="quotation-grid">
                                <span>Client: ${this.escapeHtml(payload.quotation.client || 'N/A')}</span>
                                <span>Salesperson: ${this.escapeHtml(payload.quotation.salesperson || 'N/A')}</span>
                                <span>Contact: ${this.escapeHtml(payload.quotation.contact || 'N/A')}</span>
                            </div>
                        </div>
                    ` : ''}
                    <button class="open-project-btn" onclick="AdminDashboard.openProject('${project.id}')">
                        Open Project →
                    </button>
                </div>
            </div>
        `;
    },
    
    setupUserAccordions() {
        document.querySelectorAll('.toggle-projects').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const userId = e.target.dataset.userId;
                const projectsDiv = document.getElementById(`projects-${userId}`);
                
                if (projectsDiv) {
                    const isHidden = projectsDiv.style.display === 'none';
                    projectsDiv.style.display = isHidden ? 'block' : 'none';
                    e.target.textContent = isHidden ? '▲ Hide Projects' : '▼ Show Projects';
                }
            });
        });
    },
    
    async openProject(projectId) {
        try {
            console.log('Opening project:', projectId);
            
            // Fetch project data
            const response = await fetch(`/api/admin/projects/${projectId}`, {
                headers: window.AUTH.getAuthHeaders()
            });
            
            if (!response.ok) {
                throw new Error('Failed to load project');
            }
            
            const project = await response.json();
            console.log('Project loaded:', project);
            
            // Switch to designer workspace
            const designBtn = document.querySelector('[data-workspace="design"]');
            if (designBtn) {
                designBtn.click();
            }
            
            // Use the global restore function from app.js if available
            if (typeof window.restore === 'function') {
                window.restore(project.payload || project);
            } else {
                // Fallback: manually set state
                if (window.loadState && typeof window.loadState === 'function') {
                    window.loadState(project.payload || project);
                } else {
                    alert('Project loaded. Please refresh the designer to see changes.');
                }
            }
            
            // Show success message
            if (window.message && typeof window.message === 'function') {
                window.message(`Project "${project.name}" loaded`);
            }
            
        } catch (error) {
            console.error('Failed to open project:', error);
            alert('Failed to open project: ' + error.message);
        }
    },
    
    formatDate(dateString) {
        if (!dateString) return 'N/A';
        const date = new Date(dateString);
        return date.toLocaleDateString('en-IN', { 
            year: 'numeric', 
            month: 'short', 
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    },
    
    escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }
};

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        // Wait for AUTH to initialize first
        setTimeout(() => {
            console.log('AdminDashboard: DOM ready, initializing...');
            AdminDashboard.init();
        }, 1000); // Wait 1 second for AUTH
    });
} else {
    setTimeout(() => {
        console.log('AdminDashboard: Page already loaded, initializing...');
        AdminDashboard.init();
    }, 1000);
}

// Export for use in other scripts
window.AdminDashboard = AdminDashboard;
