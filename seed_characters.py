from sqlalchemy.orm import Session
from models import Character

DEFAULT_CHARACTERS = [
    {"name": "Ressam Mindy", "asset_key": "ressam", "cost": 35},
    {"name": "Kokoş Mindy", "asset_key": "kokos", "cost": 25},
    {"name": "Büyücü Mindy", "asset_key": "buyucu", "cost": 50},
    {"name": "Çalışkan Mindy", "asset_key": "caliskan", "cost": 10},
    {"name": "İş Adamı Mindy", "asset_key": "is_adami", "cost": 60},
    {"name": "Aşçı Mindy", "asset_key": "asci", "cost": 50},
    {"name": "Sporcu Mindy", "asset_key": "sporcu", "cost": 10},
    {"name": "Yazar Mindy", "asset_key": "yazar", "cost": 60},
]

def seed_characters_if_empty(db: Session) -> int:
    exists = db.query(Character).first()
    if exists:
        return 0

    rows = [Character(**c) for c in DEFAULT_CHARACTERS]
    db.add_all(rows)
    db.commit()
    return len(rows)
