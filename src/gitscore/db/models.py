from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String, Float, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from gitscore.db.database import Base

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    github_username: Mapped[str] = mapped_column(
    String(255),
    unique=True,
    nullable=False,
    index=True,
    )
    name: Mapped[str | None] = mapped_column(
    String(255),
    nullable=True,
    )
    followers: Mapped[int] = mapped_column(
    Integer,
    nullable=False,
    default=0,
    )
    public_repos: Mapped[int] = mapped_column(
    Integer,
    nullable=False,
    default=0,
    )
    collected_at: Mapped[datetime] = mapped_column(
    DateTime,
    nullable=False,
    default=datetime.utcnow,
    )
    default=datetime.utcnow

class ProfileFeature(Base):
    __tablename__ = "profile_features"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
    ForeignKey("users.id"),
    nullable=False,
    )

    total_repos: Mapped[int] = mapped_column(Integer, nullable=False)
    original_repos: Mapped[int] = mapped_column(Integer, nullable=False)
    forked_repos: Mapped[int] = mapped_column(Integer, nullable=False)
    unique_language_count: Mapped[int] = mapped_column(Integer, nullable=False)
    ml_repository_count: Mapped[int] = mapped_column(Integer, nullable=False)
    readme_coverage_ratio: Mapped[float] = mapped_column(Float, nullable=False)
    most_used_language: Mapped[str] = mapped_column(String, nullable=False)
    python_repository_count : Mapped[int] = mapped_column(Integer, nullable = False)
    typescript_repository_count: Mapped[int] = mapped_column(Integer, nullable = False)
    has_python: Mapped[bool] = mapped_column(Boolean, nullable = False)
    has_typescript: Mapped[bool] = mapped_column(Boolean, nullable = False)
    total_stars: Mapped[int] = mapped_column(Integer, nullable = False)
    average_stars: Mapped[float] = mapped_column(Float, nullable = False)
    total_forks: Mapped[int] = mapped_column(Integer, nullable = False)
    average_forks: Mapped[float] =  mapped_column(Float, nullable = False)
    repositories_with_description: Mapped[int] = mapped_column(Integer, nullable = False)
    description_coverage_ratio: Mapped[float] = mapped_column(Float, nullable = False)
    has_pytorch: Mapped[bool] = mapped_column(Boolean, nullable = False)
    has_huggingface: Mapped[bool] = mapped_column(Boolean, nullable = False)
    has_pandas: Mapped[bool] = mapped_column(Boolean, nullable = False)
    has_catboost: Mapped[bool] = mapped_column(Boolean, nullable = False)
    ml_keyword_total: Mapped[int] = mapped_column(Integer, nullable = False)
    repositories_with_readme: Mapped[int] = mapped_column(Integer, nullable = False)
    average_readme_length: Mapped[float] = mapped_column(Float, nullable = False)
    repositories_with_installation: Mapped[int] = mapped_column(Integer, nullable = False)
    repositories_with_usage: Mapped[int] = mapped_column(Integer, nullable = False)
    repositories_with_demo: Mapped[int] = mapped_column(Integer, nullable = False)
    repositories_with_badges: Mapped[int] = mapped_column(Integer, nullable = False)
    repositories_with_license: Mapped[int] = mapped_column(Integer, nullable = False)
    repositories_with_contributing: Mapped[int] = mapped_column(Integer, nullable = False)
    collected_at: Mapped[datetime] = mapped_column(
    DateTime,
    nullable=False,
    default=datetime.utcnow,
)
    readiness_score: Mapped[int] = mapped_column(
    Integer,
    nullable=False
)