# ruff: noqa: E501
"""CAPA draft intake with scoped NCR/risk provenance."""

from alembic import op

revision = "0026_qms_capa_intake"
down_revision = "0025_ncr_evidence_links"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(r"""
ALTER TABLE qms_access_grants DROP CONSTRAINT qms_access_grants_capability_check;
ALTER TABLE qms_access_grants ADD CONSTRAINT qms_access_grants_capability_check CHECK(capability IN ('documents.read','documents.author','documents.review','documents.approve','documents.release','documents.obsolete','evidence.read','evidence.create','evidence.review','processes.read','processes.manage','controls.read','controls.manage','control_instances.read','control_instances.manage','risks.read','risks.manage','risks.review','ncr.read','ncr.manage','ncr.review','capa.read','capa.manage','capa.review'));
CREATE OR REPLACE FUNCTION validate_qms_access_grant() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
BEGIN
 IF TG_OP='UPDATE' THEN
  IF OLD.status<>'active' OR NEW.status<>'revoked'
   OR ROW(NEW.id,NEW.tenant_id,NEW.user_id,NEW.unit_id,NEW.capability,NEW.granted_by_user_id,NEW.created_at)
      IS DISTINCT FROM ROW(OLD.id,OLD.tenant_id,OLD.user_id,OLD.unit_id,OLD.capability,OLD.granted_by_user_id,OLD.created_at)
   OR NEW.revoked_by_user_id IS DISTINCT FROM NULLIF(current_setting('app.user_id',true),'')::uuid THEN
    RAISE EXCEPTION 'grant identity is immutable; only revocation is allowed' USING ERRCODE='23514';
  END IF;
 ELSE
  IF NOT EXISTS (SELECT 1 FROM organization_member_directory() d WHERE d.user_id=NEW.user_id
     AND (d.role<>'auditor' OR NEW.capability IN ('documents.read','evidence.read','processes.read','controls.read','control_instances.read','risks.read','ncr.read','capa.read')))
   OR NOT EXISTS (SELECT 1 FROM organization_units u
       WHERE u.id=NEW.unit_id AND u.tenant_id=NEW.tenant_id AND u.status='active') THEN
    RAISE EXCEPTION 'grant target or scope is invalid' USING ERRCODE='23514';
  END IF;
 END IF;
 RETURN NEW;
END; $$;
CREATE OR REPLACE FUNCTION qms_has_capability(requested_capability text, requested_unit uuid)
RETURNS boolean LANGUAGE sql STABLE SECURITY INVOKER SET search_path=pg_catalog,public AS $$
 SELECT EXISTS (SELECT 1 FROM public.qms_access_grants g
 JOIN public.organization_units unit ON unit.id=g.unit_id AND unit.tenant_id=g.tenant_id
 JOIN public.memberships m ON m.user_id=g.user_id AND m.tenant_id=g.tenant_id
 JOIN public.users u ON u.id=m.user_id JOIN public.tenants t ON t.id=m.tenant_id
 WHERE g.tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
 AND g.user_id=NULLIF(current_setting('app.user_id',true),'')::uuid
 AND g.unit_id=requested_unit AND g.capability=requested_capability AND g.status='active'
 AND unit.status='active' AND m.status='active' AND u.status='active' AND t.status='active'
 AND (m.role<>'auditor' OR g.capability IN ('documents.read','evidence.read','processes.read','controls.read','control_instances.read','risks.read','ncr.read','capa.read')));
$$;

ALTER TABLE audit_events DROP CONSTRAINT audit_events_action_check;
ALTER TABLE audit_events ADD CONSTRAINT audit_events_action_check CHECK(action IN ('auth.tenant_selected','organization.unit_created','organization.unit_updated','organization.unit_moved','organization.unit_archived','organization.unit_restored','organization.assignment_created','organization.assignment_updated','organization.assignment_deactivated','organization.assignment_reactivated','workflow.definition_created','workflow.definition_updated','workflow.definition_retired','workflow.version_created','workflow.version_updated','workflow.version_published','workflow.step_created','workflow.step_updated','workflow.transition_created','workflow.transition_updated','workflow.assignment_created','workflow.assignment_updated','workflow.instance_started','workflow.instance_transitioned','workflow.instance_completed','workflow.instance_cancelled','qms.access_granted','qms.access_revoked','process.created','process.updated','process.archived','process.restored','document.created','document.updated','document.obsoleted','revision.created','revision.updated','revision.submitted','revision.rejected','revision.approved','revision.released','control.created','control.updated','control.activated','control.retired','control_instance.created','control_instance.updated','control_instance.transitioned','control.activity_created','control.activity_updated','control.activity_deactivated','control.evidence_requirement_created','control.evidence_requirement_updated','control.evidence_requirement_deactivated','control_instance_activity.created','control_instance_activity.updated','control_instance_activity.transitioned','control_instance_evidence.created','control_instance_evidence.updated','control_instance_evidence.submitted','control_instance_evidence.accepted','control_instance_evidence.rejected','risk.created','risk.updated','risk.transitioned','risk.reviewed','risk.control_linked','risk.control_unlinked','risk.document_linked','risk.document_unlinked','ncr.created','ncr.updated','ncr.transitioned','ncr.risk_linked','ncr.risk_unlinked','ncr.control_linked','ncr.control_unlinked','ncr.document_linked','ncr.document_unlinked','ncr.evidence_linked','ncr.evidence_unlinked','capa.created','capa.updated'));

CREATE TABLE qms_capas (
 id uuid PRIMARY KEY, tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
 unit_id uuid NOT NULL, process_id uuid NOT NULL,
 code varchar(40) NOT NULL CHECK(length(btrim(code)) BETWEEN 1 AND 40),
 name varchar(160) NOT NULL CHECK(length(btrim(name)) BETWEEN 1 AND 160),
 source_type varchar(20) NOT NULL CHECK(source_type IN ('ncr','risk','other')),
 source_ncr_id uuid, source_risk_id uuid,
 source_code varchar(40) NOT NULL DEFAULT '', source_state varchar(24) NOT NULL DEFAULT '',
 problem_statement text NOT NULL CHECK(length(btrim(problem_statement)) BETWEEN 1 AND 4000),
 owner_user_id uuid REFERENCES users(id) ON DELETE RESTRICT,
 target_date date, root_cause_method varchar(20) CHECK(root_cause_method IN ('5why','fishbone','is_is_not','other')),
 state varchar(24) NOT NULL DEFAULT 'draft' CHECK(state='draft'),
 row_version integer NOT NULL CHECK(row_version>=1),
 created_by_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
 created_at timestamptz NOT NULL, updated_at timestamptz NOT NULL,
 UNIQUE(id,tenant_id,unit_id),
 FOREIGN KEY(process_id,tenant_id,unit_id) REFERENCES qms_processes(id,tenant_id,unit_id) ON DELETE RESTRICT,
 FOREIGN KEY(source_ncr_id,tenant_id,unit_id) REFERENCES qms_nonconformities(id,tenant_id,unit_id) ON DELETE RESTRICT,
 FOREIGN KEY(source_risk_id,tenant_id,unit_id) REFERENCES qms_risks(id,tenant_id,unit_id) ON DELETE RESTRICT,
 CHECK((source_type='ncr' AND source_ncr_id IS NOT NULL AND source_risk_id IS NULL)
    OR (source_type='risk' AND source_risk_id IS NOT NULL AND source_ncr_id IS NULL)
    OR (source_type='other' AND source_ncr_id IS NULL AND source_risk_id IS NULL)),
 CHECK((source_type='other' AND source_code='' AND source_state='') OR
       (source_type<>'other' AND length(btrim(source_code))>0 AND length(btrim(source_state))>0))
);
CREATE UNIQUE INDEX qms_capas_code_unique ON qms_capas(tenant_id,lower(code));
CREATE INDEX qms_capas_scope ON qms_capas(tenant_id,unit_id,code,id);
REVOKE ALL ON qms_capas FROM PUBLIC;
GRANT SELECT,INSERT,UPDATE ON qms_capas TO pmcloud_app;
REVOKE DELETE,TRUNCATE ON qms_capas FROM pmcloud_app;
ALTER TABLE qms_capas ENABLE ROW LEVEL SECURITY;
ALTER TABLE qms_capas FORCE ROW LEVEL SECURITY;
CREATE POLICY qms_capa_read ON qms_capas FOR SELECT USING (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND qms_has_capability('capa.read',unit_id)
 AND (source_type='other' OR (source_type='ncr' AND qms_has_capability('ncr.read',unit_id))
      OR (source_type='risk' AND qms_has_capability('risks.read',unit_id))));
CREATE POLICY qms_capa_insert ON qms_capas FOR INSERT WITH CHECK (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
 AND qms_has_capability('capa.read',unit_id) AND qms_has_capability('capa.manage',unit_id)
 AND qms_has_capability('processes.read',unit_id)
 AND (source_type='other' OR (source_type='ncr' AND qms_has_capability('ncr.read',unit_id))
      OR (source_type='risk' AND qms_has_capability('risks.read',unit_id)))
 AND state='draft' AND row_version=1 AND created_by_user_id=NULLIF(current_setting('app.user_id',true),'')::uuid);
CREATE POLICY qms_capa_update ON qms_capas FOR UPDATE USING (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND qms_has_capability('capa.read',unit_id)
 AND qms_has_capability('capa.manage',unit_id)
 AND (source_type='other' OR (source_type='ncr' AND qms_has_capability('ncr.read',unit_id))
      OR (source_type='risk' AND qms_has_capability('risks.read',unit_id))))
 WITH CHECK (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
 AND qms_has_capability('capa.read',unit_id) AND qms_has_capability('capa.manage',unit_id));
CREATE FUNCTION validate_qms_capa() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
DECLARE actor uuid; origin_code text; origin_state text;
BEGIN
 actor:=NULLIF(current_setting('app.user_id',true),'')::uuid;
 IF TG_OP='INSERT' THEN
  IF NEW.state<>'draft' OR NEW.row_version<>1 OR NEW.created_by_user_id IS DISTINCT FROM actor THEN
   RAISE EXCEPTION 'CAPA must start as draft by current actor' USING ERRCODE='23514';
  END IF;
  IF NOT EXISTS(SELECT 1 FROM qms_processes p WHERE p.id=NEW.process_id AND p.tenant_id=NEW.tenant_id
    AND p.unit_id=NEW.unit_id AND p.status='active') THEN
   RAISE EXCEPTION 'CAPA requires active scoped process' USING ERRCODE='23514';
  END IF;
  IF NEW.owner_user_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM organization_member_directory() d
    WHERE d.user_id=NEW.owner_user_id AND d.role<>'auditor') THEN
   RAISE EXCEPTION 'CAPA owner must be active member' USING ERRCODE='23514';
  END IF;
  IF NEW.source_type='ncr' THEN
   SELECT n.code,n.state INTO origin_code,origin_state FROM qms_nonconformities n
    WHERE n.id=NEW.source_ncr_id AND n.tenant_id=NEW.tenant_id AND n.unit_id=NEW.unit_id AND n.state<>'cancelled';
  ELSIF NEW.source_type='risk' THEN
   SELECT r.code,r.state INTO origin_code,origin_state FROM qms_risks r
    WHERE r.id=NEW.source_risk_id AND r.tenant_id=NEW.tenant_id AND r.unit_id=NEW.unit_id AND r.state<>'cancelled';
  END IF;
  IF NEW.source_type<>'other' AND (origin_code IS NULL OR NEW.source_code IS DISTINCT FROM origin_code
    OR NEW.source_state IS DISTINCT FROM origin_state) THEN
   RAISE EXCEPTION 'CAPA origin is invalid or snapshot differs' USING ERRCODE='23514';
  END IF;
 ELSE
  IF ROW(NEW.id,NEW.tenant_id,NEW.unit_id,NEW.process_id,NEW.code,NEW.source_type,
    NEW.source_ncr_id,NEW.source_risk_id,NEW.source_code,NEW.source_state,NEW.state,
    NEW.created_by_user_id,NEW.created_at)
   IS DISTINCT FROM ROW(OLD.id,OLD.tenant_id,OLD.unit_id,OLD.process_id,OLD.code,OLD.source_type,
    OLD.source_ncr_id,OLD.source_risk_id,OLD.source_code,OLD.source_state,OLD.state,
    OLD.created_by_user_id,OLD.created_at)
   OR NEW.row_version<>OLD.row_version+1 OR NEW.updated_at<=OLD.updated_at THEN
   RAISE EXCEPTION 'CAPA identity, provenance and state are immutable in intake' USING ERRCODE='23514';
  END IF;
  IF NEW.owner_user_id IS DISTINCT FROM OLD.owner_user_id AND NEW.owner_user_id IS NOT NULL
   AND NOT EXISTS(SELECT 1 FROM organization_member_directory() d
    WHERE d.user_id=NEW.owner_user_id AND d.role<>'auditor') THEN
   RAISE EXCEPTION 'CAPA owner must be active member' USING ERRCODE='23514';
  END IF;
 END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER qms_capa_validate BEFORE INSERT OR UPDATE ON qms_capas
 FOR EACH ROW EXECUTE FUNCTION validate_qms_capa();
""")


