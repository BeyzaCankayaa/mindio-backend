# database.py
import os
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# ==================== LOAD ENV ====================
load_dotenv()

# ==================== DATABASE URL ====================
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL not found. Set DATABASE_URL in your Render environment variables."
    )

# SQLAlchemy bazı ortamlarda 'postgres://' yerine 'postgresql://' ister
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)


def _ensure_sslmode(url: str) -> str:
    """
    Render / managed Postgres çoğu zaman SSL ister.
    sslmode query param yoksa ekler.
    """
    try:
        parsed = urlparse(url)
        query = dict(parse_qsl(parsed.query))

        # zaten varsa dokunma
        if "sslmode" in query:
            return url

        # yoksa require ekle
        query["sslmode"] = "require"
        new_query = urlencode(query)

        return urlunparse(
            (
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                parsed.params,
                new_query,
                parsed.fragment,
            )
        )
    except Exception:
        # parse edemezse hiç ellemeyelim
        return url


# SSL şartını güvene al
DATABASE_URL = _ensure_sslmode(DATABASE_URL)

# ==================== ENGINE ====================
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,     # kopan bağlantıyı tekrar kurar
    pool_recycle=1800,      # 30 dk sonra connection yenile
)

# ==================== SESSION ====================
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

# ==================== BASE ====================
Base = declarative_base()


# ==================== DEPENDENCY ====================
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
