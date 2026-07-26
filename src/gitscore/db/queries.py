from gitscore.db.database import SessionLocal
from gitscore.db.models import User, ProfileFeature
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

def save_profile_features(user_id, features):
    session = SessionLocal()
    profile_feature = ProfileFeature(
        user_id = user_id,
        total_repos = features["total_repos"],
        original_repos = features["original_repos"],
        forked_repos = features["forked_repos"],
        unique_language_count = features["unique_language_count"],
        ml_repository_count = features["ml_repository_count"],
        readme_coverage_ratio = features["readme_coverage_ratio"]
    )
    session.add(profile_feature)
    session.commit()
    session.refresh(profile_feature)
    session.close()
    return profile_feature
    