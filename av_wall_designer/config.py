"""Application configuration management."""
import os
import secrets

class Config:
    """Application configuration loaded from environment variables."""
    
    # Security
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-CHANGE-IN-PRODUCTION')
    
    # MongoDB Database
    MONGODB_URI = os.environ.get('MONGODB_URI', 'mongodb://localhost:27017/')
    MONGODB_DB_NAME = os.environ.get('MONGODB_DB_NAME', 'led_wall_designer')
    
    # Flask environment
    FLASK_ENV = os.environ.get('FLASK_ENV', 'development')
    
    # Cookie security
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'False').lower() in ('true', '1', 'yes')
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Token expiry
    ACCESS_TOKEN_EXPIRY = int(os.environ.get('ACCESS_TOKEN_EXPIRY', '900'))  # 15 minutes
    REFRESH_TOKEN_EXPIRY = int(os.environ.get('REFRESH_TOKEN_EXPIRY', '2592000'))  # 30 days
    
    # Rate limiting
    RATE_LIMIT_LOGIN = int(os.environ.get('RATE_LIMIT_LOGIN', '5'))
    RATE_LIMIT_REGISTER = int(os.environ.get('RATE_LIMIT_REGISTER', '3'))
    RATE_LIMIT_REFRESH = int(os.environ.get('RATE_LIMIT_REFRESH', '10'))
    RATE_LIMIT_API = int(os.environ.get('RATE_LIMIT_API', '100'))
    
    # Admin bootstrap
    ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', '').strip()
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', '').strip()
    ADMIN_NAME = os.environ.get('ADMIN_NAME', '').strip()
    
    @staticmethod
    def validate():
        """Validate production configuration."""
        if Config.FLASK_ENV == 'production':
            if Config.SECRET_KEY == 'dev-secret-CHANGE-IN-PRODUCTION':
                raise RuntimeError(
                    "SECRET_KEY must be set to a secure random value in production. "
                    "Generate: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
                )
            if not Config.SESSION_COOKIE_SECURE:
                raise RuntimeError("SESSION_COOKIE_SECURE must be True in production (requires HTTPS)")
            if Config.MONGODB_URI == 'mongodb://localhost:27017/':
                print("WARNING: Using local MongoDB in production. Set MONGODB_URI for production database.")
        
        # Validate token expiry
        if not (60 <= Config.ACCESS_TOKEN_EXPIRY <= 3600):
            raise ValueError("ACCESS_TOKEN_EXPIRY must be between 60 and 3600 seconds")
        if not (3600 <= Config.REFRESH_TOKEN_EXPIRY <= 7776000):
            raise ValueError("REFRESH_TOKEN_EXPIRY must be between 3600 and 7776000 seconds")
    
    @staticmethod
    def generate_secret_key():
        """Generate a secure random secret key."""
        return secrets.token_urlsafe(32)


# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