def downgrade() -> None:
    op.execute(r"""
DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM qms_capas)
    OR EXISTS(SELECT 1 FROM audit_events WHERE action IN ('capa.created','capa.updated')) THEN
  RAISE EXCEPTION 'cannot remove CAPA records or audit history';
 END IF;
END $$;
ALTER TABLE audit_events DROP CONSTRAINT audit_events_action_check;
ALTER TABLE audit_events ADD CONSTRAINT audit_events_action_check CHECK(action IN ('auth.tenant_selected','organization.unit_created','organization.unit_updated','organization.unit_moved','organization.unit_archived','organization.unit_restored','organization.assignment_created','organization.assignment_updated','organization.assignment_deactivated','organization.assignment_reactivated','workflow.definition_created','workflow.definition_updated','workflow.definition_retired','workflow.version_created','workflow.version_updated','workflow.version_published','workflow.step_created','workflow.step_updated','workflow.transition_created','workflow.transition_updated','workflow.assignment_created','workflow.assignment_updated','workflow.instance_started','workflow.instance_transitioned','workflow.instance_completed','workflow.instance_cancelled','qms.access_granted','qms.access_revoked','process.created','process.updated','process.archived','process.restored','document.created','document.updated','document.obsoleted','revision.created','revision.updated','revision.submitted','revision.rejected','revision.approved','revision.released','control.created','control.updated','control.activated','control.retired','control_instance.created','control_instance.updated','control_instance.transitioned','control.activity_created','control.activity_updated','control.activity_deactivated','control.evidence_requirement_created','control.evidence_requirement_updated','control.evidence_requirement_deactivated','control_instance_activity.created','control_instance_activity.updated','control_instance_activity.transitioned','control_instance_evidence.created','control_instance_evidence.updated','control_instance_evidence.submitted','control_instance_evidence.accepted','control_instance_evidence.rejected','risk.created','risk.updated','risk.transitioned','risk.reviewed','risk.control_linked','risk.control_unlinked','risk.document_linked','risk.document_unlinked','ncr.created','ncr.updated','ncr.transitioned','ncr.risk_linked','ncr.risk_unlinked','ncr.control_linked','ncr.control_unlinked','ncr.document_linked','ncr.document_unlinked','ncr.evidence_linked','ncr.evidence_unlinked'));
DROP TABLE qms_capas;
DROP FUNCTION validate_qms_capa();
CREATE OR REPLACE FUNCTION validate_qms_access_grant() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
BEGIN
 IF TG_OP='UPDATE' THEN
  IF OLD.status<>'active' OR NEW.status<>'revoked'
   OR ROW(NEW.id,NEW.tenant_id,NEW.user_id,NEW.unit_id,NEW.capability,NEW.granted_by_user_id,NEW.created_at)
      IS DISTINCT FROM ROW(OLD.id,OLD.tenant_id,OLD.user_id,OLD.unit_id,OLD.capability,OLD.granted_by_user_id,OLD.created_at)
   OR NEW.revoked_by_user_id IS DISTINCT FROM NULLIF(current_setting('app.user_id',true),'')::uuid THEN
    RAISE EXCEPTION 'grant identity is immutable; only revocation is allowed' USING ERRCODE='23514';
  END IF;
 ELSE
  IF NOT EXISTS (SELECT 1 FROM organization_member_directory() d WHERE d.user_id=NEW.user_id
     AND (d.role<>'auditor' OR NEW.capability IN ('documents.read','evidence.read','processes.read','controls.read','control_instances.read','risks.read','ncr.read')))
   OR NOT EXISTS (SELECT 1 FROM organization_units u
       WHERE u.id=NEW.unit_id AND u.tenant_id=NEW.tenant_id AND u.status='active') THEN
    RAISE EXCEPTION 'grant target or scope is invalid' USING ERRCODE='23514';
  END IF;
 END IF;
 RETURN NEW;
END; $$;
CREATE OR REPLACE FUNCTION qms_has_capability(requested_capability text, requested_unit uuid)
RETURNS boolean LANGUAGE sql STABLE SECURITY INVOKER SET search_path=pg_catalog,public AS $$
 SELECT EXISTS (SELECT 1 FROM public.qms_access_grants g
 JOIN public.organization_units unit ON unit.id=g.unit_id AND unit.tenant_id=g.tenant_id
 JOIN public.memberships m ON m.user_id=g.user_id AND m.tenant_id=g.tenant_id
 JOIN public.users u ON u.id=m.user_id JOIN public.tenants t ON t.id=m.tenant_id
 WHERE g.tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
 AND g.user_id=NULLIF(current_setting('app.user_id',true),'')::uuid
 AND g.unit_id=requested_unit AND g.capability=requested_capability AND g.status='active'
 AND unit.status='active' AND m.status='active' AND u.status='active' AND t.status='active'
 AND (m.role<>'auditor' OR g.capability IN ('documents.read','evidence.read','processes.read','controls.read','control_instances.read','risks.read','ncr.read')));
$$;


ALTER TABLE qms_access_grants DROP CONSTRAINT qms_access_grants_capability_check;
ALTER TABLE qms_access_grants ADD CONSTRAINT qms_access_grants_capability_check CHECK(capability IN ('documents.read','documents.author','documents.review','documents.approve','documents.release','documents.obsolete','evidence.read','evidence.create','evidence.review','processes.read','processes.manage','controls.read','controls.manage','control_instances.read','control_instances.manage','risks.read','risks.manage','risks.review','ncr.read','ncr.manage','ncr.review'));
""")
