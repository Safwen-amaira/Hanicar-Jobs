"""Initial schema - created via Base.metadata on startup; this revision documents it."""

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Tables are created by SQLAlchemy metadata.create_all on app startup.
    # Alembic revision kept for future additive migrations.
    pass


def downgrade() -> None:
    pass
