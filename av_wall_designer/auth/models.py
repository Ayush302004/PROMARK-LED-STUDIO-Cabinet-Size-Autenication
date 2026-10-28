"""Database models for users, sessions, and projects using MongoDB."""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError
from bson import ObjectId

from config import Config
from .utils import hash_refresh_token


# MongoDB client (singleton)
_client = None
_db = None


def get_db():
    """Get MongoDB database instance."""
    global _client, _db
    if _db is None:
        _client = MongoClient(Config.MONGODB_URI)
        _db = _client[Config.MONGODB_DB_NAME]
    return _db


class User:
    """User model for authentication and authorization."""
    
    collection_name = 'users'
    
    @staticmethod
    def ensure_indexes():
        """Create database indexes."""
        db = get_db()
        db[User.collection_name].create_index([('email', ASCENDING)], unique=True)
        db[User.collection_name].create_index([('role', ASCENDING)])
    
    @staticmethod
    def create(email: str, password_hash: str, name: str, role: str = 'user') -> str:
        """
        Create a new user.
        
        Returns:
            User ID (string)
        
        Raises:
            ValueError: If email already exists or role invalid
        """
        if role not in ('user', 'admin'):
            raise ValueError("Role must be 'user' or 'admin'")
        
        db = get_db()
        user_doc = {
            'email': email.lower().strip(),
            'password_hash': password_hash,
            'name': name.strip(),
            'role': role,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }
        
        try:
            result = db[User.collection_name].insert_one(user_doc)
            return str(result.inserted_id)
        except DuplicateKeyError:
            raise ValueError("Email already registered")
    
    @staticmethod
    def get_by_id(user_id: str) -> Optional[Dict[str, Any]]:
        """Get user by ID."""
        db = get_db()
        try:
            user = db[User.collection_name].find_one(
                {'_id': ObjectId(user_id)},
                {'password_hash': 0}  # Exclude password hash
            )
            if user:
                user['id'] = str(user.pop('_id'))
                return user
            return None
        except:
            return None
    
    @staticmethod
    def get_by_email(email: str, include_password: bool = True) -> Optional[Dict[str, Any]]:
        """Get user by email."""
        db = get_db()
        projection = {} if include_password else {'password_hash': 0}
        user = db[User.collection_name].find_one(
            {'email': email.lower().strip()},
            projection
        )
        if user:
            user['id'] = str(user.pop('_id'))
            return user
        return None
    
    @staticmethod
    def get_all(limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Get all users with pagination."""
        db = get_db()
        
        # Get users with project count
        pipeline = [
            {
                '$lookup': {
                    'from': 'projects',
                    'let': {'user_id': {'$toString': '$_id'}},
                    'pipeline': [
                        {'$match': {'$expr': {'$eq': ['$user_id', '$$user_id']}}}
                    ],
                    'as': 'projects'
                }
            },
            {
                '$project': {
                    'email': 1,
                    'name': 1,
                    'role': 1,
                    'created_at': 1,
                    'project_count': {'$size': '$projects'}
                }
            },
            {'$sort': {'created_at': DESCENDING}},
            {'$skip': offset},
            {'$limit': limit}
        ]
        
        users = []
        for user in db[User.collection_name].aggregate(pipeline):
            user['id'] = str(user.pop('_id'))
            users.append(user)
        
        return users
    
    @staticmethod
    def count() -> int:
        """Get total user count."""
        db = get_db()
        return db[User.collection_name].count_documents({})
    
    @staticmethod
    def exists_with_role(role: str) -> bool:
        """Check if any user exists with given role."""
        db = get_db()
        return db[User.collection_name].count_documents({'role': role}) > 0


class Session:
    """Session model for refresh token management."""
    
    collection_name = 'sessions'
    
    @staticmethod
    def ensure_indexes():
        """Create database indexes."""
        db = get_db()
        db[Session.collection_name].create_index([('token_hash', ASCENDING)], unique=True)
        db[Session.collection_name].create_index([('user_id', ASCENDING)])
        db[Session.collection_name].create_index([('expires_at', ASCENDING)])
    
    @staticmethod
    def create(user_id: str, token: str, expires_in_seconds: int) -> str:
        """
        Create a new session.
        
        Returns:
            Session ID (string)
        """
        db = get_db()
        token_hash = hash_refresh_token(token)
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in_seconds)
        
        session_doc = {
            'user_id': user_id,
            'token_hash': token_hash,
            'expires_at': expires_at,
            'created_at': datetime.utcnow()
        }
        
        result = db[Session.collection_name].insert_one(session_doc)
        return str(result.inserted_id)
    
    @staticmethod
    def get_by_token(token: str) -> Optional[Dict[str, Any]]:
        """Get valid session by token."""
        db = get_db()
        token_hash = hash_refresh_token(token)
        
        session = db[Session.collection_name].find_one({
            'token_hash': token_hash,
            'expires_at': {'$gt': datetime.utcnow()}
        })
        
        if session:
            session['id'] = str(session.pop('_id'))
            return session
        return None
    
    @staticmethod
    def delete(session_id: str) -> bool:
        """Delete a session."""
        db = get_db()
        try:
            result = db[Session.collection_name].delete_one({'_id': ObjectId(session_id)})
            return result.deleted_count > 0
        except:
            return False
    
    @staticmethod
    def delete_by_token(token: str) -> bool:
        """Delete session by token."""
        db = get_db()
        token_hash = hash_refresh_token(token)
        result = db[Session.collection_name].delete_one({'token_hash': token_hash})
        return result.deleted_count > 0
    
    @staticmethod
    def delete_all_for_user(user_id: str) -> int:
        """Delete all sessions for a user."""
        db = get_db()
        result = db[Session.collection_name].delete_many({'user_id': user_id})
        return result.deleted_count
    
    @staticmethod
    def cleanup_expired() -> int:
        """Delete expired sessions."""
        db = get_db()
        result = db[Session.collection_name].delete_many({
            'expires_at': {'$lte': datetime.utcnow()}
        })
        return result.deleted_count


class Project:
    """Project model for LED wall designs."""
    
    collection_name = 'projects'
    
    @staticmethod
    def ensure_indexes():
        """Create database indexes."""
        db = get_db()
        db[Project.collection_name].create_index([('user_id', ASCENDING)])
        db[Project.collection_name].create_index([('created_at', DESCENDING)])
        db[Project.collection_name].create_index([('updated_at', DESCENDING)])
    
    @staticmethod
    def create(user_id: str, name: str, payload: Dict[str, Any]) -> str:
        """
        Create a new project.
        
        Returns:
            Project ID (string)
        """
        db = get_db()
        project_doc = {
            'user_id': user_id,
            'name': name,
            'payload': payload,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }
        
        result = db[Project.collection_name].insert_one(project_doc)
        return str(result.inserted_id)
    
    @staticmethod
    def get_by_id(project_id: str, user_id: str = None) -> Optional[Dict[str, Any]]:
        """Get project by ID (with optional ownership check)."""
        db = get_db()
        try:
            query = {'_id': ObjectId(project_id)}
            if user_id:
                query['user_id'] = user_id
            
            project = db[Project.collection_name].find_one(query)
            if project:
                project['id'] = str(project.pop('_id'))
                return project
            return None
        except:
            return None
    
    @staticmethod
    def get_by_user(user_id: str, limit: int = 100, offset: int = 0) -> tuple:
        """
        Get projects for a user.
        
        Returns:
            (projects_list, total_count)
        """
        db = get_db()
        query = {'user_id': user_id}
        
        total = db[Project.collection_name].count_documents(query)
        
        projects = []
        cursor = db[Project.collection_name].find(
            query,
            {'payload': 0}  # Exclude large payload from list
        ).sort('updated_at', DESCENDING).skip(offset).limit(limit)
        
        for project in cursor:
            project['id'] = str(project.pop('_id'))
            projects.append(project)
        
        return projects, total
    
    @staticmethod
    def update(project_id: str, user_id: str, name: str, payload: Dict[str, Any]) -> bool:
        """Update a project (with ownership check)."""
        db = get_db()
        try:
            result = db[Project.collection_name].update_one(
                {'_id': ObjectId(project_id), 'user_id': user_id},
                {
                    '$set': {
                        'name': name,
                        'payload': payload,
                        'updated_at': datetime.utcnow()
                    }
                }
            )
            return result.modified_count > 0
        except:
            return False
    
    @staticmethod
    def delete(project_id: str, user_id: str) -> bool:
        """Delete a project (with ownership check)."""
        db = get_db()
        try:
            result = db[Project.collection_name].delete_one({
                '_id': ObjectId(project_id),
                'user_id': user_id
            })
            return result.deleted_count > 0
        except:
            return False
    
    @staticmethod
    def get_all_with_owners(limit: int = 100, offset: int = 0, user_id: str = None) -> tuple:
        """
        Get all projects with owner information (admin only).
        
        Returns:
            (projects_list, total_count)
        """
        db = get_db()
        
        # Build query
        match_stage = {}
        if user_id:
            match_stage = {'user_id': user_id}
        
        # Count total
        total = db[Project.collection_name].count_documents(match_stage)
        
        # Aggregation pipeline to join with users
        pipeline = []
        if match_stage:
            pipeline.append({'$match': match_stage})
        
        pipeline.extend([
            {
                '$lookup': {
                    'from': 'users',
                    'let': {'user_id_str': '$user_id'},
                    'pipeline': [
                        {
                            '$match': {
                                '$expr': {
                                    '$eq': [{'$toString': '$_id'}, '$$user_id_str']
                                }
                            }
                        },
                        {'$project': {'email': 1, 'name': 1}}
                    ],
                    'as': 'owner'
                }
            },
            {
                '$project': {
                    'name': 1,
                    'user_id': 1,
                    'created_at': 1,
                    'updated_at': 1,
                    'payload': 1,  # Include payload for admin dashboard
                    'owner_id': '$user_id',
                    'owner_email': {'$arrayElemAt': ['$owner.email', 0]},
                    'owner_name': {'$arrayElemAt': ['$owner.name', 0]}
                }
            },
            {'$sort': {'updated_at': DESCENDING}},
            {'$skip': offset},
            {'$limit': limit}
        ])
        
        projects = []
        for project in db[Project.collection_name].aggregate(pipeline):
            project['id'] = str(project.pop('_id'))
            projects.append(project)
        
        return projects, total
    
    @staticmethod
    def count() -> int:
        """Get total project count."""
        db = get_db()
        return db[Project.collection_name].count_documents({})


def initialize_database():
    """Initialize database with indexes."""
    User.ensure_indexes()
    Session.ensure_indexes()
    Project.ensure_indexes()
    print("[OK] MongoDB indexes created")
