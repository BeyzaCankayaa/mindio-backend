from sqlalchemy.orm import Session
from models import Character  # models.py içinde Character modelin olmalı

DEFAULT_CHARACTERS = [
    {"name": "Uzman", "asset_key": "uzman", "cost": 50},
    {"name": "Yazar", "asset_key": "yazar", "cost": 75},
    {"name": "Koç", "asset_key": "koc", "cost": 100},
]

def seed_characters_if_empty(db: Session) -> int:
    exists = db.query(Character).first()
    if exists:
        return 0

    rows = [Character(**c) for c in DEFAULT_CHARACTERS]
    db.add_all(rows)
    db.commit()
    return len(rows)
