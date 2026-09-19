"""Protect evidence, conclusions, review history, and audit events from mutation."""

from alembic import op

revision = "9c1dbfa324a0"
down_revision = "887fadc810b2"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE FUNCTION datalight_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'Datalight evidence and review records are append-only';
        END;
        $$
    """)
    for table in ("evidence", "findings", "reviews", "audit_events", "batches"):
        op.execute(
            f"CREATE TRIGGER immutable_record BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION datalight_append_only()"
        )


def downgrade():
    for table in ("evidence", "findings", "reviews", "audit_events", "batches"):
        op.execute(f"DROP TRIGGER immutable_record ON {table}")
    op.execute("DROP FUNCTION datalight_append_only()")
