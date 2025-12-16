from sqlalchemy.orm import Session
from models import Character

# ❗ SADECE SHOP KARAKTERLERİ
# ❗ Mindio default karakter BURADA YOK

SHOP_CHARACTERS = [
    {"name": "Uzman Mindy", "asset_key": "uzman", "cost": 40},
    {"name": "Yazar Mindy", "asset_key": "yazar", "cost": 60},
    {"name": "Sporcu Mindy", "asset_key": "sporcu", "cost": 10},
    {"name": "Aşçı Mindy", "asset_key": "asci", "cost": 50},
    {"name": "Büyücü Mindy", "asset_key": "buyucu", "cost": 50},
    {"name": "Süslü Mindy", "asset_key": "suslu", "cost": 25},
    {"name": "Sanatçı Mindy", "asset_key": "sanatci", "cost": 35},
    {"name": "Çalışkan Mindy", "asset_key": "caliskan", "cost": 10},
]

def seed_characters_if_empty(db: Session) -> int:
    exists = db.query(Character).first()
    if exists:
        return 0

    rows = [Character(**c) for c in SHOP_CHARACTERS]
    db.add_all(rows)
    db.commit()
    return len(rows)
