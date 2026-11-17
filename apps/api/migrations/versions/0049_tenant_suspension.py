"""Deny legacy business access when a company or its actor is inactive."""

from alembic import op

revision = "0049_tenant_suspension"
down_revision = "0048_audit_competence"
branch_labels = None
depends_on = None

# Identity/session tables retain their existing policies so a member can switch
# companies or sign out. QMS domain policies already require the active actor
# helper or qms_has_capability; these older tables lacked that shared boundary.
TABLES = (
    "tenant_isolation_probes",
    "organization_units",
    "organization_unit_assignments",
    "workflow_definitions",
    "workflow_versions",
    "workflow_steps",
    "workflow_transitions",
    "workflow_step_assignments",
    "workflow_instances",
    "workflow_instance_events",
    "audit_events",
)

# Replace the existing definer function rather than introducing another
# privileged function. Its owner, execute ACL, result shape and directory
# projection stay unchanged. The helper is invoker-scoped and also verifies
# active user/membership; identities remain the transaction's app.* context.
DIRECTORY = """
CREATE OR REPLACE FUNCTION public.organization_member_directory()
RETURNS TABLE (user_id uuid, display_name varchar, role varchar)
LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
 SELECT p.user_id, p.display_name, p.role
 FROM public.organization_member_directory_projection AS p
 WHERE p.tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
   AND p.membership_status = 'active'
   AND p.user_status = 'active'
   {active_guard}
   AND EXISTS (
       SELECT 1 FROM public.memberships AS actor_membership
       WHERE actor_membership.tenant_id = p.tenant_id
         AND actor_membership.user_id =
             NULLIF(current_setting('app.user_id', true), '')::uuid
         AND actor_membership.status = 'active'
   )
 ORDER BY lower(p.display_name), p.user_id;
$$;
"""

SITE_SCOPE_LOCK = """
CREATE OR REPLACE FUNCTION public.lock_qms_site_scope(
 requested_site uuid, requested_tenant uuid
) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
BEGIN
 {active_guard}
 PERFORM id FROM public.organization_unit_integrity_projection
  WHERE id=requested_site AND tenant_id=requested_tenant
   AND tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
   AND status='active' FOR SHARE;
 IF NOT FOUND THEN
  RAISE EXCEPTION 'process site must be active in the same tenant' USING ERRCODE='23514';
 END IF;
END; $$;
"""


def upgrade() -> None:
    # Restrictive AND policies only narrow the existing permissive rules. They
    # cannot grant a new capability, role, scope or SQL privilege.
    for table in TABLES:
        op.execute(f"""
CREATE POLICY tenant_active_guard ON public.{table}
 AS RESTRICTIVE FOR ALL TO pmcloud_app
 USING (
  tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
  AND public.qms_access_actor_is_active()
 )
 WITH CHECK (
  tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
  AND public.qms_access_actor_is_active()
 );
""")
    op.execute(DIRECTORY.format(active_guard="AND public.qms_access_actor_is_active()"))
    op.execute(
        SITE_SCOPE_LOCK.format(
            active_guard="""
 IF NOT public.qms_access_actor_is_active() THEN
  RAISE EXCEPTION 'tenant access denied' USING ERRCODE='42501';
 END IF;
"""
        )
    )


def downgrade() -> None:
    # Do not silently reintroduce the known suspension bypass for an existing
    # disabled company. No business rows or append-only history are discarded.
    # The migration owner is NOBYPASSRLS. A transactional owner-only NO FORCE
    # lets this check actually see disabled tenants; the table lock also
    # serializes tenant status changes. On error the entire DDL rolls back.
    op.execute("""
ALTER TABLE public.tenants NO FORCE ROW LEVEL SECURITY;
DO $$ BEGIN
 IF EXISTS (SELECT 1 FROM public.tenants WHERE status <> 'active') THEN
  RAISE EXCEPTION 'cannot remove tenant suspension guards with disabled companies'
   USING ERRCODE = '55000';
 END IF;
END $$;
ALTER TABLE public.tenants FORCE ROW LEVEL SECURITY;
""")
    for table in TABLES:
        op.execute(f"DROP POLICY tenant_active_guard ON public.{table}")
    op.execute(DIRECTORY.format(active_guard=""))
    op.execute(SITE_SCOPE_LOCK.format(active_guard=""))
