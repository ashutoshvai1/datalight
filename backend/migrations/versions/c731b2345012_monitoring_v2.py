"""Selected sources, recoverable temporal state, grouped jobs and immutable answers."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "c731b2345012"
down_revision = "9c1dbfa324a0"
branch_labels = None
depends_on = None


def upgrade():
    json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
    # Old active work must not execute under a different detector/provider contract.
    # Reports, original findings and review history remain unchanged.
    op.execute(
        "UPDATE runs SET status = 'stopped' WHERE status IN ('initializing', 'running', 'paused')"
    )
    op.execute(
        "UPDATE jobs SET status = 'cancelled', lease_token = NULL, lease_until = NULL WHERE status IN ('queued', 'leased')"
    )
    op.add_column("sources", sa.Column("path", sa.Text(), nullable=True))
    op.add_column("runs", sa.Column("detector_state", json_type, nullable=True))
    op.add_column(
        "jobs", sa.Column("task_key", sa.String(100), server_default="main", nullable=False)
    )
    op.alter_column("jobs", "task_key", server_default=None)
    op.add_column("jobs", sa.Column("payload", json_type, nullable=True))
    # Initial migration used PostgreSQL's generated name for this constraint.
    op.drop_constraint("jobs_run_id_kind_key", "jobs", type_="unique")
    op.create_unique_constraint("uq_job_task", "jobs", ["run_id", "kind", "task_key"])
    op.create_table(
        "answers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "review_id", sa.String(36), sa.ForeignKey("reviews.id"), unique=True, nullable=False
        ),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("evidence_ids", json_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.execute(
        "CREATE TRIGGER immutable_record BEFORE UPDATE OR DELETE ON answers FOR EACH ROW EXECUTE FUNCTION datalight_append_only()"
    )


def downgrade():
    op.drop_table("answers")
    op.drop_constraint("uq_job_task", "jobs", type_="unique")
    # Grouped jobs cannot be collapsed safely. Preserve data rather than silently deleting jobs.
    op.create_unique_constraint("jobs_run_id_kind_key", "jobs", ["run_id", "kind"])
    op.drop_column("jobs", "payload")
    op.drop_column("jobs", "task_key")
    op.drop_column("runs", "detector_state")
    op.drop_column("sources", "path")
