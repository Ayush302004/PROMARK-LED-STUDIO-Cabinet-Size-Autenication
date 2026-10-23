"""Authentication and authorization middleware decorators."""
from functools import wraps
from flask import request, jsonify, g

from .utils import extract_bearer_token, verify_access_token
from .models import User


def require_auth(f):
    """
    Decorator to require valid authentication for a route.
    
    Sets g.user_id, g.user_role, g.user for use in route handlers.
    Returns 401 if authentication is missing or invalid.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Extract token from Authorization header
        token = extract_bearer_token(request)
        
        if not token:
            return jsonify(error="Authentication required"), 401
        
        # Verify token
        payload = verify_access_token(token)
        
        if not payload:
            return jsonify(error="Invalid or expired token"), 401
        
        # Verify user still exists and hasn't been deleted/disabled
        user = User.get_by_id(payload['user_id'])
        
        if not user:
            return jsonify(error="User not found"), 401
        
        # Set request context
        g.user_id = payload['user_id']
        g.user_role = payload['role']
        g.user_email = payload['email']
        g.user = user
        
        return f(*args, **kwargs)
    
    return decorated_function


def require_admin(f):
    """
    Decorator to require admin role for a route.
    
    Must be used with @require_auth or equivalent.
    Returns 403 if user is not an admin.
    """
    @wraps(f)
    @require_auth
    def decorated_function(*args, **kwargs):
        if g.user_role != 'admin':
            return jsonify(error="Admin access required"), 403
        
        return f(*args, **kwargs)
    
    return decorated_function


def optional_auth(f):
    """
    Decorator for routes that work with or without authentication.
    
    Sets g.user_id, g.user_role, g.user if authenticated, otherwise None.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Extract token
        token = extract_bearer_token(request)
        
        if token:
            payload = verify_access_token(token)
            if payload:
                user = User.get_by_id(payload['user_id'])
                if user:
                    g.user_id = payload['user_id']
                    g.user_role = payload['role']
                    g.user_email = payload['email']
                    g.user = user
                    return f(*args, **kwargs)
        
        # Not authenticated
        g.user_id = None
        g.user_role = None
        g.user_email = None
        g.user = None
        
        return f(*args, **kwargs)
    
    return decorated_function
