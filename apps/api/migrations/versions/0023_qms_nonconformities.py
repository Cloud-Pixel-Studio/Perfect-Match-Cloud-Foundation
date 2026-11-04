# ruff: noqa: E501
"""Tenant-scoped nonconformity intake, containment and controlled closure."""

from alembic import op

revision = "0023_qms_nonconformities"
down_revision = "0022_risk_links"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(r"""
ALTER TABLE qms_access_grants DROP CONSTRAINT qms_access_grants_capability_check;
ALTER TABLE qms_access_grants ADD CONSTRAINT qms_access_grants_capability_check CHECK(capability IN ('documents.read','documents.author','documents.review','documents.approve','documents.release','documents.obsolete','evidence.read','evidence.create','evidence.review','processes.read','processes.manage','controls.read','controls.manage','control_instances.read','control_instances.manage','risks.read','risks.manage','risks.review','ncr.read','ncr.manage','ncr.review'));
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


ALTER TABLE audit_events DROP CONSTRAINT audit_events_action_check;
ALTER TABLE audit_events ADD CONSTRAINT audit_events_action_check CHECK(action IN ('auth.tenant_selected','organization.unit_created','organization.unit_updated','organization.unit_moved','organization.unit_archived','organization.unit_restored','organization.assignment_created','organization.assignment_updated','organization.assignment_deactivated','organization.assignment_reactivated','workflow.definition_created','workflow.definition_updated','workflow.definition_retired','workflow.version_created','workflow.version_updated','workflow.version_published','workflow.step_created','workflow.step_updated','workflow.transition_created','workflow.transition_updated','workflow.assignment_created','workflow.assignment_updated','workflow.instance_started','workflow.instance_transitioned','workflow.instance_completed','workflow.instance_cancelled','qms.access_granted','qms.access_revoked','process.created','process.updated','process.archived','process.restored','document.created','document.updated','document.obsoleted','revision.created','revision.updated','revision.submitted','revision.rejected','revision.approved','revision.released','control.created','control.updated','control.activated','control.retired','control_instance.created','control_instance.updated','control_instance.transitioned','control.activity_created','control.activity_updated','control.activity_deactivated','control.evidence_requirement_created','control.evidence_requirement_updated','control.evidence_requirement_deactivated','control_instance_activity.created','control_instance_activity.updated','control_instance_activity.transitioned','control_instance_evidence.created','control_instance_evidence.updated','control_instance_evidence.submitted','control_instance_evidence.accepted','control_instance_evidence.rejected','risk.created','risk.updated','risk.transitioned','risk.reviewed','risk.control_linked','risk.control_unlinked','risk.document_linked','risk.document_unlinked','ncr.created','ncr.updated','ncr.transitioned'));

CREATE TABLE qms_nonconformities (
 id uuid PRIMARY KEY, tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
 unit_id uuid NOT NULL, process_id uuid NOT NULL,
 code varchar(40) NOT NULL CHECK(length(btrim(code)) BETWEEN 1 AND 40),
 name varchar(160) NOT NULL CHECK(length(btrim(name)) BETWEEN 1 AND 160),
 source_type varchar(20) NOT NULL CHECK(source_type IN ('internal','customer','supplier','process','product','document','audit','other')),
 severity varchar(20) NOT NULL CHECK(severity IN ('minor','major','critical')),
 description text NOT NULL CHECK(length(btrim(description)) BETWEEN 1 AND 4000),
 detected_date date NOT NULL, detected_by_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
 owner_user_id uuid REFERENCES users(id) ON DELETE RESTRICT,
 containment_required boolean NOT NULL, containment_action text NOT NULL DEFAULT '' CHECK(length(containment_action)<=4000),
 containment_owner_user_id uuid REFERENCES users(id) ON DELETE RESTRICT, containment_date date,
 containment_completed boolean NOT NULL,
 disposition varchar(24) CHECK(disposition IN ('use_as_is','rework','repair','return','scrap','information_only','other')),
 disposition_notes text NOT NULL DEFAULT '' CHECK(length(disposition_notes)<=4000),
 root_cause_summary text NOT NULL DEFAULT '' CHECK(length(root_cause_summary)<=4000),
 closure_notes text NOT NULL DEFAULT '' CHECK(length(closure_notes)<=4000), target_date date,
 cancellation_reason varchar(500) NOT NULL DEFAULT '',
 state varchar(24) NOT NULL CHECK(state IN ('draft','open','containment','investigation','action_required','verification','closed','cancelled')),
 opened_by_user_id uuid REFERENCES users(id) ON DELETE RESTRICT, opened_at timestamptz,
 reviewed_by_user_id uuid REFERENCES users(id) ON DELETE RESTRICT, reviewed_at timestamptz,
 closed_by_user_id uuid REFERENCES users(id) ON DELETE RESTRICT, closed_at timestamptz,
 cancelled_by_user_id uuid REFERENCES users(id) ON DELETE RESTRICT, cancelled_at timestamptz,
 row_version integer NOT NULL CHECK(row_version>=1),
 created_by_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
 created_at timestamptz NOT NULL, updated_at timestamptz NOT NULL,
 UNIQUE(id,tenant_id,unit_id,process_id),
 FOREIGN KEY(process_id,tenant_id,unit_id) REFERENCES qms_processes(id,tenant_id,unit_id) ON DELETE RESTRICT,
 CHECK((opened_by_user_id IS NULL)=(opened_at IS NULL)),
 CHECK((reviewed_by_user_id IS NULL)=(reviewed_at IS NULL)),
 CHECK((closed_by_user_id IS NULL)=(closed_at IS NULL)),
 CHECK((cancelled_by_user_id IS NULL)=(cancelled_at IS NULL)),
 CHECK(state NOT IN ('open','containment','investigation','action_required','verification','closed') OR opened_at IS NOT NULL),
 CHECK((state='closed')=(closed_at IS NOT NULL)),
 CHECK((state='cancelled')=(cancelled_at IS NOT NULL)),
 CHECK(state<>'closed' OR length(btrim(closure_notes))>0),
 CHECK((state='cancelled')=(length(btrim(cancellation_reason))>0)),
 CHECK(NOT containment_completed OR (length(btrim(containment_action))>0 AND containment_date IS NOT NULL))
);
CREATE UNIQUE INDEX qms_nonconformities_code_unique ON qms_nonconformities(tenant_id,lower(code));
CREATE INDEX qms_nonconformities_scope_state ON qms_nonconformities(tenant_id,unit_id,state,code,id);
REVOKE ALL ON qms_nonconformities FROM PUBLIC;
GRANT SELECT,INSERT,UPDATE ON qms_nonconformities TO pmcloud_app;
REVOKE DELETE,TRUNCATE ON qms_nonconformities FROM pmcloud_app;
ALTER TABLE qms_nonconformities ENABLE ROW LEVEL SECURITY;
ALTER TABLE qms_nonconformities FORCE ROW LEVEL SECURITY;
CREATE POLICY qms_nonconformity_read ON qms_nonconformities FOR SELECT USING (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
 AND (qms_has_capability('ncr.read',unit_id) OR qms_has_capability('ncr.manage',unit_id) OR qms_has_capability('ncr.review',unit_id)));
CREATE POLICY qms_nonconformity_insert ON qms_nonconformities FOR INSERT WITH CHECK (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid AND qms_has_capability('ncr.manage',unit_id)
 AND state='draft' AND row_version=1 AND created_by_user_id=NULLIF(current_setting('app.user_id',true),'')::uuid);
CREATE POLICY qms_nonconformity_update ON qms_nonconformities FOR UPDATE USING (
 tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
 AND (qms_has_capability('ncr.manage',unit_id) OR qms_has_capability('ncr.review',unit_id)))
 WITH CHECK (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid
 AND (qms_has_capability('ncr.manage',unit_id) OR qms_has_capability('ncr.review',unit_id)));
CREATE FUNCTION validate_qms_nonconformity() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public AS $$
DECLARE actor uuid; workflow_command boolean; opening boolean;
BEGIN
 actor:=NULLIF(current_setting('app.user_id',true),'')::uuid;
 IF TG_OP='INSERT' THEN
  IF NEW.state<>'draft' OR NEW.row_version<>1 OR NEW.created_by_user_id IS DISTINCT FROM actor
   OR NEW.detected_by_user_id IS DISTINCT FROM actor OR NEW.opened_at IS NOT NULL
   OR NEW.reviewed_at IS NOT NULL OR NEW.closed_at IS NOT NULL OR NEW.cancelled_at IS NOT NULL
   OR NEW.cancellation_reason<>'' THEN
   RAISE EXCEPTION 'nonconformity must be created as a draft by the current actor' USING ERRCODE='23514';
  END IF;
  IF NOT EXISTS(SELECT 1 FROM qms_processes p WHERE p.id=NEW.process_id AND p.tenant_id=NEW.tenant_id
   AND p.unit_id=NEW.unit_id AND p.status='active') THEN
   RAISE EXCEPTION 'nonconformity requires an active scoped process' USING ERRCODE='23514';
  END IF;
 ELSE
  IF ROW(NEW.id,NEW.tenant_id,NEW.unit_id,NEW.process_id,NEW.code,NEW.detected_by_user_id,NEW.created_by_user_id,NEW.created_at)
   IS DISTINCT FROM ROW(OLD.id,OLD.tenant_id,OLD.unit_id,OLD.process_id,OLD.code,OLD.detected_by_user_id,OLD.created_by_user_id,OLD.created_at)
   OR NEW.row_version<>OLD.row_version+1 THEN
   RAISE EXCEPTION 'nonconformity identity is immutable; version must advance once' USING ERRCODE='23514';
  END IF;
  IF OLD.state IN ('closed','cancelled') THEN
   RAISE EXCEPTION 'closed or cancelled nonconformities are immutable' USING ERRCODE='23514';
  END IF;
  IF OLD.state<>'draft' AND OLD.containment_required AND NOT NEW.containment_required THEN
   RAISE EXCEPTION 'required containment cannot be waived after opening' USING ERRCODE='23514';
  END IF;
  workflow_command:=current_setting('app.ncr_workflow',true)='transition';
  IF COALESCE(workflow_command,false) THEN
   opening:=OLD.state='draft' AND NEW.state='open';
   IF NOT qms_has_capability(CASE WHEN opening THEN 'ncr.manage' ELSE 'ncr.review' END,NEW.unit_id) THEN
    RAISE EXCEPTION 'nonconformity workflow authority required' USING ERRCODE='42501';
   END IF;
   IF (to_jsonb(NEW)-ARRAY['state','opened_by_user_id','opened_at','reviewed_by_user_id','reviewed_at','closed_by_user_id','closed_at','cancelled_by_user_id','cancelled_at','cancellation_reason','closure_notes','row_version','updated_at'])
    IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['state','opened_by_user_id','opened_at','reviewed_by_user_id','reviewed_at','closed_by_user_id','closed_at','cancelled_by_user_id','cancelled_at','cancellation_reason','closure_notes','row_version','updated_at'])
    OR (NEW.state<>'closed' AND NEW.closure_notes IS DISTINCT FROM OLD.closure_notes) THEN
    RAISE EXCEPTION 'nonconformity workflow cannot modify record content' USING ERRCODE='23514';
   END IF;
   IF NOT ((OLD.state='draft' AND NEW.state IN ('open','cancelled')) OR
    (OLD.state='open' AND NEW.state IN ('containment','investigation','cancelled')) OR
    (OLD.state='containment' AND NEW.state IN ('investigation','cancelled')) OR
    (OLD.state='investigation' AND NEW.state IN ('action_required','cancelled')) OR
    (OLD.state='action_required' AND NEW.state IN ('verification','closed','cancelled')) OR
    (OLD.state='verification' AND NEW.state IN ('closed','cancelled'))) THEN
    RAISE EXCEPTION 'invalid nonconformity transition' USING ERRCODE='23514';
   END IF;
   IF NEW.state='containment' AND NOT NEW.containment_required THEN
    RAISE EXCEPTION 'containment must be required before starting it' USING ERRCODE='23514';
   END IF;
   IF NEW.state IN ('investigation','closed') AND NEW.containment_required AND NOT NEW.containment_completed THEN
    RAISE EXCEPTION 'required containment must be completed before investigation or closure' USING ERRCODE='23514';
   END IF;
   IF opening THEN
    IF NEW.opened_by_user_id IS DISTINCT FROM actor OR NEW.opened_at IS NULL
     OR ROW(NEW.reviewed_by_user_id,NEW.reviewed_at,NEW.closed_by_user_id,NEW.closed_at,NEW.cancelled_by_user_id,NEW.cancelled_at,NEW.cancellation_reason)
      IS DISTINCT FROM ROW(OLD.reviewed_by_user_id,OLD.reviewed_at,OLD.closed_by_user_id,OLD.closed_at,OLD.cancelled_by_user_id,OLD.cancelled_at,OLD.cancellation_reason) THEN
     RAISE EXCEPTION 'opening requires the current actor and time' USING ERRCODE='23514';
    END IF;
   ELSE
    IF ROW(NEW.opened_by_user_id,NEW.opened_at) IS DISTINCT FROM ROW(OLD.opened_by_user_id,OLD.opened_at)
     OR NEW.reviewed_by_user_id IS DISTINCT FROM actor OR NEW.reviewed_at IS NULL THEN
     RAISE EXCEPTION 'review requires current actor and preserves opening history' USING ERRCODE='23514';
    END IF;
    IF NEW.state='closed' THEN
     IF NEW.closed_by_user_id IS DISTINCT FROM actor OR NEW.closed_at IS NULL OR length(btrim(NEW.closure_notes))=0 THEN
      RAISE EXCEPTION 'closure requires notes and the current actor' USING ERRCODE='23514';
     END IF;
    ELSIF ROW(NEW.closed_by_user_id,NEW.closed_at) IS DISTINCT FROM ROW(OLD.closed_by_user_id,OLD.closed_at) THEN
     RAISE EXCEPTION 'closure history may only change on closure' USING ERRCODE='23514';
    END IF;
    IF NEW.state='cancelled' THEN
     IF NEW.cancelled_by_user_id IS DISTINCT FROM actor OR NEW.cancelled_at IS NULL OR length(btrim(NEW.cancellation_reason))=0 THEN
      RAISE EXCEPTION 'cancellation requires reason and the current actor' USING ERRCODE='23514';
     END IF;
    ELSIF ROW(NEW.cancelled_by_user_id,NEW.cancelled_at,NEW.cancellation_reason)
     IS DISTINCT FROM ROW(OLD.cancelled_by_user_id,OLD.cancelled_at,OLD.cancellation_reason) THEN
     RAISE EXCEPTION 'cancellation history may only change on cancellation' USING ERRCODE='23514';
    END IF;
   END IF;
  ELSE
   IF NEW.state IS DISTINCT FROM OLD.state OR
    ROW(NEW.opened_by_user_id,NEW.opened_at,NEW.reviewed_by_user_id,NEW.reviewed_at,NEW.closed_by_user_id,NEW.closed_at,NEW.cancelled_by_user_id,NEW.cancelled_at,NEW.cancellation_reason)
    IS DISTINCT FROM ROW(OLD.opened_by_user_id,OLD.opened_at,OLD.reviewed_by_user_id,OLD.reviewed_at,OLD.closed_by_user_id,OLD.closed_at,OLD.cancelled_by_user_id,OLD.cancelled_at,OLD.cancellation_reason) THEN
    RAISE EXCEPTION 'use nonconformity workflow commands to change state or decision history' USING ERRCODE='23514';
   END IF;
   IF NOT qms_has_capability('ncr.manage',NEW.unit_id) THEN
    RAISE EXCEPTION 'nonconformity management authority required' USING ERRCODE='42501';
   END IF;
  END IF;
 END IF;
 IF NEW.owner_user_id IS NOT NULL AND (TG_OP='INSERT' OR NEW.owner_user_id IS DISTINCT FROM OLD.owner_user_id)
  AND NOT EXISTS(SELECT 1 FROM organization_member_directory() d WHERE d.user_id=NEW.owner_user_id) THEN
  RAISE EXCEPTION 'nonconformity owner must be an active tenant member' USING ERRCODE='23514';
 END IF;
 IF NEW.containment_owner_user_id IS NOT NULL AND (TG_OP='INSERT' OR NEW.containment_owner_user_id IS DISTINCT FROM OLD.containment_owner_user_id)
  AND NOT EXISTS(SELECT 1 FROM organization_member_directory() d WHERE d.user_id=NEW.containment_owner_user_id) THEN
  RAISE EXCEPTION 'containment owner must be an active tenant member' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END; $$;
REVOKE ALL ON FUNCTION validate_qms_nonconformity() FROM PUBLIC;
CREATE TRIGGER qms_nonconformity_validate BEFORE INSERT OR UPDATE ON qms_nonconformities
 FOR EACH ROW EXECUTE FUNCTION validate_qms_nonconformity();
""")


