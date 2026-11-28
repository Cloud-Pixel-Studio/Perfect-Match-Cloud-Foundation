# ruff: noqa: S608 -- fixed migration identifiers and actions.
"""Independent employee profiles scoped to a company and organization unit."""

from alembic import op

revision = "0061_employee_directory"
down_revision = "0060_context_revision_actor"
branch_labels = None
depends_on = None


def _audit_constraint(*, downgrade: bool = False) -> None:
    membership = "AND action NOT IN" if downgrade else "OR action IN"
    op.execute(f"""
DO $$ DECLARE definition text; BEGIN
    SELECT pg_get_constraintdef(oid) INTO STRICT definition FROM pg_constraint
    WHERE conrelid = 'public.audit_events'::regclass AND conname = 'audit_events_action_check';
    ALTER TABLE public.audit_events DROP CONSTRAINT audit_events_action_check;
    definition := left(definition, length(definition) - 1) ||
        ' {membership} (''employee.created'', ''employee.updated'', ' ||
        '''employee.archived'', ''employee.restored''))';
    EXECUTE 'ALTER TABLE public.audit_events ADD CONSTRAINT audit_events_action_check '
        || definition;
END $$;
""")


def upgrade() -> None:
    _audit_constraint()
    op.execute("""
CREATE TABLE public.employee_profiles (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL,
    unit_id uuid NOT NULL,
    full_name varchar(160) NOT NULL CHECK (length(btrim(full_name)) > 0),
    job_title varchar(160) NOT NULL CHECK (length(btrim(job_title)) > 0),
    status varchar(10) NOT NULL CHECK (status IN ('active', 'archived')),
    row_version integer NOT NULL CHECK (row_version > 0),
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    FOREIGN KEY (unit_id, tenant_id)
        REFERENCES public.organization_units(id, tenant_id) ON DELETE RESTRICT
);
CREATE INDEX employee_profiles_directory
    ON public.employee_profiles(tenant_id, status, lower(full_name), id);

REVOKE ALL ON public.employee_profiles FROM PUBLIC, pmcloud_app;
GRANT SELECT, INSERT, UPDATE(unit_id, full_name, job_title, status, row_version, updated_at)
    ON public.employee_profiles TO pmcloud_app;
ALTER TABLE public.employee_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.employee_profiles FORCE ROW LEVEL SECURITY;
CREATE POLICY employee_company_admin ON public.employee_profiles TO pmcloud_app
USING (
    tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
    AND EXISTS (
        SELECT 1 FROM public.memberships AS m
        JOIN public.users AS u ON u.id = m.user_id AND u.status = 'active'
        JOIN public.tenants AS t ON t.id = m.tenant_id AND t.status = 'active'
        WHERE m.tenant_id = employee_profiles.tenant_id
          AND m.user_id = NULLIF(current_setting('app.user_id', true), '')::uuid
          AND m.status = 'active' AND m.role IN ('owner', 'admin')
    )
);

CREATE FUNCTION public.validate_employee_profile() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog, public, pg_temp AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW.status <> 'active' OR NEW.row_version <> 1 THEN
            RAISE EXCEPTION 'invalid initial employee state' USING ERRCODE = '23514';
        END IF;
    ELSE
        IF NEW.row_version <> OLD.row_version + 1
           OR (NEW.status = OLD.status AND OLD.status = 'archived')
           OR (NEW.status <> OLD.status AND (NEW.unit_id, NEW.full_name, NEW.job_title)
               IS DISTINCT FROM (OLD.unit_id, OLD.full_name, OLD.job_title)) THEN
            RAISE EXCEPTION 'invalid employee version or transition' USING ERRCODE = '23514';
        END IF;
    END IF;
    IF NEW.status = 'active' THEN
        PERFORM id FROM public.organization_units
            WHERE id = NEW.unit_id AND tenant_id = NEW.tenant_id AND status = 'active'
            FOR SHARE;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'active company unit required' USING ERRCODE = '23514';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;
REVOKE ALL ON FUNCTION public.validate_employee_profile() FROM PUBLIC, pmcloud_app;
CREATE TRIGGER employee_profile_validate BEFORE INSERT OR UPDATE ON public.employee_profiles
    FOR EACH ROW EXECUTE FUNCTION public.validate_employee_profile();
""")


def downgrade() -> None:
    op.execute("""
LOCK TABLE public.employee_profiles IN ACCESS EXCLUSIVE MODE;
ALTER TABLE public.employee_profiles NO FORCE ROW LEVEL SECURITY;
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM public.employee_profiles) THEN
        RAISE EXCEPTION 'cannot discard employee profiles' USING ERRCODE = '55000';
    END IF;
END $$;
DROP TABLE public.employee_profiles;
DROP FUNCTION public.validate_employee_profile();
""")
    _audit_constraint(downgrade=True)
