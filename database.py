import os
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL not found. Set DATABASE_URL in your Render environment variables.")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)


def _ensure_sslmode(url: str) -> str:
    try:
        parsed = urlparse(url)
        query = dict(parse_qsl(parsed.query))
        if "sslmode" in query:
            return url
        query["sslmode"] = "require"
        return urlunparse(
            (parsed.scheme, parsed.netloc, parsed.path, parsed.params, urlencode(query), parsed.fragment)
        )
    except Exception:
        return url


DATABASE_URL = _ensure_sslmode(DATABASE_URL)

SQL_ECHO = os.getenv("SQL_ECHO", "0") == "1"

connect_args = {}
if DATABASE_URL.startswith("postgresql://"):
    connect_args = {"sslmode": "require"}

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=1800,
    pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
    max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "10")),
    pool_timeout=int(os.getenv("DB_POOL_TIMEOUT", "30")),
    echo=SQL_ECHO,
    future=True,
    connect_args=connect_args,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
