# ruff: noqa: E501 -- deterministic security migration SQL.
"""Scoped execution-access counts, never grant visibility or execution permission."""

from alembic import op

revision = "0047_audit_execution_authority"
down_revision = "0046_audit_independence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
CREATE TABLE qms_audit_execution_grant_projection (
 grant_id uuid PRIMARY KEY REFERENCES qms_access_grants(id) ON DELETE CASCADE,
 tenant_id uuid NOT NULL, unit_id uuid NOT NULL, user_id uuid NOT NULL,
 capability varchar(40) NOT NULL CHECK(capability IN ('audits.read','audits.execute')),
 status varchar(20) NOT NULL CHECK(status IN ('active','revoked'))
);
REVOKE ALL ON qms_audit_execution_grant_projection FROM PUBLIC,pmcloud_app;
-- Owner-only projection. No policies: accidental future runtime grants still fail closed.
-- NO FORCE lets the migration owner's fixed, scoped definer function read this projection.
ALTER TABLE qms_audit_execution_grant_projection ENABLE ROW LEVEL SECURITY;
CREATE INDEX qms_audit_execution_projection_active ON qms_audit_execution_grant_projection(tenant_id,unit_id,user_id,capability) WHERE status='active';
ALTER TABLE qms_access_grants NO FORCE ROW LEVEL SECURITY;
INSERT INTO qms_audit_execution_grant_projection(grant_id,tenant_id,unit_id,user_id,capability,status)
 SELECT id,tenant_id,unit_id,user_id,capability,status FROM qms_access_grants WHERE capability IN ('audits.read','audits.execute');
ALTER TABLE qms_access_grants FORCE ROW LEVEL SECURITY;
CREATE FUNCTION sync_qms_audit_execution_grants() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
BEGIN
 IF NEW.capability IN ('audits.read','audits.execute') THEN
  INSERT INTO public.qms_audit_execution_grant_projection(grant_id,tenant_id,unit_id,user_id,capability,status)
   VALUES(NEW.id,NEW.tenant_id,NEW.unit_id,NEW.user_id,NEW.capability,NEW.status)
   ON CONFLICT(grant_id) DO UPDATE SET status=EXCLUDED.status;
 END IF;
 RETURN NEW;
END; $$;
REVOKE ALL ON FUNCTION sync_qms_audit_execution_grants() FROM PUBLIC,pmcloud_app;
CREATE TRIGGER qms_audit_execution_grants_sync AFTER INSERT OR UPDATE ON qms_access_grants
 FOR EACH ROW EXECUTE FUNCTION sync_qms_audit_execution_grants();
CREATE FUNCTION qms_audit_execution_authority(requested_audit uuid)
RETURNS TABLE(planned_auditors integer,authorized_auditors integer)
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$
DECLARE audit_tenant uuid; audit_unit uuid;
BEGIN
 SELECT a.tenant_id,a.unit_id INTO audit_tenant,audit_unit FROM public.qms_internal_audits a
 WHERE a.id=requested_audit AND a.tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid;
 IF audit_tenant IS NULL OR NOT public.qms_has_capability('audits.read',audit_unit)
  OR NOT public.qms_has_capability('audits.review',audit_unit) THEN
  RAISE EXCEPTION 'audit execution-access verification unavailable' USING ERRCODE='42501';
 END IF;
 RETURN QUERY SELECT count(*)::integer,
  count(*) FILTER(WHERE EXISTS(
   SELECT 1 FROM public.organization_member_directory_projection p
   WHERE p.tenant_id=audit_tenant AND p.user_id=t.user_id
    AND p.membership_status='active' AND p.user_status='active'
  ) AND EXISTS(
   SELECT 1 FROM public.qms_audit_execution_grant_projection g
   WHERE g.tenant_id=audit_tenant AND g.unit_id=audit_unit AND g.user_id=t.user_id
    AND g.status='active' AND g.capability='audits.read'
  ) AND EXISTS(
   SELECT 1 FROM public.qms_audit_execution_grant_projection g
   WHERE g.tenant_id=audit_tenant AND g.unit_id=audit_unit AND g.user_id=t.user_id
    AND g.status='active' AND g.capability='audits.execute'
  ))::integer
 FROM public.qms_audit_team_members t
 WHERE t.audit_id=requested_audit AND t.tenant_id=audit_tenant AND t.unit_id=audit_unit
  AND t.status='active' AND t.team_role='auditor';
END; $$;
REVOKE ALL ON FUNCTION qms_audit_execution_authority(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION qms_audit_execution_authority(uuid) TO pmcloud_app;
""")


def downgrade() -> None:
    op.execute("""
DROP FUNCTION qms_audit_execution_authority(uuid);
DROP TRIGGER qms_audit_execution_grants_sync ON qms_access_grants;
DROP FUNCTION sync_qms_audit_execution_grants();
DROP TABLE qms_audit_execution_grant_projection;
""")
