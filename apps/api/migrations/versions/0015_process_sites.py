# ruff: noqa: E501
"""Allow a process to apply to multiple active tenant sites."""

from alembic import op

revision = "0015_process_sites"
down_revision = "0014_document_owner_scope"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(r"""
CREATE TABLE qms_process_sites (
 tenant_id uuid NOT NULL,
 process_id uuid NOT NULL,
 process_unit_id uuid NOT NULL,
 site_unit_id uuid NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(process_id,site_unit_id),
 FOREIGN KEY(process_id,tenant_id,process_unit_id)
  REFERENCES qms_processes(id,tenant_id,unit_id) ON DELETE RESTRICT,
 FOREIGN KEY(site_unit_id,tenant_id)
  REFERENCES organization_units(id,tenant_id) ON DELETE RESTRICT
);
CREATE INDEX qms_process_sites_by_site ON qms_process_sites(tenant_id,site_unit_id,process_id);
REVOKE ALL ON qms_process_sites FROM PUBLIC;
GRANT SELECT,INSERT,DELETE ON qms_process_sites TO pmcloud_app;
ALTER TABLE qms_process_sites ENABLE ROW LEVEL SECURITY;
ALTER TABLE qms_process_sites FORCE ROW LEVEL SECURITY;
CREATE POLICY qms_process_site_read ON qms_process_sites FOR SELECT USING (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
 AND EXISTS(SELECT 1 FROM qms_processes p WHERE p.id=process_id AND p.tenant_id=qms_process_sites.tenant_id
  AND p.unit_id=process_unit_id));
CREATE POLICY qms_process_site_insert ON qms_process_sites FOR INSERT WITH CHECK (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
 AND qms_has_capability('processes.manage',process_unit_id));
CREATE POLICY qms_process_site_delete ON qms_process_sites FOR DELETE USING (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
 AND qms_has_capability('processes.manage',process_unit_id));
CREATE FUNCTION lock_qms_site_scope(requested_site uuid,requested_tenant uuid) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
BEGIN
 PERFORM id FROM public.organization_unit_integrity_projection
  WHERE id=requested_site AND tenant_id=requested_tenant
   AND tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
   AND status='active' FOR SHARE;
 IF NOT FOUND THEN
  RAISE EXCEPTION 'process site must be active in the same tenant' USING ERRCODE='23514';
 END IF;
END; $$;
REVOKE ALL ON FUNCTION lock_qms_site_scope(uuid,uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION lock_qms_site_scope(uuid,uuid) TO pmcloud_app;
CREATE FUNCTION validate_qms_process_site() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
DECLARE current_process_id uuid; current_tenant_id uuid; current_unit_id uuid; requested_site_id uuid;
BEGIN
 IF TG_OP='INSERT' THEN
  current_process_id:=NEW.process_id; current_tenant_id:=NEW.tenant_id;
  current_unit_id:=NEW.process_unit_id; requested_site_id:=NEW.site_unit_id;
 ELSE
  current_process_id:=OLD.process_id; current_tenant_id:=OLD.tenant_id;
  current_unit_id:=OLD.process_unit_id; requested_site_id:=OLD.site_unit_id;
 END IF;
 PERFORM public.lock_qms_process_scope(current_unit_id);
 IF TG_OP='INSERT' AND NOT EXISTS(
  SELECT 1 FROM public.qms_processes p WHERE p.id=current_process_id
   AND p.tenant_id=current_tenant_id AND p.unit_id=current_unit_id AND p.status='active') THEN
  RAISE EXCEPTION 'site link requires an active process in the same tenant' USING ERRCODE='23514';
 END IF;
 IF TG_OP='INSERT' THEN
  PERFORM public.lock_qms_site_scope(requested_site_id,current_tenant_id);
 END IF;
 IF TG_OP='INSERT' AND NOT EXISTS(
  SELECT 1 FROM public.organization_units u WHERE u.id=requested_site_id
   AND u.tenant_id=current_tenant_id AND u.unit_type='site' AND u.status='active') THEN
  RAISE EXCEPTION 'process site must be an active site in the same tenant' USING ERRCODE='23514';
 END IF;
 IF TG_OP='INSERT' THEN RETURN NEW; ELSE RETURN OLD; END IF;
END; $$;
REVOKE ALL ON FUNCTION validate_qms_process_site() FROM PUBLIC;
CREATE TRIGGER qms_process_site_validate BEFORE INSERT OR DELETE ON qms_process_sites
 FOR EACH ROW EXECUTE FUNCTION validate_qms_process_site();
CREATE TABLE qms_process_site_dependency_projection(
 tenant_id uuid NOT NULL, process_id uuid NOT NULL, site_unit_id uuid NOT NULL,
 status varchar(20) NOT NULL CHECK(status IN ('active','archived')),
 PRIMARY KEY(process_id,site_unit_id));
REVOKE ALL ON qms_process_site_dependency_projection FROM PUBLIC,pmcloud_app;
CREATE FUNCTION sync_qms_process_site_projection() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
BEGIN
 IF TG_OP='INSERT' THEN
  INSERT INTO public.qms_process_site_dependency_projection(tenant_id,process_id,site_unit_id,status)
   VALUES(NEW.tenant_id,NEW.process_id,NEW.site_unit_id,'active');
  RETURN NEW;
 ELSE
  DELETE FROM public.qms_process_site_dependency_projection
   WHERE process_id=OLD.process_id AND site_unit_id=OLD.site_unit_id;
  RETURN OLD;
 END IF;
END; $$;
REVOKE ALL ON FUNCTION sync_qms_process_site_projection() FROM PUBLIC;
CREATE TRIGGER qms_process_site_projection AFTER INSERT OR DELETE ON qms_process_sites
 FOR EACH ROW EXECUTE FUNCTION sync_qms_process_site_projection();
CREATE FUNCTION sync_qms_process_site_status_projection() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
BEGIN
 UPDATE public.qms_process_site_dependency_projection SET status=NEW.status
 WHERE process_id=NEW.id AND tenant_id=NEW.tenant_id;
 RETURN NEW;
END; $$;
REVOKE ALL ON FUNCTION sync_qms_process_site_status_projection() FROM PUBLIC;
CREATE TRIGGER qms_process_site_status_projection AFTER UPDATE OF status ON qms_processes
 FOR EACH ROW EXECUTE FUNCTION sync_qms_process_site_status_projection();
CREATE FUNCTION protect_site_with_qms_processes() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
BEGIN
 IF NEW.status='archived' AND OLD.status<>'archived' AND NEW.unit_type='site'
  AND EXISTS(SELECT 1 FROM public.qms_process_site_dependency_projection
   WHERE site_unit_id=NEW.id AND tenant_id=NEW.tenant_id AND status='active') THEN
  RAISE EXCEPTION 'site has active process applicability links' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END; $$;
REVOKE ALL ON FUNCTION protect_site_with_qms_processes() FROM PUBLIC;
CREATE TRIGGER organization_unit_qms_process_site_guard BEFORE UPDATE ON organization_units
 FOR EACH ROW EXECUTE FUNCTION protect_site_with_qms_processes();
CREATE FUNCTION validate_qms_process_sites_on_restore() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
BEGIN
 IF NEW.status='active' AND OLD.status='archived' AND EXISTS(
  SELECT 1 FROM public.qms_process_sites s LEFT JOIN public.organization_units u
   ON u.id=s.site_unit_id AND u.tenant_id=s.tenant_id
  WHERE s.process_id=NEW.id AND s.tenant_id=NEW.tenant_id
   AND (u.id IS NULL OR u.status<>'active' OR u.unit_type<>'site')) THEN
  RAISE EXCEPTION 'process sites must be active before restoring the process' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END; $$;
REVOKE ALL ON FUNCTION validate_qms_process_sites_on_restore() FROM PUBLIC;
CREATE TRIGGER qms_process_sites_restore_guard BEFORE UPDATE OF status ON qms_processes
 FOR EACH ROW EXECUTE FUNCTION validate_qms_process_sites_on_restore();
""")


def downgrade() -> None:
    op.execute(r"""
DROP TRIGGER organization_unit_qms_process_site_guard ON organization_units;
DROP FUNCTION protect_site_with_qms_processes();
DROP TRIGGER qms_process_sites_restore_guard ON qms_processes;
DROP FUNCTION validate_qms_process_sites_on_restore();
DROP TRIGGER qms_process_site_status_projection ON qms_processes;
DROP FUNCTION sync_qms_process_site_status_projection();
DROP TRIGGER qms_process_site_projection ON qms_process_sites;
DROP FUNCTION sync_qms_process_site_projection();
DROP TABLE qms_process_site_dependency_projection;
DROP TRIGGER qms_process_site_validate ON qms_process_sites;
DROP FUNCTION validate_qms_process_site();
DROP FUNCTION lock_qms_site_scope(uuid,uuid);
DROP TABLE qms_process_sites;
""")
