import os
from app import app, db, User

def promote_to_admin(email):
    with app.app_context():
        user = User.query.filter_by(email=email).first()
        if not user:
            print(f"❌ User with email '{email}' not found in database.")
            return
        
        user.is_admin = True
        db.session.commit()
        print(f"✅ Successfully promoted '{email}' to ADMIN.")

if __name__ == "__main__":
    email = input("Enter user email to promote to ADMIN: ").strip()
    if email:
        promote_to_admin(email)
    else:
        print("❌ No email provided.")
