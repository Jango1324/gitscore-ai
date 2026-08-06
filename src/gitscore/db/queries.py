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
        readme_coverage_ratio = features["readme_coverage_ratio"],
        most_used_language=features["most_used_language"],

        total_stars=features["total_stars"],
        average_stars=features["average_stars"],
        total_forks=features["total_forks"],
        average_forks=features["average_forks"],
        repositories_with_description=features["repositories_with_description"],
        description_coverage_ratio=features["description_coverage_ratio"],

        has_pytorch=features["has_pytorch"],
        has_huggingface=features["has_huggingface"],
        has_pandas=features["has_pandas"],
        has_catboost=features["has_catboost"],
        has_python=features["has_python"],
        has_typescript=features["has_typescript"],


        ml_keyword_total=features["ml_keyword_total"],
        python_repository_count=features["python_repository_count"],
        typescript_repository_count=features["typescript_repository_count"],

        repositories_with_readme=features["repositories_with_readme"],
        average_readme_length=features["average_readme_length"],
        repositories_with_installation=features["repositories_with_installation"],
        repositories_with_usage=features["repositories_with_usage"],
        repositories_with_demo=features["repositories_with_demo"],
        repositories_with_badges=features["repositories_with_badges"],
        repositories_with_license=features["repositories_with_license"],
        repositories_with_contributing=features["repositories_with_contributing"]
    )
    session.add(profile_feature)
    session.commit()
    session.refresh(profile_feature)
    session.close()
    return profile_feature
    