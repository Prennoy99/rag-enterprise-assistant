"""add full-text search support for hybrid retrieval

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-19

"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Stored generated column so ts_rank/plainto_tsquery never re-tokenize `content` at query time.
    op.execute(
        "ALTER TABLE document_chunks "
        "ADD COLUMN content_tsv tsvector "
        "GENERATED ALWAYS AS (to_tsvector('english', content)) STORED"
    )
    op.execute(
        "CREATE INDEX ix_document_chunks_content_tsv ON document_chunks USING GIN (content_tsv)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_content_tsv")
    op.execute("ALTER TABLE document_chunks DROP COLUMN IF EXISTS content_tsv")
