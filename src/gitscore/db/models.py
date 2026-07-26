from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String, Float
from sqlalchemy import DateTime, Integer, String
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
    collected_at: Mapped[datetime] = mapped_column(
    DateTime,
    nullable=False,
    default=datetime.utcnow,
)