from sqlalchemy.orm import Session
from database import SessionLocal
from models import Character

characters = [
    {"name": "Ressam Mindy", "asset_key": "ressam_mindy", "cost": 35},
    {"name": "Kokoş Mindy", "asset_key": "kokos_mindy", "cost": 25},
    {"name": "Büyücü Mindy", "asset_key": "buyucu_mindy", "cost": 50},
    {"name": "Çalışkan Mindy", "asset_key": "caliskan_mindy", "cost": 10},
    {"name": "İş Adamı Mindy", "asset_key": "is_adami_mindy", "cost": 60},
    {"name": "Aşçı Mindy", "asset_key": "asci_mindy", "cost": 50},
    {"name": "Sporcu Mindy", "asset_key": "sporcu_mindy", "cost": 10},
    {"name": "Yazar Mindy", "asset_key": "yazar_mindy", "cost": 60},
]

db: Session = SessionLocal()

for c in characters:
    exists = db.query(Character).filter_by(asset_key=c["asset_key"]).first()
    if not exists:
        db.add(Character(**c))

db.commit()
db.close()
print("✅ Characters seeded.")
