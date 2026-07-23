from gitscore.db.database import SessionLocal
from gitscore.db.models import User
from sqlalchemy import select
from datetime import datetime

def save_user(user_data):
    session = SessionLocal()
    statement = select(User).where(
    User.github_username == user_data["login"]
    )
    existing_user = session.scalar(statement)
    if existing_user:
        existing_user.collected_at = datetime.utcnow()
        existing_user.name = user_data["name"]
        existing_user.followers = user_data["followers"]
        existing_user.public_repos = user_data["public_repos"]
        user = existing_user
    else:
        user = User(
            github_username = user_data["login"],
            name= user_data["name"],
            followers= user_data["followers"],
            public_repos= user_data["public_repos"]
            )
        session.add(user) 
      
    session.commit()

    session.refresh(user)
    session.close()
    return user