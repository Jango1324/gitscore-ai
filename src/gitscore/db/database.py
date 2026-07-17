from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from pathlib import Path
current_file = Path(__file__).resolve()

project_root = current_file.parents[3]
database_path = project_root / "data" / "gitscore.db"
current_dir = current_file.parent

database_path.parent.mkdir(parents=True, exist_ok=True)

database_url = f"sqlite:///{database_path.as_posix()}"

engine = create_engine(
    database_url,
    echo=True,
    connect_args={"check_same_thread" :False},
)
SessionLocal = sessionmaker(

    bind=engine,
    autoflush=False,
    autocommit = False,
)

class Base(DeclarativeBase):
    pass

