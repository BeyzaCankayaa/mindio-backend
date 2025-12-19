# seed_characters.py  (REVİZE)
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

def seed_characters_upsert(db: Session) -> dict:
    inserted = 0
    updated = 0

    for c in SHOP_CHARACTERS:
        existing = db.query(Character).filter(Character.asset_key == c["asset_key"]).first()
        if existing:
            changed = False
            if existing.name != c["name"]:
                existing.name = c["name"]
                changed = True
            if int(existing.cost or 0) != int(c["cost"]):
                existing.cost = c["cost"]
                changed = True
            if hasattr(existing, "is_active") and existing.is_active is False:
                existing.is_active = True
                changed = True
            if changed:
                updated += 1
        else:
            db.add(Character(**c))
            inserted += 1

    db.commit()
    return {"inserted": inserted, "updated": updated, "total_should_be": len(SHOP_CHARACTERS)}
