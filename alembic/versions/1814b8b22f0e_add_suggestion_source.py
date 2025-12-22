"""add suggestion source

Revision ID: 1814b8b22f0e
Revises: 
Create Date: 2025-12-22 22:38:22.213754

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1814b8b22f0e'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # enum varsa geç
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'suggestion_source') THEN
            CREATE TYPE suggestion_source AS ENUM ('user','ai','system');
        END IF;
    END $$;
    """)

    # column yoksa ekle
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_name='suggestions' AND column_name='source'
        ) THEN
            ALTER TABLE suggestions
            ADD COLUMN source suggestion_source DEFAULT 'user' NOT NULL;
        END IF;
    END $$;
    """)

    # eski kayıtları user yap (güvenlik)
    op.execute("UPDATE suggestions SET source = 'user' WHERE source IS NULL;")

    # index yoksa ekle
    op.execute("CREATE INDEX IF NOT EXISTS ix_suggestions_source ON suggestions(source);")

    # default kaldır (istersen; şart değil)
    op.execute("ALTER TABLE suggestions ALTER COLUMN source DROP DEFAULT;")

def downgrade() -> None:
    op.drop_index("ix_suggestions_source", table_name="suggestions")
    op.drop_column("suggestions", "source")
    op.execute("DROP TYPE suggestion_source")

