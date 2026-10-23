"""Authentication API routes."""
from flask import Blueprint, request, jsonify, make_response, g
from datetime import datetime

from config import Config
from .utils import (
    hash_password,
    verify_password,
    validate_email,
    validate_password_strength,
    generate_access_token,
    generate_refresh_token,
)
from .models import User, Session
from .middleware import require_auth

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')


@auth_bp.route('/register', methods=['POST'])
def register():
    """
    Register a new user.
    
    Request body:
        {
            "email": "user@example.com",
            "password": "SecurePass123",
            "name": "John Doe"
        }
    
    Response:
        {
            "id": 1,
            "email": "user@example.com",
            "name": "John Doe",
            "role": "user",
            "created_at": "2026-10-23T..."
        }
    
    Security: Role is always 'user'. Admins must be created via bootstrap script.
    """
    data = request.get_json()
    
    if not isinstance(data, dict):
        return jsonify(error="Expected JSON object"), 400
    
    # Validate required fields
    email = data.get('email', '').strip()
    password = data.get('password', '')
    name = data.get('name', '').strip()
    
    if not email or not password or not name:
        return jsonify(error="Email, password, and name are required"), 400
    
    # Security check: Never allow role to be set via public registration
    if 'role' in data and data['role'] != 'user':
        return jsonify(error="Invalid request"), 400
    
    try:
        # Validate email format
        email = validate_email(email)
        
        # Validate password strength
        validate_password_strength(password)
        
        # Validate name
        if len(name) < 2 or len(name) > 100:
            return jsonify(error="Name must be between 2 and 100 characters"), 400
        
        # Hash password
        password_hash = hash_password(password)
        
        # Create user with role = 'user' (forced)
        user_id = User.create(email, password_hash, name, role='user')
        
        # Get created user
        user = User.get_by_id(user_id)
        
        # Remove password_hash from response
        user.pop('password_hash', None)
        
        return jsonify(user), 201
        
    except ValueError as e:
        return jsonify(error=str(e)), 400


@auth_bp.route('/login', methods=['POST'])
def login():
    """
    Login with email and password.
    
    Request body:
        {
            "email": "user@example.com",
            "password": "SecurePass123"
        }
    
    Response:
        {
            "access_token": "eyJ...",
            "user": {
                "id": 1,
                "email": "user@example.com",
                "name": "John Doe",
                "role": "user"
            }
        }
    
    Sets HttpOnly refresh token cookie.
    """
    data = request.get_json()
    
    if not isinstance(data, dict):
        return jsonify(error="Expected JSON object"), 400
    
    email = data.get('email', '').strip()
    password = data.get('password', '')
    
    if not email or not password:
        return jsonify(error="Email and password are required"), 400
    
    try:
        # Normalize email
        email = validate_email(email)
        
        # Get user by email
        user = User.get_by_email(email)
        
        if not user:
            return jsonify(error="Invalid email or password"), 401
        
        # Verify password
        if not verify_password(password, user['password_hash']):
            return jsonify(error="Invalid email or password"), 401
        
        # Generate tokens
        access_token = generate_access_token(
            user['id'],
            user['email'],
            user['name'],
            user['role']
        )
        
        refresh_token = generate_refresh_token()
        
        # Store refresh token session
        Session.create(user['id'], refresh_token, Config.REFRESH_TOKEN_EXPIRY)
        
        # Remove password hash from user object
        user.pop('password_hash', None)
        
        # Create response with refresh token cookie
        response = make_response(jsonify({
            'access_token': access_token,
            'user': user
        }))
        
        response.set_cookie(
            'refresh_token',
            refresh_token,
            max_age=Config.REFRESH_TOKEN_EXPIRY,
            httponly=True,
            secure=Config.SESSION_COOKIE_SECURE,
            samesite='Lax',
            path='/'
        )
        
        return response
        
    except ValueError as e:
        return jsonify(error=str(e)), 400


@auth_bp.route('/refresh', methods=['POST'])
def refresh():
    """
    Refresh access token using refresh token cookie.
    
    Response:
        {
            "access_token": "eyJ...",
            "user": {
                "id": 1,
                "email": "user@example.com",
                "name": "John Doe",
                "role": "user"
            }
        }
    
    Rotates refresh token for security.
    """
    # Get refresh token from cookie
    old_refresh_token = request.cookies.get('refresh_token')
    
    if not old_refresh_token:
        return jsonify(error="Refresh token required"), 401
    
    # Verify refresh token
    session = Session.get_by_token(old_refresh_token)
    
    if not session:
        return jsonify(error="Invalid or expired refresh token"), 401
    
    # Get user
    user = User.get_by_id(session['user_id'])
    
    if not user:
        return jsonify(error="User not found"), 401
    
    # Generate new access token
    access_token = generate_access_token(
        user['id'],
        user['email'],
        user['name'],
        user['role']
    )
    
    # Rotate refresh token for security
    new_refresh_token = generate_refresh_token()
    
    # Delete old session
    Session.delete(session['id'])
    
    # Create new session
    Session.create(user['id'], new_refresh_token, Config.REFRESH_TOKEN_EXPIRY)
    
    # Remove password hash
    user.pop('password_hash', None)
    
    # Create response with new refresh token cookie
    response = make_response(jsonify({
        'access_token': access_token,
        'user': user
    }))
    
    response.set_cookie(
        'refresh_token',
        new_refresh_token,
        max_age=Config.REFRESH_TOKEN_EXPIRY,
        httponly=True,
        secure=Config.SESSION_COOKIE_SECURE,
        samesite='Lax',
        path='/'
    )
    
    return response


@auth_bp.route('/logout', methods=['POST'])
@require_auth
def logout():
    """
    Logout current session.
    
    Requires valid access token.
    Deletes refresh token cookie and session.
    """
    # Get refresh token from cookie
    refresh_token = request.cookies.get('refresh_token')
    
    if refresh_token:
        # Delete session from database
        Session.delete_by_token(refresh_token)
    
    # Create response
    response = make_response(jsonify({'message': 'Logged out successfully'}))
    
    # Clear refresh token cookie
    response.set_cookie(
        'refresh_token',
        '',
        max_age=0,
        httponly=True,
        secure=Config.SESSION_COOKIE_SECURE,
        samesite='Lax',
        path='/'
    )
    
    return response


@auth_bp.route('/logout-all', methods=['POST'])
@require_auth
def logout_all():
    """
    Logout all sessions for current user.
    
    Requires valid access token.
    Deletes all sessions for the user.
    """
    # Delete all sessions for this user
    count = Session.delete_all_for_user(g.user_id)
    
    # Create response
    response = make_response(jsonify({
        'message': f'Logged out from {count} session(s)'
    }))
    
    # Clear refresh token cookie
    response.set_cookie(
        'refresh_token',
        '',
        max_age=0,
        httponly=True,
        secure=Config.SESSION_COOKIE_SECURE,
        samesite='Lax',
        path='/'
    )
    
    return response


@auth_bp.route('/me', methods=['GET'])
@require_auth
def get_current_user():
    """
    Get current authenticated user's profile.
    
    Requires valid access token.
    
    Response:
        {
            "id": 1,
            "email": "user@example.com",
            "name": "John Doe",
            "role": "user",
            "created_at": "2026-10-23T...",
            "updated_at": "2026-10-23T..."
        }
    """
    user = g.user.copy()
    user.pop('password_hash', None)
    return jsonify(user)
