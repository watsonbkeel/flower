"""v2.2.2 baseline; explicit migration only."""

from alembic import op
import sqlalchemy as sa

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    table = op.create_table("schema_info", sa.Column("spec_version", sa.String(), primary_key=True))
    op.bulk_insert(table, [{"spec_version": "2.2.2"}])


def downgrade():
    raise RuntimeError("Restore a verified backup; automatic downgrade is unsupported")
