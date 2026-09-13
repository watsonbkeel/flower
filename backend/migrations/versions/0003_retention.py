"""v2.2.2 verified retention and plant-specific aggregation."""

from alembic import op
import sqlalchemy as sa

revision = "0003_retention"
down_revision = "0002_domain"
branch_labels = None
depends_on = None


def upgrade():
    names = sa.inspect(op.get_bind()).get_unique_constraints("telemetry_hourly")
    old = next(
        c["name"]
        for c in names
        if c["column_names"] == ["device_id", "bucket_start", "source_type"]
    )
    with op.batch_alter_table(
        "telemetry_hourly", naming_convention={"uq": "uq_%(table_name)s_%(column_0_name)s"}
    ) as batch:
        batch.add_column(
            sa.Column("raw_purged", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch.add_column(
            sa.Column("coverage_seconds", sa.Float(), nullable=False, server_default="0")
        )
        batch.drop_constraint(old or "uq_telemetry_hourly_device_id", type_="unique")
        batch.create_unique_constraint(
            "uq_hourly_plant_source", ["device_id", "plant_id", "bucket_start", "source_type"]
        )


def downgrade():
    raise RuntimeError("Restore a verified backup; automatic schema downgrade is not supported")
