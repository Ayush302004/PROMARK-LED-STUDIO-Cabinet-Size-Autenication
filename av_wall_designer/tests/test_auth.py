"""Tests for authentication functionality."""
import unittest
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Set test database path BEFORE importing models
os.environ['DATABASE_PATH'] = ':memory:'

from auth.utils import (
    hash_password,
    verify_password,
    validate_password_strength,
    validate_email,
    generate_access_token,
    verify_access_token,
    generate_refresh_token,
    hash_refresh_token,
)
from auth.models import User, Session, initialize_database, get_db_connection
from config import Config


class PasswordHashingTests(unittest.TestCase):
    """Test password hashing and verification."""
    
    def test_password_hashing(self):
        """Test password can be hashed and verified."""
        password = "TestPass123"
        hashed = hash_password(password)
        
        self.assertIsInstance(hashed, str)
        self.assertGreater(len(hashed), 20)
        self.assertNotEqual(hashed, password)
    
    def test_password_verification_success(self):
        """Test correct password verification."""
        password = "TestPass123"
        hashed = hash_password(password)
        
        self.assertTrue(verify_password(password, hashed))
    
    def test_password_verification_failure(self):
        """Test incorrect password verification."""
        password = "TestPass123"
        hashed = hash_password(password)
        
        self.assertFalse(verify_password("WrongPass123", hashed))
    
    def test_password_strength_validation(self):
        """Test password strength requirements."""
        # Valid passwords
        validate_password_strength("Pass1234")
        validate_password_strength("SecureP4ssw0rd!")
        
        # Too short
        with self.assertRaises(ValueError):
            validate_password_strength("Pass1")
        
        # No letters
        with self.assertRaises(ValueError):
            validate_password_strength("12345678")
        
        # No numbers
        with self.assertRaises(ValueError):
            validate_password_strength("Password")


class EmailValidationTests(unittest.TestCase):
    """Test email validation."""
    
    def test_valid_emails(self):
        """Test valid email formats."""
        self.assertEqual(validate_email("test@example.com"), "test@example.com")
        self.assertEqual(validate_email("USER@EXAMPLE.COM"), "user@example.com")
        self.assertEqual(validate_email("  test@example.com  "), "test@example.com")
    
    def test_invalid_emails(self):
        """Test invalid email formats."""
        with self.assertRaises(ValueError):
            validate_email("notanemail")
        
        with self.assertRaises(ValueError):
            validate_email("@example.com")
        
        with self.assertRaises(ValueError):
            validate_email("test@")
        
        with self.assertRaises(ValueError):
            validate_email("")


class JWTTokenTests(unittest.TestCase):
    """Test JWT token generation and verification."""
    
    def test_generate_access_token(self):
        """Test access token generation."""
        token = generate_access_token(1, "test@example.com", "Test User", "user")
        
        self.assertIsInstance(token, str)
        self.assertGreater(len(token), 50)
    
    def test_verify_valid_token(self):
        """Test valid token verification."""
        token = generate_access_token(1, "test@example.com", "Test User", "user")
        payload = verify_access_token(token)
        
        self.assertIsNotNone(payload)
        self.assertEqual(payload['user_id'], 1)
        self.assertEqual(payload['email'], "test@example.com")
        self.assertEqual(payload['name'], "Test User")
        self.assertEqual(payload['role'], "user")
    
    def test_verify_invalid_token(self):
        """Test invalid token verification."""
        payload = verify_access_token("invalid.token.string")
        self.assertIsNone(payload)
    
    def test_verify_tampered_token(self):
        """Test tampered token verification."""
        token = generate_access_token(1, "test@example.com", "Test User", "user")
        tampered = token[:-5] + "xxxxx"
        
        payload = verify_access_token(tampered)
        self.assertIsNone(payload)


class RefreshTokenTests(unittest.TestCase):
    """Test refresh token generation and hashing."""
    
    def test_generate_refresh_token(self):
        """Test refresh token generation."""
        token1 = generate_refresh_token()
        token2 = generate_refresh_token()
        
        self.assertIsInstance(token1, str)
        self.assertGreater(len(token1), 30)
        self.assertNotEqual(token1, token2)  # Should be random
    
    def test_hash_refresh_token(self):
        """Test refresh token hashing."""
        token = generate_refresh_token()
        hashed1 = hash_refresh_token(token)
        hashed2 = hash_refresh_token(token)
        
        self.assertEqual(hashed1, hashed2)  # Deterministic
        self.assertEqual(len(hashed1), 64)  # SHA256 hex length
        self.assertNotEqual(hashed1, token)


