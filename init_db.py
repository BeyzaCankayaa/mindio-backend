# init_db.py

from database import engine, Base
from models import User, Mood, PersonalityResponse, Suggestion, Gamification

# Bu satır, Base'den miras alan TÜM modeller için tablo oluşturur
print("Creating tables if they do not exist...")
Base.metadata.create_all(bind=engine)
print("Done.")

