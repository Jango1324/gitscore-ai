from gitscore.db.database import Base, engine
from gitscore.db.models import User, ProfileFeature


Base.metadata.create_all(bind=engine)

print("Database tables created successfully.")