class UserModelTests(unittest.TestCase):
    """Test User model database operations."""
    
    @classmethod
    def setUpClass(cls):
        """Initialize test database once."""
        initialize_database()
    
    def setUp(self):
        """Clear users before each test."""
        with get_db_connection() as conn:
            conn.execute("DELETE FROM users")
            conn.commit()
    
    def test_create_user(self):
        """Test user creation."""
        password_hash = hash_password("TestPass123")
        user_id = User.create("test@example.com", password_hash, "Test User", "user")
        
        self.assertIsInstance(user_id, int)
        self.assertGreater(user_id, 0)
    
    def test_create_duplicate_email(self):
        """Test duplicate email rejection."""
        password_hash = hash_password("TestPass123")
        User.create("test@example.com", password_hash, "Test User", "user")
        
        with self.assertRaises(ValueError) as cm:
            User.create("test@example.com", password_hash, "Another User", "user")
        
        self.assertIn("already registered", str(cm.exception))
    
    def test_create_admin(self):
        """Test admin user creation."""
        password_hash = hash_password("AdminPass123")
        user_id = User.create("admin@example.com", password_hash, "Admin User", "admin")
        
        user = User.get_by_id(user_id)
        self.assertEqual(user['role'], "admin")
    
    def test_get_by_id(self):
        """Test get user by ID."""
        password_hash = hash_password("TestPass123")
        user_id = User.create("test@example.com", password_hash, "Test User", "user")
        
        user = User.get_by_id(user_id)
        
        self.assertIsNotNone(user)
        self.assertEqual(user['email'], "test@example.com")
        self.assertEqual(user['name'], "Test User")
        self.assertEqual(user['role'], "user")
        self.assertNotIn('password_hash', user)
    
    def test_get_by_email(self):
        """Test get user by email."""
        password_hash = hash_password("TestPass123")
        User.create("test@example.com", password_hash, "Test User", "user")
        
        user = User.get_by_email("test@example.com")
        
        self.assertIsNotNone(user)
        self.assertEqual(user['email'], "test@example.com")
        self.assertIn('password_hash', user)
    
    def test_get_by_email_case_insensitive(self):
        """Test email lookup is case-insensitive."""
        password_hash = hash_password("TestPass123")
        User.create("test@example.com", password_hash, "Test User", "user")
        
        user = User.get_by_email("TEST@EXAMPLE.COM")
        self.assertIsNotNone(user)


class SessionModelTests(unittest.TestCase):
    """Test Session model database operations."""
    
    @classmethod
    def setUpClass(cls):
        """Initialize test database once."""
        initialize_database()
    
    def setUp(self):
        """Clear sessions and create test user before each test."""
        with get_db_connection() as conn:
            conn.execute("DELETE FROM sessions")
            conn.execute("DELETE FROM users")
            conn.commit()
        
        password_hash = hash_password("TestPass123")
        self.user_id = User.create("test@example.com", password_hash, "Test User", "user")
    
    def test_create_session(self):
        """Test session creation."""
        token = generate_refresh_token()
        session_id = Session.create(self.user_id, token, 3600)
        
        self.assertIsInstance(session_id, int)
        self.assertGreater(session_id, 0)
    
    def test_get_session_by_token(self):
        """Test get session by token."""
        token = generate_refresh_token()
        session_id = Session.create(self.user_id, token, 3600)
        
        session = Session.get_by_token(token)
        
        self.assertIsNotNone(session)
        self.assertEqual(session['id'], session_id)
        self.assertEqual(session['user_id'], self.user_id)
    
    def test_get_expired_session(self):
        """Test expired session returns None."""
        token = generate_refresh_token()
        Session.create(self.user_id, token, -1)  # Already expired
        
        session = Session.get_by_token(token)
        self.assertIsNone(session)
    
    def test_delete_session(self):
        """Test session deletion."""
        token = generate_refresh_token()
        session_id = Session.create(self.user_id, token, 3600)
        
        deleted = Session.delete(session_id)
        self.assertTrue(deleted)
        
        session = Session.get_by_token(token)
        self.assertIsNone(session)
    
    def test_delete_all_for_user(self):
        """Test delete all sessions for user."""
        token1 = generate_refresh_token()
        token2 = generate_refresh_token()
        Session.create(self.user_id, token1, 3600)
        Session.create(self.user_id, token2, 3600)
        
        count = Session.delete_all_for_user(self.user_id)
        self.assertEqual(count, 2)
        
        self.assertIsNone(Session.get_by_token(token1))
        self.assertIsNone(Session.get_by_token(token2))


if __name__ == '__main__':
    unittest.main()
