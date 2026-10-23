"""Create first administrator account for LED Wall Designer."""
import sys
import getpass
from config import Config
from auth.models import User, initialize_database
from auth.utils import hash_password, validate_email, validate_password_strength


def create_admin(email: str, password: str, name: str) -> bool:
    """Create an admin user."""
    try:
        email = validate_email(email)
        validate_password_strength(password)
        
        if len(name.strip()) < 2:
            print("✗ Name must be at least 2 characters")
            return False
        
        if User.exists_with_role('admin'):
            print("✗ An administrator already exists")
            print("  Create additional admins by updating MongoDB directly")
            return False
        
        password_hash = hash_password(password)
        user_id = User.create(email, password_hash, name, role='admin')
        
        print()
        print("=" * 60)
        print("✓ Administrator created successfully!")
        print("=" * 60)
        print(f"  ID:    {user_id}")
        print(f"  Email: {email}")
        print(f"  Name:  {name}")
        print(f"  Role:  admin")
        print()
        return True
        
    except ValueError as e:
        print(f"✗ Error: {e}")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def main():
    print("=" * 60)
    print("LED Wall Designer - Administrator Setup")
    print("=" * 60)
    print()
    
    # Initialize MongoDB
    initialize_database()
    
    # Check for environment variables
    if Config.ADMIN_EMAIL and Config.ADMIN_PASSWORD and Config.ADMIN_NAME:
        print("Creating admin from environment variables...")
        return create_admin(Config.ADMIN_EMAIL, Config.ADMIN_PASSWORD, Config.ADMIN_NAME)
    
    # Check command line arguments
    if len(sys.argv) == 4:
        return create_admin(sys.argv[1], sys.argv[2], sys.argv[3])
    
    # Interactive mode
    if User.exists_with_role('admin'):
        print("✗ An administrator already exists")
        return False
    
    print("Create the first administrator account:")
    print()
    
    email = input("Email: ").strip()
    name = input("Name: ").strip()
    
    while True:
        password = getpass.getpass("Password (min 8 chars, letter + number): ")
        password_confirm = getpass.getpass("Confirm password: ")
        
        if password != password_confirm:
            print("✗ Passwords don't match. Try again.\n")
            continue
        break
    
    print()
    return create_admin(email, password, name)


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
