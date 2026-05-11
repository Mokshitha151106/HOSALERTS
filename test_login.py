# test_login.py
from app import app, db
from database import User

def test_user(username, password, user_type):
    with app.app_context():
        user = User.query.filter_by(username=username, user_type=user_type).first()
        if user:
            print(f"✓ User {username} found")
            print(f"  - Stored password: '{user.password}'")
            print(f"  - Input password: '{password}'")
            print(f"  - Match: {user.password == password}")
        else:
            print(f"✗ User {username} not found")

# Test all credentials
test_user("nurse_smith", "nurse123", "nurse")
test_user("nurse_jones", "nurse123", "nurse")
test_user("nurse_admin", "admin123", "nurse")
test_user("john_son", "family123", "family")
test_user("jane_daughter", "family123", "family")