def downgrade() -> None:
    # Reject audit-history loss before removing business records.
    op.execute(r"""
ALTER TABLE audit_events DROP CONSTRAINT audit_events_action_check;
ALTER TABLE audit_events ADD CONSTRAINT audit_events_action_check CHECK(action IN ('auth.tenant_selected','organization.unit_created','organization.unit_updated','organization.unit_moved','organization.unit_archived','organization.unit_restored','organization.assignment_created','organization.assignment_updated','organization.assignment_deactivated','organization.assignment_reactivated','workflow.definition_created','workflow.definition_updated','workflow.definition_retired','workflow.version_created','workflow.version_updated','workflow.version_published','workflow.step_created','workflow.step_updated','workflow.transition_created','workflow.transition_updated','workflow.assignment_created','workflow.assignment_updated','workflow.instance_started','workflow.instance_transitioned','workflow.instance_completed','workflow.instance_cancelled','qms.access_granted','qms.access_revoked','process.created','process.updated','process.archived','process.restored','document.created','document.updated','document.obsoleted','revision.created','revision.updated','revision.submitted','revision.rejected','revision.approved','revision.released','control.created','control.updated','control.activated','control.retired','control_instance.created','control_instance.updated','control_instance.transitioned','control.activity_created','control.activity_updated','control.activity_deactivated','control.evidence_requirement_created','control.evidence_requirement_updated','control.evidence_requirement_deactivated','control_instance_activity.created','control_instance_activity.updated','control_instance_activity.transitioned','control_instance_evidence.created','control_instance_evidence.updated','control_instance_evidence.submitted','control_instance_evidence.accepted','control_instance_evidence.rejected','risk.created','risk.updated','risk.transitioned','risk.reviewed','risk.control_linked','risk.control_unlinked','risk.document_linked','risk.document_unlinked'));

ALTER TABLE qms_access_grants DROP CONSTRAINT qms_access_grants_capability_check;
ALTER TABLE qms_access_grants ADD CONSTRAINT qms_access_grants_capability_check CHECK(capability IN ('documents.read','documents.author','documents.review','documents.approve','documents.release','documents.obsolete','evidence.read','evidence.create','evidence.review','processes.read','processes.manage','controls.read','controls.manage','control_instances.read','control_instances.manage','risks.read','risks.manage','risks.review'));
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
     AND (d.role<>'auditor' OR NEW.capability IN ('documents.read','evidence.read','processes.read','controls.read','control_instances.read','risks.read')))
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
 AND (m.role<>'auditor' OR g.capability IN ('documents.read','evidence.read','processes.read','controls.read','control_instances.read','risks.read')));
$$;


DROP TABLE qms_nonconformities;
DROP FUNCTION validate_qms_nonconformity();
""")
