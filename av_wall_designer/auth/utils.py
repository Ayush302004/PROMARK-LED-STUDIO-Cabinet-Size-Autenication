"""Authentication utilities: password hashing, JWT generation, token validation."""
import hashlib
import secrets
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

import jwt

# Try argon2, fall back to bcrypt
try:
    from argon2 import PasswordHasher
    from argon2.exceptions import VerifyMismatchError, InvalidHashError
    HASHER = PasswordHasher()
    USE_ARGON2 = True
except ImportError:
    import bcrypt
    USE_ARGON2 = False

from config import Config


def hash_password(password: str) -> str:
    """
    Hash a password using Argon2id (preferred) or bcrypt (fallback).
    
    Args:
        password: Plain text password
        
    Returns:
        Password hash string
        
    Raises:
        ValueError: If password is too short or weak
    """
    validate_password_strength(password)
    
    if USE_ARGON2:
        return HASHER.hash(password)
    else:
        # bcrypt with 12 rounds
        salt = bcrypt.gensalt(rounds=12)
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def verify_password(password: str, password_hash: str) -> bool:
    """
    Verify a password against its hash.
    
    Args:
        password: Plain text password to verify
        password_hash: Stored password hash
        
    Returns:
        True if password matches, False otherwise
    """
    try:
        if USE_ARGON2:
            HASHER.verify(password_hash, password)
            return True
        else:
            return bcrypt.checkpw(
                password.encode('utf-8'),
                password_hash.encode('utf-8')
            )
    except (VerifyMismatchError, InvalidHashError, ValueError):
        return False


def validate_password_strength(password: str) -> None:
    """
    Validate password meets minimum strength requirements.
    
    Requirements:
    - At least 8 characters
    - Contains at least one letter
    - Contains at least one number
    
    Args:
        password: Password to validate
        
    Raises:
        ValueError: If password doesn't meet requirements
    """
    if not password or len(password) < 8:
        raise ValueError("Password must be at least 8 characters long")
    
    if not re.search(r'[a-zA-Z]', password):
        raise ValueError("Password must contain at least one letter")
    
    if not re.search(r'\d', password):
        raise ValueError("Password must contain at least one number")


def validate_email(email: str) -> str:
    """
    Validate and normalize email address.
    
    Args:
        email: Email address to validate
        
    Returns:
        Normalized email (lowercase, stripped)
        
    Raises:
        ValueError: If email format is invalid
    """
    if not email or not isinstance(email, str):
        raise ValueError("Email is required")
    
    email = email.strip().lower()
    
    # Basic email validation
    pattern = r'^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$'
    if not re.match(pattern, email):
        raise ValueError("Invalid email format")
    
    return email


def generate_access_token(user_id: int, email: str, name: str, role: str) -> str:
    """
    Generate a JWT access token.
    
    Args:
        user_id: User's database ID
        email: User's email
        name: User's name
        role: User's role (user or admin)
        
    Returns:
        JWT access token string
    """
    now = datetime.utcnow()
    payload = {
        'user_id': user_id,
        'email': email,
        'name': name,
        'role': role,
        'iat': now,
        'exp': now + timedelta(seconds=Config.ACCESS_TOKEN_EXPIRY)
    }
    
    return jwt.encode(payload, Config.SECRET_KEY, algorithm='HS256')


def verify_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Verify and decode a JWT access token.
    
    Args:
        token: JWT access token string
        
    Returns:
        Decoded token payload dict, or None if invalid
    """
    try:
        payload = jwt.decode(
            token,
            Config.SECRET_KEY,
            algorithms=['HS256'],
            options={
                'verify_signature': True,
                'verify_exp': True,
                'require': ['user_id', 'email', 'role', 'exp']
            }
        )
        return payload
    except jwt.ExpiredSignatureError:
        return None  # Token expired
    except jwt.InvalidTokenError:
        return None  # Invalid token


def generate_refresh_token() -> str:
    """
    Generate a cryptographically secure random refresh token.
    
    Returns:
        URL-safe base64-encoded random token (32 bytes)
    """
    return secrets.token_urlsafe(32)


def hash_refresh_token(token: str) -> str:
    """
    Hash a refresh token for storage in database.
    
    Args:
        token: Plain text refresh token
        
    Returns:
        SHA256 hash of the token
    """
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def extract_bearer_token(request) -> Optional[str]:
    """
    Extract Bearer token from Authorization header.
    
    Args:
        request: Flask request object
        
    Returns:
        Token string, or None if not present or invalid format
    """
    auth_header = request.headers.get('Authorization', '')
    
    if not auth_header.startswith('Bearer '):
        return None
    
    return auth_header[7:].strip()  # Remove "Bearer " prefix
