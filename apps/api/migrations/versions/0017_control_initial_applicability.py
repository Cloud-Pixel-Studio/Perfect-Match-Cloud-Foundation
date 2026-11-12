# ruff: noqa: E501
"""Allow a justified not-applicable implementation at creation."""

from alembic import op

revision = "0017_ctrl_applicability"
down_revision = "0016_qms_controls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(r"""
ALTER POLICY qms_control_instance_insert ON qms_control_instances WITH CHECK (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND qms_has_capability('control_instances.manage',unit_id)
 AND status='active' AND implementation_status IN ('not_started','not_applicable') AND row_version=1
 AND created_by_user_id=NULLIF(current_setting('app.user_id',true),'')::uuid);
""")


def downgrade() -> None:
    op.execute(r"""
ALTER POLICY qms_control_instance_insert ON qms_control_instances WITH CHECK (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND qms_has_capability('control_instances.manage',unit_id)
 AND status='active' AND implementation_status='not_started' AND row_version=1
 AND created_by_user_id=NULLIF(current_setting('app.user_id',true),'')::uuid);
""")
